#!/usr/bin/env python
"""RQ4 driver: the Cinder fork and CinderX."""

from __future__ import annotations

import atexit
import compileall
import gc
import importlib
import os
import shutil
import sys
import tempfile
import textwrap
import types
from collections.abc import Sequence
from typing import Any, NoReturn

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, os.path.join(BENCH, "b1_compute"))
sys.path.insert(0, os.path.join(BENCH, "b2_branchy"))

import branchy_py as B  # noqa: E402
import kernels_py as K  # noqa: E402
import pyperf  # noqa: E402
from mp_pyperf import Suite  # noqa: E402

PARAMS = {"vec_n": 1_000_000, "mb_w": 200, "mb_h": 150, "mb_iter": 30, "mat_n": 96,
          "tok_n": 200_000, "tree_depth": 16, "bfs_n": 200_000}

KERNELS = [("arraysum", "compute"), ("mandelbrot", "compute"), ("matmul", "compute"),
           ("tokenize", "branchy"), ("binarytrees", "branchy"), ("bfs", "branchy")]


WARMUP_PARAMS = {"vec_n": 64, "mb_w": 8, "mb_h": 6, "mb_iter": 4, "mat_n": 4,
                 "tok_n": 256, "tree_depth": 4, "bfs_n": 64}

JIT_COMPILE_AFTER = 2


def check_jit_env(expected: str) -> dict[str, str]:
    """Fail unless the JIT options this run is *about* are present in this process."""
    seen: dict[str, str] = {}
    for item in filter(None, (x.strip() for x in expected.split(","))):
        name, _, value = item.partition("=")
        actual = os.environ.get(name)
        if actual != value:
            sys.exit(f"{name} is {actual!r} in this process, expected {value!r}: the "
                     f"configuration under test did not reach it. Pass "
                     f"--inherit-environ={name} so pyperf keeps it for the workers.")
        seen[name] = value
    return seen


def setup_cinderx(use_jit: bool, funcs: Sequence[Any], compile_after: int = JIT_COMPILE_AFTER
                  ) -> dict[str, Any]:
    """Initialise CinderX; optionally get every kernel compiled by the JIT."""
    info: dict[str, Any] = {"cinderx": False, "jit": False, "compiled": [], "failed": []}
    import cinderx  # ty: ignore[unresolved-import]

    cinderx.init()
    info["cinderx"] = True
    info["version"] = getattr(cinderx, "__version__", "?")
    try:
        cinderx.install_frame_evaluator()
        info["frame_evaluator"] = True
    except Exception as exc:
        info["frame_evaluator"] = f"failed: {exc!r}"
    if use_jit:
        import cinderx.jit as jit  # ty: ignore[unresolved-import]

        if compile_after >= 0:
            jit.compile_after_n_calls(compile_after)
        info["compile_after_n_calls"] = jit.get_compile_after_n_calls()
        warm = kernel_table(WARMUP_PARAMS)
        for call in warm.values():
            for _ in range(max(compile_after, 0) + 1):
                call()
        for name, fn in funcs:
            try:
                if not jit.is_jit_compiled(fn):
                    info["failed"].append(f"{name}: not compiled after warm-up")
                    continue
                before = jit.count_interpreted_calls(fn)
                for call in warm.values():
                    call()
                if jit.count_interpreted_calls(fn) != before:
                    info["failed"].append(f"{name}: compiled but still interpreted")
                    continue
                info["compiled"].append(name)
            except Exception as exc:
                info["failed"].append(f"{name}: {type(exc).__name__}: {exc}")
        info["jit"] = bool(info["compiled"]) and not info["failed"]
    return info


def kernel_table(p: dict[str, Any]) -> dict[str, Any]:
    a = K.make_vector(p["vec_n"])
    ma, mb = K.make_matrices(p["mat_n"])
    mc = [0.0] * (p["mat_n"] ** 2)
    data = B.make_bytes(p["tok_n"])
    n, m = p["vec_n"], p["mat_n"]
    w, h, mx = p["mb_w"], p["mb_h"], p["mb_iter"]
    return {
        "arraysum": lambda: K.arraysum_py(a, n),
        "mandelbrot": lambda: K.mandelbrot_py(w, h, mx),
        "matmul": lambda: K.matmul_py(ma, mb, mc, m),
        "tokenize": lambda: B.tokenize_py(data, p["tok_n"]),
        "binarytrees": lambda: B.binarytrees_py(p["tree_depth"]),
        "bfs": lambda: B.bfs_py(p["bfs_n"], 0),
    }


