#!/usr/bin/env python
"""Compute-bound kernels across every acceleration technology available here."""

from __future__ import annotations

import ctypes
import json
import os
import sys
from collections.abc import Callable
from typing import Any, cast

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, HERE)

import kernels_py as K  # noqa: E402
import pyperf  # noqa: E402
from kernels_py import F64, Built, Kernel, NativeKernel, Params  # noqa: E402
from mp_pyperf import RESULTS, Suite, bench_tag, interp_facts, native_flag  # noqa: E402

PARAMS: Params = {"vec_n": 1_000_000, "mb_w": 200, "mb_h": 150, "mb_iter": 30, "mat_n": 96}
KERNELS = ("arraysum", "mandelbrot", "matmul")
SO = "dylib" if sys.platform == "darwin" else "so"
NATIVE_FLAG = native_flag()

IMPLS = [
    ("cpython_loop", "pure Python, list of float"),
    ("cpython_builtin_sum", "builtin sum() over a list"),
    ("numpy", "vectorised; matmul dispatches to the vendor BLAS, which is MULTI-THREADED "
              "by default -- the only implementation here that is not single-threaded"),
    ("numpy_1t", "the same NumPy with its BLAS held to one thread, so it is comparable with "
                 "the single-threaded implementations below"),
    ("cython", "cython -O3, boundscheck off"),
    ("numba", "numba njit(fastmath=False)"),
    ("numba_fastmath", "numba njit(fastmath=True)"),
    ("c_ctypes", f"clang -O3 {NATIVE_FLAG}, called through ctypes"),
    ("c_pybind11", "same C kernels behind a pybind11 extension module"),
    ("rust_ctypes", "rustc opt-level=3, lto=fat, target-cpu=native, via ctypes"),
    ("codon_pyext", "Codon compiled ahead of time by `codon build -pyext` into a CPython "
                    "extension module; arrays indexed as ndarray, i.e. through their strides"),
    ("codon_pyext_ptr", "the same Codon extension with the array's data pointer taken once "
                        "and indexed directly -- Codon cannot declare contiguity in a "
                        "signature the way Cython's double[::1] does, so this is the only way "
                        "to say it. No mandelbrot row: that kernel touches no array, so the "
                        "two forms compile to the same code"),
    ("codon_jit", "the same kernels under @codon.jit, compiled in-process at first call"),
]

def tol_for(impl: str, case: str) -> float:
    if case == "mandelbrot":
        return 1e-4 if "fastmath" in impl else 0.0
    if "fastmath" in impl:
        return 1e-3
    if impl == "cpython_loop":
        return 0.0
    return 1e-12

CALL_IMPLS = ["python_function", "cython", "c_pybind11", "c_ctypes", "numba"]


def build_dir() -> str:
    return os.path.join(BENCH, "build", bench_tag())


def native_dir() -> str:
    return os.path.join(BENCH, "build", "native")


def _np_data(p: Params) -> tuple[F64, F64, F64, F64]:
    import numpy as np

    a = np.array(K.make_vector(p["vec_n"]), dtype=np.float64)
    ma_l, mb_l = K.make_matrices(p["mat_n"])
    ma = np.array(ma_l, dtype=np.float64)
    mb = np.array(mb_l, dtype=np.float64)
    mc = np.zeros(p["mat_n"] ** 2, dtype=np.float64)
    return a, ma, mb, mc


def _b_cpython_loop(p: Params, case: str) -> Built:
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        a = K.make_vector(n)
        return lambda: K.arraysum_py(a, n), lambda: K.arraysum_py(a, n)
    if case == "mandelbrot":
        return (lambda: K.mandelbrot_py(w, h, mx), lambda: K.mandelbrot_py(w, h, mx))
    ma, mb = K.make_matrices(m)
    mc = [0.0] * (m * m)
    return (lambda: K.matmul_py(ma, mb, mc, m),
            lambda: (K.matmul_py(ma, mb, mc, m), sum(mc))[1])


