#!/usr/bin/env python
"""Specialisation warm-up: what the k-th execution of a *fresh* code object costs."""

from __future__ import annotations

import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

CALLS = 24
HOT_SRC = ("def hot(a, b):\n    v0 = a + b\n"
           + "".join(f"    v{i + 1} = v{i} * a + (b >> 1) - {i}\n" for i in range(40))
           + "    return v40\n")


def main() -> None:
    suite = Suite("b3_spec")
    suite.parse()
    label = suite.label
    code_src = HOT_SRC

    for k in range(1, CALLS + 1):
        def time_kth(loops: int, k: int = k) -> float:
            compile_ = compile
            perf = pyperf.perf_counter
            total = 0.0
            for _ in range(loops):
                ns: dict[str, Any] = {}
                exec(compile_(code_src, "<hot>", "exec"), ns)
                f = ns["hot"]
                for _ in range(k - 1):
                    f(3, 4)
                t0 = perf()
                f(3, 4)
                total += perf() - t0
            return total

        suite.bench_time(case=f"call{k:02d}", impl=label, time_fn=time_kth,
                         params={"k": k, "body_ops": 41},
                         note=f"time of execution number {k} of a freshly compiled "
                              f"straight-line function")

    suite.facts = {"calls": CALLS, "source_lines": code_src.count("\n")}
    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
