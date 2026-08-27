#!/usr/bin/env python3
"""The versions the paper declares must be the ones the build scripts pin and the machine has.

Table~\\ref{tab:versions} is generated from the pins in bench/bootstrap.sh, bench/setup_env.sh
and bench/build_uniform.sh rather than typed, so it cannot fall behind them. This gate closes
the other half: it checks that what is actually installed matches those pins, so the table
cannot fall behind the machine either.

The failure this exists to prevent is not hypothetical. bootstrap.sh once pinned Codon 0.19.4
while 0.19.6 was on disk and in the results, and an unpinned NumPy sat at 2.4.4 under one
interpreter and 2.4.6 everywhere else -- differences no significance test can see, because they
move every implementation by a different amount.

Anything not installed is reported and not counted as a mismatch: a checkout without the stack
can still verify that the table agrees with the pins.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.expanduser("~")
PREFIX = os.environ.get("PREFIX", os.path.join(HOME, "mp-x86"))

PIN_FILES = ("bootstrap.sh", "setup_env.sh", "build_uniform.sh")
TABLE = os.path.join(ROOT, "paper", "tables", "t7_versions.tex")

PRINTED_KEYS = ("CLANG_VERSION", "LLVM19_VERSION", "RUST_VERSION", "CODON_VERSION",
                "PYPY_VERSION", "PYPERF_VERSION", "NUMPY_VERSION", "NUMBA_VERSION",
                "CYTHON_VERSION", "PYBIND11_VERSION", "THREADPOOLCTL_VERSION")


def pins() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in PIN_FILES:
        path = os.path.join(ROOT, "bench", name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for m in re.finditer(r'^(\w+)="\$\{\1:-([^}]*)\}"', fh.read(), re.M):
                # Only versions: the same files also pin directories, URLs and job counts.
                if m.group(1).endswith("_VERSION") or m.group(1) == "VERSIONS":
                    found.setdefault(m.group(1), m.group(2))
    return found


def run(*cmd: str) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (out.stdout or out.stderr or "").strip()


def first_version(text: str) -> str:
    m = re.search(r"\d+\.\d+(?:\.\d+)?", text)
    return m.group(0) if m else ""


def dist_version(python: str, package: str) -> str:
    if not os.path.exists(python):
        return ""
    return run(python, "-c",
               f"import importlib.metadata as m; print(m.version({package!r}))")


def codon_root() -> str:
    base = os.environ.get("CODON_DIR", os.path.join(PREFIX, "codon"))
    for candidate in (os.path.join(base, "codon-deploy-linux-x86_64"), base):
        if os.path.exists(os.path.join(candidate, "bin", "codon")):
            return candidate
    return ""


def installed(p: dict[str, str]) -> dict[str, str]:
    u313 = os.path.join(ROOT, "bench", "venvs", "u313", "bin", "python")
    u314 = os.path.join(ROOT, "bench", "venvs", "u314", "bin", "python")
    pypy = os.environ.get("PYPY", os.path.join(PREFIX, "pypy", "bin", "pypy3"))
    llvm = os.environ.get("LLVM19", os.path.join(HOME, ".local", "llvm19", "bin"))
    croot = codon_root()

    found = {
        "CLANG_VERSION": first_version(run("clang", "--version")),
        "RUST_VERSION": first_version(run("cargo", "--version")),
        "TECTONIC_VERSION": first_version(run("tectonic", "--version")),
        "LLVM19_VERSION": first_version(run(os.path.join(llvm, "clang"), "--version")),
        "CODON_VERSION": first_version(run(os.path.join(croot, "bin", "codon"), "--version"))
        if croot else "",
        "PYPY_VERSION": run(pypy, "-c",
                            "import sys; print('.'.join(map(str, sys.pypy_version_info[:3])))"),
    }
    for key, package in (("PYPERF_VERSION", "pyperf"), ("NUMPY_VERSION", "numpy"),
                         ("NUMBA_VERSION", "numba"), ("CYTHON_VERSION", "cython"),
                         ("PYBIND11_VERSION", "pybind11"),
                         ("THREADPOOLCTL_VERSION", "threadpoolctl")):
        found[key] = dist_version(u314, package)
    found["MATPLOTLIB_VERSION"] = dist_version(u313, "matplotlib")

    if "VERSIONS" in p:
        seen = []
        for spec in p["VERSIONS"].split():
            exe = os.path.join(PREFIX, "uniform", "v" + spec.replace(".", "")[:3]
                               + ("t" if spec.endswith("t") else ""),
                               "bin", "python3." + spec.split(".")[1]
                               + ("t" if spec.endswith("t") else ""))
            # A free-threaded build reports 3.14.6, not 3.14.6t: the suffix names the
            # configuration, so read that from the build rather than from the version string.
            probe = ("import sys, sysconfig; "
                     "print(sys.version.split()[0] + "
                     "('t' if sysconfig.get_config_var('Py_GIL_DISABLED') else ''))")
            got = run(exe, "-c", probe) if os.path.exists(exe) else ""
            seen.append(got or "?")
        found["VERSIONS"] = " ".join(seen) if any(v != "?" for v in seen) else ""
    return found


def table_versions() -> list[str]:
    if not os.path.exists(TABLE):
        return []
    with open(TABLE, encoding="utf-8") as fh:
        return re.findall(r"\d+\.\d+(?:\.\d+)?t?", fh.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="print only failures")
    args = parser.parse_args()

    p = pins()
    if not p:
        print("no pins found: bench/bootstrap.sh and friends are missing")
        return 2
    have = installed(p)

    mismatched: list[str] = []
    unchecked: list[str] = []
    for key in sorted(p):
        want, got = p[key], have.get(key, "")
        if not got:
            unchecked.append(key)
            continue
        if got != want:
            mismatched.append(f"  [drift] {key}: pinned {want}, installed {got}")
        elif not args.quiet:
            print(f"  {key:24} {want}")

    missing_from_table: list[str] = []
    printed = table_versions()
    if printed:
        missing_from_table.extend(
            f"  [table] {key} is pinned at {p[key]}, which the table does not print"
            for key in PRINTED_KEYS if key in p and p[key] not in printed)
    else:
        missing_from_table.append("  [table] paper/tables/t7_versions.tex does not exist")

    for line in mismatched + missing_from_table:
        print(line)
    if unchecked and not args.quiet:
        print(f"\n  not installed here, so not checked: {', '.join(unchecked)}")

    print()
    problems = len(mismatched) + len(missing_from_table)
    if problems:
        print(f"VERSION GATE: {len(mismatched)} drifted, "
              f"{len(missing_from_table)} table problem(s)")
    else:
        print("VERSION GATE: PASS -- the declared versions are the pinned ones "
              "and the installed ones")
    return problems


if __name__ == "__main__":
    sys.exit(main())