def _b_cpython_builtin_sum(p: Params, case: str) -> Built | None:
    if case != "arraysum":
        return None
    a = K.make_vector(p["vec_n"])
    return lambda: sum(a), lambda: sum(a)


def _b_numpy(p: Params, case: str) -> Built:
    a, ma, mb, mc = _np_data(p)
    fns = K.numpy_impls()
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: fns["arraysum"](a, n), lambda: fns["arraysum"](a, n)
    if case == "mandelbrot":
        return (lambda: fns["mandelbrot"](w, h, mx), lambda: fns["mandelbrot"](w, h, mx))
    return (lambda: fns["matmul"](ma, mb, mc, m),
            lambda: (fns["matmul"](ma, mb, mc, m), float(mc.sum()))[1])


def _b_cython(p: Params, case: str) -> Built:
    sys.path.insert(0, build_dir())
    import kernels_cy  # type: ignore

    a, ma, mb, mc = _np_data(p)
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: kernels_cy.arraysum(a, n), lambda: kernels_cy.arraysum(a, n)
    if case == "mandelbrot":
        return (lambda: kernels_cy.mandelbrot(w, h, mx),
                lambda: kernels_cy.mandelbrot(w, h, mx))
    return (lambda: kernels_cy.matmul(ma, mb, mc, m),
            lambda: (kernels_cy.matmul(ma, mb, mc, m), float(mc.sum()))[1])


def _numba_kernel(case: str, fastmath: bool) -> NativeKernel:
    import numba

    jit = numba.njit(cache=False, fastmath=fastmath)
    if case == "arraysum":
        @jit
        def arraysum(a: F64, n: int) -> float:
            s = 0.0
            for i in range(n):
                s += a[i]
            return s
        return arraysum
    if case == "mandelbrot":
        @jit
        def mandelbrot(w: int, h: int, maxiter: int) -> int:
            total = 0
            for py in range(h):
                y0 = -1.25 + 2.5 * py / h
                for px in range(w):
                    x0 = -2.0 + 3.0 * px / w
                    x = 0.0
                    y = 0.0
                    it = 0
                    while x * x + y * y <= 4.0 and it < maxiter:
                        xt = x * x - y * y + x0
                        y = 2.0 * x * y + y0
                        x = xt
                        it += 1
                    total += it
            return total
        return mandelbrot

    @jit
    def matmul(a: F64, b: F64, c: F64, n: int) -> None:
        for i in range(n):
            row = i * n
            for j in range(n):
                s = 0.0
                for k in range(n):
                    s += a[row + k] * b[k * n + j]
                c[row + j] = s
    return matmul


def _b_numba(p: Params, case: str, fastmath: bool = False) -> Built:
    a, ma, mb, mc = _np_data(p)
    fn = _numba_kernel(case, fastmath)
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        fn(a, n)
        return lambda: fn(a, n), lambda: fn(a, n)
    if case == "mandelbrot":
        fn(w, h, mx)
        return lambda: fn(w, h, mx), lambda: fn(w, h, mx)
    fn(ma, mb, mc, m)
    return (lambda: fn(ma, mb, mc, m),
            lambda: (fn(ma, mb, mc, m), float(mc.sum()))[1])


def load_c(variant: str = "O3native") -> ctypes.CDLL:
    path = os.path.join(native_dir(), f"libkernels_c_{variant}.{SO}")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    lib = ctypes.CDLL(path)
    dp = ctypes.POINTER(ctypes.c_double)
    lib.c_arraysum.restype = ctypes.c_double
    lib.c_arraysum.argtypes = [dp, ctypes.c_ssize_t]
    lib.c_mandelbrot.restype = ctypes.c_longlong
    lib.c_mandelbrot.argtypes = [ctypes.c_int] * 3
    lib.c_matmul.restype = None
    lib.c_matmul.argtypes = [dp, dp, dp, ctypes.c_ssize_t]
    lib.c_noop.restype = ctypes.c_int
    lib.c_noop.argtypes = []
    return lib


