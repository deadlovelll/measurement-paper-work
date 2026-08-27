#!/usr/bin/env python3
"""One interpreter provenance, checked rather than asserted."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Any

PROBE = (
    "import sysconfig as s, sys, platform;"
    "print(sys.version.split()[0]);"
    "print(platform.python_compiler());"
    "print(s.get_config_var('CONFIG_ARGS') or '');"
    "print(s.get_config_var('Py_GIL_DISABLED') or 0);"
    "print(((s.get_config_var('PY_CORE_CFLAGS') or '') + ' ' "
    "       + (s.get_config_var('PY_CORE_LDFLAGS') or '')))"
)


def interpreters(root: str) -> list[tuple[str, str]]:
    """Every interpreter under root, as (tag, executable), in directory order."""
    out: list[tuple[str, str]] = []
    for tag in sorted(os.listdir(root)):
        bindir = os.path.join(root, tag, "bin")
        if not os.path.isdir(bindir):
            continue
        for cand in sorted(os.listdir(bindir)):
            if re.fullmatch(r"python3\.\d+t?", cand):
                exe = os.path.join(bindir, cand)
                if os.access(exe, os.X_OK):
                    out.append((tag, exe))
                break
    return out


def probe(exe: str) -> dict[str, Any] | None:
    r = subprocess.run([exe, "-c", PROBE], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None
    v, comp, args, gil, flags = (r.stdout.split("\n") + [""] * 5)[:5]
    return {"version": v.strip(), "compiler": comp.strip(), "args": args.strip(),
            "gil_disabled": gil.strip() == "1", "flags": flags.strip()}


def normalise(config_args: str) -> frozenset:
    """The configuration as a comparable set of tokens."""
    s = config_args.replace("'", " ").replace('"', " ")
    toks: list[str] = []
    for t in s.split():
        if t.startswith("--prefix="):
            t = "--prefix=<masked>"
        if t == "--disable-gil":
            continue
        toks.append(t)
    return frozenset(toks)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="install root containing one directory per interpreter")
    ap.add_argument("--expect-differences", action="store_true",
                    help="report the configuration of each build without requiring agreement "
                         "(for the build-configuration set, where differing is the point)")
    args = ap.parse_args()

    found = interpreters(args.root)
    if not found:
        print(f"no interpreters under {args.root}", file=sys.stderr)
        return 1

    rows: list[tuple[str, str, dict[str, Any]]] = []
    for tag, exe in found:
        info = probe(exe)
        if info is None:
            print(f"  {tag:24} FAILED TO RUN  {exe}")
            return 1
        rows.append((tag, exe, info))

    width = max(len(t) for t, _, _ in rows)
    print(f"{'build'.ljust(width)}  {'version':10} {'GIL':5} {'PGO':4} {'LTO':9} "
          f"{'arch':14} compiler")
    for tag, _, i in rows:
        f = i["flags"]
        pgo = "yes" if ("fprofile" in f or "profile-use" in f) else "no"
        lto = next((t for t in f.split() if "lto" in t), "none").replace("-flto=", "")
        arch = next((t for t in f.split() if t.startswith(("-march=", "-mcpu="))), "none")
        gil = "off" if i["gil_disabled"] else "on"
        print(f"{tag.ljust(width)}  {i['version']:10} {gil:5} {pgo:4} {lto:9} "
              f"{arch:14} {i['compiler']}")

    if args.expect_differences:
        sets = {tag: normalise(i["args"]) for tag, _, i in rows}
        base_tag = min(sets, key=lambda t: (len(sets[t]), t))
        base = sets[base_tag]
        print(f"\nconfigure lines relative to {base_tag} "
              f"(differences are the experiment here):")
        print(f"  {base_tag.ljust(width)}  {' '.join(sorted(base))}")
        for tag, _, _i in rows:
            if tag == base_tag:
                continue
            added = sorted(f"+{t}" for t in sets[tag] - base)
            removed = sorted(f"-{t}" for t in base - sets[tag])
            delta = " ".join(added + removed) or "(identical to the control)"
            print(f"  {tag.ljust(width)}  {delta}")
        return 0

    base_tag, _, base_info = rows[0]
    base = normalise(base_info["args"])
    bad: list[tuple[str, list[str]]] = []
    for tag, _, i in rows[1:]:
        diff = normalise(i["args"]) ^ base
        if diff:
            bad.append((tag, sorted(diff)))

    print()
    if bad:
        print(f"PROVENANCE GATE: FAIL -- {len(bad)} of {len(rows)} differ from {base_tag}")
        for tag, diff in bad:
            print(f"  {tag}: {' '.join(diff)}")
        return 1

    print(f"PROVENANCE GATE: PASS -- all {len(rows)} interpreters share one configure line")
    print("  " + " ".join(sorted(base)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
