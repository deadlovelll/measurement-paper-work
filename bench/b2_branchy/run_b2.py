#!/usr/bin/env python
"""Branchy, allocation-heavy and pointer-chasing kernels across the same technologies."""

from __future__ import annotations

import ctypes
import json
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))
sys.path.insert(0, HERE)

import branchy_py as B  # noqa: E402
import pyperf  # noqa: E402
from branchy_py import Kernel, Params  # noqa: E402
from mp_pyperf import RESULTS, Suite, bench_tag, interp_facts, native_flag  # noqa: E402

PARAMS: Params = {"tok_n": 2_000_000, "tree_depth": 18, "bfs_n": 500_000}
KERNELS = ("tokenize", "binarytrees", "bfs")
SO = "dylib" if sys.platform == "darwin" else "so"
NATIVE_FLAG = native_flag()

IMPLS = [
    ("cpython_loop", "pure Python, __slots__ objects for the tree"),
    ("cpython_flat", "pure Python, flat preallocated lists instead of deque/dict"),
    ("cython", "typed cython; tree nodes are still CPython objects"),
    ("numba", "numba njit with NumPy-typed rewrites where expressible"),
    ("c_ctypes", f"clang -O3 {NATIVE_FLAG} via ctypes; malloc per tree node"),
    ("rust_ctypes", "rustc opt-level=3, lto=fat, target-cpu=native via ctypes; Box per node"),
    ("codon_pyext", "Codon built ahead of time by `codon build -pyext`; the tree is a Codon "
                    "class with a real pointer chase, not a jitclass and not a flat array"),
    ("codon_jit", "the same kernels under @codon.jit, compiled in-process at first call"),
]


def build_dir() -> str:
    return os.path.join(BENCH, "build", bench_tag())


def native_dir() -> str:
    return os.path.join(BENCH, "build", "native")


def _b_cpython_loop(p: Params, case: str) -> Kernel:
    if case == "tokenize":
        data = B.make_bytes(p["tok_n"])
        return lambda: B.tokenize_py(data, p["tok_n"])
    if case == "binarytrees":
        return lambda: B.binarytrees_py(p["tree_depth"])
    return lambda: B.bfs_py(p["bfs_n"], 0)


def _b_cpython_flat(p: Params, case: str) -> Kernel | None:
    if case != "bfs":
        return None
    return lambda: B.bfs_py_flat(p["bfs_n"], 0)


def _b_cython(p: Params, case: str) -> Kernel:
    sys.path.insert(0, build_dir())
    import branchy_cy  # type: ignore

    if case == "tokenize":
        mv = memoryview(B.make_bytes(p["tok_n"]))
        return lambda: branchy_cy.tokenize(mv, p["tok_n"])
    if case == "binarytrees":
        return lambda: branchy_cy.binarytrees(p["tree_depth"])
    return lambda: branchy_cy.bfs(p["bfs_n"], 0)


def _b_codon_pyext(p: Params, case: str) -> Kernel:
    """Codon compiled ahead of time, imported like any other extension module."""
    import numpy as np

    sys.path.insert(0, build_dir())
    import branchy_codon  # type: ignore

    if case == "tokenize":
        data = np.frombuffer(B.make_bytes(p["tok_n"]), dtype=np.uint8)
        return lambda: branchy_codon.tokenize(data, p["tok_n"])
    if case == "binarytrees":
        return lambda: branchy_codon.binarytrees(p["tree_depth"])
    return lambda: branchy_codon.bfs(p["bfs_n"], 0)


def _b_codon_jit(p: Params, case: str) -> Kernel:
    """Codon's JIT. Imported here, not at module scope: importing it compiles."""
    import branchy_codon_jit as cj
    import numpy as np

    if case == "tokenize":
        data = np.frombuffer(B.make_bytes(p["tok_n"]), dtype=np.uint8)
        return lambda: cj.tokenize(data, p["tok_n"])
    if case == "binarytrees":
        return lambda: cj.binarytrees(p["tree_depth"])
    return lambda: cj.bfs(p["bfs_n"], 0)


