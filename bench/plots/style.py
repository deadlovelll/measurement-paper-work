"""Shared figure style and data access for the paper's figures."""

from __future__ import annotations

import os
import re
import statistics
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyperf_load
from pyperf_load import Comparison, Record, Stats

if TYPE_CHECKING:
    from matplotlib.artist import Artist
    from matplotlib.axes import Axes
    from matplotlib.container import BarContainer
    from matplotlib.figure import Figure

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "results")
FIGS = os.path.join(ROOT, "figures")
os.makedirs(FIGS, exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8983"
GRID = "#e6e5e1"

CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#e87ba4", "#008300"]
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
GOOD = "#0ca30c"
CRIT = "#d03b3b"
NEUTRAL = "#b9b8b2"


def apply_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 8.5,
        "font.family": "sans-serif",
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK2,
        "axes.titlesize": 9.5,
        "axes.titleweight": "semibold",
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.8,
        "lines.markersize": 4.5,
        "figure.dpi": 140,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,
    })


def seq_colors(n: int) -> list[str]:
    """n ordered steps from the sequential ramp, dark enough to read on white."""
    usable = SEQ[1:]
    if n <= len(usable):
        idx = [round(i * (len(usable) - 1) / max(1, n - 1)) for i in range(n)]
        return [usable[i] for i in idx]
    return [usable[i % len(usable)] for i in range(n)]


def load(prefix: str) -> list[Record]:
    """All records for a suite, read from the pyperf result files."""
    return pyperf_load.load(prefix)


def facts_of(records: Sequence[Record], label: str | None = None) -> dict[str, Any]:
    """The sidecar facts for a configuration."""
    for r in records:
        if r.get("status") == "facts" and (label is None or r.get("label") == label):
            return r.get("extra") or {}
    return {}


def compare(a: Record, b: Record) -> Comparison:
    """Significance test between two records, using pyperf's own test."""
    return pyperf_load.compare(stats_of(a)["raw_per_op_s"], stats_of(b)["raw_per_op_s"])


def ok(records: Iterable[Record]) -> list[Record]:
    return [r for r in records if r.get("status") == "ok" and r.get("stats")]


def is_pypy(rec: Record) -> bool:
    """Whether a record came from PyPy."""
    return (rec["interp"].get("implementation") or "").lower() == "pypy"


def stats_of(rec: Record) -> Stats:
    """The measurement carried by a record."""
    s = rec["stats"]
    if s is None:
        raise TypeError(f"{rec['case']}/{rec['impl']} carries no timing")
    return s


def med(rec: Record | None) -> float:
    if rec is None or rec["stats"] is None:
        raise TypeError("med() received no timed record: check pick() before calling it")
    return rec["stats"]["median_s"]


def by(records: Iterable[Record], case: str | None = None,
       impl: str | None = None) -> list[Record]:
    out = list(records)
    if case is not None:
        out = [r for r in out if r["case"] == case]
    if impl is not None:
        out = [r for r in out if r["impl"] == impl]
    return out


def pick(records: Iterable[Record], case: str, impl: str) -> Record | None:
    hits = by(records, case, impl)
    return hits[0] if hits else None


def geomean(xs: Iterable[float | None]) -> float:
    vals = [x for x in xs if x and x > 0]
    if not vals:
        return float("nan")
    return statistics.geometric_mean(vals)


HOOKS: list[Callable[[Figure, str], None]] = []


def fit_labels(fig: Figure) -> None:
    """Grow each axis until every label it carries fits inside it."""
    fig.canvas.draw()
    for ax in fig.axes:
        texts = [t for t in ax.texts if t.get_text()]
        if not texts:
            continue
        abox = ax.get_window_extent()
        inv = ax.transData.inverted()
        for axis in ("x", "y"):
            lo, hi = (ax.get_xlim() if axis == "x" else ax.get_ylim())
            flip = hi < lo
            over_hi = over_lo = 0.0
            for t in texts:
                tb = t.get_window_extent()
                if axis == "x":
                    over_hi = max(over_hi, tb.x1 - abox.x1)
                    over_lo = max(over_lo, abox.x0 - tb.x0)
                else:
                    over_hi = max(over_hi, tb.y1 - abox.y1)
                    over_lo = max(over_lo, abox.y0 - tb.y0)
            if over_hi <= 0 and over_lo <= 0:
                continue
            span_px = (abox.width if axis == "x" else abox.height)
            if span_px <= 0:
                continue
            log = (ax.get_xscale() if axis == "x" else ax.get_yscale()) == "log"
            if log:
                import math
                d_lo, d_hi = math.log10(lo), math.log10(hi)
                per_px = (d_hi - d_lo) / span_px
                cap = 0.25 * (d_hi - d_lo)
                g_lo = min(max(0.0, over_lo + 4) * per_px, cap)
                g_hi = min(max(0.0, over_hi + 4) * per_px, cap)
                new_lo = 10 ** (d_lo - g_lo)
                new_hi = 10 ** (d_hi + g_hi)
            else:
                per_px = (hi - lo) / span_px
                new_lo = lo - max(0.0, over_lo + 4) * per_px
                new_hi = hi + max(0.0, over_hi + 4) * per_px
                if flip:
                    new_lo, new_hi = lo + max(0.0, over_lo + 4) * per_px, \
                        hi - max(0.0, over_hi + 4) * per_px
            if axis == "x":
                ax.set_xlim(new_lo, new_hi)
            else:
                ax.set_ylim(new_lo, new_hi)
        del inv
    fig.canvas.draw()


