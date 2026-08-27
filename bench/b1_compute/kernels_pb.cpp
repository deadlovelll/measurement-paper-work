/* pybind11 wrapper around the same C kernels: measures the cost/benefit of a real CPython extension module boundary versus ctypes (RQ1 table, RQ2 FFI overhead figure). */
#include <cstddef>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

using ssize = std::ptrdiff_t;

extern "C" {
double c_arraysum(const double *a, ssize n);
long long c_mandelbrot(int w, int h, int maxiter);
void c_matmul(const double *a, const double *b, double *c, ssize n);
int c_noop(void);
}

namespace py = pybind11;

static double arraysum(py::array_t<double, py::array::c_style | py::array::forcecast> a,
                       ptrdiff_t n) {
    return c_arraysum(a.data(), n);
}

static long long mandelbrot(int w, int h, int maxiter) { return c_mandelbrot(w, h, maxiter); }

static void matmul(py::array_t<double, py::array::c_style | py::array::forcecast> a,
                   py::array_t<double, py::array::c_style | py::array::forcecast> b,
                   py::array_t<double, py::array::c_style> c, ptrdiff_t n) {
    c_matmul(a.data(), b.data(), c.mutable_data(), n);
}

PYBIND11_MODULE(kernels_pb, m) {
    m.doc() = "RQ1 kernels behind a pybind11 boundary";
    m.def("arraysum", &arraysum);
    m.def("mandelbrot", &mandelbrot);
    m.def("matmul", &matmul);
    m.def("noop", []() { return c_noop(); });
}
