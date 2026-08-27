#!/usr/bin/env python
"""RQ7 driver: does stacking the techniques compose on a realistic mixed pipeline?"""

from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import sysconfig
import threading
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

import pyperf  # noqa: E402
from mp_pyperf import RESULTS, Suite, bench_tag, interp_facts  # noqa: E402

Rec = dict[str, Any]
Stage = Callable[[], Any]
NumT = TypeVar("NumT", int, float)

N_REC = 20_000
CODE_LEN = 24
WORKERS = 4
SO = "dylib" if sys.platform == "darwin" else "so"


def make_jsonl(n: int) -> list[str]:
    lines: list[str] = []
    x = 987654321
    for i in range(n):
        chars: list[str] = []
        for _ in range(CODE_LEN):
            x = (1103515245 * x + 12345) & 0x7FFFFFFF
            r = x % 100
            if r < 40:
                chars.append(chr(97 + (x >> 7) % 26))
            elif r < 70:
                chars.append(chr(48 + (x >> 7) % 10))
            elif r < 85:
                chars.append(" ")
            else:
                chars.append(chr(33 + (x >> 7) % 14))
        rec = {"id": i, "code": "".join(chars),
               "x": ((i * 37) % 1000) / 7.0, "y": ((i * 11) % 97) / 3.0,
               "ok": (i % 17) != 0}
        lines.append(json.dumps(rec))
    return lines


def stage_parse(lines: list[str]) -> list[Rec]:
    return [json.loads(ln) for ln in lines]


def classify_py(code: str) -> tuple[int, int]:
    """Branchy per-record classification: token count + checksum."""
    tokens = 0
    checksum = 0
    state = 0
    for ch in code:
        c = ord(ch)
        if 48 <= c <= 57:
            if state != 1:
                tokens += 1
                state = 1
            checksum += c - 48
        elif 97 <= c <= 122:
            if state != 2:
                tokens += 1
                state = 2
            checksum += c - 96
        elif c == 32:
            state = 0
        else:
            if state != 3:
                tokens += 1
                state = 3
            checksum += 7
    return tokens, checksum


def stage_validate_py(recs: list[Rec]) -> tuple[int, int, int]:
    kept = 0
    tokens = 0
    checksum = 0
    for r in recs:
        if not r["ok"]:
            continue
        if r["x"] < 0.0 or r["y"] < 0.0:
            continue
        t, c = classify_py(r["code"])
        if t == 0:
            continue
        kept += 1
        tokens += t
        checksum += c
    return kept, tokens, checksum


def stage_aggregate_py(recs: list[Rec]) -> tuple[float, float]:
    total = 0.0
    weighted = 0.0
    for r in recs:
        if not r["ok"]:
            continue
        x = r["x"]
        y = r["y"]
        total += x * x + y * y
        weighted += math.sqrt(x * x + 1.0) * (y + 1.0)
    return total, weighted


def summarize(kept: int, tokens: int, checksum: int, total: float, weighted: float) -> str:
    return json.dumps({"kept": kept, "tokens": tokens, "checksum": checksum,
                       "total": round(total, 6), "weighted": round(weighted, 6)},
                      sort_keys=True)


def same_summary(a: str, b: str, tol: float = 1e-9) -> bool:
    """Integer fields must match exactly; the two float sums are compared relatively."""
    da, db = json.loads(a), json.loads(b)
    for key in ("kept", "tokens", "checksum"):
        if da[key] != db[key]:
            return False
    for key in ("total", "weighted"):
        scale = max(1.0, abs(da[key]), abs(db[key]))
        if abs(da[key] - db[key]) > tol * scale:
            return False
    return True


def make_numba_aggregate(recs: list[Rec]) -> Callable[[list[Rec]], tuple[float, float]]:
    import numba
    import numpy as np

    @numba.njit(cache=False)
    def agg(xs: Any, ys: Any, oks: Any) -> tuple[float, float]:
        total = 0.0
        weighted = 0.0
        for i in range(xs.shape[0]):
            if not oks[i]:
                continue
            x = xs[i]
            y = ys[i]
            total += x * x + y * y
            weighted += math.sqrt(x * x + 1.0) * (y + 1.0)
        return total, weighted

    def stage(rs: list[Rec]) -> tuple[float, float]:
        xs = np.fromiter((r["x"] for r in rs), dtype=np.float64, count=len(rs))
        ys = np.fromiter((r["y"] for r in rs), dtype=np.float64, count=len(rs))
        oks = np.fromiter((r["ok"] for r in rs), dtype=np.bool_, count=len(rs))
        return agg(xs, ys, oks)

    stage(recs)
    return stage


