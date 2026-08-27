#!/usr/bin/env python
"""Generate every figure in the paper from results/*.json."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mpl_ticker
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, TwoSlopeNorm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyperf_load import Record
from style import (
    B3_CASES,
    CAT,
    CRIT,
    GOOD,
    GRID,
    INK,
    INK2,
    MUTED,
    NEUTRAL,
    SEQ,
    apply_style,
    bar_labels,
    by,
    facts_of,
    geomean,
    is_pypy,
    label,
    load,
    med,
    ok,
    pick,
    save,
    seq_colors,
    sized_label,
)
from style import RESULTS as RESULTS_DIR
from style import ROOT as ROOT_DIR
from style import SURFACE as SURFACE_C

REF_TAG = "314"
REF_VERSION = "v314"
BREAKEVEN_FACTS: dict[str, Any] = {}


def host_name() -> str:
    """Short description of the machine, read from the results rather than written here."""
    import glob as _glob
    for pat in ("b1_compute-*.facts.json", "b3_runtime-*.facts.json"):
        for path in sorted(_glob.glob(os.path.join(RESULTS_DIR, "pyperf", pat))):
            try:
                with open(path) as fh:
                    m = json.load(fh).get("machine", {})
            except Exception:
                continue
            brand = (m.get("cpu_brand") or "").replace("(R)", "").replace("(TM)", "").strip()
            if brand:
                n = m.get("cpu_count")
                return f"{brand}, {n} cores" if n else brand
    return "this host"


HOST = host_name()
COMPUTE = ["arraysum", "mandelbrot", "matmul"]
BRANCHY = ["tokenize", "binarytrees", "bfs"]

DIVERGING = LinearSegmentedColormap.from_list(
    "red_gray_blue", ["#7d1f1f", "#d03b3b", "#f0a3a3", "#f0efec", "#9ec5f4", "#2a78d6", "#0d366b"])


def fmt_time(s: float) -> str:
    """Unit-aware label for a duration in seconds."""
    if s >= 1:
        return f"{s:.2f} s"
    if s >= 1e-3:
        return f"{s * 1e3:.2f} ms"
    if s >= 1e-6:
        return f"{s * 1e6:.1f} us"
    return f"{s * 1e9:.0f} ns"


def tag_of(rec: Record) -> str:
    """The configuration a record belongs to."""
    return rec.get("label") or ""


def only(records: Iterable[Record], tag: str = REF_TAG) -> list[Record]:
    return [r for r in records if tag_of(r) == tag]


def fig1_compute() -> None:
    recs = only(ok(load("b1_compute-")))
    if not recs:
        print("[fig1] no data")
        return
    order = ["cpython_loop", "cpython_builtin_sum", "cython", "codon_pyext",
             "codon_pyext_ptr", "numba", "numba_fastmath", "codon_jit",
             "c_ctypes", "c_pybind11", "rust_ctypes", "numpy"]
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.2))
    fig.subplots_adjust(wspace=0.75)
    for ax, kern in zip(axes, COMPUTE, strict=True):
        base = pick(recs, kern, "cpython_loop")
        if not base:
            continue
        vals: list[float] = []
        colors: list[str] = []
        for impl in order:
            r = pick(recs, kern, impl)
            vals.append(med(base) / med(r) if r else np.nan)
            colors.append(NEUTRAL if impl.startswith("cpython")
                          else (CAT[2] if impl == "numpy" else CAT[0]))
        ys = np.arange(len(order))
        bars = ax.barh(ys, vals, color=colors, height=0.62)
        ax.set_yticks(ys, [label(i) for i in order])
        ax.invert_yaxis()
        ax.set_xscale("log")
        top = np.nanmax(vals)
        ax.set_xlim(0.6, top * 8)
        bar_labels(ax, bars, vals, fmt="{:.1f}x")
        ax.set_title(label(kern))
        ax.grid(axis="y", visible=False)
        ax.axvline(1.0, color=MUTED, lw=0.8, ls=":")
        ax.set_xlabel("speedup over the pure-Python loop (log)")
    fig.suptitle(f"Compute-bound kernels on CPython 3.14.6 ({HOST})",
                 fontsize=10.5, y=1.08, color=INK)
    save(fig, "f1_compute_speedup")


FLAG_VARIANTS = ["O0", "O2", "O3", "O3native", "O3native_novec", "O3native_ffast"]
def _native_flag() -> str:
    path = os.path.join(ROOT_DIR, "bench", "build", "native", "native_flag.txt")
    try:
        with open(path) as fh:
            return fh.read().strip() or "-march=native"
    except OSError:
        return "-march=native"


FLAG_LABEL = {"O0": "-O0", "O2": "-O2", "O3": "-O3",
              "O3native": f"-O3 {_native_flag()}",
              "O3native_novec": "  + no vectoriser", "O3native_ffast": "  + -ffast-math"}


def fig2_archflags() -> None:
    """What the flags change, before what they cost."""
    recs = ok(load("b1_flags-"))
    ident_path = os.path.join(RESULTS_DIR, "codegen_identity.json")
    ident: dict[str, Any] = {}
    if os.path.exists(ident_path):
        with open(ident_path) as fh:
            ident = json.load(fh).get("kernels", {})
    if not recs:
        print("[fig2] no data")
        return

    fig = plt.figure(figsize=(11.2, 3.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.15, 0.95], wspace=0.42)

    ax = fig.add_subplot(gs[0, 0])
    if ident:
        kerns = [k for k in ("c_arraysum", "c_mandelbrot", "c_matmul") if k in ident]
        grid = np.zeros((len(FLAG_VARIANTS), len(kerns)))
        letters: dict[tuple[int, int], str] = {}
        for j, k in enumerate(kerns):
            seen: dict[str, int] = {}
            for i, v in enumerate(FLAG_VARIANTS):
                h = ident[k].get(v, {}).get("hash")
                if h is None:
                    grid[i, j] = np.nan
                    continue
                if h not in seen:
                    seen[h] = len(seen)
                grid[i, j] = seen[h]
                letters[(i, j)] = chr(ord("A") + seen[h])
        ax.imshow(grid, cmap=ListedColormap([CAT[0], CAT[1], CAT[2], CAT[3], SEQ[1]]),
                  aspect="auto", vmin=0, vmax=4)
        for (i, j), ch in letters.items():
            ax.text(j, i, ch, ha="center", va="center", color=SURFACE_C,
                    fontsize=9, fontweight="bold")
        short = {"c_arraysum": "sum", "c_mandelbrot": "mandel", "c_matmul": "matmul"}
        ax.set_xticks(range(len(kerns)), [short.get(k, k) for k in kerns], fontsize=7.5)
        ax.set_yticks(range(len(FLAG_VARIANTS)), [FLAG_LABEL[v] for v in FLAG_VARIANTS],
                      fontsize=7.5)
        ax.grid(False)
        ax.set_title("Same letter = same machine code")
    else:
        ax.text(0.5, 0.5, "run codegen_diff.sh", ha="center", va="center")
        ax.set_axis_off()

    ax = fig.add_subplot(gs[0, 1])
    width = 0.26
    for gi, kern in enumerate(COMPUTE):
        base = pick(recs, kern, "O2")
        if not base:
            continue
        vals: list[float] = []
        xs: list[float] = []
        for i, v in enumerate(FLAG_VARIANTS):
            r = pick(recs, kern, v)
            if r:
                vals.append(med(base) / med(r))
                xs.append(i + (gi - 1) * width)
        ax.barh(xs, vals, height=width * 0.9, color=CAT[gi],
                label=label(kern).split(" (")[0])
    ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    ax.set_yticks(range(len(FLAG_VARIANTS)), [""] * len(FLAG_VARIANTS))
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xscale("log")
    ticks = [0.125, 0.25, 0.5, 1, 2, 4, 8]
    ax.set_xticks(ticks, [f"{t:g}x" for t in ticks])
    ax.xaxis.set_minor_locator(mpl_ticker.NullLocator())
    ax.set_xlim(0.1, 10)
    ax.set_xlabel("time of -O2 / time of this variant (log)")
    ax.set_title("What the flags cost")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncols=3, fontsize=7,
              frameon=False)

    ax = fig.add_subplot(gs[0, 2])
    base = pick(recs, "arraysum", "O2")
    ladder = [("accum_acc1", "1 accumulator"), ("accum_acc2", "2"), ("accum_acc4", "4"),
              ("accum_acc8", "8")]
    rows = [(nm, med(base) / med(pick(recs, "arraysum", k)))
            for k, nm in ladder if base and pick(recs, "arraysum", k)]
    ff = pick(recs, "arraysum", "O3native_ffast")
    if base and ff:
        rows.append(("-ffast-math", med(base) / med(ff)))
    if rows:
        ys = np.arange(len(rows))
        cols = [CAT[0]] * (len(rows) - 1) + [CAT[1]]
        bars = ax.barh(ys, [r[1] for r in rows], color=cols, height=0.62)
        ax.set_yticks(ys, [r[0] for r in rows], fontsize=7.5)
        ax.invert_yaxis()
        bar_labels(ax, bars, [r[1] for r in rows], fmt="{:.1f}x")
        ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("speedup over the serial -O2 loop")
        ax.set_title("Regrouped in the source, at -O2")
    fig.suptitle("One C source: what the flags change, and where the one large effect lives",
                 fontsize=10.5, color=INK)
    save(fig, "f2_arch_flags")


def fig3_breakeven() -> None:
    global BREAKEVEN_FACTS
    BREAKEVEN_FACTS = facts_of(load("b1_breakeven-"))
    """Break-even vs input size (preferred), with the per-kernel view as a fallback."""
    be = ok(load("b1_breakeven-"))
    if be:
        sizes, t_py, t_nb, ks = [], [], [], []
        for r in sorted(by(be, impl="numba"), key=lambda x: x["params"].get("n", 0)):
            if r["case"] == "compile_latency" or "n" not in r["params"]:
                continue
            n = r["params"]["n"]
            base = pick(be, r["case"], "cpython_loop")
            if not base:
                continue
            sizes.append(n)
            t_py.append(med(base))
            t_nb.append(med(r))
            ks.append((r.get("extra") or {}).get("break_even_calls"))
        compile_s = BREAKEVEN_FACTS.get("numba_compile_s")
        if compile_s is None:
            comp = pick(be, "compile_latency", "numba")
            compile_s = med(comp) if comp else None
        if compile_s and any(k is None for k in ks):
            ks = [((compile_s / (py - nb)) if py > nb else float("nan"))
                  for py, nb in zip(t_py, t_nb, strict=True)]
        if sizes:
            fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.6))
            fig.subplots_adjust(wspace=0.42, top=0.80)
            ax = axes[0]
            cod = BREAKEVEN_FACTS.get("codon_cost_s") or {}
            t_cd = [med(r) for n in sizes
                    if (r := pick(be, f"arraysum_n{n}", "codon_jit"))] if cod else []
            ax.plot(sizes, np.array(t_py) * 1e3, color=NEUTRAL, marker="o", label="pure Python")
            ax.plot(sizes, np.array(t_nb) * 1e3, color=CAT[0], marker="o",
                    label="Numba, steady state")
            if len(t_cd) == len(sizes):
                ax.plot(sizes, np.array(t_cd) * 1e3, color=CAT[2], marker="s", ms=4,
                        label="Codon JIT, steady state")
            if compile_s:
                ax.axhline(compile_s * 1e3, color=CAT[1], ls="--", lw=1.0)
                ax.annotate(f"Numba compilation: {compile_s * 1e3:.0f} ms",
                            (sizes[0], compile_s * 1e3), xytext=(2, 4),
                            textcoords="offset points", color=CAT[1], fontsize=7.5)
            if cod.get("compile_s"):
                ax.axhline(cod["compile_s"] * 1e3, color=CAT[2], ls="--", lw=1.0)
                ax.annotate(f"Codon compilation: {cod['compile_s'] * 1e3:.0f} ms",
                            (sizes[0], cod["compile_s"] * 1e3), xytext=(2, 4),
                            textcoords="offset points", color=CAT[2], fontsize=7.5)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel("array length")
            ax.set_ylabel("time per call, ms")
            lo = min([*t_py, *t_nb, *(t_cd or [t_py[0]])]) * 1e3
            ax.set_ylim(bottom=lo / 12)
            ax.legend(loc="lower right", frameon=False, fontsize=7.5)
            ax.set_title("Cost per call vs input size")

            ax2 = axes[1]
            ax2.plot(sizes, ks, color=CAT[0], marker="o", label="Numba")
            for n, k in zip(sizes, ks, strict=True):
                if k:
                    ax2.annotate(f"{k:,.0f}".replace(",", " "), (n, k), xytext=(0, 6),
                                 textcoords="offset points", ha="center", fontsize=7.5,
                                 color=INK2)
            if len(t_cd) == len(sizes) and cod.get("compile_s"):
                kc = [(cod["compile_s"] / (py - cd)) if py > cd else float("nan")
                      for py, cd in zip(t_py, t_cd, strict=True)]
                ax2.plot(sizes, kc, color=CAT[2], marker="s", ms=4, label="Codon JIT")
                ax2.legend(loc="upper right", frameon=False, fontsize=7.5)
            ax2.set_xscale("log")
            ax2.set_yscale("log")
            ax2.set_xlabel("array length")
            ax2.set_ylabel("calls needed to break even")
            ax2.set_title("How long until the JIT has paid for itself")
            ver = (be[0]["interp"].get("version") or "").strip() or REF_TAG
            fig.suptitle("JIT compilation is not free "
                         f"(array-sum kernel, CPython {ver})",
                         fontsize=10.5, y=0.98, color=INK)
            save(fig, "f3_jit_breakeven")
            return

    recs = only(ok(load("b1_compute-")))
    if not recs:
        print("[fig3] no data")
        return
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 2.9))
    for ax, kern in zip(axes, COMPUTE, strict=True):
        py = pick(recs, kern, "cpython_loop")
        nb = pick(recs, kern, "numba")
        if not (py and nb):
            continue
        c = BREAKEVEN_FACTS.get("numba_compile_s")
        if not c:
            continue
        tp, tn = med(py), med(nb)
        ks = np.logspace(0, 6, 200)
        ax.plot(ks, ks * tp, color=NEUTRAL, label="pure Python")
        ax.plot(ks, c + ks * tn, color=CAT[0], label="Numba (compile + run)")
        kstar = c / (tp - tn) if tp > tn else None
        if kstar:
            ax.axvline(kstar, color=CAT[1], ls="--", lw=1.0)
            ax.annotate(f"break-even\n{kstar:,.0f} calls".replace(",", " "),
                        (kstar, c * 1.2), color=CAT[1], fontsize=7.5, ha="left", va="bottom")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(label(kern))
        ax.set_xlabel("number of calls")
        if kern == COMPUTE[0]:
            ax.set_ylabel("cumulative wall time, s")
        ax.legend(loc="upper left")
    fig.suptitle("JIT compilation is not free: when Numba starts paying off",
                 fontsize=10.5, y=1.04, color=INK)
    save(fig, "f3_jit_breakeven")


def fig4_divergence() -> None:
    c_recs = only(ok(load("b1_compute-")))
    b_recs = only(ok(load("b2_branchy-")))
    if not (c_recs and b_recs):
        print("[fig4] no data")
        return
    impls = ["cython", "codon_pyext", "numba", "codon_jit", "c_ctypes", "rust_ctypes"]
    comp, bran, notes = [], [], []
    for impl in impls:
        cb = [med(pick(c_recs, k, "cpython_loop")) / med(pick(c_recs, k, impl))
              for k in COMPUTE if pick(c_recs, k, impl) and pick(c_recs, k, "cpython_loop")]
        bb = [med(pick(b_recs, k, "cpython_loop")) / med(pick(b_recs, k, impl))
              for k in BRANCHY if pick(b_recs, k, impl) and pick(b_recs, k, "cpython_loop")]
        comp.append(geomean(cb))
        bran.append(geomean(bb))
        notes.append(f"{len(cb)}/{len(COMPUTE)} vs {len(bb)}/{len(BRANCHY)} kernels")
    ys = np.arange(len(impls))
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    h = 0.36
    b1 = ax.barh(ys - h / 2, comp, height=h - 0.03, color=CAT[0], label="compute-bound kernels")
    b2 = ax.barh(ys + h / 2, bran, height=h - 0.03, color=CAT[1],
                 label="branchy / allocating kernels")
    bar_labels(ax, b1, comp, fmt="{:.0f}x")
    bar_labels(ax, b2, bran, fmt="{:.0f}x")
    ax.set_yticks(ys, [label(i) for i in impls])
    ax.invert_yaxis()
    ax.set_xlabel("geometric-mean speedup over pure Python (CPython 3.14)")
    ax.axvline(1.0, color=MUTED, lw=0.8, ls=":")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(max(comp), max(bran)) * 1.14)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncols=2)
    ax.set_title("Where the acceleration goes: compute-bound vs branchy workloads")
    save(fig, "f4_compute_vs_branchy")


def fig5_ffi() -> None:
    recs = only(ok(load("b1_compute-")))
    rows = [(label(r["impl"]), med(r) * 1e9) for r in by(recs, case="call_overhead")]
    if not rows:
        print("[fig5] no data")
        return
    rows.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(5.4, 2.2))
    ys = np.arange(len(rows))
    bars = ax.barh(ys, [r[1] for r in rows], color=CAT[0], height=0.6)
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.invert_yaxis()
    bar_labels(ax, bars, [r[1] for r in rows], fmt="{:.0f} ns")
    ax.set_xlabel("cost of one call with an empty callee, ns")
    ax.set_xlim(0, max(r[1] for r in rows) * 1.25)
    ax.grid(axis="y", visible=False)
    ax.set_title("The FFI boundary itself")
    save(fig, "f5_call_overhead")


VERSIONS = ["v310", "v311", "v312", "v313", "v314", "v314t"]
VLABEL = {"v310": "3.10", "v311": "3.11", "v312": "3.12", "v313": "3.13", "v314": "3.14",
          "v314t": "3.14t"}


def b3_dataset() -> tuple[list[Record], list[str], str]:
    """The runtime operation suite across the uniformly built interpreters."""
    recs = [r for r in ok(load("b3_runtime-")) if r["impl"] in VERSIONS]
    present = [v for v in VERSIONS if any(r["impl"] == v for r in recs)]
    return recs, present, "compiled here, one compiler, one configure line"


def fig6_versions() -> None:
    recs, versions, prov = b3_dataset()
    if not recs:
        print("[fig6] no data")
        return
    mat = np.full((len(B3_CASES), len(versions)), np.nan)
    for i, case in enumerate(B3_CASES):
        base = pick(recs, case, versions[0])
        if not base:
            continue
        for j, v in enumerate(versions):
            r = pick(recs, case, v)
            if r:
                mat[i, j] = med(base) / med(r)
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    lm = np.log2(mat)
    lim = np.nanmax(np.abs(lm[np.isfinite(lm)])) if np.isfinite(lm).any() else 1.0
    im = ax.imshow(lm, cmap=DIVERGING, norm=TwoSlopeNorm(0.0, -lim, lim), aspect="auto")
    ax.set_xticks(range(len(versions)), [VLABEL[v] for v in versions])
    ax.set_yticks(range(len(B3_CASES)), [c.replace("_", " ") for c in B3_CASES])
    ax.grid(False)
    for i in range(len(B3_CASES)):
        for j in range(len(versions)):
            if np.isfinite(mat[i, j]):
                v = mat[i, j]
                ax.annotate(f"{v:.2f}", (j, i), ha="center", va="center", fontsize=7,
                            color="#ffffff" if abs(np.log2(v)) > lim * 0.55 else INK)
    cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.045)
    cb.set_label(f"speedup vs {VLABEL[versions[0]]} (log2 scale, 1.00 = same)")
    ax.set_title(f"CPython {VLABEL[versions[0]]} → {VLABEL[versions[-1]]}: per-operation speedup\n"
                 f"(x-factors vs {VLABEL[versions[0]]}; interpreters {prov})")
    save(fig, "f6_version_sweep")


def fig7_specialization() -> None:
    """One benchmark per execution number, so the curve is 24 medians and not one array."""
    recs = ok(load("b3_spec-"))
    if not recs:
        print("[fig7] no data")
        return
    curves: list[tuple[str, list[float]]] = []
    for v in VERSIONS:
        pts = sorted((r["params"].get("k", 0), med(r)) for r in recs if r["impl"] == v)
        if pts:
            curves.append((v, [t for _, t in pts]))
    if not curves:
        print("[fig7] no data")
        return
    cols = seq_colors(len(curves))
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    for (v, curve), c in zip(curves, cols, strict=True):
        xs = np.arange(1, len(curve) + 1)
        ax.plot(xs, np.array(curve) * 1e6, color=c, label=VLABEL[v], marker="o", ms=3)
    ax.set_xlabel("execution number of a freshly compiled code object")
    ax.set_ylabel("time of that execution, us")
    ax.set_xlim(0.5, len(curves[0][1]) + 0.5)
    ax.set_title("Adaptive specialisation warm-up")
    ax.legend(loc="upper right", ncols=2, fontsize=7.5)
    save(fig, "f7_specialization_warmup")


def fig8_cinder() -> None:
    allrecs = load("b6_cinderx-")
    recs = ok(allrecs)
    srecs = ok(load("b6_static-"))
    if not recs:
        print("[fig8] no data")
        return
    kernels = COMPUTE + BRANCHY
    fig = plt.figure(figsize=(13.4, 7.0))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.3, 1.0], hspace=0.62, wspace=1.06)

    ax = fig.add_subplot(gs[0, :])
    ys = np.arange(len(kernels))
    h = 0.26
    for k, (cfg, col) in enumerate(zip(["fork", "fork_cinderx", "fork_jit"],
                                       [CAT[0], CAT[1], CAT[3]], strict=True)):
        vals = [med(pick(recs, kern, cfg)) / med(pick(recs, kern, "stock"))
                if (pick(recs, kern, cfg) and pick(recs, kern, "stock")) else np.nan
                for kern in kernels]
        bars = ax.barh(ys + (k - 1) * h, vals, height=h - 0.04, color=col, label=label(cfg))
        bar_labels(ax, bars, vals, fmt="{:.2f}")
    ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    b6_params = next((r["params"] for r in recs if r.get("params")), {})
    ax.set_yticks(ys, [sized_label(k, b6_params) for k in kernels])
    ax.invert_yaxis()
    ax.set_xlim(0, 2.1)
    ax.set_xlabel("run time relative to stock CPython 3.14.6  (>1 = slower)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=3)
    ax.set_title("Cinder fork and CinderX on unmodified Python code, relative to stock CPython")

    ax0 = fig.add_subplot(gs[1, 0])
    pairs = [("fork_cinderx", "fork_cinderx_adaptive", "runtime", CAT[1]),
             ("fork_jit", "fork_jit_adaptive", "JIT", CAT[3])]
    if any(pick(recs, kernels[0], b) for _, b, _, _ in pairs):
        hh = 0.34
        for k, (base_cfg, ad_cfg, nm, col) in enumerate(pairs):
            vals = [med(pick(recs, kern, ad_cfg)) / med(pick(recs, kern, base_cfg))
                    if (pick(recs, kern, ad_cfg) and pick(recs, kern, base_cfg)) else np.nan
                    for kern in kernels]
            ax0.barh(ys + (k - 0.5) * hh, vals, height=hh - 0.04, color=col, label=nm)
        ax0.axvline(1.0, color=MUTED, lw=0.9, ls="--")
        ax0.set_yticks(ys, [label(k).split(" (")[0] for k in kernels])
        ax0.invert_yaxis()
        ax0.set_xlim(0.8, 1.2)
        ax0.grid(axis="y", visible=False)
        ax0.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncols=2,
                   fontsize=7.5, frameon=False)
        ax0.set_xlabel("adaptive on / adaptive off")
        ax0.set_title("Effect of the adaptive flag")
    else:
        print("[fig8] no adaptive-configuration records -- that subpanel is missing")

    ax2 = fig.add_subplot(gs[1, 1])
    order: list[tuple[str, bool, str, str]] = [
        ("boxed_python", False, "Python int (boxed)", NEUTRAL),
        ("boxed_jit", False, "Python int + JIT", CAT[0]),
        ("static_interp", False, "Static int64, interp", CRIT),
        ("static_interp", True, "  + adaptive", CAT[1]),
        ("static_jit", False, "Static int64 + JIT", GOOD),
    ]
    rows: list[tuple[str, float]] = []
    cols2: list[str] = []
    for suffix, adaptive, nm, col in order:
        hits = [r for r in srecs if r["impl"].endswith(suffix)
                and (("adaptive" in r["impl"]) == adaptive)]
        if hits:
            rows.append((nm, med(hits[0]) * 1e3))
            cols2.append(col)
    if rows:
        ys2 = np.arange(len(rows))
        bars = ax2.barh(ys2, [r[1] for r in rows], color=cols2, height=0.6)
        ax2.set_yticks(ys2, [r[0] for r in rows], fontsize=7.5)
        ax2.invert_yaxis()
        ax2.set_xscale("log")
        for b, v in zip(bars, [r[1] for r in rows], strict=True):
            ax2.annotate(fmt_time(v / 1e3), (b.get_width(), b.get_y() + b.get_height() / 2),
                         xytext=(4, 0), textcoords="offset points", va="center", ha="left",
                         fontsize=7.5, color=INK2)
        ax2.set_xlim(0.5, max(r[1] for r in rows) * 12)
        ax2.grid(axis="y", visible=False)
        ax2.set_xlabel("ms per call (log)")
        ax2.set_title("Static Python, 96x96 int matmul")
    else:
        print("[fig8] no Static Python records -- that subpanel is missing")

    ax3 = fig.add_subplot(gs[1, 2])
    rows3: list[tuple[str, float, int]] = []
    for case, impl, nm in (("import_200_modules_eager", "stock", "CPython, eager"),
                           ("import_200_modules_eager", "fork", "fork, eager"),
                           ("import_200_modules_lazy", "fork", "fork, lazy imports")):
        r = pick(recs, case, impl)
        if r:
            li = facts_of(allrecs, impl).get("lazy_imports", {})
            n = (li.get("lazy_module_bodies_run") if "lazy" in case
                 else li.get("eager_module_bodies_run"))
            rows3.append((nm, med(r) * 1e3, n))
    if rows3:
        ys3 = np.arange(len(rows3))
        bars = ax3.barh(ys3, [r[1] for r in rows3], color=[NEUTRAL, CAT[0], GOOD][:len(rows3)],
                        height=0.6)
        ax3.set_yticks(ys3, [r[0] for r in rows3])
        ax3.invert_yaxis()
        ax3.set_xscale("log")
        for b, (_nm, v, nmods) in zip(bars, rows3, strict=True):
            txt = fmt_time(v / 1e3) + (f"  ({nmods} bodies)" if nmods is not None else "")
            ax3.annotate(txt, (b.get_width(), b.get_y() + b.get_height() / 2),
                         xytext=(4, 0), textcoords="offset points", va="center", ha="left",
                         fontsize=7.5, color=INK2)
        ax3.set_xlim(min(r[1] for r in rows3) * 0.3, max(r[1] for r in rows3) * 120)
        ax3.grid(axis="y", visible=False)
        ax3.set_xlabel("import time, ms (log)")
        ax3.set_title("200-module package import")
    else:
        print("[fig8] no lazy-import records -- that subpanel is missing")

    ax4 = fig.add_subplot(gs[1, 3])
    grecs = ok(load("b6_gcscale-"))
    rows = [("stock", "state_visible", "stock 3.14"),
            ("fork_cinderx", "state_visible", "CinderX, state visible"),
            ("fork_cinderx", "frozen", "+ gc.freeze()"),
            ("fork_cinderx", "immortal", "+ immortalize_heap()")]
    labels: list[str] = []
    ser: list[float] = []
    par: list[float] = []
    for cfg, mode, nm in rows:
        s_rec = pick(grecs, "gc_collect", f"{cfg}/{mode}_serial")
        if not s_rec:
            continue
        p_rec = pick(grecs, "gc_collect", f"{cfg}/{mode}_par6")
        labels.append(nm)
        ser.append(med(s_rec) * 1e3)
        par.append(med(p_rec) * 1e3 if p_rec else np.nan)
    if labels:
        ys = np.arange(len(labels))
        h = 0.38
        b_s = ax4.barh(ys - h / 2, ser, height=h - 0.03, color=CAT[0], label="serial")
        b_p = ax4.barh(ys + h / 2, par, height=h - 0.03, color=CAT[1], label="6 threads")
        bar_labels(ax4, b_s, ser, fmt="{:.0f}")
        bar_labels(ax4, b_p, par, fmt="{:.0f}")
        ax4.set_yticks(ys, labels, fontsize=7)
        ax4.invert_yaxis()
        ax4.grid(axis="y", visible=False)
        ax4.set_xlabel("gc.collect(), ms")
        ax4.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncols=2,
                   fontsize=7.5, frameon=False)
        ax4.set_title("What the collector can see", pad=9)
    else:
        print("[fig8] no gc-scale records -- that subpanel is missing")
    save(fig, "f8_cinder")


JITOPT_ORDER = [
    ("default", "default"),
    ("compile_at_first_call", "compile at first call"),
    ("no_attr_caches", "attribute caches off"),
    ("split_code_sections", "hot/cold code split"),
    ("split_code_sections_hugepages", "hot/cold split + huge pages"),
]


def fig18_jitopts() -> None:
    recs = ok(load("b6_cinderx-jitopt_"))
    if not recs:
        print("[fig18] no data")
        return
    kernels = COMPUTE + BRANCHY
    present = [(tag, name) for tag, name in JITOPT_ORDER
               if any(r["label"] == f"jitopt_{tag}" for r in recs)]
    if len(present) < 2 or present[0][0] != "default":
        print("[fig18] need the default configuration and at least one other")
        return

    def med_of(tag: str, kern: str) -> float:
        hits = [r for r in recs if r["label"] == f"jitopt_{tag}" and r["case"] == kern]
        return med(hits[0]) if hits else float("nan")

    rows = present[1:]
    mat = np.full((len(rows), len(kernels)), np.nan)
    for i, (tag, _) in enumerate(rows):
        for j, kern in enumerate(kernels):
            base = med_of("default", kern)
            v = med_of(tag, kern)
            if base == base and v == v:
                mat[i, j] = base / v
    geo = np.array([np.exp(np.nanmean(np.log(mat[i]))) for i in range(len(rows))])

    fig = plt.figure(figsize=(11.6, 0.62 * len(rows) + 2.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.06)

    ax = fig.add_subplot(gs[0, 0])
    lm = np.log2(mat)
    lim = np.nanmax(np.abs(lm[np.isfinite(lm)])) if np.isfinite(lm).any() else 1.0
    ax.imshow(lm, cmap=DIVERGING, norm=TwoSlopeNorm(0.0, -lim, lim), aspect="auto")
    short = {"arraysum": "array sum", "mandelbrot": "mandelbrot", "matmul": "matmul",
             "tokenize": "tokenize", "binarytrees": "bin. trees", "bfs": "graph BFS"}
    ax.set_xticks(range(len(kernels)), [short.get(k, k) for k in kernels],
                  rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(rows)), [name for _, name in rows])
    ax.grid(False)
    for i in range(len(rows)):
        for j in range(len(kernels)):
            if np.isfinite(mat[i, j]):
                v = mat[i, j]
                ax.annotate(f"{v:.2f}", (j, i), ha="center", va="center", fontsize=7,
                            color="#ffffff" if abs(np.log2(v)) > lim * 0.55 else INK)
    ax.set_title("Speed relative to the default JIT configuration  (>1 = faster)")

    ax2 = fig.add_subplot(gs[0, 1], sharey=ax)
    ys = np.arange(len(rows))
    bars = ax2.barh(ys, geo, color=[CRIT if g < 0.98 else NEUTRAL for g in geo], height=0.62)
    ax2.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    bar_labels(ax2, bars, list(geo), fmt="{:.2f}")
    ax2.set_xlim(0.0, 1.12)
    ax2.tick_params(labelleft=False)
    ax2.grid(axis="y", visible=False)
    ax2.set_xlabel("geometric mean over the six kernels")
    ax2.set_title("Nothing is faster than the default")
    save(fig, "f18_jitopts")


def fig9_threads() -> None:
    recs = ok(load("b4_threads-"))
    if not recs:
        print("[fig9] no data")
        return
    cases = ["py_arith", "py_branchy", "c_ffi_uniform", "c_ffi_mandelbrot"]
    configs = ["gil", "ft_gil", "ft"]
    threads = [1, 2, 3, 4, 6, 8]
    fig, axes = plt.subplots(1, 4, figsize=(11.0, 2.9), sharey=True)
    for ax, case in zip(axes, cases, strict=True):
        ax.plot(threads, threads, color=GRID, lw=1.2, ls="--", zorder=1)
        ax.annotate("linear", (threads[-1], threads[-1]), xytext=(-2, -10),
                    textcoords="offset points", color=MUTED, fontsize=7, ha="right")
        ends: list[tuple[float, float, str]] = []
        for cfg, col in zip(configs, [CAT[0], CAT[1], CAT[3]], strict=True):
            xs: list[int] = []
            ys: list[float] = []
            base = pick(recs, case, f"{cfg}/T1")
            ctl = pick(recs, case, f"{cfg}/T1_control")
            if not base:
                continue
            t1 = min(med(base), med(ctl)) if ctl else med(base)
            for t in threads:
                r = pick(recs, case, f"{cfg}/T{t}")
                if r:
                    xs.append(t)
                    ys.append(1.0 if t == 1 else t1 / med(r))
            if xs:
                ax.plot(xs, ys, color=col, marker="o", label=label(cfg), zorder=3)
                ends.append((ys[-1], xs[-1], col))
        ends.sort()
        for i, (y, x, col) in enumerate(ends):
            ax.annotate(f"{y:.2f}x", (x, y), xytext=(5, (i - (len(ends) - 1) / 2) * 11),
                        textcoords="offset points", color=col, fontsize=7.5, va="center")
        ax.set_title(label(case))
        ax.set_xlabel("threads")
        ax.set_xticks(threads)
        ax.set_xlim(0.7, 9.6)
    axes[0].set_ylabel("speedup over 1 thread")
    handles, labels_ = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels_, loc="lower center", bbox_to_anchor=(0.5, -0.12), ncols=3,
               frameon=False)
    fig.suptitle(f"Thread scalability: GIL build vs free-threaded build ({HOST})",
                 fontsize=10.5, y=1.04, color=INK)
    save(fig, "f9_thread_scaling")


def fig10_ft_tax() -> None:
    recs = ok(load("b4_threads-"))
    cases = ["single_thread_arith", "single_thread_branchy"]
    configs = ["gil", "ft_gil", "ft"]
    rows: list[tuple[str, list[tuple[str, float]]]] = []
    for case in cases:
        base = pick(recs, case, "gil")
        if not base:
            continue
        rows.append((case, [(cfg, med(pick(recs, case, cfg)) / med(base))
                            for cfg in configs if pick(recs, case, cfg)]))
    if not rows:
        print("[fig10] no data")
        return
    fig, ax = plt.subplots(figsize=(5.6, 2.4))
    ys = np.arange(len(rows))
    h = 0.26
    for k, (cfg, col) in enumerate(zip(configs, [NEUTRAL, CAT[1], CAT[3]], strict=True)):
        vals = [dict(r[1]).get(cfg, np.nan) for r in rows]
        bars = ax.barh(ys + (k - 1) * h, vals, height=h - 0.03, color=col, label=label(cfg))
        bar_labels(ax, bars, vals, fmt="{:.2f}")
    ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    ax.set_yticks(ys, ["arithmetic", "branchy"])
    ax.invert_yaxis()
    ax.set_xlabel("single-thread time relative to the GIL build (>1 = slower)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncols=3, frameon=False)
    ax.set_title("The single-thread cost of free-threading")
    save(fig, "f10_ft_tax")


def fig12_pipeline() -> None:
    recs = ok(load("b7_pipeline-"))
    if not recs:
        print("[fig12] no data")
        return
    variants = ["v0_pure", "v1_numba", "v2_numba_native", "v3_native_threads", "v4_all"]
    vnames = {"v0_pure": "all pure Python", "v1_numba": "+ Numba (numeric)",
              "v2_numba_native": "+ C (classification)",
              "v3_native_threads": "C + 4 threads (no Numba)", "v4_all": "Numba + C + 4 threads"}
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.1), width_ratios=[1.2, 1.0])
    fig.subplots_adjust(wspace=0.42)
    ax = axes[0]
    ys = np.arange(len(variants))
    h = 0.36
    for k, (cfg, col) in enumerate(zip(["gil", "ft"], [CAT[0], CAT[3]], strict=True)):
        vals: list[float] = []
        sp: list[float] = []
        base = pick(recs, "end_to_end", f"{cfg}/v0_pure")
        for v in variants:
            r = pick(recs, "end_to_end", f"{cfg}/{v}")
            vals.append(med(r) * 1e3 if r else np.nan)
            sp.append(med(base) / med(r) if (r and base) else np.nan)
        bars = ax.barh(ys + (k - 0.5) * h, vals, height=h - 0.04, color=col,
                       label=f"{label(cfg)}")
        bar_labels(ax, bars, sp, fmt="{:.2f}x")
    ax.set_yticks(ys, [vnames[v] for v in variants])
    ax.invert_yaxis()
    ax.set_xlabel("end-to-end time, ms   (bar label = speedup vs pure Python)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.24), ncols=2, frameon=False)
    ax.set_title("Composing techniques on a mixed pipeline")

    ax2 = axes[1]
    stages = [("stage_parse", "parse (json)"), ("stage_validate", "classify"),
              ("stage_aggregate", "aggregate")]
    setups = [("gil/v0_pure", "pure Python"), ("gil/v2_native", "C classify"),
              ("gil/v1_numba", "Numba aggregate")]
    bottom = np.zeros(len(setups))
    xs = np.arange(len(setups))
    for (case, nm), col in zip(stages, [CAT[0], CAT[1], CAT[2]], strict=True):
        vals: list[float] = []
        for impl, _ in setups:
            r = pick(recs, case, impl) or pick(recs, case, "gil/v0_pure")
            vals.append(med(r) * 1e3 if r else 0.0)
        ax2.bar(xs, vals, bottom=bottom, color=col, label=nm, width=0.55,
                edgecolor="#fcfcfb", linewidth=1.5)
        bottom += np.array(vals)
    for x, tot in zip(xs, bottom, strict=True):
        ax2.annotate(f"{tot:.0f} ms", (x, tot), xytext=(0, 3), textcoords="offset points",
                     ha="center", fontsize=7.5, color=INK2)
    ax2.set_xticks(xs, [nm for _, nm in setups])
    ax2.set_ylabel("stage time, ms")
    ax2.grid(axis="x", visible=False)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncols=3)
    ax2.set_title("Where the time sits (per stage)")
    save(fig, "f12_pipeline")


def _build_flavour(rec: Record) -> str:
    """Short description of how an interpreter was built, from its own CONFIG_ARGS."""
    args = (rec["interp"].get("config_args") or "")
    bits: list[str] = []
    if "--enable-optimizations" in args:
        bits.append("PGO")
    if "--with-lto" in args:
        bits.append("LTO")
    if "--enable-framework" in args:
        bits.append("framework")
    return "+".join(bits) if bits else "plain"


def fig14_tier2_jit() -> None:
    """CPython's own experimental JIT against the identical build without it."""
    recs = ok(load("b5_buildcfg-"))
    if not recs:
        print("[fig14] no data")
        return
    rows: list[tuple[str, float]] = []
    for case in B3_CASES:
        b, j = pick(recs, case, "plain"), pick(recs, case, "jit")
        if b and j:
            rows.append((case.replace("_", " "), med(b) / med(j)))
    if not rows:
        print("[fig14] no paired cases")
        return
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    ys = np.arange(len(rows))
    cols = [GOOD if v > 1.02 else (CRIT if v < 0.98 else NEUTRAL) for _, v in rows]
    bars = ax.barh(ys, [r[1] for r in rows], color=cols, height=0.62)
    ax.set_yticks(ys, [r[0] for r in rows])
    bar_labels(ax, bars, [r[1] for r in rows], fmt="{:.3f}x")
    ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    ax.set_xlim(0.85, max(r[1] for r in rows) * 1.14)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("speedup of --enable-experimental-jit over the identical non-JIT build")
    ax.set_title("CPython 3.14.6 tier-2 JIT, same source and toolchain")
    save(fig, "f14_tier2_jit")