JIT_TARGETS = [
    ("arraysum_py", K.arraysum_py), ("mandelbrot_py", K.mandelbrot_py),
    ("matmul_py", K.matmul_py), ("tokenize_py", B.tokenize_py),
    ("binarytrees_py", B.binarytrees_py), ("bfs_py", B.bfs_py),
    ("_build", B._build), ("_check", B._check),
]


def bench_kernels(suite: Suite, label: str, p: dict[str, Any]) -> None:
    state: dict[str, Any] = {}

    def table() -> dict[str, Any]:
        if "t" not in state:
            state["t"] = kernel_table(p)
        return state["t"]

    for name, family in KERNELS:
        def time_fn(loops: int, name: str = name) -> float:
            fn = table()[name]
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        suite.bench_time(case=name, impl=label, time_fn=time_fn, params=p, note=family)


def bench_frames(suite: Suite, label: str, p: dict[str, Any]) -> None:
    """Frame-creation and traceback cost — what 'lightweight frames' is supposed to improve."""
    def deep(n: int) -> int:
        if n == 0:
            return 1
        return deep(n - 1) + 0

    suite.bench(case="call_depth_200", impl=label, params=p, fn=lambda: deep(200),
                note="200 nested Python calls (frame push/pop cost)")

    def raise_deep(n: int) -> NoReturn:
        if n == 0:
            raise ValueError("boom")
        raise_deep(n - 1)

    import traceback

    def tb_cost() -> int:
        try:
            raise_deep(50)
        except ValueError:
            return len(traceback.format_exc())

    suite.bench(case="traceback_depth_50", impl=label, params=p, fn=tb_cost,
                note="raise + format_exc across 50 frames (frame materialisation)")

    def introspect() -> int:
        f = sys._getframe()
        d = 0
        while f is not None:
            d += len(f.f_locals)
            f = f.f_back
        return d

    def introspect_deep(n: int) -> int:
        if n == 0:
            return introspect()
        return introspect_deep(n - 1)

    suite.bench(case="frame_walk_depth_100", impl=label, params=p,
                fn=lambda: introspect_deep(100),
                note="sys._getframe walk + f_locals materialisation over 100 frames")


