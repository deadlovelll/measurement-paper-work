/* Why the floating-point contract is worth several times the run time of a reduction. */

#include <stddef.h>

double c_sum_acc1(const double *a, ptrdiff_t n) {
    double s = 0.0;
    for (ptrdiff_t i = 0; i < n; ++i) s += a[i];
    return s;
}

double c_sum_acc2(const double *a, ptrdiff_t n) {
    double s0 = 0.0, s1 = 0.0;
    ptrdiff_t i = 0;
    for (; i + 2 <= n; i += 2) { s0 += a[i]; s1 += a[i + 1]; }
    for (; i < n; ++i) s0 += a[i];
    return s0 + s1;
}

double c_sum_acc4(const double *a, ptrdiff_t n) {
    double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;
    ptrdiff_t i = 0;
    for (; i + 4 <= n; i += 4) {
        s0 += a[i]; s1 += a[i + 1]; s2 += a[i + 2]; s3 += a[i + 3];
    }
    for (; i < n; ++i) s0 += a[i];
    return (s0 + s1) + (s2 + s3);
}

double c_sum_acc8(const double *a, ptrdiff_t n) {
    double s0 = 0.0, s1 = 0.0, s2 = 0.0, s3 = 0.0;
    double s4 = 0.0, s5 = 0.0, s6 = 0.0, s7 = 0.0;
    ptrdiff_t i = 0;
    for (; i + 8 <= n; i += 8) {
        s0 += a[i];     s1 += a[i + 1]; s2 += a[i + 2]; s3 += a[i + 3];
        s4 += a[i + 4]; s5 += a[i + 5]; s6 += a[i + 6]; s7 += a[i + 7];
    }
    for (; i < n; ++i) s0 += a[i];
    return ((s0 + s1) + (s2 + s3)) + ((s4 + s5) + (s6 + s7));
}
