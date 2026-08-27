# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False
"""Cython implementations of the RQ1 compute kernels (statically typed, bounds checks off)."""

def arraysum(double[::1] a, Py_ssize_t n):
    cdef double s = 0.0
    cdef Py_ssize_t i
    for i in range(n):
        s += a[i]
    return s


def mandelbrot(int w, int h, int maxiter):
    cdef long long total = 0
    cdef int px, py, it
    cdef double x, y, xt, x0, y0
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


def matmul(double[::1] a, double[::1] b, double[::1] c, Py_ssize_t n):
    cdef Py_ssize_t i, j, k, row
    cdef double s
    for i in range(n):
        row = i * n
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += a[row + k] * b[k * n + j]
            c[row + j] = s


def noop():
    """Empty call, used to measure the Cython call-boundary cost."""
    return 0