def bench_parallel_gc(suite: Suite, label: str, p: dict[str, Any]) -> None:
    """gc.collect() latency on a large cyclic graph, CinderX parallel GC off vs on."""
    import cinderx  # ty: ignore[unresolved-import]

    n_obj = 200_000

    def make_garbage() -> None:
        junk: list[dict[str, Any]] = []
        for _ in range(n_obj // 2):
            a: dict[str, Any] = {}
            b: dict[str, Any] = {"peer": a}
            a["peer"] = b
            junk.append(a)
        junk.clear()

    try:
        cinderx.enable_parallel_gc()
        cinderx.disable_parallel_gc()
        have_parallel = True
    except Exception as exc:
        have_parallel = False
        suite.unavailable(case="gc_collect_200k_cycles", impl=f"{label}/parallel_gc_on",
                          note=repr(exc)[:200])

    states = ("off", "on") if have_parallel else ("off",)
    for state in states:
        def time_gc(loops: int, state: str = state) -> float:
            if state == "on":
                cinderx.enable_parallel_gc()
            else:
                try:
                    cinderx.disable_parallel_gc()
                except Exception:
                    pass
            total = 0.0
            for _ in range(loops):
                make_garbage()
                t0 = pyperf.perf_counter()
                gc.collect()
                total += pyperf.perf_counter() - t0
            return total

        suite.bench_time(case="gc_collect_200k_cycles", impl=f"{label}/parallel_gc_{state}",
                         time_fn=time_gc, params=p,
                         note=f"{n_obj} objects in reference cycles, parallel GC {state}")


N_LAZY_MODULES = 200
LAZY_PKG = "genpkg"
LAZY_IMPORT = compile(f"import {LAZY_PKG}.main as m", "<import_200_modules>", "exec")
LAZY_NAMES = ([LAZY_PKG, f"{LAZY_PKG}.main"]
              + [f"{LAZY_PKG}.m{i:03d}" for i in range(N_LAZY_MODULES)])


def gen_lazy_package(root: str, n_mods: int) -> None:
    pkg = os.path.join(root, LAZY_PKG)
    os.makedirs(pkg, exist_ok=True)
    open(os.path.join(pkg, "__init__.py"), "w").close()
    for i in range(n_mods):
        with open(os.path.join(pkg, f"m{i:03d}.py"), "w") as fh:
            fh.write(textwrap.dedent(f'''\
                TABLE = {{k: k * k for k in range(200)}}
                def value() -> int:
                    return sum(TABLE.values()) + {i}
                CONST = value()
                '''))
    with open(os.path.join(pkg, "main.py"), "w") as fh:
        for i in range(n_mods):
            fh.write(f"from {LAZY_PKG} import m{i:03d}\n")
        fh.write("\ndef touch_one():\n    return m000.CONST\n")


def lazy_package(state: dict[str, Any]) -> None:
    """Write the package and byte-compile it, once per process and never inside a timing."""
    if "root" in state:
        return
    root = tempfile.mkdtemp(prefix="mp_lazy_")
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    gen_lazy_package(root, N_LAZY_MODULES)
    compileall.compile_dir(os.path.join(root, LAZY_PKG), quiet=2)
    sys.path.insert(0, root)
    state["root"] = root


def purge_lazy_package() -> None:
    """Put the process back in front of the import, so the next one is a first import again."""
    for name in LAZY_NAMES:
        sys.modules.pop(name, None)


def module_bodies_run() -> int:
    return sum(1 for k in sys.modules
               if k.startswith(f"{LAZY_PKG}.m") and k != f"{LAZY_PKG}.main")


def bench_lazy_imports(suite: Suite, label: str, p: dict[str, Any]) -> None:
    """Import latency of a 200-module dependency graph: eager vs fork-native lazy imports."""
    state: dict[str, Any] = {}
    have_lazy = hasattr(importlib, "set_lazy_imports")

    def time_import(loops: int, lazy: bool) -> float:
        lazy_package(state)
        if lazy:
            importlib.set_lazy_imports()  # ty: ignore[unresolved-attribute]
        total = 0.0
        for _ in range(loops):
            purge_lazy_package()
            ns: dict[str, Any] = {}
            t0 = pyperf.perf_counter()
            exec(LAZY_IMPORT, ns)
            total += pyperf.perf_counter() - t0
        return total

    suite.bench_time(case="import_200_modules_eager", impl=label, params=p,
                     time_fn=lambda loops: time_import(loops, False),
                     note=f"{N_LAZY_MODULES}-module package imported eagerly; every module "
                          "body runs")

    if not have_lazy:
        for case in ("import_200_modules_lazy", "import_200_modules_first_touch"):
            suite.unavailable(case=case, impl=label,
                              note="importlib.set_lazy_imports() does not exist on this "
                                   "interpreter; lazy imports are a fork feature")
        return

    suite.bench_time(case="import_200_modules_lazy", impl=label, params=p,
                     time_fn=lambda loops: time_import(loops, True),
                     note="the same import statement with lazy imports enabled; no module "
                          "body runs")

    def time_first_touch(loops: int) -> float:
        lazy_package(state)
        importlib.set_lazy_imports()  # ty: ignore[unresolved-attribute]
        total = 0.0
        for _ in range(loops):
            purge_lazy_package()
            ns: dict[str, Any] = {}
            exec(LAZY_IMPORT, ns)
            t0 = pyperf.perf_counter()
            ns["m"].touch_one()
            total += pyperf.perf_counter() - t0
        return total

    suite.bench_time(case="import_200_modules_first_touch", impl=label, params=p,
                     time_fn=time_first_touch,
                     note="first use of a lazily imported module: what the deferred import "
                          "costs when it is finally paid")


def lazy_import_facts() -> dict[str, Any]:
    """How many module bodies each mode actually executed. Counts, not timings."""
    state: dict[str, Any] = {}
    lazy_package(state)
    purge_lazy_package()
    ns: dict[str, Any] = {}
    exec(LAZY_IMPORT, ns)
    facts = {"n_modules": N_LAZY_MODULES, "eager_module_bodies_run": module_bodies_run(),
             "lazy_imports_available": hasattr(importlib, "set_lazy_imports")}
    if facts["lazy_imports_available"]:
        purge_lazy_package()
        importlib.set_lazy_imports()  # ty: ignore[unresolved-attribute]
        ns: dict[str, Any] = {}
        exec(LAZY_IMPORT, ns)
        facts["lazy_module_bodies_run"] = module_bodies_run()
        ns["m"].touch_one()
        facts["lazy_module_bodies_run_after_first_use"] = module_bodies_run()
    return facts


def _compile_probe() -> int:
    return 0


def bench_jit_compile(suite: Suite, label: str,
                      targets: Sequence[tuple[str, types.FunctionType]]) -> None:
    """What one JIT compilation costs, measured on a copy of the kernel per iteration."""
    import cinderx.jit as jit  # ty: ignore[unresolved-import]

    def fresh(fn: types.FunctionType) -> types.FunctionType:
        return types.FunctionType(fn.__code__.replace(), fn.__globals__, fn.__name__,
                                  fn.__defaults__, fn.__closure__)

    try:
        probe = fresh(_compile_probe)
        usable = not jit.is_jit_compiled(probe)
        if usable:
            jit.force_compile(probe)
            usable = bool(jit.is_jit_compiled(probe))
        note = "a copy of a compiled function is not recompiled"
    except Exception as exc:
        usable = False
        note = f"{type(exc).__name__}: {exc}"[:200]
    if not usable:
        suite.unavailable(case="jit_force_compile", impl=label,
                          note=f"compile latency is not measurable repeatably: {note}")
        return

    for name, fn in targets:
        def time_fn(loops: int, fn: types.FunctionType = fn) -> float:
            total = 0.0
            for _ in range(loops):
                f = fresh(fn)
                t0 = pyperf.perf_counter()
                jit.force_compile(f)
                total += pyperf.perf_counter() - t0
            return total

        suite.bench_time(case="jit_force_compile", impl=f"{label}/{name}", time_fn=time_fn,
                         note=f"CinderX JIT compilation of {name}, one unseen code object "
                              "per iteration")


def main() -> None:
    suite = Suite("b6_cinderx", forward=("cinderx", "jit", "features", "expect-jit-env",
                                        "jit-compile-after"))
    ap = suite.runner.argparser
    ap.add_argument("--cinderx", action="store_true",
                    help="initialise the CinderX runtime (frame evaluator)")
    ap.add_argument("--jit", action="store_true",
                    help="force-compile every kernel with the CinderX JIT")
    ap.add_argument("--features", action="store_true",
                    help="also run the fork-feature benchmarks (lazy imports, parallel GC)")
    ap.add_argument("--jit-compile-after", type=int, default=JIT_COMPILE_AFTER,
                    help="calls before the JIT is asked to compile; negative leaves the "
                         "threshold as the environment configured it")
    ap.add_argument("--expect-jit-env", default="",
                    help="comma-separated NAME=VALUE that must be set in every process of this "
                         "run; use with pyperf's --inherit-environ when measuring a JIT option")
    args = suite.parse()
    label = suite.label
    p = PARAMS
    suite.log(f"=== b6_cinderx [{label}] {sys.version.splitlines()[0]} ===")

    jit_env = check_jit_env(args.expect_jit_env)
    cx_info: dict[str, Any] = {"cinderx": False}
    if args.cinderx:
        try:
            cx_info = setup_cinderx(args.jit, JIT_TARGETS, args.jit_compile_after)
            suite.log(f"cinderx: {cx_info}")
        except Exception as exc:
            sys.exit(f"cinderx setup failed in {'master' if suite.is_master else 'worker'}: "
                     f"{type(exc).__name__}: {exc}")
        if not cx_info.get("cinderx"):
            sys.exit("cinderx setup reported it did not initialise; refusing to run, because "
                     "the benchmark list would differ from a process where it did")
    suite.facts = {"params": p, "cinderx": cx_info,
                   "config": {"cinderx": args.cinderx, "jit": args.jit,
                              "features": args.features, "jit_env": jit_env}}

    bench_kernels(suite, label, p)
    bench_frames(suite, label, p)

    if args.features:
        if args.cinderx and cx_info.get("cinderx"):
            bench_parallel_gc(suite, label, p)
        bench_lazy_imports(suite, label, p)
    if args.jit and cx_info.get("cinderx"):
        bench_jit_compile(suite, label, JIT_TARGETS)

    if suite.is_master:
        if args.cinderx and cx_info.get("cinderx"):
            try:
                import cinderx  # ty: ignore[unresolved-import]

                before = cinderx.get_parallel_gc_settings()
                cinderx.enable_parallel_gc()
                suite.facts["parallel_gc_settings"] = cinderx.get_parallel_gc_settings()
                if before is None:
                    cinderx.disable_parallel_gc()
                suite.facts["parallel_gc_compiled_in"] = bool(cinderx.has_parallel_gc())
            except Exception as exc:
                suite.facts["parallel_gc_settings"] = repr(exc)[:200]
        if args.features:
            suite.facts["lazy_imports"] = lazy_import_facts()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