def _b_numba(p: Params, case: str) -> Kernel:
    import numba
    import numpy as np

    jit = numba.njit(cache=False)
    if case == "tokenize":
        @jit
        def tokenize(data: Any, n: int) -> tuple[int, int]:
            tokens = 0
            checksum = 0
            state = 0
            for i in range(n):
                ch = data[i]
                if 48 <= ch <= 57:
                    if state != 1:
                        tokens += 1
                        state = 1
                    checksum += ch - 48
                elif (65 <= ch <= 90) or (97 <= ch <= 122):
                    if state != 2:
                        tokens += 1
                        state = 2
                    checksum += (ch | 32) - 96
                elif ch == 32 or ch == 10 or ch == 9:
                    state = 0
                else:
                    if state != 3:
                        tokens += 1
                        state = 3
                    checksum += 7
            return tokens, checksum

        data = np.frombuffer(B.make_bytes(p["tok_n"]), dtype=np.uint8)
        n = p["tok_n"]
        tokenize(data, n)
        return lambda: tokenize(data, n)

    if case == "bfs":
        @jit
        def bfs(n: int, start: int) -> int:
            dist = np.full(n, -1, dtype=np.int64)
            q = np.empty(n, dtype=np.int64)
            head = 0
            tail = 0
            dist[start] = 0
            q[tail] = start
            tail += 1
            total = 0
            mult = (7, 13, 29)
            add = (3, 5, 11)
            while head < tail:
                u = q[head]
                head += 1
                du = dist[u]
                total += du
                for e in range(3):
                    v = (u * mult[e] + add[e]) % n
                    if dist[v] < 0:
                        dist[v] = du + 1
                        q[tail] = v
                        tail += 1
            return total

        nn = p["bfs_n"]
        bfs(nn, 0)
        return lambda: bfs(nn, 0)

    node_type = numba.deferred_type()

    @numba.experimental.jitclass([("left", numba.optional(node_type)),
                                  ("right", numba.optional(node_type))])
    class NbNode:
        def __init__(self, left: Any, right: Any) -> None:
            self.left = left
            self.right = right

    node_type.define(NbNode.class_type.instance_type)  # ty: ignore[unresolved-attribute]

    @jit
    def build(depth: int) -> Any:
        if depth == 0:
            return None
        return NbNode(build(depth - 1), build(depth - 1))

    @jit
    def check(node: Any) -> int:
        if node is None:
            return 0
        return 1 + check(node.left) + check(node.right)

    @jit
    def binarytrees(depth: int) -> int:
        return check(build(depth))

    binarytrees(3)
    d = p["tree_depth"]
    return lambda: binarytrees(d)


def _load_c() -> ctypes.CDLL:
    lib = ctypes.CDLL(os.path.join(native_dir(), f"libbranchy_c.{SO}"))
    lib.c_tokenize.restype = ctypes.c_longlong
    lib.c_tokenize.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t,
                               ctypes.POINTER(ctypes.c_longlong)]
    lib.c_binarytrees.restype = ctypes.c_longlong
    lib.c_binarytrees.argtypes = [ctypes.c_int]
    lib.c_bfs.restype = ctypes.c_longlong
    lib.c_bfs.argtypes = [ctypes.c_longlong, ctypes.c_longlong]
    return lib


def _b_c_ctypes(p: Params, case: str) -> Kernel:
    lib = _load_c()
    if case == "tokenize":
        data = B.make_bytes(p["tok_n"])
        n = p["tok_n"]

        def tok() -> tuple[int, int]:
            cs = ctypes.c_longlong(0)
            return lib.c_tokenize(data, n, ctypes.byref(cs)), cs.value
        return tok
    if case == "binarytrees":
        return lambda: lib.c_binarytrees(p["tree_depth"])
    return lambda: lib.c_bfs(p["bfs_n"], 0)


def _load_rust() -> ctypes.CDLL:
    lib = ctypes.CDLL(os.path.join(native_dir(), f"libmpkernels.{SO}"))
    lib.rs_tokenize.restype = ctypes.c_longlong
    lib.rs_tokenize.argtypes = [ctypes.c_char_p, ctypes.c_ssize_t,
                                ctypes.POINTER(ctypes.c_longlong)]
    lib.rs_binarytrees.restype = ctypes.c_longlong
    lib.rs_binarytrees.argtypes = [ctypes.c_int]
    lib.rs_bfs.restype = ctypes.c_longlong
    lib.rs_bfs.argtypes = [ctypes.c_longlong, ctypes.c_longlong]
    return lib


def _b_rust_ctypes(p: Params, case: str) -> Kernel:
    lib = _load_rust()
    if case == "tokenize":
        data = B.make_bytes(p["tok_n"])
        n = p["tok_n"]

        def tok() -> tuple[int, int]:
            cs = ctypes.c_longlong(0)
            return lib.rs_tokenize(data, n, ctypes.byref(cs)), cs.value
        return tok
    if case == "binarytrees":
        return lambda: lib.rs_binarytrees(p["tree_depth"])
    return lambda: lib.rs_bfs(p["bfs_n"], 0)


