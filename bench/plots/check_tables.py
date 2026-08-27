#!/usr/bin/env python3
"""The two language versions of a generated table must carry the same numbers.

Both are written by the generators from the same result files, so a difference between them
means one was regenerated and the other was not, or one was edited by hand. Either way the
number a reader sees depends on which language they read, which is the one thing a generated
table exists to prevent.

Also checks the sentences that point into a table by position. "The last row of Table 3" is a
claim about the table's shape, invisible to the compiler and wrong for a whole release of this
paper: the row it meant was the second-to-last, and the real last row said something else.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "paper")

CELL = re.compile(r"-?\d+(?:\.\d+)?")
LABEL_INPUT = re.compile(r"\\label\{(tab:[^}]+)\}.*?\\input\{tables(?:-ru)?/([^}]+)\}", re.S)

POSITION = {
    "last": -1,
    "second-to-last": -2,
    "first": 0,
    "последняя": -1,
    "предпоследняя": -2,
    "первая": 0,
}
POSITION_RE = re.compile(
    r"(?:the\s+)?(last|second-to-last|first)\s+row\s+of\s+Table~\\ref\{(tab:[^}]+)\}"
    r"|(Последняя|Предпоследняя|Первая)\s+строка\s+таблицы~\\ref\{(tab:[^}]+)\}",
    re.I,
)


def body_rows(path: str) -> list[str]:
    """The data rows of a tabular, in order, without the rules."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body = text.split(r"\midrule")[-1].split(r"\bottomrule")[0]
    rows = [r.strip() for r in body.split(r"\\")]
    return [r for r in rows if r and not r.startswith("%")]


def numbers_of(row: str) -> list[str]:
    return [f"{float(v):g}" for v in CELL.findall(row)]


def label_map() -> dict[str, str]:
    """tab:label -> table file basename, read from wherever the table is \\input."""
    found: dict[str, str] = {}
    sources = sorted(glob.glob(os.path.join(PAPER, "*.tex")))
    for sub in ("sections", "sections-ru"):
        sources += sorted(glob.glob(os.path.join(PAPER, sub, "*.tex")))
    for path in sources:
        with open(path, encoding="utf-8") as fh:
            for label, table in LABEL_INPUT.findall(fh.read()):
                found.setdefault(label, table)
    return found


def check_pairs() -> list[str]:
    problems: list[str] = []
    for en_path in sorted(glob.glob(os.path.join(PAPER, "tables", "*.tex"))):
        name = os.path.basename(en_path)
        ru_path = os.path.join(PAPER, "tables-ru", name)
        if not os.path.exists(ru_path):
            problems.append(f"{name}: no Russian counterpart")
            continue
        en_rows, ru_rows = body_rows(en_path), body_rows(ru_path)
        if len(en_rows) != len(ru_rows):
            problems.append(f"{name}: {len(en_rows)} data rows in EN, {len(ru_rows)} in RU")
            continue
        for index, (en_row, ru_row) in enumerate(zip(en_rows, ru_rows, strict=True), start=1):
            if numbers_of(en_row) != numbers_of(ru_row):
                problems.append(f"{name} row {index}: EN {numbers_of(en_row)} "
                                f"vs RU {numbers_of(ru_row)}")
    return problems


def check_positions() -> list[str]:
    labels = label_map()
    problems: list[str] = []
    sources: list[str] = []
    for sub in ("sections", "sections-ru"):
        sources += sorted(glob.glob(os.path.join(PAPER, sub, "*.tex")))
    for path in sources:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        directory = "tables-ru" if "-ru" in path else "tables"
        for match in POSITION_RE.finditer(text):
            word = (match.group(1) or match.group(3)).lower()
            label = match.group(2) or match.group(4)
            line = text.count("\n", 0, match.start()) + 1
            where = f"{os.path.relpath(path, ROOT)}:{line}"
            table = labels.get(label)
            if not table:
                problems.append(f"{where} points at {label}, which is \\input nowhere")
                continue
            rows = body_rows(os.path.join(PAPER, directory, table))
            if not rows:
                problems.append(f"{where}: {table} has no data rows to point at")
                continue
            row = rows[POSITION[word]]
            sentence = text[match.start(): text.find(".", match.end()) + 1]
            quoted = set(numbers_of(sentence)) - {f"{float(n):g}" for n in ("1", "2", "3")}
            in_row = set(numbers_of(row))
            if quoted and not (quoted & in_row):
                problems.append(f"{where} calls it the {word} row of {label} and quotes "
                                f"{sorted(quoted)}, but that row holds {sorted(in_row)}")
    return problems


CHECKS = [
    ("EN/RU table cells", check_pairs,
     "both languages are generated from the same results and must agree"),
    ("rows named by position", check_positions,
     "a sentence that points into a table by position must point at the right row"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

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

    tables = len(glob.glob(os.path.join(PAPER, "tables", "*.tex")))
    print()
    print("TABLES GATE: " + (f"{total} finding(s)" if total
                             else "PASS -- both languages agree and every positional "
                                  "reference lands on the row it names"))
    print(f"\n{tables} table pairs, {len(label_map())} labelled tables")
    return total


if __name__ == "__main__":
    sys.exit(main())
