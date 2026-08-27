#!/usr/bin/env python
"""What the CPython runtime itself does for object-heavy code, 3.10 -> 3.14."""

from __future__ import annotations

import gc
import os
import platform
import resource
import sys
from collections.abc import Callable
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

N_OBJ = 20_000
LOOP = 100_000


class Plain:
    """Fixture for the object-operation benchmarks."""

    x: int
    y: int
    z: int | Plain

    def __init__(self, x: int, y: int, z: int | Plain) -> None:
        self.x = x
        self.y = y
        self.z = z

    def total(self) -> int:
        return self.x + self.y + self.z  # ty: ignore[unsupported-operator]


class Slotted:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: int, y: int, z: int) -> None:
        self.x = x
        self.y = y
        self.z = z

    def total(self) -> int:
        return self.x + self.y + self.z


def plain_func(a: int, b: int) -> int:
    return a + b


def object_cases() -> list[tuple[str, Callable[[], object], int, str]]:
    def create_plain() -> list[Plain]:
        return [Plain(i, i + 1, i + 2) for i in range(N_OBJ)]

    def create_slots() -> list[Slotted]:
        return [Slotted(i, i + 1, i + 2) for i in range(N_OBJ)]

    def create_dict() -> list[dict[str, int]]:
        return [{"x": i, "y": i + 1, "z": i + 2} for i in range(N_OBJ)]

    def create_tuple() -> list[tuple[int, int, int]]:
        return [(i, i + 1, i + 2) for i in range(N_OBJ)]

    objs = create_plain()
    sobjs = create_slots()

    def attr_get() -> int:
        s = 0
        for o in objs:
            s += o.x + o.y + o.z  # ty: ignore[unsupported-operator]
        return s

    def attr_get_slots() -> int:
        s = 0
        for o in sobjs:
            s += o.x + o.y + o.z
        return s

    def attr_set() -> None:
        for o in objs:
            o.x = 1

    def method_call() -> int:
        s = 0
        for o in objs:
            s += o.total()
        return s

    return [
        ("create_plain_obj", create_plain, N_OBJ, "instances per operation"),
        ("create_slots_obj", create_slots, N_OBJ, "instances per operation"),
        ("create_dict", create_dict, N_OBJ, "dict literals per operation"),
        ("create_tuple", create_tuple, N_OBJ, "tuples per operation"),
        ("attr_get", attr_get, N_OBJ, "objects traversed per operation"),
        ("attr_get_slots", attr_get_slots, N_OBJ, "objects traversed per operation"),
        ("attr_set", attr_set, N_OBJ, "attribute stores per operation"),
        ("method_call", method_call, N_OBJ, "bound method calls per operation"),
    ]


def interp_cases() -> list[tuple[str, Callable[[], object], int, str]]:
    def int_arith() -> int:
        s = 0
        for i in range(LOOP):
            s += i * 3 - (i >> 1)
        return s

    def float_arith() -> float:
        s = 0.0
        for i in range(LOOP):
            s += i * 0.5 - 1.25
        return s

    def list_append() -> int:
        out: list[int] = []
        for i in range(LOOP // 2):
            out.append(i)
        return len(out)

    def dict_setitem() -> int:
        d: dict[int, int] = {}
        for i in range(LOOP // 2):
            d[i & 1023] = i
        return len(d)

    def str_format_join() -> int:
        parts: list[str] = []
        for i in range(LOOP // 10):
            parts.append("k%d" % i)
        return len("".join(parts))

    def func_call() -> int:
        s = 0
        for i in range(LOOP):
            s = plain_func(s, i)
        return s

    def exception_roundtrip() -> int:
        n = 0
        for _ in range(LOOP // 10):
            try:
                raise ValueError
            except ValueError:
                n += 1
        return n

    return [
        ("int_arith", int_arith, LOOP, "iterations per operation"),
        ("float_arith", float_arith, LOOP, "iterations per operation"),
        ("list_append", list_append, LOOP // 2, "appends per operation"),
        ("dict_setitem", dict_setitem, LOOP // 2, "stores per operation"),
        ("str_format_join", str_format_join, LOOP // 10, "formats per operation"),
        ("func_call", func_call, LOOP, "calls per operation"),
        ("exception_roundtrip", exception_roundtrip, LOOP // 10, "raises per operation"),
    ]


def runtime_facts() -> dict[str, Any]:
    """Structural properties of the runtime. Not timings, and not presented as such."""
    getref = getattr(sys, "getrefcount", None)
    facts: dict[str, Any] = {
        "version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "refcount_none": getref(None) if getref else None,
        "refcount_true": getref(True) if getref else None,
        "refcount_small_int": getref(1) if getref else None,
        "refcount_empty_str": getref("") if getref else None,
        "immortal_singletons": (getref(None) > 2**30) if getref else None,
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
    }
    blocks = getattr(sys, "getallocatedblocks", None)
    if blocks:
        gc.collect()
        base = blocks()
        keep = [Plain(i, i + 1, i + 2) for i in range(N_OBJ)]
        facts["blocks_per_plain_obj"] = (blocks() - base) / N_OBJ
        del keep
        gc.collect()
        base = blocks()
        keep2 = [Slotted(i, i + 1, i + 2) for i in range(N_OBJ)]
        facts["blocks_per_slots_obj"] = (blocks() - base) / N_OBJ
        del keep2
    else:
        facts["blocks_per_plain_obj"] = facts["blocks_per_slots_obj"] = None
    gc.collect()
    div = 1024 if sys.platform != "darwin" else 1024 * 1024
    facts["maxrss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / div, 1)
    return facts


def main() -> None:
    name = "b3_runtime"
    if "--suite-name" in sys.argv:
        name = sys.argv[sys.argv.index("--suite-name") + 1]
    suite = Suite(name, forward=("suite-name",))
    suite.runner.argparser.add_argument("--suite-name", default=name,
                                        help="result file stem")
    suite.parse()
    label = suite.label

    for name, fn, count, unit in object_cases() + interp_cases():
        suite.bench(case=name, impl=label, fn=fn, params={"count": count},
                    note=f"{count} {unit}")

    holder: list[Plain] = []

    def make_cycles() -> None:
        holder.clear()
        junk: list[Plain] = []
        for _ in range(50_000):
            a = Plain(1, 2, 3)
            b = Plain(4, 5, 6)
            a.z = b
            b.z = a
            junk.append(a)
        junk.clear()

    def time_gc(loops: int) -> float:
        total = 0.0
        for _ in range(loops):
            make_cycles()
            t0 = pyperf.perf_counter()
            gc.collect()
            total += pyperf.perf_counter() - t0
        return total

    suite.bench_time(case="gc_collect_100k_cycles", impl=label, time_fn=time_gc,
                     params={"objects": 100_000},
                     note="gc.collect() over 100k objects held in reference cycles; "
                          "the graph is rebuilt untimed before each collection")

    if suite.is_master:
        suite.facts = runtime_facts()
        for k, v in suite.facts.items():
            print(f"  [fact] {k:<26} {v}")
    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
