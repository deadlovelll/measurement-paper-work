#!/usr/bin/env python3
"""Does this campaign's data deserve to reach the paper?"""

from __future__ import annotations

import collections
import glob
import json
import os
import statistics
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def values_of(bench) -> list[float]:
    return [v for r in bench.get("runs", []) if r.get("values") for v in r["values"]]


def per_run_medians(bench) -> list[float]:
    return [statistics.median(r["values"]) for r in bench.get("runs", []) if r.get("values")]


def mad_pct(vals) -> float:
    med = statistics.median(vals)
    return 100 * statistics.median([abs(v - med) for v in vals]) / med if med else float("nan")


def load(resdir: str) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(glob.glob(os.path.join(resdir, "*.json"))):
        if path.endswith((".facts.json", ".plan.json")):
            continue
        try:
            with open(path) as fh:
                out.append((os.path.basename(path)[:-5], json.load(fh)))
        except Exception as exc:
            print(f"  ! {path}: {exc}")
    return out


def main() -> int:
    resdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "pyperf")
    data = load(resdir)
    findings = 0

    print("=" * 78)
    print("1. MACHINE PROBE -- how far the host moved across the campaign")
    print("=" * 78)
    probes: dict[str, float] = {}
    for name, d in data:
        for b in d.get("benchmarks", []):
            if b.get("metadata", {}).get("name", "").startswith("machine_probe"):
                v = values_of(b)
                if v:
                    probes[name] = statistics.median(v)
    if probes:
        fastest = min(probes.values())
        for name, med in sorted(probes.items(), key=lambda kv: kv[1]):
            print(f"  {name:34} {med*1e3:8.4f} ms   {med/fastest:5.3f}x the fastest")
        ratios = sorted(v / fastest for v in probes.values())
        n = len(ratios)
        print(f"\n  {n} probes: median {ratios[n//2]:.3f}x, "
              f"p90 {ratios[int(n*0.9)]:.3f}x, worst {ratios[-1]:.3f}x")
        if ratios[-1] > 1.10:
            print("  ^ the host moved by more than 10% between suites; "
                  "cross-suite ratios smaller than that are inside the drift")
            findings += 1
    else:
        print("  no machine probe found in any suite")
        findings += 1

    print()
    print("=" * 78)
    print("2. DISPERSION -- MAD as a percentage of the median, per suite")
    print("=" * 78)
    print(f"  {'suite':34} {'n':>4} {'median':>8} {'p90':>8} {'worst':>8}  worst benchmark")
    for name, d in data:
        rows: list[tuple[float, str]] = []
        for b in d.get("benchmarks", []):
            v = values_of(b)
            if len(v) >= 5:
                rows.append((mad_pct(v), b.get("metadata", {}).get("name", "?")))
        if not rows:
            continue
        rows.sort()
        n = len(rows)
        worst_pct, worst_name = rows[-1]
        flag = "  <-- look" if worst_pct > 5 else ""
        print(f"  {name:34} {n:4} {rows[n//2][0]:7.2f}% {rows[int(n*0.9)][0]:7.2f}% "
              f"{worst_pct:7.2f}%  {worst_name}{flag}")
        if worst_pct > 5:
            findings += 1

    print()
    print("=" * 78)
    print("3. TWO-PASS AGREEMENT -- forward pass against the reversed pass")
    print("=" * 78)
    print("  A benchmark tight inside each pass but far apart between them is not noise:")
    print("  the reported median then sits between two modes and equals neither.\n")
    any_split = False
    for name, d in data:
        for b in d.get("benchmarks", []):
            meds = per_run_medians(b)
            if len(meds) < 8:
                continue
            h = len(meds) // 2
            p1, p2 = meds[:h], meds[h:]
            m1, m2 = statistics.median(p1), statistics.median(p2)
            if not m1:
                continue
            ratio = m2 / m1
            s1 = (max(p1) - min(p1)) / m1 if m1 else 0
            if abs(ratio - 1) > 0.05 and abs(ratio - 1) > 3 * max(s1, 1e-9):
                any_split = True
                findings += 1
                print(f"  {name:30} {b['metadata'].get('name','?'):24} "
                      f"pass2/pass1 = {ratio:5.3f}x   (spread inside pass 1: {s1*100:.1f}%)")
    if not any_split:
        print("  no benchmark disagrees between its two passes beyond its own spread")

    print()
    print("=" * 78)
    print("4. NON-OK VERDICTS -- each is either a result or a hole in the setup")
    print("=" * 78)
    buckets = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(resdir, "*.facts.json"))):
        suite = os.path.basename(path)[:-11]
        try:
            with open(path) as fh:
                f = json.load(fh)
        except Exception:
            continue
        for g in f.get("gate_failures", []):
            note = (g.get("note") or "")[:60]
            buckets[(g.get("status", "?"), g.get("impl", "?"), note)].append(suite)
    if not buckets:
        print("  none -- every registered implementation passed its correctness gate")
    else:
        for (status, impl, note), suites in sorted(buckets.items()):
            where = ", ".join(sorted(set(suites)))
            print(f"  {status:14} {impl:18} x{len(suites):<3} {note}")
            print(f"                 in: {where}")
        print(f"\n  {sum(len(v) for v in buckets.values())} verdicts across "
              f"{len(buckets)} distinct causes -- read each one")

    print()
    print("=" * 78)
    print(f"FINDINGS NEEDING A DECISION: {findings}")
    print("=" * 78)
    return findings


if __name__ == "__main__":
    sys.exit(main())
