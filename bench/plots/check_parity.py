#!/usr/bin/env python3
"""Every number stated in one language must be stated in the other.

Occurrences are not compared, only presence: the two texts are written independently, so one
may repeat a value the other refers back to. A value that appears in one language and nowhere
in the other is either a divergence or a statement only half the readers get.

Comparison is per section, paired by \\label, not per file. A whole-file comparison misses the
defect this gate exists for: a number dropped from one section of one language while the same
digits survive in an unrelated section, which is exactly how the 4.4 % band went missing from
the Russian RQ1 while the Russian abstract still promised it.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "paper")

PAIRS: list[tuple[str, str, str]] = [
    ("front matter", "paper.tex", "paper-ru.tex"),
    ("results", "sections/results.tex", "sections-ru/results.tex"),
    ("discussion", "sections/discussion.tex", "sections-ru/discussion.tex"),
    ("conclusion", "sections/conclusion.tex", "sections-ru/conclusion.tex"),
    ("t1 compute", "tables/t1_compute.tex", "tables-ru/t1_compute.tex"),
    ("t2 branchy", "tables/t2_branchy.tex", "tables-ru/t2_branchy.tex"),
    ("t3 runtime facts", "tables/t3_runtime_facts.tex", "tables-ru/t3_runtime_facts.tex"),
    ("t4 platforms", "tables/t4_platforms.tex", "tables-ru/t4_platforms.tex"),
    ("t5 cinder matrix", "tables/t5_cinder_matrix.tex", "tables-ru/t5_cinder_matrix.tex"),
    ("t6 codegen", "tables/t6_codegen.tex", "tables-ru/t6_codegen.tex"),
]

NUMBER = re.compile(r"(?<![A-Za-zА-Яа-яЁё0-9_\\.])(\d+(?:[.,]\d+)?)")
SECTION = re.compile(r"\\label\{(sec:[^}]+)\}")

TYPESETTING: list[tuple[str, str]] = [
    (r"\\tolerance\s*=\s*\d+", "line-breaking tolerance, not a measurement"),
    (r"\\emergencystretch\s*=\s*[\d.]+", "line-breaking slack, not a measurement"),
    (r"\\(hbadness|vbadness|hfuzz|vfuzz|pretolerance)\s*=?\s*[\d.]+", "TeX badness knobs"),
    (r"\[Scale\s*=\s*[\d.]+\]", "font scale"),
    (r"\{HTML\}\{[0-9A-Fa-f]+\}", "colour definition"),
    (r"[\d.]+\\(line|text|column)width", "graphics width"),
    (r"\\(label|ref|eqref|cite|input|include)\{[^}]*\}", "cross-reference key"),
    (r"\\includegraphics(\[[^\]]*\])?\{[^}]*\}", "graphics path"),
    (r"\\figifexists\{[^}]*\}\{[^}]*\}", "graphics path"),
    (r"\\begin\{[^}]*\}(\[[^\]]*\])?|\\end\{[^}]*\}", "environment name"),
    (r"(?<!\\)%.*$", "TeX comment, but not an escaped per-cent sign"),
    (r"\\newcommand\{[^}]*\}(\[\d+\])?", "macro definition and its arity"),
    (r"\\newenvironment\{[^}]*\}(\[\d+\])?", "macro definition and its arity"),
    (r"#\d", "macro argument"),
    (r"\\(setmainfont|setsansfont|setmonofont|usepackage)\{[^}]*\}", "font and package setup"),
]

ALLOW: list[tuple[str, str, str]] = [
]


MEAS = re.compile(r"\\meas\{[^}]*\}\{([^}]*)\}")


def strip_typesetting(text: str) -> str:
    """Unwrap provenance annotations to the value they print, then drop the plumbing.

    A source string carries digits of its own -- b1_compute-314, b3_runtime-v310 -- and those
    are not claims the two languages have to agree on.
    """
    text = MEAS.sub(lambda m: m.group(1), text)
    for pattern, _why in TYPESETTING:
        text = re.sub(pattern, " ", text, flags=re.M)
    return text


def values(text: str) -> set[str]:
    found: set[str] = set()
    for match in NUMBER.finditer(text):
        try:
            found.add(f"{float(match.group(1).replace(',', '.')):g}")
        except ValueError:
            continue
    return found


def blocks_in(path: str) -> dict[str, set[str]]:
    """Numbers per section, keyed by the \\label that opens it.

    Sectioning is found in the raw source and the typesetting stripped per block: the strip
    removes \\label itself, so looking for section marks after it finds none.
    """
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    marks = list(SECTION.finditer(raw))
    if not marks:
        return {"": values(strip_typesetting(raw))}
    out = {"": values(strip_typesetting(raw[: marks[0].start()]))}
    for current, following in zip(marks, [*marks[1:], None], strict=True):
        end = following.start() if following else len(raw)
        out[current.group(1)] = values(strip_typesetting(raw[current.end(): end]))
    return out


def allowed(section: str, value: str) -> str | None:
    for sec, val, why in ALLOW:
        if sec == section and val == value:
            return why
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-allowed", action="store_true",
                        help="list the asymmetries the allowlist silences")
    args = parser.parse_args()

    live: list[tuple[str, str, str]] = []
    silenced: list[tuple[str, str, str]] = []

    for section, en_rel, ru_rel in PAIRS:
        en_path, ru_path = os.path.join(PAPER, en_rel), os.path.join(PAPER, ru_rel)
        if not (os.path.exists(en_path) and os.path.exists(ru_path)):
            print(f"  [{section}] missing file, skipped")
            continue
        en_blocks, ru_blocks = blocks_in(en_path), blocks_in(ru_path)
        only_en = set(en_blocks) - set(ru_blocks)
        only_ru = set(ru_blocks) - set(en_blocks)
        for label in sorted(only_en | only_ru):
            side = "EN" if label in only_en else "RU"
            live.append((section, side, f"section {label} exists only in {side}"))
        for label in sorted(set(en_blocks) & set(ru_blocks)):
            where = section if not label else f"{section} / {label}"
            en, ru = en_blocks[label], ru_blocks[label]
            for lang, extra in (("EN", en - ru), ("RU", ru - en)):
                for value in extra:
                    why = allowed(where, value)
                    if why:
                        silenced.append((where, value, why))
                    else:
                        live.append((where, lang, value))

    if live:
        print("PARITY BREAKS: numbers present in one language and not the other\n")
        for section, lang, value in sorted(live):
            print(f"  [{section}]  only in {lang}: {value}")
        print("\nEach is either a real divergence or a legitimate rephrasing. Decide, then fix")
        print("the text or add the value to ALLOW in this file with the reason.")
    else:
        print("PARITY GATE: PASS -- every number appears in both languages")

    if silenced:
        print(f"\n({len(silenced)} asymmetr{'y' if len(silenced) == 1 else 'ies'} silenced by "
              f"the allowlist{'' if args.show_allowed else '; --show-allowed to list them'})")
        if args.show_allowed:
            for section, value, why in silenced:
                print(f"  [{section}] {value}: {why}")

    print(f"\ncompared {len(PAIRS)} EN/RU file pairs, section by section")
    return len(live)


if __name__ == "__main__":
    sys.exit(main())
