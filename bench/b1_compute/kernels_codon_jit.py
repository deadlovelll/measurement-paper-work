"""Codon's JIT path for the RQ1 compute kernels: the same kernels, compiled at run time."""

from __future__ import annotations

import codon


@codon.jit
def arraysum(a, n):
    s = 0.0
    for i in range(n):
        s += a[i]
    return s


@codon.jit
def mandelbrot(w, h, maxiter):
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


@codon.jit
def matmul(a, b, c, n):
    for i in range(n):
        row = i * n
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += a[row + k] * b[k * n + j]
            c[row + j] = s
