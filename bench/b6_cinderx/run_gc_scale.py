#!/usr/bin/env python
"""What decides the cost of a collection: how many threads run it, or what it can see?"""

from __future__ import annotations

import gc
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

LIVE_OBJECTS = 800_000
GARBAGE_OBJECTS = 800_000

THREADS = (0, 6)

MODES = ("state_visible", "frozen", "immortal")


def make_cycles(n_obj: int) -> list[dict[str, Any]]:
    """n_obj objects in cyclic pairs, so only the collector can reclaim them."""
    out: list[dict[str, Any]] = []
    for _ in range(n_obj // 2):
        a: dict[str, Any] = {}
        b: dict[str, Any] = {"peer": a}
        a["peer"] = b
        out.append(a)
    return out


class Heap:
    """One process's heap in one composition, built once and kept for the whole benchmark."""

    def __init__(self, mode: str, cinderx: Any) -> None:
        self.state = make_cycles(LIVE_OBJECTS)
        if mode == "frozen":
            gc.freeze()
        elif mode == "immortal":
            cinderx.immortalize_heap()
        self.parallel_on = False

    def set_parallel(self, threads: int, cinderx: Any) -> None:
        """Enable once per process, not per collection."""
        if threads and not self.parallel_on:
            cinderx.enable_parallel_gc(2, threads)
            self.parallel_on = True

    def collect_once(self) -> int:
        """One unit of work's garbage, then the collection. Returns what it reclaimed."""
        make_cycles(GARBAGE_OBJECTS)
        gc.disable()
        found = gc.collect()
        gc.enable()
        return found


def main() -> None:
    suite = Suite("b6_gcscale", forward=())
    args = suite.parse()

    try:
        import cinderx  # ty: ignore[unresolved-import]

        cinderx.init()
    except ImportError:
        cinderx = None

    have_parallel = False
    settings: Any = "no cinderx on this interpreter"
    if cinderx is not None:
        try:
            cinderx.enable_parallel_gc(2, THREADS[-1])
            settings = cinderx.get_parallel_gc_settings()
            cinderx.disable_parallel_gc()
            have_parallel = True
        except Exception as exc:
            settings = repr(exc)[:200]
    suite.facts["parallel_gc_settings_when_on"] = settings
    suite.facts["live_objects"] = LIVE_OBJECTS
    suite.facts["garbage_objects"] = GARBAGE_OBJECTS

    modes = list(MODES)
    if cinderx is None:
        modes.remove("immortal")
        suite.unavailable(case="gc_collect", impl=f"{args.label}/immortal",
                          note="immortalize_heap() is CinderX's; not present on this interpreter")

    heaps: dict[str, Heap] = {}

    for mode in modes:
        for threads in THREADS if have_parallel else (0,):
            def time_gc(loops: int, mode: str = mode, threads: int = threads) -> float:
                heap = heaps.get(mode)
                if heap is None:
                    heap = heaps[mode] = Heap(mode, cinderx)
                heap.set_parallel(threads, cinderx)
                total = 0.0
                for _ in range(loops):
                    make_cycles(GARBAGE_OBJECTS)
                    gc.disable()
                    t0 = pyperf.perf_counter()
                    gc.collect()
                    total += pyperf.perf_counter() - t0
                    gc.enable()
                return total

            impl = f"{args.label}/{mode}" + (f"_par{threads}" if threads else "_serial")
            suite.bench_time(case="gc_collect", impl=impl, time_fn=time_gc,
                             params={"live": LIVE_OBJECTS, "garbage": GARBAGE_OBJECTS,
                                     "threads": threads},
                             note="gc.collect() only; the garbage is rebuilt untimed")

    if suite.is_master:
        for mode in modes:
            heap = Heap(mode, cinderx)
            found = heap.collect_once()
            expected = GARBAGE_OBJECTS
            suite.gate(case="gc_collect", impl=f"{args.label}/{mode}", got=float(found),
                       expected=float(expected), tol=0.02,
                       note="objects reclaimed by one collection")
            suite.facts[f"reclaimed_{mode}"] = found
            del heap

    suite.machine_probe()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
