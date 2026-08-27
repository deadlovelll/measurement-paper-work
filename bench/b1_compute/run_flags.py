#!/usr/bin/env python
"""What compiler flags are worth on identical C source -- and what the mechanism is."""

from __future__ import annotations

import ctypes
import json
import os
import sys
from typing import Any, cast

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, HERE)

import kernels_py as K  # noqa: E402
import pyperf  # noqa: E402
import run_b1 as B1  # noqa: E402
from kernels_py import F64, Built, Kernel, Params  # noqa: E402
from mp_pyperf import RESULTS, Suite, bench_tag, interp_facts, native_flag  # noqa: E402

PARAMS = B1.PARAMS
KERNELS = ("arraysum", "mandelbrot", "matmul")
VARIANTS = ("O0", "O2", "O3", "O3native", "O3native_novec", "O3native_ffast")
ACCUMS = ("acc1", "acc2", "acc4", "acc8")


NATIVE_FLAG = native_flag()


def _variant_label(v: str) -> str:
    """Variant name -> the exact command line bench/build_all.sh compiled it with."""
    parts: list[str] = []
    for tok in v.split("_"):
        if tok == "novec":
            parts.append("-fno-vectorize -fno-slp-vectorize")
        elif tok == "ffast":
            parts.append("-ffast-math")
        elif tok.startswith("O3native"):
            parts.append(f"-O3 {NATIVE_FLAG}")
        else:
            parts.append(f"-{tok}")
    return "clang " + " ".join(parts)


SO = B1.SO


def load_accum() -> ctypes.CDLL:
    path = os.path.join(B1.native_dir(), f"libaccum_c.{SO}")
    lib = ctypes.CDLL(path)
    dp = ctypes.POINTER(ctypes.c_double)
    for n in ACCUMS:
        fn = getattr(lib, f"c_sum_{n}")
        fn.restype = ctypes.c_double
        fn.argtypes = [dp, ctypes.c_ssize_t]
    return lib


def _data(p: Params) -> tuple[F64, F64, Any, Any, Any, Any]:
    a, ma, mb, mc = B1._np_data(p)
    dp = ctypes.POINTER(ctypes.c_double)
    pa, pma, pmb, pmc = (x.ctypes.data_as(dp) for x in (a, ma, mb, mc))
    return a, mc, pa, pma, pmb, pmc


def build(kind: str, name: str, case: str, p: Params) -> Built:
    """Return (timed, verify) for one (kind, name, case)."""
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    if kind == "cflags":
        lib = B1.load_c(name)
        _a, mc, pa, pma, pmb, pmc = _data(p)
        if case == "arraysum":
            return lambda: lib.c_arraysum(pa, n), lambda: lib.c_arraysum(pa, n)
        if case == "mandelbrot":
            return (lambda: lib.c_mandelbrot(w, h, mx), lambda: lib.c_mandelbrot(w, h, mx))
        return (lambda: lib.c_matmul(pma, pmb, pmc, m),
                lambda: (lib.c_matmul(pma, pmb, pmc, m), float(mc.sum()))[1])
    if kind == "accum":
        lib = load_accum()
        fn = getattr(lib, f"c_sum_{name}")
        _a, mc, pa, pma, pmb, pmc = _data(p)
        return lambda: fn(pa, n), lambda: fn(pa, n)
    if kind == "numba":
        return B1._b_numba(p, case, fastmath=(name == "fastmath"))
    raise KeyError(kind)


PLAN_KINDS = (
    [("cflags", v, KERNELS, 1e-3 if "ffast" in v else 1e-9, _variant_label(v))
     for v in VARIANTS]
    + [("accum", a, ("arraysum",), 1e-9,
        f"clang -O2, {a[3:]} independent accumulator(s) written in the source")
       for a in ACCUMS]
    + [("numba", nm, KERNELS, 1e-3 if nm == "fastmath" else 1e-9,
        f"numba njit(fastmath={nm == 'fastmath'})") for nm in ("plain", "fastmath")]
)