def fig15_pypy() -> None:
    """PyPy against CPython 3.14 on the operation suite and on the six kernels."""
    suite = [r for r in ok(load("b3_runtime-")) if r["impl"] in (REF_VERSION, "pypy311")]
    b1 = load("b1_compute-")
    b2 = load("b2_branchy-")
    pypy_k = [r for r in ok(b1) + ok(b2) if is_pypy(r)]
    if not (suite or pypy_k):
        print("[fig15] no data")
        return
    if not suite:
        print(f"[fig15] no operation-suite pair ({REF_VERSION} vs pypy311) -- left panel dropped")
    if not pypy_k:
        print("[fig15] no PyPy kernel records -- right panel dropped")
    ncols = 2 if (suite and pypy_k) else 1
    fig, axes = plt.subplots(1, ncols, figsize=(5.6 * ncols, 3.8))
    if ncols == 2:
        fig.subplots_adjust(wspace=0.52)
    axes = np.atleast_1d(axes)
    ax = axes[0]
    if suite:
        rows: list[tuple[str, float]] = []
        for case in B3_CASES:
            b, j = pick(suite, case, REF_VERSION), pick(suite, case, "pypy311")
            if b and j:
                rows.append((case.replace("_", " "), med(b) / med(j)))
        if len(rows) != len(B3_CASES):
            print(f"[fig15] WARNING: {len(rows)}/{len(B3_CASES)} operation pairs present; "
                  "the caption's count and this panel no longer agree")
        rows.sort(key=lambda r: r[1])
        ys = np.arange(len(rows))
        cols = [GOOD if v > 1.05 else (CRIT if v < 0.95 else NEUTRAL) for _, v in rows]
        bars = ax.barh(ys, [r[1] for r in rows], color=cols, height=0.62)
        ax.set_yticks(ys, [r[0] for r in rows])
        bar_labels(ax, bars, [r[1] for r in rows], fmt="{:.2f}x")
        ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
        ax.set_xscale("log")
        ax.set_xlim(0.2, max(r[1] for r in rows) * 3)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("PyPy speedup over CPython 3.14 (log)")
        ax.set_title("Interpreter-level operations")
    if pypy_k:
        ax2 = axes[-1] if ncols == 2 else axes[0]
        kerns = COMPUTE + BRANCHY
        rows: list[tuple[str, float]] = []
        for k in kerns:
            src = ok(b1) if k in COMPUTE else ok(b2)
            p_ = pick([r for r in src if is_pypy(r)],
                      k, "cpython_loop")
            c_ = pick(only(src), k, "cpython_loop")
            if p_ and c_:
                rows.append((label(k), med(c_) / med(p_)))
        if rows:
            ys = np.arange(len(rows))
            bars = ax2.barh(ys, [r[1] for r in rows], color=CAT[0], height=0.62)
            ax2.set_yticks(ys, [r[0] for r in rows])
            ax2.invert_yaxis()
            bar_labels(ax2, bars, [r[1] for r in rows], fmt="{:.1f}x")
            ax2.axvline(1.0, color=MUTED, lw=0.9, ls="--")
            ax2.set_xlim(0, max(r[1] for r in rows) * 1.2)
            ax2.grid(axis="y", visible=False)
            ax2.set_xlabel("PyPy speedup over CPython 3.14, same pure-Python source")
            ax2.set_title("The six kernels, unmodified")
    save(fig, "f15_pypy")


