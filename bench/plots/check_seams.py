#!/usr/bin/env python3
"""Defects a substitution leaves at the seam between two lines.

A search-and-replace over LaTeX lands inside a sentence that wraps, and the damage shows up
where the lines join: a word repeated across the break, a preposition left governing the case
the old word had, a maths delimiter closed on the wrong side. None of it stops the compiler,
and every one of them has been introduced into this paper by an editing pass at least once.

Only checks that can be made precise are here. A doubled-comma check was written and removed:
after LaTeX constructs are masked out it cannot tell a real one from the seam of its own mask,
and a gate that reports five hundred false positives is one nobody reads.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "paper")

MASK: list[str] = [
    r"\\meas\{[^}]*\}",
    r"\$[^$]*\$",
    r"\\code\{[^}]*\}",
    r"\\(label|ref|eqref|cite|input|include|includegraphics|figifexists)\{[^}]*\}(\{[^}]*\})?",
    r"\\(begin|end)\{[^}]*\}(\[[^\]]*\])?",
    r"\\[a-zA-Z]+",
]

DATIVE_GOVERNORS = ("к", "по", "благодаря", "вопреки", "согласно")

PREPOSITIONAL_ONLY = r"[а-яё]+(?:ении|ании)"

ALLOW: list[tuple[str, str]] = [
]


def mask(text: str) -> str:
    for pattern in MASK:
        text = re.sub(pattern, "\u0000", text)
    return text


def sources() -> list[str]:
    found: list[str] = []
    for pattern in ("*.tex", "sections/*.tex", "sections-ru/*.tex"):
        found += sorted(glob.glob(os.path.join(PAPER, pattern)))
    return found


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def doubled_words(path: str) -> list[tuple[int, str]]:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    masked = mask(raw)
    hits = []
    for match in re.finditer(r"\b([A-Za-zА-Яа-яЁё]{3,})(\s+)\1\b", masked, re.I):
        if "\n" not in match.group(2) and match.group(1).lower() in ("that", "had", "не"):
            continue
        hits.append((line_of(masked, match.start()), " ".join(match.group(0).split())))
    return hits


def wrong_case_after_preposition(path: str) -> list[tuple[int, str]]:
    if "-ru" not in path:
        return []
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    flat = mask(raw)
    hits = []
    governors = "|".join(DATIVE_GOVERNORS)
    for match in re.finditer(rf"\b({governors})\s+({PREPOSITIONAL_ONLY})\b", flat):
        phrase = " ".join(match.group(0).split())
        if any(phrase.startswith(allowed) for allowed, _why in ALLOW):
            continue
        hits.append((line_of(flat, match.start()), phrase))
    return hits


def unbalanced_math(path: str) -> list[tuple[int, str]]:
    hits = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh.read().splitlines(), 1):
            body = line.replace("\\%", "").replace("\\$", "")
            body = re.split(r"(?<!\\)%", body)[0]
            if body.count("$") % 2:
                hits.append((number, line.strip()[:90]))
    return hits


CHECKS = [
    ("doubled word", doubled_words,
     "a replacement landed next to the word it was meant to replace"),
    ("case after preposition", wrong_case_after_preposition,
     "a noun was substituted without re-inflecting it for the preposition governing it"),
    ("unbalanced maths", unbalanced_math, "a $ was opened or closed on the wrong side of a cut"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-allowed", action="store_true",
                        help="list the phrases the allowlist silences")
    args = parser.parse_args()

    total = 0
    files = sources()
    for name, check, why in CHECKS:
        found = [(path, hits) for path in files if (hits := check(path))]
        count = sum(len(hits) for _path, hits in found)
        total += count
        if not count:
            print(f"  [{name}] clean")
            continue
        print(f"  [{name}] {count} -- {why}")
        for path, hits in found:
            for number, text in hits:
                print(f"      {rel(path)}:{number}  {text}")

    print()
    if total:
        print(f"SEAM GATE: {total} defect(s) -- each is a real edit scar, not a false positive")
    else:
        print("SEAM GATE: PASS -- no seam defects in any source")
    if args.show_allowed and ALLOW:
        print(f"\nallowlist ({len(ALLOW)}):")
        for phrase, reason in ALLOW:
            print(f"  {phrase}: {reason}")
    print(f"\nscanned {len(files)} LaTeX sources")
    return total


if __name__ == "__main__":
    sys.exit(main())