def _b_c_ctypes(p: Params, case: str) -> Built:
    lib = load_c()
    a, ma, mb, mc = _np_data(p)
    dp = ctypes.POINTER(ctypes.c_double)
    pa, pma, pmb, pmc = (x.ctypes.data_as(dp) for x in (a, ma, mb, mc))
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: lib.c_arraysum(pa, n), lambda: lib.c_arraysum(pa, n)
    if case == "mandelbrot":
        return lambda: lib.c_mandelbrot(w, h, mx), lambda: lib.c_mandelbrot(w, h, mx)
    return (lambda: lib.c_matmul(pma, pmb, pmc, m),
            lambda: (lib.c_matmul(pma, pmb, pmc, m), float(mc.sum()))[1])


def _b_c_pybind11(p: Params, case: str) -> Built:
    sys.path.insert(0, build_dir())
    import kernels_pb  # type: ignore

    a, ma, mb, mc = _np_data(p)
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: kernels_pb.arraysum(a, n), lambda: kernels_pb.arraysum(a, n)
    if case == "mandelbrot":
        return (lambda: kernels_pb.mandelbrot(w, h, mx),
                lambda: kernels_pb.mandelbrot(w, h, mx))
    return (lambda: kernels_pb.matmul(ma, mb, mc, m),
            lambda: (kernels_pb.matmul(ma, mb, mc, m), float(mc.sum()))[1])


def load_rust() -> ctypes.CDLL:
    lib = ctypes.CDLL(os.path.join(native_dir(), f"libmpkernels.{SO}"))
    dp = ctypes.POINTER(ctypes.c_double)
    lib.rs_arraysum.restype = ctypes.c_double
    lib.rs_arraysum.argtypes = [dp, ctypes.c_ssize_t]
    lib.rs_mandelbrot.restype = ctypes.c_longlong
    lib.rs_mandelbrot.argtypes = [ctypes.c_int] * 3
    lib.rs_matmul.restype = None
    lib.rs_matmul.argtypes = [dp, dp, dp, ctypes.c_ssize_t]
    lib.rs_noop.restype = ctypes.c_int
    lib.rs_noop.argtypes = []
    return lib


def _b_rust_ctypes(p: Params, case: str) -> Built:
    lib = load_rust()
    a, ma, mb, mc = _np_data(p)
    dp = ctypes.POINTER(ctypes.c_double)
    pa, pma, pmb, pmc = (x.ctypes.data_as(dp) for x in (a, ma, mb, mc))
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: lib.rs_arraysum(pa, n), lambda: lib.rs_arraysum(pa, n)
    if case == "mandelbrot":
        return lambda: lib.rs_mandelbrot(w, h, mx), lambda: lib.rs_mandelbrot(w, h, mx)
    return (lambda: lib.rs_matmul(pma, pmb, pmc, m),
            lambda: (lib.rs_matmul(pma, pmb, pmc, m), float(mc.sum()))[1])


def _b_codon_pyext(p: Params, case: str, ptr: bool = False) -> Built | None:
    """Codon compiled ahead of time, imported like any other extension module."""
    sys.path.insert(0, build_dir())
    import kernels_codon  # type: ignore

    if ptr and case == "mandelbrot":
        return None
    a, ma, mb, mc = _np_data(p)
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        fn = kernels_codon.arraysum_ptr if ptr else kernels_codon.arraysum
        return lambda: fn(a, n), lambda: fn(a, n)
    if case == "mandelbrot":
        return (lambda: kernels_codon.mandelbrot(w, h, mx),
                lambda: kernels_codon.mandelbrot(w, h, mx))
    mm = kernels_codon.matmul_ptr if ptr else kernels_codon.matmul
    return (lambda: mm(ma, mb, mc, m),
            lambda: (mm(ma, mb, mc, m), float(mc.sum()))[1])


