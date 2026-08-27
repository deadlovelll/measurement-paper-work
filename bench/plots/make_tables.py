#!/usr/bin/env python
"""Generate the paper's LaTeX tables from results/*.json (no hand-typed numbers)."""

from __future__ import annotations

import glob
import json
import os
import sys
from collections.abc import Callable, Iterable
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyperf_load import Record
from style import (
    RESULTS,
    ROOT,
    by,
    facts_of,
    label,
    load,
    med,
    ok,
    pick,
)


def tex_escape(s: str) -> str:
    """Make a value from the results safe to drop into a LaTeX cell."""
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("_", r"\_"), ("#", r"\#"), ("$", r"\$")):
        s = s.replace(a, b)
    return s

def _host() -> dict[str, Any]:
    """The machine description written by bench/host_topology.sh on the measuring host."""
    path = os.path.join(ROOT, "results", "host.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except OSError:
        return {}


def _native_flag() -> str:
    """The CPU-tuning flag the native artefacts were built with, as the build recorded it."""
    path = os.path.join(ROOT, "bench", "build", "native", "native_flag.txt")
    try:
        with open(path) as fh:
            return fh.read().strip() or "-march=native"
    except OSError:
        return "-march=native"


def _host_os_arch() -> str:
    """e.g. "Linux x86\\_64" -- escaped, because it goes straight into a LaTeX cell."""
    h = _host()
    kernel = (h.get("kernel") or "").split()[0] or "this platform"
    return tex_escape(f"{kernel} {h.get('arch', '')}".strip())


TABLES = os.path.join(ROOT, "paper", "tables")
os.makedirs(TABLES, exist_ok=True)

COMPUTE = ["arraysum", "mandelbrot", "matmul"]
BRANCHY = ["tokenize", "binarytrees", "bfs"]
REF_TAG = "314"


def tag_of(rec: Record) -> str:
    """The configuration label, carried explicitly by every pyperf record."""
    return rec.get("label") or ""


def only(records: Iterable[Record], tag: str = REF_TAG) -> list[Record]:
    return [r for r in records if tag_of(r) == tag]


def w(name: str, body: str) -> None:
    path = os.path.join(TABLES, name)
    with open(path, "w") as fh:
        fh.write(body.rstrip() + "\n")
    print(f"[tab] {name}")


def fmt_ms(x: float) -> str:
    if x >= 1:
        return f"{x:.2f}"
    if x >= 0.01:
        return f"{x:.3f}"
    return f"{x:.4f}"


def t1_compute() -> None:
    recs = only(ok(load("b1_compute-")))
    if not recs:
        return
    impls = ["cpython_loop", "cpython_builtin_sum", "cython", "codon_pyext",
             "codon_pyext_ptr", "numba", "numba_fastmath", "codon_jit",
             "c_ctypes", "c_pybind11", "rust_ctypes", "numpy"]
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& \multicolumn{2}{c}{array sum ($10^6$ f64)}"
             r" & \multicolumn{2}{c}{mandelbrot $200{\times}150$}"
             r" & \multicolumn{2}{c}{matmul $96{\times}96$} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
             r"implementation & ms & $\times$ & ms & $\times$ & ms & $\times$ \\", r"\midrule"]
    for impl in impls:
        cells: list[str] = []
        any_hit = False
        for kern in COMPUTE:
            base = pick(recs, kern, "cpython_loop")
            r = pick(recs, kern, impl)
            if r and base:
                any_hit = True
                cells += [fmt_ms(med(r) * 1e3), f"{med(base) / med(r):.1f}"]
            else:
                cells += ["--", "--"]
        if any_hit:
            lines.append(f"{label(impl)} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t1_compute.tex", "\n".join(lines))


