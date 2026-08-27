#!/usr/bin/env python
"""The JIT break-even point as a function of input size."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, HERE)

import kernels_py as K  # noqa: E402
import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

SIZES = [1_000, 10_000, 100_000, 1_000_000]


def make_numba() -> tuple[Callable[..., Any], float, float]:
    """Compile the kernel and return it together with what the compilation cost."""
    t_imp = time.perf_counter()
    import numba

    import_s = time.perf_counter() - t_imp
    import numpy as np

    @numba.njit(cache=False)
    def nb_arraysum(a: Any, n: int) -> float:
        s = 0.0
        for i in range(n):
            s += a[i]
        return s

    warm = np.zeros(4, dtype=np.float64)
    t0 = time.perf_counter()
    nb_arraysum(warm, 4)
    return nb_arraysum, time.perf_counter() - t0, import_s


def make_codon() -> tuple[Callable[..., Any], dict[str, float]]:
    """The same, for Codon's JIT, with the cost split into the three stages that make it up."""
    import numpy as np

    t0 = time.perf_counter()
    import codon

    import_s = time.perf_counter() - t0

    t0 = time.perf_counter()

    @codon.jit
    def cd_arraysum(a, n):
        s = 0.0
        for i in range(n):
            s += a[i]
        return s

    decorate_s = time.perf_counter() - t0

    warm = np.zeros(4, dtype=np.float64)
    t0 = time.perf_counter()
    cd_arraysum(warm, 4)
    first_call_s = time.perf_counter() - t0
    return cd_arraysum, {"import_s": import_s, "decorate_s": decorate_s,
                         "first_call_s": first_call_s,
                         "compile_s": decorate_s + first_call_s}


def main() -> None:
    import numpy as np

    suite = Suite("b1_breakeven")
    suite.parse()

    state: dict[Any, Any] = {}

    def kernels(n: int) -> tuple[Callable[..., Any], tuple[list[float], Any]]:
        """Data and callables for one size, built once per process outside any timed region."""
        if "fn" not in state:
            state["fn"], state["compile_s"], state["import_s"] = make_numba()
        if n not in state:
            lst = K.make_vector(n)
            state[n] = (lst, np.array(lst, dtype=np.float64))
        return state["fn"], state[n]

    def codon_fn() -> Callable[..., Any]:
        if "codon_fn" not in state:
            state["codon_fn"], state["codon_cost"] = make_codon()
        return state["codon_fn"]

    for n in SIZES:
        def time_py(loops: int, n: int = n) -> float:
            _fn, (lst, _arr) = kernels(n)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                K.arraysum_py(lst, n)
            return pyperf.perf_counter() - t0

        def time_nb(loops: int, n: int = n) -> float:
            fn, (_lst, arr) = kernels(n)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn(arr, n)
            return pyperf.perf_counter() - t0

        def time_cd(loops: int, n: int = n) -> float:
            fn = codon_fn()
            _fn, (_lst, arr) = kernels(n)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn(arr, n)
            return pyperf.perf_counter() - t0

        suite.bench_time(case=f"arraysum_n{n}", impl="cpython_loop", time_fn=time_py,
                         params={"n": n}, note="pure-Python loop over a list of float")
        suite.bench_time(case=f"arraysum_n{n}", impl="numba", time_fn=time_nb,
                         params={"n": n}, note="numba njit, compiled before the timed region")
        suite.bench_time(case=f"arraysum_n{n}", impl="codon_jit", time_fn=time_cd,
                         params={"n": n},
                         note="codon.jit, compiled before the timed region")

    if suite.is_master:
        fn, compile_s, nb_import_s = make_numba()
        lst = K.make_vector(1000)
        arr = np.array(lst, dtype=np.float64)
        ref, got = K.arraysum_py(lst, 1000), fn(arr, 1000)
        dev = abs(got - ref) / max(1.0, abs(ref))
        suite.gate(case="arraysum_n1000", impl="numba", got=got, expected=ref, tol=1e-9)
        cfn, ccost = make_codon()
        cgot = cfn(arr, 1000)
        cdev = abs(cgot - ref) / max(1.0, abs(ref))
        suite.gate(case="arraysum_n1000", impl="codon_jit", got=cgot, expected=ref, tol=1e-9)
        suite.facts = {"numba_compile_s": compile_s, "numba_import_s": nb_import_s,
                       "sizes": SIZES,
                       "reference_deviation": dev,
                       "codon_cost_s": ccost,
                       "codon_reference_deviation": cdev,
                       "note": "compile latency is one observation of a one-off event, "
                               "not a pyperf benchmark"}
        print(f"  [fact] numba: import {nb_import_s * 1e3:.0f} ms (start-up), "
              f"compile latency {compile_s * 1e3:.1f} ms")
        print(f"  [fact] codon: import {ccost['import_s'] * 1e3:.0f} ms (start-up), "
              f"compile latency {ccost['compile_s'] * 1e3:.0f} ms "
              f"(decorate {ccost['decorate_s'] * 1e3:.0f} + first call "
              f"{ccost['first_call_s'] * 1e3:.0f})")
    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