BUILD_CFGS = [("pgo", "PGO"), ("ltothin", "LTO (thin)"), ("ltofull", "LTO (full)"),
              ("pgo_ltofull", "PGO + full LTO"),
              ("pgo_ltofull_native", "PGO + full LTO + native"),
              ("jit", "tier-2 JIT")]


def fig17_realbuild() -> None:
    """Seven build configurations of one source tree, and where the losing one loses."""
    recs = ok(load("b5_buildcfg-"))
    if not recs:
        print("[fig17] no data")
        return
    cases = [c for c in B3_CASES if pick(recs, c, "plain")]

    def ratio(cfg: str, case: str) -> float:
        a, b = pick(recs, case, "plain"), pick(recs, case, cfg)
        return (med(a) / med(b)) if (a and b) else np.nan

    def geo(cfg: str) -> float:
        rr = [ratio(cfg, k) for k in cases if pick(recs, k, cfg)]
        rr = [r for r in rr if np.isfinite(r)]
        return geomean(rr) if rr else np.nan

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.4), width_ratios=[1.0, 1.15])
    fig.subplots_adjust(wspace=0.38)

    ax = axes[0]
    rows = [(nm, geo(cfg)) for cfg, nm in BUILD_CFGS if np.isfinite(geo(cfg))]
    ys = np.arange(len(rows))
    cols = [GOOD if v > 1.02 else (CRIT if v < 0.98 else NEUTRAL) for _, v in rows]
    bars = ax.barh(ys, [r[1] for r in rows], color=cols, height=0.62)
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.invert_yaxis()
    bar_labels(ax, bars, [r[1] for r in rows], fmt="{:.3f}x")
    ax.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    lo, hi = min(r[1] for r in rows), max(r[1] for r in rows)
    ax.set_xlim(min(0.95, lo * 0.96), hi * 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"geomean over {len(cases)} operations, vs plain ./configure")
    ax.set_title("What each build option is worth")

    ax2 = axes[1]
    prof = sorted(((ratio("pgo_ltofull", c), c) for c in cases
                   if np.isfinite(ratio("pgo_ltofull", c))), reverse=True)
    ys2 = np.arange(len(prof))
    cols2 = [GOOD if v > 1.02 else (CRIT if v < 0.98 else NEUTRAL) for v, _ in prof]
    b2 = ax2.barh(ys2, [v for v, _ in prof], color=cols2, height=0.7)
    ax2.set_yticks(ys2, [label(c) for _, c in prof], fontsize=6.8)
    ax2.invert_yaxis()
    bar_labels(ax2, b2, [v for v, _ in prof], fmt="{:.2f}x")
    ax2.axvline(1.0, color=MUTED, lw=0.9, ls="--")
    ax2.grid(axis="y", visible=False)
    ax2.set_xlabel("PGO + full LTO, per operation, vs plain")
    ax2.set_title("Where the combination gains and loses")

    fig.suptitle("CPython 3.14.6: seven build configurations, one source tree, one compiler",
                 fontsize=10.5, color=INK)
    save(fig, "f17_real_builds")


def main() -> None:
    apply_style()
    for fn in (fig1_compute, fig2_archflags, fig3_breakeven, fig4_divergence, fig5_ffi,
               fig6_versions, fig7_specialization, fig8_cinder, fig9_threads, fig10_ft_tax,
               fig12_pipeline, fig14_tier2_jit, fig15_pypy, fig17_realbuild,
               fig18_jitopts):
        try:
            fn()
        except Exception as exc:
            import traceback
            print(f"[{fn.__name__}] FAILED: {exc!r}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