def legend_below(fig: Figure, handles: Sequence[Artist], labels: Sequence[str],
                 ncols: int = 3, y: float = -0.02) -> None:
    """One legend for the whole figure, outside the data area."""
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, y),
               ncols=ncols, frameon=False, fontsize=8)


def save(fig: Figure, name: str) -> None:
    fit_labels(fig)
    for hook in HOOKS:
        hook(fig, name)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGS, f"{name}.{ext}"))
    plt.close(fig)
    print(f"[fig] {name}.pdf/.png")


def bar_labels(ax: Axes, bars: BarContainer, values: Sequence[float | None],
               fmt: str = "{:.1f}x", color: str = INK2, horizontal: bool = True,
               inside_frac: float = 0.82) -> None:
    """Direct labels on bar ends."""
    for b, v in zip(bars, values, strict=True):
        if v is None or v != v:
            continue
        if horizontal:
            lo, hi = ax.get_xlim()
            frac = (b.get_width() - lo) / (hi - lo) if hi != lo else 0.0
            if frac > inside_frac:
                ax.annotate(fmt.format(v), (b.get_width(), b.get_y() + b.get_height() / 2),
                            xytext=(-3, 0), textcoords="offset points", va="center",
                            ha="right", fontsize=7.5, color=SURFACE)
            else:
                ax.annotate(fmt.format(v), (b.get_width(), b.get_y() + b.get_height() / 2),
                            xytext=(3, 0), textcoords="offset points", va="center",
                            ha="left", fontsize=7.5, color=color)
        else:
            lo, hi = ax.get_ylim()
            frac = (b.get_height() - lo) / (hi - lo) if hi != lo else 0.0
            if frac > inside_frac:
                ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, -3), textcoords="offset points", ha="center",
                            va="top", fontsize=7.5, color=SURFACE)
            else:
                ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, 2), textcoords="offset points", ha="center",
                            va="bottom", fontsize=7.5, color=color)


B3_CASES = ["int_arith", "float_arith", "func_call", "method_call", "attr_get",
            "attr_get_slots", "attr_set", "create_plain_obj", "create_slots_obj",
            "create_dict", "create_tuple", "list_append", "dict_setitem",
            "str_format_join", "exception_roundtrip", "gc_collect_100k_cycles"]


IMPL_LABEL = {
    "cpython_loop": "CPython loop",
    "cpython_builtin_sum": "CPython sum()",
    "numpy": "NumPy",
    "cython": "Cython",
    "numba": "Numba",
    "numba_fastmath": "Numba fastmath",
    "c_ctypes": "C (ctypes)",
    "c_pybind11": "C (pybind11)",
    "rust_ctypes": "Rust (ctypes)",
    "codon_pyext": "Codon AOT",
    "codon_pyext_ptr": "Codon AOT (ptr)",
    "codon_jit": "Codon JIT",
    "python_function": "Python function",
    "c_O0": "clang -O0",
    "c_O2": "clang -O2",
    "c_O3": "clang -O3",
    "c_O3native": "-O3 -mcpu=native",
    "c_O3native_novec": "+ no vectorise",
    "c_O3native_ffast": "+ -ffast-math",
    "stock": "CPython 3.14.6",
    "fork": "Cinder fork",
    "fork_cinderx": "+ CinderX runtime",
    "fork_jit": "+ CinderX JIT",
    "fork_cinderx_adaptive": "+ CinderX runtime, adaptive on",
    "fork_jit_adaptive": "+ CinderX JIT, adaptive on",
    "base": "default",
    "lto": "LTO",
    "pgo": "PGO",
    "pgo_lto_native": "PGO+LTO+native",
    "gil": "3.14 (GIL)",
    "ft_gil": "3.14t, GIL on",
    "ft": "3.14t, GIL off",
}

CASE_LABEL = {
    "arraysum": "array sum (1e6 f64)",
    "mandelbrot": "mandelbrot 200x150",
    "matmul": "matmul 96x96",
    "tokenize": "tokenize (2e6 bytes)",
    "binarytrees": "binary trees (d=18)",
    "bfs": "graph BFS (5e5 nodes)",
    "py_arith": "pure-Python arithmetic",
    "py_branchy": "pure-Python branchy",
    "c_ffi_uniform": "C kernel, balanced",
    "c_ffi_mandelbrot": "C kernel, imbalanced",
}


def label(key: str) -> str:
    return IMPL_LABEL.get(key, CASE_LABEL.get(key, key))


_SIZE_FIELD = {"arraysum": "vec_n", "tokenize": "tok_n", "bfs": "bfs_n"}


def _si(n: float) -> str:
    exp = len(str(int(n))) - 1
    return f"{n / 10 ** exp:g}e{exp}"


def sized_label(key: str, params: dict[str, Any]) -> str:
    """Kernel label whose size annotation is taken from the record being plotted.

    CASE_LABEL carries the RQ1/RQ2 workload sizes, and RQ4 runs the same three branchy kernels
    smaller. A figure over b6 records that labels its rows from CASE_LABEL therefore annotates
    its own bars with another suite's parameters. Only the number is substituted, so a
    translated label keeps its translation.
    """
    text = label(key)
    if key == "binarytrees" and "tree_depth" in params:
        return re.sub(r"d=\d+", f"d={params['tree_depth']}", text, count=1)
    field = _SIZE_FIELD.get(key)
    if field and field in params:
        return re.sub(r"\d+(?:\.\d+)?e\d+", _si(params[field]), text, count=1)
    return text