def make_native_validate() -> Callable[[list[Rec]], tuple[int, int, int]]:
    lib = ctypes.CDLL(os.path.join(BENCH, "build", "native", f"libbranchy_c.{SO}"))
    lib.c_tokenize.restype = ctypes.c_longlong
    lib.c_tokenize.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t,
                               ctypes.POINTER(ctypes.c_longlong)]

    def stage(recs: list[Rec]) -> tuple[int, int, int]:
        cs = ctypes.c_longlong(0)
        kept = 0
        tokens = 0
        checksum = 0
        for r in recs:
            if not r["ok"]:
                continue
            if r["x"] < 0.0 or r["y"] < 0.0:
                continue
            code = r["code"].encode()
            t = lib.c_tokenize(code, len(code), ctypes.byref(cs))
            if t == 0:
                continue
            kept += 1
            tokens += t
            checksum += cs.value
        return kept, tokens, checksum

    return stage


def parallel_map(fn: Callable[[list[Rec]], Sequence[NumT]],
                 recs: list[Rec], workers: int = WORKERS) -> list[NumT]:
    """Split the record list across threads and combine the per-chunk tuples."""
    step = (len(recs) + workers - 1) // workers
    chunks = [recs[i:i + step] for i in range(0, len(recs), step)]
    out: list[Sequence[NumT]] = [()] * len(chunks)

    def work(i: int, c: list[Rec]) -> None:
        out[i] = fn(c)

    ts = [threading.Thread(target=work, args=(i, c)) for i, c in enumerate(chunks)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return [sum(col) for col in zip(*out, strict=True)]


STAGE_ROWS = [
    ("stage_parse", "v0_pure", "json.loads per line (stdlib)"),
    ("stage_validate", "v0_pure", "pure-Python classification"),
    ("stage_aggregate", "v0_pure", "pure-Python numeric fold"),
    ("stage_aggregate", "v1_numba", "numba njit fold, incl. dict->ndarray conversion"),
    ("stage_validate", "v2_native", "classification in C via ctypes, one call per record"),
]

E2E_ROWS = [
    ("v0_pure", "everything in pure Python"),
    ("v1_numba", "numeric stage on Numba"),
    ("v2_numba_native", "numeric on Numba + classification in C"),
    ("v3_native_threads", "C classification + numeric fold on 4 threads"),
    ("v4_all", "Numba + C + 4 threads"),
]


def build_stage(case: str, variant: str, lines: list[str],
                recs: list[Rec]) -> Stage:
    if case == "stage_parse":
        return lambda: stage_parse(lines)
    if case == "stage_validate":
        if variant == "v0_pure":
            return lambda: stage_validate_py(recs)
        nat = make_native_validate()
        return lambda: nat(recs)
    if variant == "v0_pure":
        return lambda: stage_aggregate_py(recs)
    nb = make_numba_aggregate(recs)
    return lambda: nb(recs)


def build_e2e(variant: str, lines: list[str],
              recs: list[Rec]) -> Callable[[], str]:
    if variant == "v0_pure":
        def pure() -> str:
            r = stage_parse(lines)
            return summarize(*stage_validate_py(r), *stage_aggregate_py(r))
        return pure

    if variant == "v1_numba":
        nb = make_numba_aggregate(recs)

        def numeric_on_numba() -> str:
            r = stage_parse(lines)
            return summarize(*stage_validate_py(r), *nb(r))
        return numeric_on_numba

    nat = make_native_validate()

    if variant == "v2_numba_native":
        nb = make_numba_aggregate(recs)

        def numba_and_c() -> str:
            r = stage_parse(lines)
            return summarize(*nat(r), *nb(r))
        return numba_and_c

    if variant == "v3_native_threads":
        def native_threads() -> str:
            r = stage_parse(lines)
            return summarize(*parallel_map(nat, r, workers=WORKERS),
                             *parallel_map(stage_aggregate_py, r, workers=WORKERS))
        return native_threads

    nb = make_numba_aggregate(recs)

    def everything() -> str:
        r = stage_parse(lines)
        return summarize(*parallel_map(nat, r, workers=WORKERS),
                         *parallel_map(nb, r, workers=WORKERS))
    return everything


def build(case: str, variant: str, lines: list[str],
          recs: list[Rec]) -> Stage:
    if case == "end_to_end":
        return build_e2e(variant, lines, recs)
    return build_stage(case, variant, lines, recs)


def stage_summary(case: str, out, pure_validate, pure_aggregate) -> str:
    """A stage's own output, substituted into the otherwise pure-Python pipeline."""
    if case == "stage_parse":
        return summarize(*stage_validate_py(out), *stage_aggregate_py(out))
    if case == "stage_validate":
        return summarize(*out, *pure_aggregate)
    return summarize(*pure_validate, *out)


def config_facts() -> dict[str, Any]:
    """Which of the three GIL configurations this process is. Observations, not timings."""
    return {
        "ft_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
        "python_gil_env": os.environ.get("PYTHON_GIL"),
        "cpu_count": os.cpu_count(),
    }


def discover(n: int) -> dict[str, Any]:
    """Build every row once, verify it at full size, and write the plan."""
    lines = make_jsonl(n)
    recs = stage_parse(lines)
    pure_validate = stage_validate_py(recs)
    pure_aggregate = stage_aggregate_py(recs)
    ref = summarize(*pure_validate, *pure_aggregate)
    cfg = config_facts()
    print(f"=== pipeline discovery on {sys.version.split()[0]} ({bench_tag()}) n={n} "
          f"ft_build={cfg['ft_build']} gil_enabled={cfg['gil_enabled']}")
    print(f"    reference summary: {ref}")
    plan: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []

    rows = list(STAGE_ROWS) + [("end_to_end", v, note) for v, note in E2E_ROWS]

    for case, variant, note in rows:
        try:
            fn = build(case, variant, lines, recs)
        except Exception as exc:
            problems.append({"case": case, "impl": variant, "status": "unavailable",
                             "note": f"{type(exc).__name__}: "
                                     f"{str(exc).splitlines()[0][:200]}"})
            print(f"  unavailable {case:<16} {variant:<18} {type(exc).__name__}")
            continue
        try:
            out = fn()
        except Exception as exc:
            problems.append({"case": case, "impl": variant, "status": "raised",
                             "note": f"{type(exc).__name__}: "
                                     f"{str(exc).splitlines()[0][:200]}"})
            print(f"  raised      {case:<16} {variant:<18} {type(exc).__name__}")
            continue
        if case == "end_to_end":
            got = out
        else:
            got = stage_summary(case, out, pure_validate, pure_aggregate)
        if not same_summary(got, ref):
            problems.append({"case": case, "impl": variant, "status": "wrong_result",
                             "got": got[:120], "expected": ref[:120],
                             "note": "summary differs from the pure-Python pipeline"})
            print(f"  WRONG       {case:<16} {variant:<18} {got[:80]}")
            continue
        plan.append({"case": case, "variant": variant, "note": note})
        exact = "" if got == ref else "  (float fields differ within tolerance)"
        print(f"  ok          {case:<16} {variant:<18}{exact}")

    return {"suite": "b7_pipeline",
            "params": {"n": n, "code_len": CODE_LEN, "workers": WORKERS},
            "interp": interp_facts(), "config": cfg, "reference": ref,
            "plan": plan, "problems": problems}


def measure(plan_path: str) -> None:
    with open(plan_path) as fh:
        disc = json.load(fh)
    p = disc["params"]
    suite = Suite("b7_pipeline", forward=("plan",))
    suite.runner.argparser.add_argument("--plan", default=plan_path)
    suite.parse()
    suite.gate_failures = [dict(prob, impl=f"{suite.label}/{prob['impl']}")
                           for prob in disc["problems"]]
    suite.facts = {"params": p, "reference": disc["reference"], **config_facts()}
    suite.log(f"=== b7_pipeline [{suite.label}] {sys.version.split()[0]} n={p['n']} "
              f"{len(disc['plan'])} benchmarks")

    state: dict[str, Any] = {}

    def data() -> tuple[list[str], list[Rec]]:
        if "recs" not in state:
            state["lines"] = make_jsonl(p["n"])
            state["recs"] = stage_parse(state["lines"])
        return state["lines"], state["recs"]

    cache: dict[tuple[str, str], Stage] = {}

    def timed_for(case: str, variant: str) -> Stage:
        if (case, variant) not in cache:
            cache[(case, variant)] = build(case, variant, *data())
        return cache[(case, variant)]

    for e in disc["plan"]:
        def time_fn(loops: int, case: str = e["case"],
                    variant: str = e["variant"]) -> float:
            fn = timed_for(case, variant)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        suite.bench_time(case=e["case"], impl=f"{suite.label}/{e['variant']}",
                         time_fn=time_fn, params=p, note=e["note"])

    suite.machine_probe()
    suite.write_sidecar()


def main() -> None:
    label = bench_tag()
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    if "--discover" in sys.argv:
        sys.argv.remove("--discover")
        os.makedirs(RESULTS, exist_ok=True)
        out = os.path.join(RESULTS, f"b7_pipeline-{label}.plan.json")
        disc = discover(N_REC)
        with open(out, "w") as fh:
            json.dump(disc, fh, indent=1, default=str)
        print(f"[discovery] {len(disc['plan'])} benchmarks, "
              f"{len(disc['problems'])} problems -> {out}")
        return
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    else:
        plan = os.environ.get("MP_PLAN") or os.path.join(
            RESULTS, f"b7_pipeline-{label}.plan.json")
    if not os.path.exists(plan):
        sys.exit(f"no plan at {plan}; run with --discover first")
    measure(plan)


if __name__ == "__main__":
    main()
