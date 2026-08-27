#!/usr/bin/env python3
"""Where a number in the paper could have come from, and what a stated source actually gives.

Shared by the annotation pass, which needs the menu of candidates for each printed value, and
by check_meas.py, which needs to resolve one stated source back to a value.

A source is a string the paper carries next to the number. The two sides of a ratio are split
on `|` because a benchmark name contains `/` itself:

    med:<file>:<benchmark>:<unit>        a median, in ms / us / ns / s
    ratio:<file>:<benchmark>|<file>:<benchmark>    the first over the second
    pct:<file>:<benchmark>|<file>:<benchmark>      the same pair as per cent MORE time
    saving:<file>:<benchmark>|<file>:<benchmark>   the same pair as per cent SAVED
    share:<file>:<benchmark>|<file>:<benchmark>    the first as a per cent OF the second
    geomean:<file>|<file>                geometric mean of the per-case ratios of two runs,
                                         the machine probe excluded as the generator excludes it
    min:<file>:<case>:<unit> / max:...   the fastest or slowest implementation of one case
    mad:<file>:<benchmark>               relative median absolute deviation, per cent
    madagg:<prefix>:<how>                that dispersion aggregated over every benchmark of
                                         every file starting with <prefix>; how is median,
                                         max, min or p90
    probeagg:<how>                       the machine probe aggregated across every file that
                                         carries one, as a ratio to the fastest
    dur:<file>:<how>                     wall time of one pyperf value, from run metadata
    fact:<file>:<dotted.path>[:<unit>]   a value out of a .facts.json sidecar, optionally
                                         rescaled (a sidecar holds seconds; the paper prints ms)

Both sides of a ratio may name the same file, which is how one implementation is compared with
another inside a suite.
"""

from __future__ import annotations

import functools
import glob
import json
import math
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "results", "pyperf")

SCALE = {"ms": 1e3, "us": 1e6, "ns": 1e9, "s": 1.0}