def discover(p: Params) -> dict[str, Any]:
    ref = K.reference(p)
    print(f"=== flag/codegen discovery on {sys.version.split()[0]} ({bench_tag()})")
    plan: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for kind, name, cases, tol, note in PLAN_KINDS:
        for case in cases:
            impl = f"{kind}_{name}" if kind != "cflags" else name
            try:
                _timed, verify = build(kind, name, case, p)
                got = verify()
            except Exception as exc:
                problems.append({"case": case, "impl": impl, "status": "unavailable",
                                 "note": repr(exc)[:300]})
                print(f"  unavailable {case:<12} {impl:<18} {repr(exc)[:60]}")
                continue
            exp = ref[case]
            dev = 0.0 if got == exp else abs(got - exp) / max(1.0, abs(exp))
            if dev > tol:
                problems.append({"case": case, "impl": impl, "status": "wrong_result",
                                 "got": repr(got)[:60], "expected": repr(exp)[:60],
                                 "deviation": dev, "tol": tol})
                print(f"  WRONG       {case:<12} {impl:<18} dev={dev:.2e}")
                continue
            plan.append({"case": case, "impl": impl, "kind": kind, "name": name,
                         "note": note, "deviation": dev, "tol": tol})
            flag = "" if dev == 0.0 else f"  (deviates {dev:.2e})"
            print(f"  ok          {case:<12} {impl:<18}{flag}")
    return {"suite": "b1_flags", "params": p, "interp": interp_facts(),
            "reference": {k: str(v) for k, v in ref.items()},
            "plan": plan, "problems": problems}


def measure(plan_path: str) -> None:
    with open(plan_path) as fh:
        disc = json.load(fh)
    p = cast("Params", disc["params"])
    suite = Suite("b1_flags", forward=("plan", "only", "reverse"))
    suite.runner.argparser.add_argument("--plan", default=plan_path)
    suite.runner.argparser.add_argument(
        "--only", default=None,
        help="comma-separated case:impl pairs; restricts the plan to these")
    suite.runner.argparser.add_argument(
        "--reverse", action="store_true",
        help="register the plan back to front; run once each way and append into one file, "
             "so no benchmark is always measured first")
    args = suite.parse()
    if args.reverse:
        disc["plan"] = list(reversed(disc["plan"]))
    if args.only:
        want = {tuple(x.split(":", 1)) for x in args.only.split(",")}
        disc["plan"] = [e for e in disc["plan"] if (e["case"], e["impl"]) in want]
    suite.gate_failures = disc["problems"]
    ident = os.path.join(os.path.dirname(RESULTS), "codegen_identity.json")
    if os.path.exists(ident):
        with open(ident) as fh:
            identity = json.load(fh)
    else:
        identity = "not generated; run codegen_diff.sh"
    suite.facts = {"params": p, "reference": disc["reference"], "codegen_identity": identity}

    cache: dict[tuple[str, str, str], Kernel] = {}

    def timed_for(kind: str, name: str, case: str) -> Kernel:
        key = (kind, name, case)
        if key not in cache:
            cache[key] = build(kind, name, case, p)[0]
        return cache[key]

    for e in disc["plan"]:
        def time_fn(loops: int, kind: str = e["kind"], name: str = e["name"],
                    case: str = e["case"]) -> float:
            fn = timed_for(kind, name, case)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        note = e["note"]
        if e.get("deviation"):
            note += f"; result deviates by {e['deviation']:.2e}"
        suite.bench_time(case=e["case"], impl=e["impl"], time_fn=time_fn, params=p, note=note)

    suite.machine_probe()
    suite.write_sidecar()


def main() -> None:
    label = bench_tag()
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    if "--discover" in sys.argv:
        sys.argv.remove("--discover")
        os.makedirs(RESULTS, exist_ok=True)
        out = os.path.join(RESULTS, f"b1_flags-{label}.plan.json")
        disc = discover(PARAMS)
        with open(out, "w") as fh:
            json.dump(disc, fh, indent=1, default=str)
        print(f"[discovery] {len(disc['plan'])} benchmarks, "
              f"{len(disc['problems'])} problems -> {out}")
        return
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    else:
        plan = os.path.join(RESULTS, f"b1_flags-{label}.plan.json")
    if not os.path.exists(plan):
        sys.exit(f"no plan at {plan}; run with --discover first")
    measure(plan)


if __name__ == "__main__":
    main()
