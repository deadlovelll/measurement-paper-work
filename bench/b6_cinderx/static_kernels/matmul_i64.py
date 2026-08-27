"""Static Python matrix multiplication on UNBOXED int64 primitives.
Do not delete the bare `import __static__`: it is what selects the static compiler.
"""
# Removing this silently yields boxed CPython timed as "Static Python" (happened 2026-08-05);
# run_b6_static.py counts 61 primitive ops of 158 when it is right, 0 of 69 when it is not.
import __static__  # ty: ignore[unresolved-import]
from __static__ import Array, box, int64  # ty: ignore[unresolved-import]


def matmul(a: Array[int64], b: Array[int64], n: int64) -> Array[int64]:
    out: Array[int64] = Array[int64](box(n * n))
    i: int64 = 0
    while i < n:
        j: int64 = 0
        while j < n:
            s: int64 = 0
            k: int64 = 0
            while k < n:
                s = s + a[i * n + k] * b[k * n + j]
                k = k + 1
            out[i * n + j] = s
            j = j + 1
        i = i + 1
    return out


def checksum(a: Array[int64], n: int64) -> int:
    s: int64 = 0
    i: int64 = 0
    while i < n * n:
        s = s + a[i]
        i = i + 1
    return box(s)