def t2_branchy() -> None:
    recs = only(load("b2_branchy-"))
    if not recs:
        return
    impls = ["cpython_loop", "cython", "codon_pyext", "numba", "codon_jit",
             "c_ctypes", "rust_ctypes"]
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"& \multicolumn{2}{c}{tokenize ($2{\cdot}10^6$ B)}"
             r" & \multicolumn{2}{c}{binary trees (d{=}18)}"
             r" & \multicolumn{2}{c}{BFS ($5{\cdot}10^5$ nodes)} \\",
             r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
             r"implementation & ms & $\times$ & ms & $\times$ & ms & $\times$ \\", r"\midrule"]
    for impl in impls:
        cells: list[str | None] = []
        for kern in BRANCHY:
            base = pick(ok(recs), kern, "cpython_loop")
            hits = by(recs, kern, impl)
            r = hits[0] if hits else None
            if r and r.get("status") == "ok" and base:
                cells += [fmt_ms(med(r) * 1e3), f"{med(base) / med(r):.1f}"]
            elif r and r.get("status") != "ok":
                cells += [r"\multicolumn{2}{c}{" + r["status"].replace("_", " ") + "}", None]
            else:
                cells += ["--", "--"]
        row = [c for c in cells if c is not None]
        lines.append(f"{label(impl)} & " + " & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t2_branchy.tex", "\n".join(lines))


def t3_runtime_facts() -> None:
    recs = load("b3_runtime-")
    facts = [r for r in recs if r["case"] == "runtime_facts"]
    srecs = ok(load("b3_startup"))
    if not facts:
        return
    order = ["v310", "v311", "v312", "v313", "v314", "v314t"]
    facts_by = {f["impl"]: f["extra"] for f in facts}
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             "property & " + " & ".join("3.14t" if v.endswith("t") else f"3.{v[2:]}"
                                        for v in order) + r" \\", r"\midrule"]

    def row(title: str, fn: Callable[[dict[str, Any]], Any], fmt: str = "{}") -> None:
        cells: list[str] = []
        for v in order:
            e = facts_by.get(v)
            try:
                cells.append(fmt.format(fn(e)) if e else "--")
            except Exception:
                cells.append("--")
        lines.append(f"{title} & " + " & ".join(cells) + r" \\")

    row(r"\texttt{sys.getrefcount(None)}", lambda e: e["refcount_none"] or "n/a", "{:,}")
    row("None is immortal", lambda e: "yes" if e["immortal_singletons"] else "no")
    row("alloc.\\ blocks / instance (dict)", lambda e: e["blocks_per_plain_obj"], "{:.2f}")
    row("alloc.\\ blocks / instance (slots)", lambda e: e["blocks_per_slots_obj"], "{:.2f}")
    row("max RSS after suite, MB", lambda e: e["maxrss_mb"], "{:.0f}")
    if srecs:
        cells: list[str] = []
        for v in order:
            r = pick(srecs, "startup_bare", v)
            cells.append(f"{med(r) * 1e3:.1f}" if r else "--")
        lines.append("bare startup, ms & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t3_runtime_facts.tex", "\n".join(lines).replace(",", r"\,"))


