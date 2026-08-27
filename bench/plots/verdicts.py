#!/usr/bin/env python
"""Significance verdicts for every place the paper says two things are the same."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyperf_load as P
from pyperf_load import Comparison
from style import load, ok, pick, stats_of

PAIRS = [
    ("RQ1b  -O2 vs -O3, array sum (identical machine code)",
     "b1_flags-", "arraysum", "O2", "O3"),
    ("RQ1b  -O2 vs -O3 -mcpu=native, array sum (identical machine code)",
     "b1_flags-", "arraysum", "O2", "O3native"),
    ("RQ1b  -O2 vs -O3, matmul (identical machine code)",
     "b1_flags-", "matmul", "O2", "O3"),
    ("RQ1b  -O2 vs no vectoriser, matmul (identical machine code)",
     "b1_flags-", "matmul", "O2", "O3native_novec"),
    ("RQ1b  C -O2 vs Numba, array sum",
     "b1_flags-", "arraysum", "O2", "numba_plain"),
    ("RQ1b  C -ffast-math vs Numba fastmath, array sum",
     "b1_flags-", "arraysum", "O3native_ffast", "numba_fastmath"),
    ("RQ1b  8 accumulators at -O2 vs -ffast-math, array sum",
     "b1_flags-", "arraysum", "accum_acc8", "O3native_ffast"),
    ("RQ1   Cython vs C (ctypes), array sum", "b1_compute-", "arraysum", "cython", "c_ctypes"),
    ("RQ1   Cython vs Rust (ctypes), array sum", "b1_compute-", "arraysum", "cython",
     "rust_ctypes"),
    ("RQ1   Numba vs C (ctypes), array sum", "b1_compute-", "arraysum", "numba", "c_ctypes"),
    ("RQ2   Numba vs C (ctypes), tokenize", "b2_branchy-", "tokenize", "numba", "c_ctypes"),
    ("RQ2   Cython vs C (ctypes), tokenize", "b2_branchy-", "tokenize", "cython", "c_ctypes"),
    ("RQ2   Cython vs C (ctypes), BFS", "b2_branchy-", "bfs", "cython", "c_ctypes"),
    ("RQ6   thin LTO vs full LTO, int arithmetic", "b5_buildcfg-", "int_arith",
     "ltothin", "ltofull"),
]

PROBE_SUITES = ["b1_compute-", "b1_flags-", "b2_branchy-", "b3_runtime-", "b3_spec-",
                "b4_threads-", "b5_buildcfg-", "b7_pipeline-"]


def verdict(prefix: str, case: str, a: str, b: str) -> Comparison | None:
    recs = ok(load(prefix))
    ra, rb = pick(recs, case, a), pick(recs, case, b)
    if not (ra and rb):
        return None
    return P.compare(stats_of(ra)["raw_per_op_s"], stats_of(rb)["raw_per_op_s"])


def main() -> None:
    print("=" * 78)
    print("Equality claims: pyperf's significance test (Student's t, 95%)")
    print("=" * 78)
    for title, prefix, case, a, b in PAIRS:
        v = verdict(prefix, case, a, b)
        if v is None:
            print(f"  {title:<62} no data")
            continue
        word = "SIGNIFICANT" if v["significant"] else "not significant"
        print(f"  {title:<62} {v['ratio']:6.4f}x  {word}  (t={v['t_score']:.2f})")

    print()
    print("=" * 78)
    print("Machine probe across suites: how much the host moved during the campaign")
    print("=" * 78)
    probes: list[tuple[str, str, float]] = []
    for prefix in PROBE_SUITES:
        probes.extend((r["label"], r["suite"], stats_of(r)["median_s"])
                      for r in ok(load(prefix)) if r["case"] == "machine_probe")
    if not probes:
        print("  no machine probe recorded")
        return
    lo = min(t for _, _, t in probes)
    for label, suite, t in probes:
        print(f"  {suite:<14} {label:<12} {t * 1e3:8.4f} ms   {t / lo:5.3f}x the fastest")
    ratios = sorted(t / lo for _, _, t in probes)
    hi = ratios[-1]
    import statistics
    med = statistics.median(ratios)
    p90 = ratios[int(0.9 * (len(ratios) - 1))]
    print(f"\n  {len(probes)} probes: median {med:.3f}x, p90 {p90:.3f}x, worst {hi:.3f}x "
          f"of the fastest.")
    print("  The distribution is what matters, not the worst case: a cross-invocation ratio")
    print("  smaller than the spread between the two invocations it compares is inside the")
    print("  drift. Ratios taken inside one invocation are not affected by it.")


if __name__ == "__main__":
    main()
