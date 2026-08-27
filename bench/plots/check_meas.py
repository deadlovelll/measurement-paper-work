#!/usr/bin/env python3
"""Every annotated number must still equal what the source it names actually gives.

This is the gate that a corpus-membership check could not be. The earlier attempt asked "does
some run produce this number", and with 162 000 derivable values the answer was yes for 100 %
of two-digit and 99.6 % of three-digit values, so it caught none of the 41 defects three audits
found -- every one of which was a real number taken from the wrong place.

Here the paper says where each number came from:

    \\meas{ratio:b1_flags-314:mandelbrot/numba_plain|b1_flags-314:mandelbrot/O2}{1.12}

and the gate re-derives it. A number moved to another baseline, another statistic or another
kernel now fails, because the source no longer prints as the value beside it. Re-run the
campaign and every annotated number is re-checked against the new data at once.

Coverage is reported, not assumed: a number with no annotation is not checked, and the gate
says how many those are.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import provenance as pv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MEAS = re.compile(r"\\meas\{([^}]*)\}\{([^}]*)\}")
UNIT = re.compile(
    r"\$?(\d+(?:\.\d+)?)\$?\\,?\\?%"
    r"|\$?(\d+(?:\.\d+)?)\$?\\,(?:ms|мс|s|с|ns|нс|мкс)\b"
    r"|\$(\d+(?:\.\d+)?)\\times\$"
    r"|\$(\d+(?:\.\d+)?)\$~раза"
)


def sources(paper: str) -> list[str]:
    found = sorted(glob.glob(os.path.join(paper, "*.tex")))
    for sub in ("sections", "sections-ru"):
        found += sorted(glob.glob(os.path.join(paper, sub, "*.tex")))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", default="paper",
                        help="which paper directory to check (default: paper)")
    parser.add_argument("--min-coverage", type=float, default=0.0,
                        help="fail if fewer than this fraction of numbers are annotated")
    args = parser.parse_args()

    paper = os.path.join(ROOT, args.paper)
    if not os.path.isdir(paper):
        print(f"no such paper directory: {args.paper}")
        return 2

    broken: list[str] = []
    unresolved: list[str] = []
    checked = 0
    bare = 0

    for path in sources(paper):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        where = os.path.relpath(path, ROOT)
        for match in MEAS.finditer(text):
            source, printed = match.group(1), match.group(2)
            line = text.count("\n", 0, match.start()) + 1
            checked += 1
            try:
                value = pv.resolve(source)
            except pv.Unresolved:
                unresolved.append(f"{where}:{line} names {source!r}, which resolves to nothing")
                continue
            if not pv.prints_as(value, printed):
                broken.append(f"{where}:{line} prints {printed} but {source} gives "
                              f"{value:.6g}")
        stripped = MEAS.sub("", text)
        bare += len(UNIT.findall(stripped))

    total = checked + bare
    coverage = checked / total if total else 1.0

    for problem in broken:
        print(f"  [stale] {problem}")
    for problem in unresolved:
        print(f"  [dangling] {problem}")

    print()
    if broken or unresolved:
        print(f"MEAS GATE: {len(broken)} stale, {len(unresolved)} dangling")
    else:
        print("MEAS GATE: PASS -- every annotated number still equals its source")

    print(f"\n{checked} annotated of {total} measured numbers ({100 * coverage:.1f}% coverage); "
          f"{bare} carry no source and are not checked")
    if args.min_coverage and coverage < args.min_coverage:
        print(f"coverage below the required {100 * args.min_coverage:.0f}%")
        return len(broken) + len(unresolved) + 1
    return len(broken) + len(unresolved)


if __name__ == "__main__":
    sys.exit(main())
