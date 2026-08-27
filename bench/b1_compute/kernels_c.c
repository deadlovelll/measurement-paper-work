/* C implementations of the RQ1 kernels. */
#include <stddef.h>
#include <stdint.h>

double c_arraysum(const double *a, ptrdiff_t n) {
    double s = 0.0;
    for (ptrdiff_t i = 0; i < n; ++i) s += a[i];
    return s;
}

long long c_mandelbrot(int w, int h, int maxiter) {
    long long total = 0;
    for (int py = 0; py < h; ++py) {
        double y0 = -1.25 + 2.5 * py / h;
        for (int px = 0; px < w; ++px) {
            double x0 = -2.0 + 3.0 * px / w;
            double x = 0.0, y = 0.0;
            int it = 0;
            while (x * x + y * y <= 4.0 && it < maxiter) {
                double xt = x * x - y * y + x0;
                y = 2.0 * x * y + y0;
                x = xt;
                ++it;
            }
            total += it;
        }
    }
    return total;
}

/* Perfectly balanced compute kernel for the RQ5 thread-scaling study: the cost is exactly proportional to `iters`, there is no memory traffic, and ctypes releases the GIL around the call — so the measured curve reflects the runtime, not load imbalance or bandwidth. */
double c_busy(long long iters, double seed) {
    double x = seed;
    for (long long i = 0; i < iters; ++i) x = x * 1.0000001 + 0.5 * (double)(i & 7);
    return x;
}

/* Row-range variant of the mandelbrot kernel: also GIL-releasing, but the per-row cost is data-dependent, so a contiguous split is deliberately imbalanced. Kept as a control. */
long long c_mandelbrot_rows(int w, int h, int maxiter, int y0i, int y1i) {
    long long total = 0;
    for (int py = y0i; py < y1i; ++py) {
        double y0 = -1.25 + 2.5 * py / h;
        for (int px = 0; px < w; ++px) {
            double x0 = -2.0 + 3.0 * px / w;
            double x = 0.0, y = 0.0;
            int it = 0;
            while (x * x + y * y <= 4.0 && it < maxiter) {
                double xt = x * x - y * y + x0;
                y = 2.0 * x * y + y0;
                x = xt;
                ++it;
            }
            total += it;
        }
    }
    return total;
}

void c_matmul(const double *a, const double *b, double *c, ptrdiff_t n) {
    for (ptrdiff_t i = 0; i < n; ++i) {
        ptrdiff_t row = i * n;
        for (ptrdiff_t j = 0; j < n; ++j) {
            double s = 0.0;
            for (ptrdiff_t k = 0; k < n; ++k) s += a[row + k] * b[k * n + j];
            c[row + j] = s;
        }
    }
}

int c_noop(void) { return 0; }
