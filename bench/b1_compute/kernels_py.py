"""Canonical kernel semantics for RQ1/RQ2 plus the pure-Python and NumPy implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

    F64 = npt.NDArray[np.float64]
else:
    F64 = Any


class Params(TypedDict):
    """Problem sizes shared by every RQ1/RQ1b implementation of the three kernels."""

    vec_n: int
    mb_w: int
    mb_h: int
    mb_iter: int
    mat_n: int


Kernel = Callable[[], Any]
Built = tuple[Kernel, Kernel]
NativeKernel = Callable[..., Any]


def make_vector(n: int) -> list[float]:
    return [((i * 37) % 1000) / 7.0 for i in range(n)]


def make_matrices(n: int) -> tuple[list[float], list[float]]:
    a = [float((i // n * 3 + i % n) % 7) for i in range(n * n)]
    b = [float((i // n + 2 * (i % n)) % 5) for i in range(n * n)]
    return a, b


def arraysum_py(a: list[float], n: int) -> float:
    s = 0.0
    for i in range(n):
        s += a[i]
    return s


def arraysum_py_builtin(a: list[float], n: int) -> float:
    return sum(a)


def mandelbrot_py(w: int, h: int, maxiter: int) -> int:
    total = 0
    for py in range(h):
        y0 = -1.25 + 2.5 * py / h
        for px in range(w):
            x0 = -2.0 + 3.0 * px / w
            x = 0.0
            y = 0.0
            it = 0
            while x * x + y * y <= 4.0 and it < maxiter:
                xt = x * x - y * y + x0
                y = 2.0 * x * y + y0
                x = xt
                it += 1
            total += it
    return total


def matmul_py(a: list[float], b: list[float], c: list[float], n: int) -> None:
    for i in range(n):
        row = i * n
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += a[row + k] * b[k * n + j]
            c[row + j] = s


def numpy_impls() -> dict[str, NativeKernel]:
    import numpy as np

    def arraysum(a: F64, n: int) -> float:
        return float(a.sum())

    def mandelbrot(w: int, h: int, maxiter: int) -> int:
        py = np.arange(h, dtype=np.float64)
        px = np.arange(w, dtype=np.float64)
        y0 = (-1.25 + 2.5 * py / h)[:, None]
        x0 = (-2.0 + 3.0 * px / w)[None, :]
        x = np.zeros((h, w))
        y = np.zeros((h, w))
        it = np.zeros((h, w), dtype=np.int64)
        alive = np.ones((h, w), dtype=bool)
        for _ in range(maxiter):
            alive &= (x * x + y * y) <= 4.0
            if not alive.any():
                break
            xt = np.where(alive, x * x - y * y + x0, x)
            y = np.where(alive, 2.0 * x * y + y0, y)
            x = xt
            it += alive
        return int(it.sum())

    def matmul(a: F64, b: F64, c: F64, n: int) -> None:
        np.matmul(a.reshape(n, n), b.reshape(n, n), out=c.reshape(n, n))

    return {"arraysum": arraysum, "mandelbrot": mandelbrot, "matmul": matmul}


def reference(params: Params) -> dict[str, float | int]:
    n = params["vec_n"]
    w, h, mx = params["mb_w"], params["mb_h"], params["mb_iter"]
    m = params["mat_n"]
    a = make_vector(n)
    ma, mb = make_matrices(m)
    c = [0.0] * (m * m)
    matmul_py(ma, mb, c, m)
    return {
        "arraysum": arraysum_py(a, n),
        "mandelbrot": mandelbrot_py(w, h, mx),
        "matmul": sum(c),
    }