BUILDERS = {
    "cpython_loop": _b_cpython_loop,
    "cpython_flat": _b_cpython_flat,
    "cython": _b_cython,
    "numba": _b_numba,
    "c_ctypes": _b_c_ctypes,
    "rust_ctypes": _b_rust_ctypes,
    "codon_pyext": _b_codon_pyext,
    "codon_jit": _b_codon_jit,
}


def normalise(kern: str, value: Any) -> int | tuple[int, int]:
    """The kernels return different shapes; compare them on a common one."""
    if kern == "tokenize":
        return (int(value[0]), int(value[1]))
    return int(value)


def discover(p: Params) -> dict[str, Any]:
    ref = B.reference(p)
    print(f"=== branchy discovery on {sys.version.split()[0]} ({bench_tag()})")
    print(f"    reference: {ref}")
    plan: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for impl, note in IMPLS:
        for case in KERNELS:
            try:
                fn = BUILDERS[impl](p, case)
                if fn is None:
                    continue
            except Exception as exc:
                problems.append({"case": case, "impl": impl, "status": "unsupported",
                                 "note": f"{type(exc).__name__}: "
                                         f"{str(exc).splitlines()[0][:200]}"})
                print(f"  unsupported {case:<13} {impl:<14} {type(exc).__name__}")
                continue
            try:
                got = normalise(case, fn())
            except Exception as exc:
                problems.append({"case": case, "impl": impl, "status": "runtime_error",
                                 "note": f"{type(exc).__name__}: "
                                         f"{str(exc).splitlines()[0][:200]}"})
                print(f"  error       {case:<13} {impl:<14} {type(exc).__name__}")
                continue
            exp = normalise(case, ref[case])
            if got != exp:
                problems.append({"case": case, "impl": impl, "status": "wrong_result",
                                 "got": repr(got)[:60], "expected": repr(exp)[:60]})
                print(f"  WRONG       {case:<13} {impl:<14} got={got!r} exp={exp!r}")
                continue
            plan.append({"case": case, "impl": impl, "note": note})
            print(f"  ok          {case:<13} {impl}")
    return {"suite": "b2_branchy", "params": p, "interp": interp_facts(),
            "reference": {k: str(v) for k, v in ref.items()},
            "reference_raw": {k: normalise(k, v) for k, v in ref.items()},
            "plan": plan, "problems": problems}


def measure(plan_path: str) -> None:
    with open(plan_path) as fh:
        disc = json.load(fh)
    p = disc["params"]
    suite = Suite("b2_branchy", forward=("plan", "reverse"))
    suite.runner.argparser.add_argument("--plan", default=plan_path)
    suite.runner.argparser.add_argument(
        "--reverse", action="store_true",
        help="register the plan back to front; run once each way and append into one file, "
             "so no benchmark is always measured first")
    args = suite.parse()
    if args.reverse:
        disc["plan"] = list(reversed(disc["plan"]))
    suite.gate_failures = disc["problems"]
    suite.facts = {"params": p, "reference": disc["reference"]}

    cache: dict[tuple[str, str], Kernel] = {}
    ref = disc["reference_raw"]

    def timed_for(case: str, impl: str) -> Kernel:
        key = (case, impl)
        if key not in cache:
            fn = BUILDERS[impl](p, case)
            if fn is None:
                raise RuntimeError(
                    f"{impl} has no {case} implementation; the plan should not list it")
            suite.check_once(key, lambda: normalise(case, fn()), ref[case], 0.0)
            cache[key] = fn
        return cache[key]

    for e in disc["plan"]:
        def time_fn(loops: int, case: str = e["case"], impl: str = e["impl"]) -> float:
            fn = timed_for(case, impl)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        suite.bench_time(case=e["case"], impl=e["impl"], time_fn=time_fn, params=p,
                         note=e["note"])
    suite.machine_probe()
    suite.write_sidecar()


def main() -> None:
    label = bench_tag()
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    if "--discover" in sys.argv:
        sys.argv.remove("--discover")
        os.makedirs(RESULTS, exist_ok=True)
        out = os.path.join(RESULTS, f"b2_branchy-{label}.plan.json")
        disc = discover(PARAMS)
        with open(out, "w") as fh:
            json.dump(disc, fh, indent=1, default=str)
        print(f"[discovery] {len(disc['plan'])} benchmarks, "
              f"{len(disc['problems'])} problems -> {out}")
        return
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    else:
        plan = os.path.join(RESULTS, f"b2_branchy-{label}.plan.json")
    if not os.path.exists(plan):
        sys.exit(f"no plan at {plan}; run with --discover first")
    measure(plan)


if __name__ == "__main__":
    main()