def _b_codon_jit(p: Params, case: str) -> Built:
    """Codon's JIT. The import is deliberately inside the builder."""
    import kernels_codon_jit as cj

    a, ma, mb, mc = _np_data(p)
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if case == "arraysum":
        return lambda: cj.arraysum(a, n), lambda: cj.arraysum(a, n)
    if case == "mandelbrot":
        return lambda: cj.mandelbrot(w, h, mx), lambda: cj.mandelbrot(w, h, mx)
    return (lambda: cj.matmul(ma, mb, mc, m),
            lambda: (cj.matmul(ma, mb, mc, m), float(mc.sum()))[1])


def _b_numpy_1t(p: Params, case: str) -> Built:
    """NumPy with its BLAS restricted to one thread."""
    from threadpoolctl import threadpool_limits

    threadpool_limits(limits=1, user_api="blas")
    return _b_numpy(p, case)


def blas_threads() -> object:
    """How many threads NumPy's BLAS actually has. An observation, not a timing."""
    try:
        from threadpoolctl import threadpool_info

        return [{"library": i.get("internal_api"), "threads": i.get("num_threads")}
                for i in threadpool_info()]
    except Exception as exc:
        return f"unavailable: {exc!r}"


BUILDERS: dict[str, Callable[[Params, str], Built | None]] = {
    "cpython_loop": _b_cpython_loop,
    "cpython_builtin_sum": _b_cpython_builtin_sum,
    "numpy": _b_numpy,
    "numpy_1t": _b_numpy_1t,
    "cython": _b_cython,
    "numba": lambda p, c: _b_numba(p, c, fastmath=False),
    "numba_fastmath": lambda p, c: _b_numba(p, c, fastmath=True),
    "c_ctypes": _b_c_ctypes,
    "c_pybind11": _b_c_pybind11,
    "rust_ctypes": _b_rust_ctypes,
    "codon_pyext": lambda p, c: _b_codon_pyext(p, c, ptr=False),
    "codon_pyext_ptr": lambda p, c: _b_codon_pyext(p, c, ptr=True),
    "codon_jit": _b_codon_jit,
}


def build_call(impl: str) -> Kernel:
    """Zero-work callables, one per boundary, for the per-call cost of crossing it."""
    if impl == "python_function":
        def py_noop() -> int:
            return 0
        return py_noop
    if impl == "cython":
        sys.path.insert(0, build_dir())
        import kernels_cy  # type: ignore
        return kernels_cy.noop
    if impl == "c_pybind11":
        sys.path.insert(0, build_dir())
        import kernels_pb  # type: ignore
        return kernels_pb.noop
    if impl == "c_ctypes":
        return load_c().c_noop
    if impl == "numba":
        import numba
        f = numba.njit(lambda: 0)
        f()
        return f
    raise KeyError(impl)


def discover(p: Params) -> dict[str, Any]:
    """Build everything once, verify at full size, and write the plan."""
    ref = K.reference(p)
    print(f"=== discovery on {sys.version.split()[0]} ({bench_tag()})")
    print(f"    reference: {ref}")
    plan: list[dict] = []
    problems: list[dict] = []

    for impl, note in IMPLS:
        try:
            builder = BUILDERS[impl]
        except KeyError:
            continue
        for case in KERNELS:
            tol = tol_for(impl, case)
            try:
                built = builder(p, case)
            except Exception as exc:
                problems.append({"case": case, "impl": impl, "status": "unavailable",
                                 "note": repr(exc)[:300]})
                print(f"  unavailable {case:<12} {impl:<20} {repr(exc)[:70]}")
                continue
            if built is None:
                continue
            _timed, verify = built
            try:
                got = verify()
            except Exception as exc:
                problems.append({"case": case, "impl": impl, "status": "raised",
                                 "note": repr(exc)[:300]})
                print(f"  raised      {case:<12} {impl:<20} {repr(exc)[:70]}")
                continue
            exp = ref[case]
            dev = 0.0 if got == exp else abs(got - exp) / max(1.0, abs(exp))
            if dev > tol:
                problems.append({"case": case, "impl": impl, "status": "wrong_result",
                                 "got": repr(got)[:60], "expected": repr(exp)[:60],
                                 "deviation": dev, "tol": tol})
                print(f"  WRONG       {case:<12} {impl:<20} got={got!r} exp={exp!r} "
                      f"dev={dev:.2e}")
                continue
            plan.append({"case": case, "impl": impl, "note": note,
                         "deviation": dev, "tol": tol})
            flag = "" if dev == 0.0 else f"  (result deviates by {dev:.2e})"
            print(f"  ok          {case:<12} {impl:<20}{flag}")

    for impl in CALL_IMPLS:
        try:
            fn = build_call(impl)
            fn()
        except Exception as exc:
            problems.append({"case": "call_overhead", "impl": impl,
                             "status": "unavailable", "note": repr(exc)[:300]})
            print(f"  unavailable call_overhead {impl:<20} {repr(exc)[:60]}")
            continue
        plan.append({"case": "call_overhead", "impl": impl,
                     "note": "cost of crossing the boundary with no work in the callee",
                     "deviation": 0.0, "tol": 0.0})
        print(f"  ok          call_overhead {impl}")

    return {"suite": "b1_compute", "params": p,
            "reference": {k: (v if isinstance(v, (int, float)) else str(v))
                          for k, v in ref.items()},
            "interp": interp_facts(), "plan": plan, "problems": problems}


