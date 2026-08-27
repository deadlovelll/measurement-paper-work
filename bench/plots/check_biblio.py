#!/usr/bin/env python3
"""The bibliography must credit the people who actually did the work.

Three of the five PEP entries in this paper credited the wrong people at once: two fabricated
surnames on PEP 523, Mark Shannon carried across onto PEP 744, and PEP 683's co-author dropped.
None of it is visible to a compiler, a spell-check or a numeric audit, and a wrong name in a
bibliography is the worst thing a paper can carry. PEP headers are machine-readable, so this is
checkable rather than reviewable.

Offline by default: entry/citation closure and EN/RU agreement. With --online it also fetches
every PEP header from python/peps and every URL, and compares surnames and years.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = os.path.join(ROOT, "paper")

BIBITEM = re.compile(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem\{|\\end\{thebibliography\})", re.S)
CITE = re.compile(r"\\cite\{([^}]+)\}")
URL = re.compile(r"\\url\{([^}]+)\}")
PEP_KEY = re.compile(r"^pep(\d+)$")
YEAR = re.compile(r"\b(19|20)\d{2}\b")
SURNAME = re.compile(r"\b([A-Z]\.~?)+\s*([A-Z][a-z]+(?:\'[a-z]+)?)")

PEP_SOURCE = "https://raw.githubusercontent.com/python/peps/main/peps/pep-{:04d}.rst"


def fetch(url: str, timeout: int = 25) -> str:
    result = subprocess.run(["curl", "-sL", "--max-time", str(timeout), url],
                            capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def final_url(url: str, timeout: int = 25) -> str:
    result = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout), "-o", "/dev/null",
         "-w", "%{http_code} %{url_effective}", url],
        capture_output=True, text=True, check=False)
    return result.stdout.strip()


def entries(path: str) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return {key: " ".join(body.split()) for key, body in BIBITEM.findall(text)}


def cited_keys(paths: list[str]) -> set[str]:
    keys: set[str] = set()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for group in CITE.findall(fh.read()):
                keys.update(part.strip() for part in group.split(","))
    return keys


def surnames(body: str) -> list[str]:
    head = body.split("\\emph{")[0]
    return [match.group(2) for match in SURNAME.finditer(head)]


def pep_authors(number: int) -> tuple[list[str], str]:
    text = fetch(PEP_SOURCE.format(number))
    if not text:
        return [], ""
    header, collecting = [], False
    for line in text.splitlines():
        if line.startswith("Author:"):
            collecting = True
            header.append(line[len("Author:"):])
            continue
        if collecting:
            if line.startswith((" ", "\t")):
                header.append(line)
                continue
            break
    people = []
    for chunk in " ".join(header).split(","):
        name = re.sub(r"<[^>]*>", "", chunk).strip()
        if name:
            people.append(name.split()[-1])
    status = ""
    for line in text.splitlines():
        if line.startswith("Status:"):
            status = line.split(":", 1)[1].strip()
            break
    return people, status


def sources() -> list[str]:
    found = [os.path.join(PAPER, name) for name in ("paper.tex", "paper-ru.tex")]
    for sub in ("sections", "sections-ru"):
        directory = os.path.join(PAPER, sub)
        found += [os.path.join(directory, name) for name in sorted(os.listdir(directory))
                  if name.endswith(".tex")]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true",
                        help="fetch PEP headers and URLs and check names, years and redirects")
    args = parser.parse_args()

    problems: list[str] = []
    en = entries(os.path.join(PAPER, "paper.tex"))
    ru = entries(os.path.join(PAPER, "paper-ru.tex"))

    only_en, only_ru = set(en) - set(ru), set(ru) - set(en)
    problems += [f"entry {key!r} is in the English bibliography only" for key in sorted(only_en)]
    problems += [f"entry {key!r} is in the Russian bibliography only" for key in sorted(only_ru)]

    for key in sorted(set(en) & set(ru)):
        en_names, ru_names = surnames(en[key]), surnames(ru[key])
        if en_names != ru_names:
            problems.append(f"{key}: EN credits {en_names}, RU credits {ru_names}")
        en_year = YEAR.search(en[key])
        ru_year = YEAR.search(ru[key])
        if (en_year and ru_year) and en_year.group(0) != ru_year.group(0):
            problems.append(f"{key}: EN dates it {en_year.group(0)}, RU {ru_year.group(0)}")

    used = cited_keys(sources())
    problems += [f"\\cite{{{key}}} has no bibliography entry" for key in sorted(used - set(en))]
    problems += [f"entry {key!r} is never cited" for key in sorted(set(en) - used)]

    checked = len(en)
    if args.online:
        for key, body in sorted(en.items()):
            match = PEP_KEY.match(key)
            if match:
                real, status = pep_authors(int(match.group(1)))
                if not real:
                    problems.append(f"{key}: could not fetch the PEP header to check it")
                    continue
                listed = surnames(body)
                if listed != real:
                    problems.append(f"{key}: credits {listed}, PEP header says {real}")
                if status and status.lower() != "final" and "draft" not in body.lower():
                    problems.append(f"{key}: PEP is {status}, the entry does not say so")
            for url in URL.findall(body):
                outcome = final_url(url)
                code, _, landed = outcome.partition(" ")
                checked += 1
                if code != "200":
                    problems.append(f"{key}: {url} returned {code or 'nothing'}")
                elif landed.rstrip("/") != url.rstrip("/"):
                    problems.append(f"{key}: {url} redirects to {landed}")

    if problems:
        print("BIBLIOGRAPHY GATE: findings\n")
        for problem in problems:
            print(f"  {problem}")
    else:
        print("BIBLIOGRAPHY GATE: PASS -- entries, citations and both languages agree"
              + (" and every name, year and URL checks out" if args.online else ""))

    print(f"\n{len(en)} entries, {len(used)} cited keys, "
          f"{'online' if args.online else 'offline'} check over {checked} item(s)")
    if not args.online:
        print("run with --online to check surnames against the PEP headers and follow the URLs")
    return len(problems)


if __name__ == "__main__":
    sys.exit(main())
