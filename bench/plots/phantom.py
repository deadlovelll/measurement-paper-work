#!/usr/bin/env python3
"""Find traces of a document that does not exist."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PATTERNS: list[tuple[str, str, str]] = [
    ("thesis-named", r"\bthes[ie]s\b|\bтезис", "names the source document"),
    ("prior-work-of-ours", r"\b(our|the)\s+(earlier|previous|original|prior)\s+"
                           r"(work|paper|document|study|version|text)\b|"
                           r"\b(предыдущ\w+|исходн\w+|первоначальн\w+)\s+(работ\w+|документ\w+|"
                           r"текст\w+|версия)", "refers to a document the reader does not have"),
    ("the-map", r"\bthe map\b|\bmap entry\b|\brow of the map\b|\bкарт[аеуы]\s+(технолог|решен)",
     "the 'map' framing belonged to the earlier document"),

    ("claim-noun", r"\b(the|a|this|that|其)\s+claim\b|\bclaim'?s\b|\bclaimed\b|"
                   r"\bзаявленн\w+|\bутвержда(ется|лось|ют)\b|\bпосылка\s+утвержден",
     "treats an outside statement as the thing being judged"),
    ("verdict-verbs", r"\b(confirm|refut|disprov|corroborat|overturn|contradict)\w*\s+"
                      r"(the|that|this|his|her|their|its)\b|"
                      r"\b(подтвержда|опроверга|refut)\w*\s+(ся|ется|ются)?\s*(ли|"
                      r"утвержден|заявлен|тезис)", "delivers a verdict on an outside claim"),
    ("verdict-headings", r"^\s*\\(sub)*section\*?\{[^}]*\b(Confirmed|Refuted|Corrected|"
                         r"Подтверждено|Опровергнуто|Уточнено)\b",
     "section structured as a verdict"),
    ("what-this-adds", r"What this adds\b|Что это добавляет", "paragraph written as a delta"),

    ("attributed-number", r"\b(claimed|reported|quoted|stated|заявленн\w+|указанн\w+)\s*"
                          r"[^.]{0,24}?\b\d+(\.\d+)?\s*[x×]\b|"
                          r"\b\d+(\.\d+)?\s*[x×]\s*(claim|as claimed|as reported|по\s+утвержден)",
     "a speed-up attributed to an outside source"),
    ("order-of-magnitude-hedge", r"\bin order of magnitude but not exactly\b|"
                                 r"\bпо порядку величины,? но не точно\b",
     "the shape a phantom takes after a careless edit"),

    ("folklore", r"\bit is (widely )?(believed|assumed|thought|held)\b|"
                 r"\b(commonly|usually|often) (believed|assumed|claimed|cited)\b|"
                 r"\b(считается|принято считать|бытует мнение|общеизвестно),?\s*что",
     "asserts what people believe rather than what was measured"),
    ("literature-appeal", r"\b(the|in the) literature\b|\bas reported in\b|"
                          r"\bв литературе\b|\bсогласно (источник|публикац)",
     "appeals to an unnamed body of work"),
]

ALLOW: list[tuple[str, str]] = [
    (r"Ivankov", "the author's name"),
    (r"Иванков", "the author's name"),
    (r"significance (test |verdict )?for every claim that two configurations",
     "a claim made by this paper about its own configurations"),
    (r"claim that two configurations are the same",
     "a claim made by this paper about its own configurations"),
    (r"every claim (in|of) this paper", "this paper's own claims"),
    (r"reproduced from the (accompanying |)artifact", "our own artefact"),
    (r"каждое утверждение (этой |)работы", "this paper's own claims"),
    (r"ctypes releases the GIL", "a statement about a mechanism, not about anyone's opinion"),
    (r"a claim turns on", "our own claim, deciding which statistical treatment it needs"),
    (r"claims that turn on a", "our own claims"),
    (r"Equality claims: pyperf", "heading of our own significance-test table"),
    (r"control on the same binary confirms",
     "a control of ours confirming a mechanism, not a verdict on an outside claim"),
    (r"confirms that the lock rather than the build is responsible",
     "our own PYTHON_GIL=1 control deciding between two mechanisms of ours"),
]


def allowed(line: str) -> str | None:
    for pat, why in ALLOW:
        if re.search(pat, line, re.I):
            return why
    return None


def tex_files() -> list[str]:
    out: list[str] = []
    for sub in ("", "sections", "sections-ru", "tables", "tables-ru"):
        d = os.path.join(ROOT, "paper", sub)
        if not os.path.isdir(d):
            continue
        out.extend(os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".tex"))
    return out


def generator_files() -> list[str]:
    """The figure and table generators, because a phantom can be baked into a label.

    The check_*.py gates are skipped: nothing they print reaches the paper, and their subject
    is the paper's own statements, so their prose trips these patterns by construction.
    """
    d = os.path.join(ROOT, "bench", "plots")
    return [os.path.join(d, f) for f in sorted(os.listdir(d))
            if f.endswith(".py") and not f.startswith("check_") and f != "phantom.py"]


def pdf_text(path: str) -> str | None:
    """Extracted text of a built PDF, or None if it cannot be read."""
    try:
        r = subprocess.run(["pdftotext", "-q", path, "-"],
                           capture_output=True, text=True, timeout=120)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def scan_text(name: str, text: str, is_pdf: bool) -> list[tuple[str, str, str, str]]:
    """Return (source, pattern, matched-line, allow-reason-or-empty)."""
    hits: list[tuple[str, str, str, str]] = []
    lines = text.split("\n")
    for i, raw in enumerate(lines, 1):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if is_pdf and i < len(lines):
            line = re.sub(r"(\w)-$", r"\1", line)
        for pname, pat, _why in PATTERNS:
            if re.search(pat, line, re.I | re.M):
                hits.append((f"{name}:{i}", pname, line[:150], allowed(line) or ""))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="specific files; default is the whole paper")
    ap.add_argument("--sources-only", action="store_true", help="skip the built PDFs")
    ap.add_argument("--show-allowed", action="store_true", help="also list silenced hits")
    args = ap.parse_args()

    targets: list[tuple[str, str, bool]] = []
    if args.files:
        for f in args.files:
            with open(f, encoding="utf-8", errors="replace") as fh:
                targets.append((os.path.relpath(f, ROOT), fh.read(), False))
    else:
        for f in tex_files() + generator_files():
            with open(f, encoding="utf-8", errors="replace") as fh:
                targets.append((os.path.relpath(f, ROOT), fh.read(), False))
        if not args.sources_only:
            for pdf in ("paper/paper.pdf", "paper/paper-ru.pdf"):
                p = os.path.join(ROOT, pdf)
                if os.path.exists(p):
                    t = pdf_text(p)
                    if t is None:
                        print(f"  ! could not extract text from {pdf} "
                              f"(is pdftotext installed?)", file=sys.stderr)
                    else:
                        targets.append((pdf, t, True))

    live: list[tuple[str, str, str, str]] = []
    silenced: list[tuple[str, str, str, str]] = []
    for name, text, is_pdf in targets:
        for hit in scan_text(name, text, is_pdf):
            (silenced if hit[3] else live).append(hit)

    if live:
        print(f"PHANTOMS: {len(live)} hit(s) needing a decision\n")
        by_pat: dict[str, list] = {}
        for where, pname, line, _ in live:
            by_pat.setdefault(pname, []).append((where, line))
        why = {p: w for p, _r, w in PATTERNS}
        for pname, items in sorted(by_pat.items()):
            print(f"  [{pname}] {why[pname]}")
            for where, line in items:
                print(f"      {where}")
                print(f"        {line}")
            print()
    else:
        print("PHANTOMS: none")

    if silenced:
        print(f"({len(silenced)} hit(s) silenced by the allowlist"
              f"{'' if args.show_allowed else '; --show-allowed to list them'})")
        if args.show_allowed:
            for where, pname, line, why in silenced:
                print(f"  {where}  [{pname}]  allowed: {why}")
                print(f"    {line}")

    print(f"\nscanned {len(targets)} text sources "
          f"({sum(1 for _, _, p in targets if p)} of them built PDFs)")
    return len(live)


if __name__ == "__main__":
    sys.exit(main())
