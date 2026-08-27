#!/usr/bin/env python
"""RQ4b: CinderX Static Python — unboxed int64 kernels, interpreter and JIT."""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Callable
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(BENCH, "harness"))

import pyperf  # noqa: E402
from mp_pyperf import RESULTS, Suite, bench_tag, interp_facts  # noqa: E402

N = 96
CASE = "matmul96_int"


def boxed_matmul(a: list[int], b: list[int], c: list[int], n: int) -> None:
    for i in range(n):
        row = i * n
        for j in range(n):
            s = 0
            for k in range(n):
                s += a[row + k] * b[k * n + j]
            c[row + j] = s


def make_flat(n: int) -> tuple[list[int], list[int]]:
    a = [(i // n * 3 + i % n) % 7 for i in range(n * n)]
    b = [(i // n + 2 * (i % n)) % 5 for i in range(n * n)]
    return a, b


def build_boxed(n: int) -> tuple[Callable[[], None], Callable[[], int]]:
    """The reference: the same multiplication on ordinary Python ints."""
    a_l, b_l = make_flat(n)
    c_l = [0] * (n * n)
    return (lambda: boxed_matmul(a_l, b_l, c_l, n),
            lambda: (boxed_matmul(a_l, b_l, c_l, n), sum(c_l))[1])


def static_kernel(n: int) -> tuple[Any, Any, Any]:
    """Boot CinderX's static compiler and build the unboxed inputs."""
    import cinderx  # ty: ignore[unresolved-import]

    cinderx.init()
    cinderx.install_frame_evaluator()
    from cinderx.compiler.strict.loader import (  # ty: ignore[unresolved-import]
        init_static_python,
        install,
    )

    init_static_python()
    install()
    sys.path.insert(0, os.path.join(HERE, "static_kernels"))
    import matmul_i64  # type: ignore
    from __static__ import Array, int64  # type: ignore

    a_l, b_l = make_flat(n)
    fa = Array[int64](n * n)
    fb = Array[int64](n * n)
    for i in range(n * n):
        fa[i] = a_l[i]
        fb[i] = b_l[i]
    return matmul_i64, fa, fb


def jit_compile_hot(fn: Any, call: Callable[[], Any]) -> None:
    """Get `fn` compiled the way a deployment would, and check that its code is what runs."""
    import cinderx.jit as jit  # ty: ignore[unresolved-import]

    jit.compile_after_n_calls(2)
    for _ in range(3):
        call()
    before = jit.count_interpreted_calls(fn)
    call()
    if jit.count_interpreted_calls(fn) != before:
        raise RuntimeError(f"{fn.__name__} is still interpreted after warm-up: the JIT did "
                           f"not take it, and timing it here would report the interpreter")


def build(impl: str, n: int) -> Callable[[], Any]:
    """The callable pyperf loops over, built inside the worker that was sent this row."""
    if impl in ("boxed_python", "boxed_jit"):
        call = build_boxed(n)[0]
        if impl == "boxed_jit":
            jit_compile_hot(boxed_matmul, call)
        return call
    mod, fa, fb = static_kernel(n)
    call = lambda: mod.matmul(fa, fb, n)  # noqa: E731
    if impl == "static_jit":
        jit_compile_hot(mod.matmul, call)
    return call


def static_bytecode_facts(fn: Any) -> dict[str, Any]:
    """How much of the kernel actually lowered to primitives. An observation, not a timing."""
    import dis

    names = [i.opname for i in dis.get_instructions(fn.__code__)]
    prims = sum(1 for nm in names if "PRIMITIVE" in nm or nm == "EXTENDED_OPCODE")
    return {"primitive_ops": prims, "total_ops": len(names)}


def discover(n: int) -> dict[str, Any]:
    """Check every row against the boxed reference at full size and write the plan."""
    print(f"=== b6_static discovery {sys.version.splitlines()[0]}")
    ref = build_boxed(n)[1]()
    print(f"reference checksum: {ref}")
    plan: list[dict] = [{"impl": "boxed_python",
                         "note": "ordinary Python ints on the same interpreter"},
                        {"impl": "boxed_jit",
                         "note": "the same boxed kernel, compiled by the CinderX JIT -- the "
                                 "row that says what the types are worth against the same "
                                 "compiler rather than against the interpreter"}]
    problems: list[dict] = []
    facts: dict[str, Any] = {}

    try:
        mod, fa, fb = static_kernel(n)
        got = mod.checksum(mod.matmul(fa, fb, n), n)
    except Exception as exc:
        traceback.print_exc()
        problems.append({"case": CASE, "impl": "static", "status": "failed",
                         "note": f"{type(exc).__name__}: {exc}"[:300]})
        print(f"  FAILED      static boot: {type(exc).__name__}: {exc}")
        return _plan(n, ref, plan, problems, facts)

    if got != ref:
        problems.append({"case": CASE, "impl": "static_interp", "status": "wrong_result",
                         "got": repr(got)[:60], "expected": repr(ref)[:60],
                         "note": f"got {got} expected {ref}"})
        print(f"  WRONG       static_interp got={got} expected={ref}")
        return _plan(n, ref, plan, problems, facts)

    facts.update(static_bytecode_facts(mod.matmul))
    print(f"static bytecode: {facts['primitive_ops']} primitive/extended ops "
          f"of {facts['total_ops']}")
    if not facts["primitive_ops"]:
        problems.append({"case": CASE, "impl": "static_interp", "status": "not_static",
                         "note": f"0 primitive/extended ops of {facts['total_ops']}: the "
                                 "module compiled as ordinary boxed bytecode, so there is no "
                                 "Static Python here to measure"})
        print(f"  NOT STATIC  0 primitive ops of {facts['total_ops']} -- boxed bytecode")
        return _plan(n, ref, plan, problems, facts)
    plan.append({"impl": "static_interp", "note": "Array[int64] primitives, CinderX interpreter"})
    print("  ok          static_interp")

    try:
        import cinderx.jit as jit  # ty: ignore[unresolved-import]

        jit.force_compile(mod.matmul)
        compiled = bool(jit.is_jit_compiled(mod.matmul))
        got2 = mod.checksum(mod.matmul(fa, fb, n), n)
    except Exception as exc:
        problems.append({"case": CASE, "impl": "static_jit", "status": "failed",
                         "note": f"{type(exc).__name__}: {exc}"[:300]})
        print(f"  FAILED      static_jit: {type(exc).__name__}: {exc}")
        return _plan(n, ref, plan, problems, facts)

    facts["is_jit_compiled"] = compiled
    if got2 != ref:
        problems.append({"case": CASE, "impl": "static_jit", "status": "wrong_result",
                         "got": repr(got2)[:60], "expected": repr(ref)[:60],
                         "note": "JIT changed the result"})
        print(f"  WRONG       static_jit got={got2} expected={ref}")
        return _plan(n, ref, plan, problems, facts)

    plan.append({"impl": "static_jit",
                 "note": f"force-compiled by the CinderX JIT (compiled={compiled})"})
    print(f"  ok          static_jit (compiled={compiled})")
    return _plan(n, ref, plan, problems, facts)


def _plan(n: int, ref: Any, plan: list[dict[str, Any]], problems: list[dict[str, Any]],
          facts: dict[str, Any]) -> dict[str, Any]:
    return {"suite": "b6_static", "params": {"n": n}, "reference": ref,
            "interp": interp_facts(), "plan": plan, "problems": problems, "facts": facts}


def measure(plan_path: str) -> None:
    with open(plan_path) as fh:
        disc = json.load(fh)
    n = disc["params"]["n"]
    suite = Suite("b6_static", forward=("plan",))
    suite.runner.argparser.add_argument("--plan", default=plan_path)
    suite.parse()
    suite.gate_failures = [dict(prob, impl=f"{suite.label}/{prob['impl']}")
                           for prob in disc["problems"]]
    suite.facts = {"params": disc["params"], "reference": disc["reference"], **disc["facts"]}
    suite.log(f"=== b6_static [{suite.label}] {sys.version.splitlines()[0]} "
              f"{len(disc['plan'])} benchmarks")

    cache: dict[str, Callable[[], Any]] = {}

    def timed_for(impl: str) -> Callable[[], Any]:
        if impl not in cache:
            cache[impl] = build(impl, n)
        return cache[impl]

    for row in disc["plan"]:
        def time_fn(loops: int, impl: str = row["impl"]) -> float:
            fn = timed_for(impl)
            t0 = pyperf.perf_counter()
            for _ in range(loops):
                fn()
            return pyperf.perf_counter() - t0

        suite.bench_time(case=CASE, impl=f"{suite.label}/{row['impl']}", time_fn=time_fn,
                         params=disc["params"], note=row["note"])

    suite.write_sidecar()


def main() -> None:
    label = bench_tag()
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    if "--discover" in sys.argv:
        sys.argv.remove("--discover")
        os.makedirs(RESULTS, exist_ok=True)
        out = os.path.join(RESULTS, f"b6_static-{label}.plan.json")
        disc = discover(N)
        with open(out, "w") as fh:
            json.dump(disc, fh, indent=1, default=str)
        print(f"[discovery] {len(disc['plan'])} benchmarks, "
              f"{len(disc['problems'])} problems -> {out}")
        return
    if "--plan" in sys.argv:
        plan = sys.argv[sys.argv.index("--plan") + 1]
    else:
        plan = os.path.join(RESULTS, f"b6_static-{label}.plan.json")
    if not os.path.exists(plan):
        sys.exit(f"no plan at {plan}; run with --discover first")
    measure(plan)


if __name__ == "__main__":
    main()
