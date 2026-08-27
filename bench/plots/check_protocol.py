#!/usr/bin/env python3
"""What the paper says about how it measured, checked against what the runs recorded.

Four of the defects three audits found were here, and none of them was a wrong measurement:
the two-pass protocol was described as covering every millisecond-scale suite when five files
have it, "every suite registers a machine probe" was true of 46 files out of 64, an alternating
protocol was described that produced no artifact at all, and one result file was shipped that
no script produces and no figure reads.

Every claim below is stated once here, with the sentence it protects. A number the paper prints
is re-derived from the metadata; a structural claim is checked against the tree. When a rerun
changes the campaign, this fails and names the sentence to update.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "results", "pyperf")
PAPER = os.path.join(ROOT, "paper")
PLOTS = os.path.join(ROOT, "bench", "plots")
CAMPAIGN = os.path.join(ROOT, "bench", "run_campaign.sh")


def result_files() -> list[str]:
    return [p for p in sorted(glob.glob(os.path.join(RESULTS, "*.json")))
            if not p.endswith((".facts.json", ".plan.json"))]


def benchmark_names(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [(b.get("metadata", {}) or {}).get("name", "") for b in data.get("benchmarks", [])]


def value_shape(path: str) -> tuple[int, int]:
    """(worker runs, values) of the first timed benchmark in the file."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for bench in data.get("benchmarks", []):
        if "machine_probe" in ((bench.get("metadata", {}) or {}).get("name", "")):
            continue
        runs = [r for r in bench.get("runs", []) if r.get("values")]
        if runs:
            return len(runs), sum(len(r["values"]) for r in runs)
    return 0, 0


def probe_coverage() -> tuple[int, int]:
    with_probe = sum(1 for p in result_files()
                     if any("machine_probe" in n for n in benchmark_names(p)))
    return with_probe, len(result_files())


def two_pass_suites() -> set[str]:
    """Suites the campaign runs twice, read from run_campaign.sh rather than assumed."""
    with open(CAMPAIGN, encoding="utf-8") as fh:
        return set(re.findall(r"^\s*(?:&&\s*)?run2\s+(\S+)", fh.read(), re.M))


def load_prefixes() -> set[str]:
    """Prefixes the generators read. The gates are skipped: they would match their own text."""
    found: set[str] = set()
    for path in glob.glob(os.path.join(PLOTS, "*.py")):
        if os.path.basename(path).startswith("check_"):
            continue
        with open(path, encoding="utf-8") as fh:
            found |= set(re.findall(r'load\("([^"]+)"', fh.read()))
    return found


def stated(pattern: str, *files: str) -> list[tuple[str, int, str]]:
    """Every place the paper prints a number matching `pattern`, with file and line."""
    out: list[tuple[str, int, str]] = []
    for name in files:
        path = os.path.join(PAPER, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out.extend((name, text.count("\n", 0, match.start()) + 1, match.group(1))
                   for match in re.finditer(pattern, text))
    return out


def check_probe_count() -> list[str]:
    with_probe, total = probe_coverage()
    sites = stated(r"across the (\d+) result files that carry it", "paper.tex")
    sites += stated(r"по (\d+) файлам результатов, которые её несут", "paper-ru.tex")
    problems = []
    if not sites:
        problems.append("no sentence states the probe-carrying file count; the check is blind")
    for name, line, printed in sites:
        if int(printed) != with_probe:
            problems.append(f"{name}:{line} says {printed} files carry the machine probe; "
                            f"{with_probe} of {total} do")
    return problems


def check_two_pass() -> list[str]:
    declared = two_pass_suites()
    problems = []
    for path in result_files():
        tag = os.path.basename(path)[:-5]
        runs, values = value_shape(path)
        if tag in declared and values < 60:
            problems.append(f"{tag} is run2 in run_campaign.sh but carries {values} values "
                            f"from {runs} runs, not the sixty a second pass would add")
        if tag not in declared and values >= 60 and runs >= 20 and tag.startswith(("b1_", "b2_")):
            problems.append(f"{tag} carries {values} values from {runs} runs but is not run2; "
                            f"either the campaign or the description of it is stale")
    return problems


def check_no_orphans() -> list[str]:
    prefixes = load_prefixes()
    names = [os.path.basename(p) for p in result_files()]
    problems = [f"{name} is shipped but no figure or table reads it: no load() prefix matches"
                for name in names
                if not any(name.startswith(prefix) for prefix in prefixes)]
    problems += [f"the generators read a prefix that matches no result file: {prefix!r}"
                 for prefix in sorted(prefixes)
                 if not any(name.startswith(prefix) for name in names)]
    return problems


def check_named_artifacts() -> list[str]:
    """A protocol the paper describes must have left something behind."""
    problems = []
    for name in ("paper.tex", "paper-ru.tex"):
        with open(os.path.join(PAPER, name), encoding="utf-8") as fh:
            text = fh.read()
        describes = "ab_flags.sh" in text
        claims_use = bool(re.search(r"\\S\\ref\{sec:rq1b\} (uses|пользуется)", text))
        if describes and claims_use and not glob.glob(os.path.join(RESULTS, "ab_*")):
            problems.append(f"{name} says RQ1b uses the alternating protocol, but "
                            f"results/pyperf/ab_* does not exist")
    return problems


CHECKS = [
    ("machine probe coverage", check_probe_count,
     "paper.tex:404 and its RU mirror print how many files carry the probe"),
    ("two-pass protocol", check_two_pass,
     "the method section describes which suites are run twice"),
    ("no orphan result files", check_no_orphans,
     "every shipped run should be read by something, and every reader should have a run"),
    ("described protocols exist", check_named_artifacts,
     "a protocol the method section describes must have produced files"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", action="store_true",
                        help="print the derived protocol facts and exit")
    args = parser.parse_args()

    if args.facts:
        with_probe, total = probe_coverage()
        shapes: collections.Counter[tuple[int, int]] = collections.Counter()
        for path in result_files():
            shapes[value_shape(path)] += 1
        print(f"result files            {total}")
        print(f"carrying a machine probe {with_probe}")
        print(f"run twice (run2)         {sorted(two_pass_suites())}")
        print("shape (worker runs, values) -> files")
        for shape, count in sorted(shapes.items()):
            print(f"  {shape}  x{count}")
        return 0

    total = 0
    for name, check, protects in CHECKS:
        problems = check()
        total += len(problems)
        if problems:
            print(f"  [{name}] {len(problems)} -- {protects}")
            for problem in problems:
                print(f"      {problem}")
        else:
            print(f"  [{name}] clean")

    print()
    if total:
        print(f"PROTOCOL GATE: {total} claim(s) the runs do not support")
    else:
        print("PROTOCOL GATE: PASS -- what the paper says it did is what the runs record")
    print(f"\n{len(result_files())} result files, {len(CHECKS)} claims checked")
    return total


if __name__ == "__main__":
    sys.exit(main())
