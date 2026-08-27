#!/usr/bin/env python
"""Thread scalability with and without the GIL."""

from __future__ import annotations

import ctypes
import os
import sys
import sysconfig
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, os.path.join(BENCH, "b2_branchy"))

import branchy_py as B  # noqa: E402
import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

THREADS = (1, 2, 3, 4, 6, 8)
ARITH_ITERS = 4_000_000
TOK_N = 2_000_000
MB_W, MB_H, MB_ITER = 400, 400, 60
BUSY_ITERS = 40_000_000
SINGLE_ITERS = 200_000
SO = "dylib" if sys.platform == "darwin" else "so"


def arith_chunk(lo: int, hi: int) -> int:
    s = 0
    for i in range(lo, hi):
        s += i * 3 - (i >> 1)
    return s


def tokenize_chunk(data: bytes, lo: int, hi: int) -> int:
    tokens = 0
    state = 0
    for i in range(lo, hi):
        ch = data[i]
        if 48 <= ch <= 57:
            if state != 1:
                tokens += 1
                state = 1
        elif (65 <= ch <= 90) or (97 <= ch <= 122):
            if state != 2:
                tokens += 1
                state = 2
        elif ch == 32 or ch == 10 or ch == 9:
            state = 0
        else:
            if state != 3:
                tokens += 1
                state = 3
    return tokens


def _load_native() -> ctypes.CDLL:
    lib = ctypes.CDLL(os.path.join(BENCH, "build", "native", f"libkernels_c_O3native.{SO}"))
    lib.c_mandelbrot_rows.restype = ctypes.c_longlong
    lib.c_mandelbrot_rows.argtypes = [ctypes.c_int] * 5
    lib.c_busy.restype = ctypes.c_double
    lib.c_busy.argtypes = [ctypes.c_longlong, ctypes.c_double]
    return lib


def split(total: int, parts: int) -> list[tuple[int, int]]:
    step = total // parts
    return [(i * step, (i + 1) * step if i < parts - 1 else total) for i in range(parts)]


def run_threaded(fn: Callable[[int, int], float], ranges: Sequence[tuple[int, int]],
                 out: list[float]) -> None:
    def worker(idx: int, lo: int, hi: int) -> None:
        out[idx] = fn(lo, hi)

    ts = [threading.Thread(target=worker, args=(i, lo, hi))
          for i, (lo, hi) in enumerate(ranges)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()


def _proc_arith(args: tuple[int, int]) -> float:
    return arith_chunk(*args)


def main() -> None:
    suite = Suite("b4_threads")
    suite.parse()
    gil_on = getattr(sys, "_is_gil_enabled", lambda: True)()
    ft_build = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    label = suite.label
    suite.facts = {"ft_build": ft_build, "gil_enabled": gil_on,
                   "cpu_count": os.cpu_count(),
                   "python_gil_env": os.environ.get("PYTHON_GIL")}
    suite.log(f"=== b4_threads [{label}] {sys.version.split()[0]} "
              f"ft_build={ft_build} gil_enabled={gil_on}")

    data = B.make_bytes(TOK_N)
    try:
        lib = _load_native()
    except Exception as exc:
        lib = None
        suite.unavailable(case="c_ffi_uniform", impl=label, note=repr(exc))

    families = [
        ("py_arith", lambda lo, hi: arith_chunk(lo, hi), ARITH_ITERS,
         "pure-Python integer arithmetic; total iterations fixed"),
        ("py_branchy", lambda lo, hi: tokenize_chunk(data, lo, hi), TOK_N,
         "pure-Python byte classification over a shared bytes object"),
    ]
    if lib is not None:
        families += [
            ("c_ffi_uniform", lambda lo, hi: int(lib.c_busy(hi - lo, 1.0) != 0.0), BUSY_ITERS,
             "balanced C compute kernel via ctypes; the GIL is released per call"),
            ("c_ffi_mandelbrot",
             lambda lo, hi: lib.c_mandelbrot_rows(MB_W, MB_H, MB_ITER, lo, hi), MB_H,
             "C mandelbrot rows via ctypes; per-row cost is data-dependent "
             "(deliberate load imbalance)"),
        ]

    STEPS = [(t, f"T{t}") for t in THREADS] + [(1, "T1_control")]
    for name, fn, total, note in families:
        for T, suffix in STEPS:
            ranges = split(total, T)
            impl = f"{label}/{suffix}"

            def time_threads(loops: int, fn: Callable[[int, int], float] = fn,
                             ranges: Sequence[tuple[int, int]] = ranges) -> float:
                out: list[float] = [0.0] * len(ranges)
                t0 = pyperf.perf_counter()
                for _ in range(loops):
                    run_threaded(fn, ranges, out)
                return pyperf.perf_counter() - t0

            note_i = note if suffix != "T1_control" else \
                note + "; repeat of the single-thread point after the whole curve, as a "\
                       "measure of how much the machine moved while it was collected"
            suite.bench_time(case=name, impl=impl, time_fn=time_threads,
                             params={"threads": T, "total": total}, note=note_i)

    pool_ranges = split(ARITH_ITERS, 8)
    state: dict[str, Any] = {}

    def time_procs(loops: int) -> float:
        ex = state.get("pool")
        if ex is None:
            ex = state["pool"] = ProcessPoolExecutor(max_workers=8)
            list(ex.map(_proc_arith, pool_ranges))
        t0 = pyperf.perf_counter()
        for _ in range(loops):
            list(ex.map(_proc_arith, pool_ranges))
        return pyperf.perf_counter() - t0

    suite.bench_time(case="py_arith", impl=f"{label}/procs8", time_fn=time_procs,
                     params={"procs": 8},
                     note="ProcessPoolExecutor with 8 workers; submit and collect included")

    suite.bench(case="single_thread_arith", impl=label,
                fn=lambda: arith_chunk(0, SINGLE_ITERS), params={"iters": SINGLE_ITERS},
                note="single-threaded arithmetic, no threads involved")
    suite.bench(case="single_thread_branchy", impl=label,
                fn=lambda: tokenize_chunk(data, 0, SINGLE_ITERS), params={"n": SINGLE_ITERS},
                note="single-threaded byte classification, no threads involved")

    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