@functools.cache
def medians(tag: str) -> dict[str, float]:
    path = os.path.join(RESULTS, f"{tag}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out: dict[str, float] = {}
    for bench in data.get("benchmarks", []):
        name = (bench.get("metadata", {}) or {}).get("name", "")
        values = [v for run in bench.get("runs", []) for v in run.get("values", [])]
        if name and values:
            out[name] = statistics.median(values)
    return out


@functools.cache
def raw_values(tag: str) -> dict[str, list[float]]:
    """Every timed value per benchmark, which dispersion needs and a median does not."""
    path = os.path.join(RESULTS, f"{tag}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out: dict[str, list[float]] = {}
    for bench in data.get("benchmarks", []):
        name = (bench.get("metadata", {}) or {}).get("name", "")
        values = [v for run in bench.get("runs", []) for v in run.get("values", [])]
        if name and values:
            out[name] = values
    return out


@functools.cache
def facts(tag: str) -> dict:
    path = os.path.join(RESULTS, f"{tag}.facts.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def tags() -> list[str]:
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(RESULTS, "*.json"))
                  if not p.endswith((".facts.json", ".plan.json")))


class Unresolved(Exception):
    """The source string does not name anything that exists."""


def resolve(source: str) -> float:
    """The value a source string denotes, or Unresolved."""
    kind, _, rest = source.partition(":")
    if kind == "med":
        tag, _, tail = rest.partition(":")
        bench, _, unit = tail.rpartition(":")
        series = medians(tag)
        if bench not in series or unit not in SCALE:
            raise Unresolved(source)
        return series[bench] * SCALE[unit]
    if kind in ("ratio", "pct", "saving", "share"):
        left, _, right = rest.partition("|")
        ltag, _, lbench = left.partition(":")
        rtag, _, rbench = right.partition(":")
        a, b = medians(ltag).get(lbench), medians(rtag).get(rbench)
        if not a or not b:
            raise Unresolved(source)
        if kind == "ratio":
            return a / b
        if kind == "pct":
            return (a / b - 1) * 100
        if kind == "saving":
            return (1 - a / b) * 100
        return a / b * 100
    if kind == "geomean":
        left, _, right = rest.partition("|")
        a, b = medians(left), medians(right)
        pairs = [(a[k], b[j]) for k in a for j in b
                 if k.partition("/")[0] == j.partition("/")[0]
                 and "machine_probe" not in k]
        if not pairs:
            raise Unresolved(source)
        products = [x / y for x, y in pairs if y]
        if not products:
            raise Unresolved(source)
        return math.exp(sum(math.log(v) for v in products) / len(products))
    if kind in ("min", "max"):
        tag, _, tail = rest.partition(":")
        case, _, unit = tail.rpartition(":")
        values = [v for k, v in medians(tag).items() if k.partition("/")[0] == case]
        if not values or unit not in SCALE:
            raise Unresolved(source)
        return (min(values) if kind == "min" else max(values)) * SCALE[unit]
    if kind == "mad":
        tag, _, bench = rest.partition(":")
        values = raw_values(tag).get(bench)
        if not values:
            raise Unresolved(source)
        centre = statistics.median(values)
        if not centre:
            raise Unresolved(source)
        return statistics.median([abs(v - centre) for v in values]) / centre * 100
    if kind in ("madagg", "probeagg", "dur"):
        return _aggregate(kind, rest)
    if kind == "fact":
        tag, _, tail = rest.partition(":")
        path, unit = tail, ""
        if tail.rpartition(":")[2] in SCALE:
            path, unit = tail.rpartition(":")[0], tail.rpartition(":")[2]
        node = facts(tag)
        for step in path.split("."):
            if isinstance(node, dict) and step in node:
                node = node[step]
            else:
                raise Unresolved(source)
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            return float(node) * (SCALE[unit] if unit else 1.0)
        raise Unresolved(source)
    raise Unresolved(source)


def _pick(values: list[float], how: str) -> float:
    values = sorted(values)
    if not values:
        raise Unresolved(how)
    if how == "median":
        return statistics.median(values)
    if how == "max":
        return values[-1]
    if how == "min":
        return values[0]
    if how == "p90":
        return values[min(len(values) - 1, round(0.9 * (len(values) - 1)))]
    raise Unresolved(how)


def _aggregate(kind: str, rest: str) -> float:
    if kind == "probeagg":
        probes = []
        for tag in tags():
            for bench, seconds in medians(tag).items():
                if "machine_probe" in bench:
                    probes.append(seconds)
        if not probes:
            raise Unresolved(kind)
        return _pick([p / min(probes) for p in probes], rest)
    target, _, how = rest.rpartition(":")
    if kind == "madagg":
        spreads = []
        for tag in tags():
            if not tag.startswith(target):
                continue
            for bench, values in raw_values(tag).items():
                if "machine_probe" in bench:
                    continue
                centre = statistics.median(values)
                if centre:
                    spreads.append(statistics.median([abs(v - centre) for v in values])
                                   / centre * 100)
        return _pick(spreads, how)
    durations = []
    for tag in tags():
        if not tag.startswith(target):
            continue
        path = os.path.join(RESULTS, f"{tag}.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for bench in data.get("benchmarks", []):
            if "machine_probe" in ((bench.get("metadata", {}) or {}).get("name", "")):
                continue
            for run in bench.get("runs", []):
                values = run.get("values", [])
                meta = run.get("metadata", {}) or {}
                if values and meta.get("duration"):
                    durations.append(meta["duration"]
                                     / (len(values) + len(run.get("warmups", []) or [])) * 1e3)
    return _pick(durations, how)


def prints_as(value: float, printed: str) -> bool:
    """Whether `value` rounds to what the paper typed, at the precision it typed it."""
    text = printed.strip()
    places = len(text.partition(".")[2])
    try:
        return f"{value:.{places}f}" == f"{float(text):.{places}f}"
    except ValueError:
        return False


def candidates(printed: str, limit: int = 60) -> list[str]:
    """Every source that prints as `printed`, most specific kind first."""
    try:
        float(printed)
    except ValueError:
        return []
    found: list[str] = []
    series = {tag: medians(tag) for tag in tags()}

    for tag, values in series.items():
        for bench, seconds in values.items():
            for unit, scale in SCALE.items():
                if prints_as(seconds * scale, printed):
                    found.append(f"med:{tag}:{bench}:{unit}")

    for tag, values in series.items():
        by_case: dict[str, list[str]] = {}
        for bench in values:
            by_case.setdefault(bench.partition("/")[0], []).append(bench)
        for members in by_case.values():
            for left in members:
                for right in members:
                    if left == right:
                        continue
                    a, b = values[left], values[right]
                    if b and prints_as(a / b, printed):
                        found.append(f"ratio:{tag}:{left}|{tag}:{right}")
                    if b and prints_as((a / b - 1) * 100, printed):
                        found.append(f"pct:{tag}:{left}|{tag}:{right}")

    families: dict[str, list[str]] = {}
    for tag in series:
        families.setdefault(tag.split("-")[0], []).append(tag)
    for members in families.values():
        cases: dict[str, list[tuple[str, str]]] = {}
        for tag in members:
            for bench in series[tag]:
                cases.setdefault(bench.partition("/")[0], []).append((tag, bench))
        for entries in cases.values():
            for ltag, lbench in entries:
                for rtag, rbench in entries:
                    if (ltag, lbench) == (rtag, rbench):
                        continue
                    a, b = series[ltag][lbench], series[rtag][rbench]
                    if b and prints_as(a / b, printed):
                        found.append(f"ratio:{ltag}:{lbench}|{rtag}:{rbench}")
                    if b and prints_as((a / b - 1) * 100, printed):
                        found.append(f"pct:{ltag}:{lbench}|{rtag}:{rbench}")

    for tag in tags():
        stack: list[tuple[str, object]] = [("", facts(tag))]
        while stack:
            path, node = stack.pop()
            if isinstance(node, dict):
                stack.extend((f"{path}.{k}" if path else k, v) for k, v in node.items())
            elif (isinstance(node, (int, float)) and not isinstance(node, bool)
                  and prints_as(float(node), printed)):
                found.append(f"fact:{tag}:{path}")

    seen: list[str] = []
    for source in found:
        if source not in seen:
            seen.append(source)
        if len(seen) >= limit:
            break
    return seen


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        if ":" in arg:
            try:
                print(f"{arg} = {resolve(arg):.6g}")
            except Unresolved:
                print(f"{arg} = UNRESOLVED")
        else:
            found = candidates(arg)
            print(f"{arg}: {len(found)} candidate(s)")
            for source in found[:12]:
                print(f"    {source}")
