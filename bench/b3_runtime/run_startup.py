#!/usr/bin/env python
"""Interpreter start-up: the cost that is paid before any of a program's code runs."""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

from mp_pyperf import Suite  # noqa: E402

STDLIB_IMPORTS = ("import json, re, argparse, subprocess, logging, "
                  "datetime, collections, dataclasses, typing")


def main() -> None:
    name = "b3_startup"
    if "--suite-name" in sys.argv:
        name = sys.argv[sys.argv.index("--suite-name") + 1]
    suite = Suite(name, forward=("suite-name",))
    suite.runner.argparser.add_argument("--suite-name", default=name, help="result file stem")
    suite.parse()
    label = suite.label
    exe = sys.executable
    suite.facts = {"executable": exe, "version": sys.version.split()[0]}

    suite.bench_command(case="startup_bare", impl=label, command=[exe, "-S", "-c", "pass"],
                        note="python -S -c pass: the runtime floor, site processing skipped")
    suite.bench_command(case="startup_site", impl=label, command=[exe, "-c", "pass"],
                        note="python -c pass as invoked in practice, site processing included")
    suite.bench_command(case="startup_stdlib", impl=label,
                        command=[exe, "-c", STDLIB_IMPORTS],
                        note=f"start-up plus nine common stdlib imports ({STDLIB_IMPORTS})")
    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