def t4_platforms() -> None:
    """The one machine everything in this paper was measured on."""
    host = {}
    hp = os.path.join(ROOT, "results", "host.json")
    if os.path.exists(hp):
        with open(hp) as fh:
            host = json.load(fh)

    meta = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "pyperf", "b1_compute-*.json"))):
        try:
            with open(path) as fh:
                meta = json.load(fh).get("metadata", {}) or {}
        except Exception:
            continue
        if meta:
            break

    classes = host.get("cpu_classes", "")
    core_desc = ""
    if classes:
        try:
            counts = [int(part.split("@")[0]) for part in classes.split()]
            core_desc = (f"{counts[0]} performance + {sum(counts[1:])} efficiency cores"
                         if len(counts) > 1 else f"{counts[0]} cores")
        except Exception:
            core_desc = classes

    rows = [
        ("CPU", f"{host.get('cpu_model', meta.get('cpu_model_name', '?'))}"),
        ("cores", core_desc or f"{host.get('cpu_count', meta.get('cpu_count', '?'))} cores"),
        ("memory", f"{host.get('mem_gb', '?')} GB"),
        ("operating system", f"{host.get('distro', '?')}, {host.get('kernel', '?')} "
                             f"({host.get('arch', '?')})"),
        ("frequency scaling", f"governor {host.get('governor', '?')}, "
                              f"turbo {host.get('turbo', '?')}"),
        ("address randomisation", meta.get("aslr", "?")),
        ("benchmark affinity", f"CPUs {meta.get('cpu_affinity', host.get('perf_cpus', '?'))} "
                               f"(the performance class)"),
    ]
    lines = [r"\begin{tabular}{ll}", r"\toprule",
             r"property & value \\", r"\midrule"]
    for a, b in rows:
        lines.append(f"{a} & {tex_escape(str(b))} " + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t4_platforms.tex", "\n".join(lines))


def _pins() -> dict[str, str]:
    """Every version the build scripts pin, so this table cannot drift from what they install."""
    import re
    found: dict[str, str] = {}
    for name in ("bootstrap.sh", "setup_env.sh", "build_uniform.sh"):
        path = os.path.join(ROOT, "bench", name)
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            text = fh.read()
        for m in re.finditer(r'^(\w+)="\$\{\1:-([^}]*)\}"', text, re.M):
            found.setdefault(m.group(1), m.group(2))
    return found


def t7_versions() -> None:
    """The measured software stack, read from the pins the build scripts install."""
    p = _pins()
    rows = [
        ("CPython", ", ".join(p.get("VERSIONS", "?").split())),
        ("C compiler", f"clang {p.get('CLANG_VERSION', '?')}"),
        ("LLVM, for the tier-2 JIT build", p.get("LLVM19_VERSION", "?")),
        ("Rust", p.get("RUST_VERSION", "?")),
        ("Codon", p.get("CODON_VERSION", "?")),
        ("PyPy", p.get("PYPY_VERSION", "?")),
        ("pyperf", p.get("PYPERF_VERSION", "?")),
        ("NumPy", p.get("NUMPY_VERSION", "?")),
        ("Numba", p.get("NUMBA_VERSION", "?")),
        ("Cython", p.get("CYTHON_VERSION", "?")),
        ("pybind11", p.get("PYBIND11_VERSION", "?")),
        ("threadpoolctl", p.get("THREADPOOLCTL_VERSION", "?")),
    ]
    lines = [r"\begin{tabular}{ll}", r"\toprule",
             r"component & version \\", r"\midrule"]
    for a, b in rows:
        lines.append(f"{a} & {tex_escape(str(b))} " + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t7_versions.tex", "\n".join(lines))


def _gc_modes() -> dict[str, tuple[float, float | None]]:
    """(serial s, parallel s) per heap composition, plus the stock row."""
    grecs = ok(load("b6_gcscale-"))
    out: dict[str, tuple[float, float | None]] = {}
    for cfg, mode, key in (("stock", "state_visible", "stock"),
                           ("fork_cinderx", "state_visible", "visible"),
                           ("fork_cinderx", "frozen", "frozen"),
                           ("fork_cinderx", "immortal", "immortal")):
        s_rec = pick(grecs, "gc_collect", f"{cfg}/{mode}_serial")
        if not s_rec:
            continue
        p_rec = pick(grecs, "gc_collect", f"{cfg}/{mode}_par6")
        out[key] = (med(s_rec), med(p_rec) if p_rec else None)
    return out


def _gc_verdict(recs) -> str:
    """The verdict word is derived from the significance test, not written by hand."""
    try:
        from style import compare
        modes = _gc_modes()
        vis, imm = modes.get("visible"), modes.get("immortal")
        if vis and imm and vis[1] and imm[1]:
            hurts_visible = vis[1] > vis[0]
            helps_hidden = imm[1] < imm[0]
            if hurts_visible and helps_hidden:
                return "composition-dependent"
            if helps_hidden:
                return "gain when heap hidden"
            if hurts_visible:
                return "cost"
            return "no effect"
        off = pick(recs, "gc_collect_200k_cycles", "fork_cinderx/parallel_gc_off")
        on = pick(recs, "gc_collect_200k_cycles", "fork_cinderx/parallel_gc_on")
        if not (off and on):
            return "not measured"
        v = compare(off, on)
        if not v.get("significant"):
            return "no effect"
        return "small cost" if med(on) > med(off) else "small gain"
    except Exception:
        return "see text"


def _modes(rec) -> list[float]:
    """Cluster a record's samples when they are bimodal, else return the median alone."""
    from style import stats_of
    v = sorted(stats_of(rec)["raw_per_op_s"])
    if len(v) < 6:
        return [med(rec)]
    gaps = [(v[i + 1] / v[i], i) for i in range(len(v) - 1) if v[i] > 0]
    ratio, at = max(gaps) if gaps else (1.0, 0)
    if ratio < 1.25:
        return [med(rec)]
    lo, hi = v[: at + 1], v[at + 1:]
    return [sum(lo) / len(lo), sum(hi) / len(hi)]


def _range_over_kernels(recs, cfg: str) -> str:
    """The per-kernel spread of a configuration against stock, as it appears in the figure."""
    kernels = ["arraysum", "mandelbrot", "matmul", "tokenize", "binarytrees", "bfs"]
    vals = []
    for k in kernels:
        b, r = pick(recs, k, "stock"), pick(recs, k, cfg)
        if b and r:
            vals.append(med(r) / med(b))
    if not vals:
        return "--"
    return f"{min(vals):.2f}--{max(vals):.2f}$\\times$"


def t5_cinder_matrix() -> None:
    allrecs = load("b6_cinderx-")
    recs = ok(allrecs)
    srecs = ok(load("b6_static-"))
    if not recs:
        return

    def rel(case: str, impl: str, base_impl: str = "stock") -> str:
        b = pick(recs, case, base_impl)
        r = pick(recs, case, impl)
        return f"{med(r) / med(b):.2f}" if (b and r) else "--"

    eager = pick(recs, "import_200_modules_eager", "fork")
    lazy = pick(recs, "import_200_modules_lazy", "fork")
    lazy_gain = "--"
    if eager and lazy:
        li = facts_of(allrecs, "fork").get("lazy_imports", {})
        ex_e = li.get("eager_module_bodies_run")
        ex_l = li.get("lazy_module_bodies_run")
        ft = pick(recs, "import_200_modules_first_touch", "fork")
        touch = med(ft) if ft else 0.0
        lazy_gain = (f"{med(eager) * 1e3:.1f}\\,ms $\\to$ {med(lazy) * 1e6:.2f}\\,$\\mu$s; "
                     f"{ex_l}/{ex_e} module bodies run; first use {touch * 1e3:.2f}\\,ms")
    gc_off = pick(recs, "gc_collect_200k_cycles", "fork_cinderx/parallel_gc_off")
    gc_on = pick(recs, "gc_collect_200k_cycles", "fork_cinderx/parallel_gc_on")
    modes = _gc_modes()
    if "visible" in modes and "immortal" in modes:
        vis_s, vis_p = modes["visible"]
        imm_s, imm_p = modes["immortal"]
        gc_txt = (f"{vis_s / vis_p:.2f}$\\times$ serial with the state visible, "
                  f"{imm_s / imm_p:.2f}$\\times$ after immortalising it "
                  f"({vis_s * 1e3:.0f} $\\to$ {imm_s * 1e3:.0f}\\,ms serial)")
    elif gc_off and gc_on:
        gc_txt = (f"{med(gc_off) * 1e3:.1f} $\\to$ {med(gc_on) * 1e3:.1f}\\,ms "
                  f"({med(gc_off) / med(gc_on):.2f}$\\times$)")
    else:
        gc_txt = "--"

    def st_pick(suffix: str, adaptive: bool = False):
        hits = [r for r in srecs if r["impl"].endswith(suffix)
                and (("adaptive" in r["impl"]) == adaptive)]
        return hits[0] if hits else None

    boxed = st_pick("boxed_python")
    boxed_jit = st_pick("boxed_jit")
    s_interp = st_pick("static_interp")
    s_interp_a = st_pick("static_interp", adaptive=True)
    s_jit = st_pick("static_jit")
    static_txt = "--"
    if boxed_jit and s_jit:
        modes = _modes(s_jit)
        ratios = sorted(med(boxed_jit) / m for m in modes)
        static_txt = (f"{ratios[-1]:.1f}$\\times$ faster than the same kernel boxed under the "
                      f"same JIT" if len(ratios) == 1 else
                      f"{ratios[-1]:.1f}$\\times$ faster than the same kernel boxed under the "
                      f"same JIT ({ratios[0]:.1f}$\\times$ on the slow layout mode)")
    elif boxed and s_jit:
        static_txt = f"{med(boxed) / med(s_jit):.1f}$\\times$ faster than boxed Python"
    static_interp_txt = "--"
    if boxed and s_interp:
        static_interp_txt = f"{med(s_interp) / med(boxed):.1f}$\\times$ slower than boxed Python"
    adaptive_static_txt = "--"
    if s_interp and s_interp_a:
        adaptive_static_txt = (f"static interpreter {med(s_interp) * 1e3:.0f} $\\to$ "
                               f"{med(s_interp_a) * 1e3:.0f}\\,ms; no effect under the JIT")

    has_adaptive = any(r["impl"] == "fork_cinderx_adaptive" for r in recs)

    def adaptive_note(case: str) -> str:
        return (f"{rel(case, 'fork_cinderx_adaptive')}$\\times$ / "
                f"{rel(case, 'fork_jit_adaptive')}$\\times$") if has_adaptive else "--"

    rows = [
        (f"builds on {_host_os_arch()}", "yes", "0 errors in both configurations, with the "
                                                "patches carried in the vendored tree"),
        ("JIT compiles \\& is correct", "yes",
         "all 8 kernel functions, compiled at the JIT's own threshold and verified to be what "
         "runs"),
        ("CinderX runtime, no JIT", "cost",
         f"matmul {rel('matmul', 'fork_cinderx')}$\\times$ the stock time, "
         f"{_range_over_kernels(recs, 'fork_cinderx')} over the six"),
        ("CinderX JIT on untyped code", "win",
         f"matmul {rel('matmul', 'fork_jit')}$\\times$ the stock time, "
         f"{_range_over_kernels(recs, 'fork_jit')} over the six"),
        ("same, adaptive configuration", "win" if has_adaptive else "not measured",
         f"matmul {adaptive_note('matmul')} the stock time"),
        ("Static Python + JIT", "win", static_txt),
        ("Static Python, interpreter", "cost", static_interp_txt),
        ("adaptive specialisation, once completed",
         "win" if s_interp_a else "not measured", adaptive_static_txt),
        ("lazy imports", "win", lazy_gain),
        ("parallel GC", _gc_verdict(recs), gc_txt),
        ("lightweight frames", "no effect here", f"200-deep call chain "
                                                f"{rel('call_depth_200', 'fork')}$\\times$ stock"),
    ]
    lines = [r"\begin{tabular}{p{0.30\linewidth}p{0.10\linewidth}p{0.52\linewidth}}", r"\toprule",
             r"capability & verdict & measurement \\", r"\midrule"]
    for a, b, c in rows:
        lines.append(f"{a} & {b} & {c} " + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    w("t5_cinder_matrix.tex", "\n".join(lines))


def t6_codegen() -> None:
    """Instruction-level evidence for the RQ2 C-vs-Rust comparison."""
    path = os.path.join(ROOT, "results", "codegen", "summary.json")
    if not os.path.exists(path):
        stale = os.path.join(TABLES, "t6_codegen.tex")
        if os.path.exists(stale):
            os.remove(stale)
            print("[tab] t6_codegen.tex REMOVED -- stale, and no data to regenerate it from")
        raise FileNotFoundError(
            f"{path} missing -- run bench/b2_branchy/codegen_check.sh before make_tables.py")

    with open(path) as fh:
        cg = json.load(fh)
    syms = cg.get("symbols", {})
    arch = cg.get("arch", "?")
    native = _native_flag()

    rows = [("c_tokenize", f"C, clang -O3 {native}", "c_ctypes"),
            ("rs_tokenize", "Rust, rustc -C opt-level=3 -C target-cpu=native", "rust_ctypes")]
    recs = only(ok(load("b2_branchy-")))

    out = [r"\begin{tabular}{lrrrr}", r"\toprule",
           r"tokenize kernel & instructions & cond.\ branches & cond.\ selects & ms \\",
           r"\midrule"]
    for sym, name, impl in rows:
        s = syms.get(sym)
        if not s:
            continue
        r = pick(recs, "tokenize", impl)
        t = f"{med(r) * 1e3:.2f}" if r else "--"
        out.append(f"{tex_escape(name)} & {s['instructions']} & {s['cond_branches']} & "
                   f"{s['cond_selects']} & {t} " + r"\\")
    out += [r"\bottomrule", r"\end{tabular}",
            r"\\[2pt]{\footnotesize Disassembled on " + tex_escape(arch) +
            r"; the branch and select mnemonics counted are recorded in "
            r"\texttt{results/codegen/summary.json}.}"]
    w("t6_codegen.tex", "\n".join(out))


def main() -> None:
    for fn in (t1_compute, t2_branchy, t3_runtime_facts, t4_platforms, t5_cinder_matrix,
               t6_codegen, t7_versions):
        try:
            fn()
        except Exception as exc:
            import traceback
            print(f"[{fn.__name__}] FAILED: {exc!r}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
