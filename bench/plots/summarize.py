#!/usr/bin/env python
"""Print a compact digest of every result file — the numbers quoted in the paper."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyperf_load import Record
from style import (
    B3_CASES,
    by,
    compare,
    facts_of,
    geomean,
    is_pypy,
    load,
    med,
    ok,
    pick,
    stats_of,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPUTE = ["arraysum", "mandelbrot", "matmul"]
BRANCHY = ["tokenize", "binarytrees", "bfs"]
VERSIONS = ["v310", "v311", "v312", "v313", "v314", "v314t"]


def tag_of(r: Record) -> str:
    """The configuration label, which pyperf carries in every record."""
    return r.get("label") or ""


def only(recs: Iterable[Record], tag: str) -> list[Record]:
    return [r for r in recs if tag_of(r) == tag]


def hdr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def rq1() -> None:
    hdr("RQ1 compute-bound kernels")
    allr = ok(load("b1_compute-"))
    for tag in ["311", "312", "313", "314", "314t"]:
        recs = only(allr, tag)
        if not recs:
            continue
        print(f"\n-- CPython {tag} --")
        for kern in COMPUTE:
            base = pick(recs, kern, "cpython_loop")
            if not base:
                continue
            line = [f"  {kern:<11} py={med(base) * 1e3:9.3f}ms"]
            for impl in ("cpython_builtin_sum", "numpy", "cython", "numba", "numba_fastmath",
                         "c_ctypes", "c_pybind11", "rust_ctypes"):
                r = pick(recs, kern, impl)
                if r:
                    line.append(f"{impl}={med(base) / med(r):.1f}x")
            print("  ".join(line))
    recs = only(allr, "314")
    print("\n-- numba compile latency (314) --")
    for kern in COMPUTE:
        for impl in ("numba", "numba_fastmath"):
            r = pick(recs, kern, impl)
            c = facts_of(load("b1_breakeven-")).get("numba_compile_s")
            if c:
                py = pick(recs, kern, "cpython_loop")
                be = c / (med(py) - med(r)) if py and med(py) > med(r) else float("inf")
                print(f"  {kern:<11} {impl:<15} compile={c * 1e3:8.1f}ms  "
                      f"break-even={be:,.0f} calls")
    print("\n-- call overhead (314) --")
    for r in sorted(by(recs, case="call_overhead"), key=med):
        print(f"  {r['impl']:<18} {med(r) * 1e9:8.1f} ns")
    print("\n-- MAD distribution --")
    mads = sorted(stats_of(r)["mad_rel"] for r in allr)
    print(f"  n={len(mads)}  median={mads[len(mads) // 2] * 100:.2f}%  "
          f"p90={mads[int(len(mads) * 0.9)] * 100:.2f}%  max={mads[-1] * 100:.2f}%")


def rq1b() -> None:
    hdr("RQ1b compiler flags: which of them change the program at all")
    recs = ok(load("b1_flags-"))

    groups: dict[str, list[list[str]]] = {}
    try:
        with open(os.path.join(ROOT, "results", "codegen_identity.json")) as fh:
            ident = json.load(fh)
        print(f"  compiler    : {ident.get('compiler', '?')}")
        print(f"  architecture: {ident.get('arch', '?')}   "
              f"tuning flag: {ident.get('native_flag', '?')}")
        for kern, vs in ident.get("kernels", {}).items():
            g: dict[str, list[str]] = {}
            for v, info in vs.items():
                g.setdefault(info["hash"], []).append(v)
            groups[kern.replace("c_", "", 1)] = list(g.values())
    except Exception as exc:
        print(f"  (no codegen identity map: {exc})")

    for kern in COMPUTE:
        base = pick(recs, kern, "O2")
        if not base:
            continue
        print(f"\n  {kern} -- baseline clang -O2 = {med(base) * 1e3:.4f} ms")
        same = {v: i for i, members in enumerate(groups.get(kern, [])) for v in members}
        for impl in ("O0", "O2", "O3", "O3native", "O3native_novec", "O3native_ffast",
                     "numba_plain", "numba_fastmath"):
            r = pick(recs, kern, impl)
            if not r:
                continue
            tag = ""
            if impl in same:
                peers = [v for v in groups[kern][same[impl]] if v != impl]
                if peers:
                    tag = f"   same machine code as {', '.join(peers)}"
            print(f"    {impl:<18} {med(r) * 1e3:9.4f} ms  {med(base) / med(r):6.2f}x{tag}")

    ladder = [(n, pick(recs, "arraysum", f"accum_acc{n}")) for n in (1, 2, 4, 8)]
    ladder = [(n, r) for n, r in ladder if r]
    if ladder:
        one = med(ladder[0][1])
        print("\n  accumulator ladder on arraysum (clang -O2, no fast-math anywhere)")
        for n, r in ladder:
            print(f"    {n} accumulator{'s' if n > 1 else ' ':<2}     "
                  f"{med(r) * 1e3:9.4f} ms  {one / med(r):6.2f}x vs 1 accumulator")
        ffast = pick(recs, "arraysum", "O3native_ffast")
        if ffast:
            best = min(med(r) for _, r in ladder)
            verdict = ("the chain explains it" if abs(med(ffast) / best - 1) < 0.15
                       else "not fully explained by the chain")
            print(f"    -ffast-math          {med(ffast) * 1e3:9.4f} ms  "
                  f"{med(ffast) / best:6.2f}x of the best ladder step ({verdict})")


def rq2() -> None:
    hdr("RQ2 branchy / allocating kernels")
    allr = load("b2_branchy-")
    for tag in ["313", "314"]:
        recs = only(allr, tag)
        if not recs:
            continue
        print(f"\n-- CPython {tag} --")
        for kern in BRANCHY:
            base = pick(ok(recs), kern, "cpython_loop")
            if not base:
                continue
            print(f"  {kern:<12} py={med(base) * 1e3:9.3f}ms")
            for impl in ("cython", "numba", "c_ctypes", "rust_ctypes"):
                hits = by(recs, kern, impl)
                if not hits:
                    continue
                r = hits[0]
                if r.get("status") == "ok":
                    print(f"    {impl:<14} {med(r) * 1e3:9.4f} ms  {med(base) / med(r):7.1f}x")
                else:
                    print(f"    {impl:<14} {r['status']}: {r.get('note', '')[:70]}")
    hdr("RQ2 geometric means (314)")
    c_recs, b_recs = only(ok(load("b1_compute-")), "314"), only(ok(load("b2_branchy-")), "314")
    for impl in ("cython", "numba", "c_ctypes", "rust_ctypes"):
        cb = [med(pick(c_recs, k, "cpython_loop")) / med(pick(c_recs, k, impl))
              for k in COMPUTE if pick(c_recs, k, impl)]
        bb = [med(pick(b_recs, k, "cpython_loop")) / med(pick(b_recs, k, impl))
              for k in BRANCHY if pick(b_recs, k, impl)]
        print(f"  {impl:<14} compute={geomean(cb):7.1f}x ({len(cb)})   "
              f"branchy={geomean(bb):7.1f}x ({len(bb)})")


def rq3() -> None:
    hdr("RQ3 runtime sweep 3.10 -> 3.14")
    recs = load("b3_runtime-")
    cases = sorted({r["case"] for r in ok(recs)})
    print(f"{'case':<26}" + "".join(f"{v:>8}" for v in VERSIONS))
    for case in cases:
        base = pick(ok(recs), case, "v310")
        if not base:
            continue
        row = f"{case:<26}"
        for v in VERSIONS:
            r = pick(ok(recs), case, v)
            row += f"{med(base) / med(r):>8.2f}" if r else f"{'--':>8}"
        print(row)
    print("\n-- specialisation warm-up: first execution vs steady state --")
    spec = ok(load("b3_spec-"))
    for v in VERSIONS:
        pts = sorted((x["params"].get("k", 0), med(x)) for x in spec if x["impl"] == v)
        if not pts:
            continue
        first = pts[0][1]
        tail = [t for k, t in pts if k > len(pts) // 2]
        steady = sum(tail) / len(tail) if tail else first
        print(f"  {v:<6} first={first * 1e6:7.3f}us  steady={steady * 1e6:7.3f}us  "
              f"ratio={first / steady:.2f}  (k=1..{pts[-1][0]})")
    print("\n-- runtime facts --")
    for v in VERSIONS:
        f = pick([x for x in recs if x["case"] == "runtime_facts"], "runtime_facts", v)
        if f:
            e = f["extra"]
            print(f"  {v:<6} refcount(None)={e['refcount_none']:<12} "
                  f"immortal={e['immortal_singletons']}"
                  f"  blocks/obj dict={e['blocks_per_plain_obj']:.2f} "
                  f"slots={e['blocks_per_slots_obj']:.2f}"
                  f"  rss={e['maxrss_mb']}MB")
    s = ok(load("b3_startup"))
    if s:
        print("\n-- startup (ms, whole process: pyperf bench_command) --")
        for v in VERSIONS:
            for case in ("startup_bare", "startup_site", "startup_stdlib"):
                r = pick(s, case, v)
                if r:
                    print(f"  {v:<6} {case:<22} {med(r) * 1e3:6.1f}")


def rq4() -> None:
    hdr("RQ4 Cinder fork / CinderX")
    allrecs = load("b6_cinderx-")
    recs = ok(allrecs)
    kernels = COMPUTE + BRANCHY + ["call_depth_200", "traceback_depth_50",
                                   "frame_walk_depth_100"]
    print(f"{'case':<22}{'stock ms':>10}{'fork':>8}{'cinderx':>9}{'jit':>8}")
    for k in kernels:
        b = pick(recs, k, "stock")
        if not b:
            continue
        row = f"{k:<22}{med(b) * 1e3:10.3f}"
        for cfg in ("fork", "fork_cinderx", "fork_jit"):
            r = pick(recs, k, cfg)
            row += f"{med(r) / med(b):>8.2f}" if r else f"{'--':>8}"
        print(row)
    print("\n-- lazy imports / parallel gc --")
    for case in ("import_200_modules_eager", "import_200_modules_lazy",
                 "gc_collect_200k_cycles"):
        for r in by(recs, case=case):
            print(f"  {case:<28} {r['impl']:<32} {med(r) * 1e3:9.3f} ms  "
                  f"{facts_of(allrecs, r['impl']).get('lazy_imports', {})}")
    print("\n-- parallel gc, by graph size (b6_gcscale) --")
    grecs = ok(load("b6_gcscale-"))
    sizes = sorted({int(r["case"].rsplit("_", 1)[1]) for r in grecs
                    if r["case"].startswith("gc_collect_")})
    for cfg in ("fork_cinderx", "fork_cinderx_adaptive"):
        for n in sizes:
            off = pick(grecs, f"gc_collect_{n}", f"{cfg}/parallel_gc_off")
            on = pick(grecs, f"gc_collect_{n}", f"{cfg}/parallel_gc_on")
            if off and on:
                v = compare(off, on)
                print(f"  {cfg:<24} {n:>8}  serial {med(off) * 1e3:8.2f} ms  "
                      f"parallel {med(on) * 1e3:8.2f} ms  {med(on) / med(off):5.3f}x  "
                      f"{'significant' if v.get('significant') else 'not resolved'}")

    print("\n-- JIT compile latency (jit_force_compile, one benchmark per function) --")
    jit_c = sorted(by(recs, case="jit_force_compile"), key=med)
    for r in jit_c:
        print(f"  {r['impl']:<34} {med(r) * 1e3:8.2f} ms")
    kernels_only = [r for r in jit_c if not r["impl"].rsplit("/", 1)[-1].startswith("_")]
    if kernels_only:
        print(f"  range over {len(kernels_only)} kernel functions: "
              f"{med(kernels_only[0]) * 1e3:.1f}--{med(kernels_only[-1]) * 1e3:.1f} ms")
    print("\n-- Static Python --")
    static_all = load("b6_static-")
    for r in ok(static_all):
        e = facts_of(static_all, r["label"])
        print(f"  {r['impl']:<34} {med(r) * 1e3:9.3f} ms  prims={e.get('primitive_ops')}"
              f"/{e.get('total_ops')} jit={e.get('is_jit_compiled')} "
              f"compile={(e.get('jit_compile_s') or 0) * 1e3:.1f}ms")


def rq5() -> None:
    hdr("RQ5 thread scaling")
    recs = ok(load("b4_threads-"))
    for case in ("py_arith", "py_branchy", "c_ffi_uniform", "c_ffi_mandelbrot"):
        print(f"\n  {case}")
        for cfg in ("gil", "ft_gil", "ft"):
            base = pick(recs, case, f"{cfg}/T1")
            ctl = pick(recs, case, f"{cfg}/T1_control")
            if not base:
                continue
            row = f"    {cfg:<8} T1={med(base) * 1e3:8.2f}ms  "
            ref = min(med(base), med(ctl)) if ctl else med(base)
            for t in (2, 3, 4, 6, 8):
                r = pick(recs, case, f"{cfg}/T{t}")
                row += f"T{t}={ref / med(r):5.2f}x " if r else ""
            print(row)
        p = pick(recs, case, "gil/procs8")
        if p:
            b = pick(recs, case, "gil/T1")
            print(f"    procs8 (gil)  {med(b) / med(p):.2f}x vs 1 thread")
    print("\n-- free-threading tax (single thread, relative to the GIL build) --")
    for case in ("single_thread_arith", "single_thread_branchy"):
        b = pick(recs, case, "gil")
        if not b:
            continue
        row = f"  {case:<24}"
        for cfg in ("gil", "ft_gil", "ft"):
            r = pick(recs, case, cfg)
            row += f" {cfg}={med(r) / med(b):.2f}x" if r else ""
        print(row)


def rq6b() -> None:
    hdr("RQ6b CPython experimental JIT (tier 2) vs identical non-JIT build")
    recs = ok(load("b5_buildcfg-"))
    if not recs:
        print("  no data")
        return
    cases = sorted({r["case"] for r in recs})
    ratios: list[float] = []
    print(f"{'case':<28}{'plain ms':>10}{'jit ms':>10}{'speedup':>10}")
    for case in cases:
        b, j = pick(recs, case, "plain"), pick(recs, case, "jit")
        if not (b and j):
            continue
        sp = med(b) / med(j)
        ratios.append(sp)
        print(f"{case:<28}{med(b) * 1e3:10.4f}{med(j) * 1e3:10.4f}{sp:10.3f}")
    if ratios:
        print(f"{'GEOMEAN':<28}{'':>10}{'':>10}{geomean(ratios):10.3f}")


def rq8() -> None:
    hdr("RQ8 PyPy vs CPython")
    recs = ok(load("b3_runtime-"))
    if recs:
        cases = sorted({r["case"] for r in recs})
        ratios: list[float] = []
        print(f"{'case':<28}{'cpy314 ms':>12}{'pypy ms':>10}{'speedup':>10}")
        for case in cases:
            b, j = pick(recs, case, "314"), pick(recs, case, "pypy311")
            if not (b and j):
                continue
            sp = med(b) / med(j)
            ratios.append(sp)
            print(f"{case:<28}{med(b) * 1e3:12.4f}{med(j) * 1e3:10.4f}{sp:10.2f}")
        if ratios:
            print(f"{'GEOMEAN':<28}{'':>12}{'':>10}{geomean(ratios):10.2f}")
    print("\n-- kernels on PyPy (b1/b2) --")
    for prefix, kerns in (("b1_compute-", COMPUTE), ("b2_branchy-", BRANCHY)):
        allr = load(prefix)
        pypy = [r for r in allr if is_pypy(r)]
        cpy = only(ok(allr), "314")
        for k in kerns:
            p_ = pick(ok(pypy), k, "cpython_loop")
            c_ = pick(cpy, k, "cpython_loop")
            if p_ and c_:
                print(f"  {k:<12} CPython {med(c_) * 1e3:9.3f} ms   PyPy {med(p_) * 1e3:9.3f} ms"
                      f"   {med(c_) / med(p_):6.2f}x")
        for k in kerns:
            for impl in ("c_ctypes", "rust_ctypes"):
                p_ = pick(ok(pypy), k, impl)
                c_ = pick(cpy, k, impl)
                if p_ and c_:
                    print(f"  {k:<12} {impl:<12} CPython {med(c_) * 1e3:8.3f} ms  "
                          f"PyPy {med(p_) * 1e3:8.3f} ms  {med(c_) / med(p_):6.2f}x")


def rq6real() -> None:
    hdr("RQ6 build configurations of one 3.14.6 source tree")
    recs = ok(load("b5_buildcfg-"))
    if not recs:
        print("  no data")
        return
    order = ["plain", "pgo", "ltothin", "ltofull", "pgo_ltofull", "pgo_ltofull_native",
             "jit"]
    present = [c for c in order if any(r["impl"] == c for r in recs)]
    cases = [c for c in B3_CASES if pick(recs, c, "plain")]
    print(f"{'case':<26}" + "".join(f"{c[:14]:>15}" for c in present))
    ratios = {c: [] for c in present}
    for case in cases:
        b = pick(recs, case, "plain")
        if not b:
            continue
        row = f"{case:<26}"
        for c in present:
            r = pick(recs, case, c)
            if r:
                v = med(b) / med(r)
                ratios[c].append(v)
                row += f"{v:>15.3f}"
            else:
                row += f"{'--':>15}"
        print(row)
    print(f"\n{'GEOMEAN vs plain':<26}" + "".join(f"{geomean(ratios[c]):>15.3f}" for c in present))
    srecs = ok(load("b5_startup-"))
    for case in ("startup_bare", "startup_site", "startup_stdlib"):
        row = f"{case:<26}"
        for c in present:
            r = pick(srecs, case, c)
            row += f"{med(r) * 1e3:>15.1f}" if r else f"{'--':>15}"
        print(row + "   (ms)")


def rq7() -> None:
    hdr("RQ7 mixed pipeline")
    recs = ok(load("b7_pipeline-"))
    for cfg in ("gil", "ft"):
        base = pick(recs, "end_to_end", f"{cfg}/v0_pure")
        if not base:
            continue
        print(f"\n  {cfg}")
        for v in ("v0_pure", "v1_numba", "v2_numba_native", "v3_native_threads", "v4_all"):
            r = pick(recs, "end_to_end", f"{cfg}/{v}")
            if r:
                print(f"    {v:<18} {med(r) * 1e3:8.2f} ms  {med(base) / med(r):5.2f}x")
        for case in ("stage_parse", "stage_validate", "stage_aggregate"):
            for impl in (f"{cfg}/v0_pure", f"{cfg}/v1_numba", f"{cfg}/v2_native"):
                r = pick(recs, case, impl)
                if r:
                    print(f"    {case:<18} {impl:<16} {med(r) * 1e3:8.2f} ms")


ALL = {"rq1": rq1, "rq1b": rq1b, "rq2": rq2, "rq3": rq3, "rq4": rq4, "rq5": rq5,
       "rq6": rq6real, "rq6b": rq6b, "rq7": rq7, "rq8": rq8}

if __name__ == "__main__":
    want = [a.lower() for a in sys.argv[1:]] or list(ALL)
    for k in want:
        if k in ALL:
            try:
                ALL[k]()
            except Exception as exc:
                import traceback
                print(f"[{k}] FAILED {exc!r}")
                traceback.print_exc()