def measure(plan_path: str) -> None:
    with open(plan_path) as fh:
        disc = json.load(fh)
    p = cast("Params", disc["params"])
    suite = Suite("b1_compute", forward=("plan", "reverse"))
    suite.runner.argparser.add_argument("--plan", default=plan_path)
    suite.runner.argparser.add_argument(
        "--reverse", action="store_true",
        help="register the plan back to front; run once each way and append into one file, "
             "so no benchmark is always measured first")
    suite.parse()
    if suite.runner.args.reverse:  # ty: ignore[unresolved-attribute]
        disc["plan"] = list(reversed(disc["plan"]))
    suite.gate_failures = disc["problems"]
    suite.facts = {"reference": disc["reference"], "params": p,
                   "blas_threadpools": blas_threads()}

    cache: dict[tuple[str, str], Kernel] = {}
    ref = disc["reference"]

    def timed_for(case: str, impl: str, tol: float) -> Kernel:
        key = (case, impl)
        if key not in cache:
            if case == "call_overhead":
                cache[key] = build_call(impl)
            else:
                built = BUILDERS[impl](p, case)
                if built is None:
                    raise RuntimeError(
                        f"{impl} has no {case} implementation; the plan should not list it")
                timed, verify = built
                suite.check_once(key, verify, ref[case], tol)
                cache[key] = timed
        return cache[key]

    for entry in disc["plan"]:
        case, impl, tol = entry["case"], entry["impl"], entry.get("tol", 0.0)

        def time_fn(loops: int, case: str = case, impl: str = impl,
                    tol: float = tol) -> float:
            fn = timed_for(case, impl, tol)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        note = entry["note"]
        if entry.get("deviation"):
            note += f"; result deviates by {entry['deviation']:.2e} (FP reassociation)"
        suite.bench_time(case=case, impl=impl, time_fn=time_fn, params=p, note=note)

    suite.machine_probe()
    suite.write_sidecar()


def main() -> None:
    if "--discover" in sys.argv:
        sys.argv.remove("--discover")
        label = bench_tag()
        if "--label" in sys.argv:
            label = sys.argv[sys.argv.index("--label") + 1]
        os.makedirs(RESULTS, exist_ok=True)
        out = os.path.join(RESULTS, f"b1_compute-{label}.plan.json")
        disc = discover(PARAMS)
        with open(out, "w") as fh:
            json.dump(disc, fh, indent=1, default=str)
        print(f"[discovery] {len(disc['plan'])} benchmarks, "
              f"{len(disc['problems'])} problems -> {out}")
        return
    label = bench_tag()
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    else:
        plan = os.path.join(RESULTS, f"b1_compute-{label}.plan.json")
    if not os.path.exists(plan):
        sys.exit(f"no plan at {plan}; run with --discover first")
    measure(plan)


if __name__ == "__main__":
    main()
