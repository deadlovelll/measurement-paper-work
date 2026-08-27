# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False
"""Cython implementations of the RQ2 branchy kernels."""

from cpython.mem cimport PyMem_Free, PyMem_Malloc


def tokenize(const unsigned char[::1] data, Py_ssize_t n):
    cdef Py_ssize_t i
    cdef long long tokens = 0, checksum = 0
    cdef unsigned char ch
    cdef int state = 0
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


cdef class CyNode:
    cdef public CyNode left
    cdef public CyNode right

    def __cinit__(self, CyNode left, CyNode right):
        self.left = left
        self.right = right


cdef CyNode _build(int depth):
    if depth == 0:
        return None
    return CyNode(_build(depth - 1), _build(depth - 1))


cdef long long _check(CyNode node):
    if node is None:
        return 0
    return 1 + _check(node.left) + _check(node.right)


def binarytrees(int depth):
    return _check(_build(depth))


def bfs(Py_ssize_t n, Py_ssize_t start):
    cdef long long total = 0
    cdef Py_ssize_t head = 0, tail = 0, u, v, e
    cdef long long du
    cdef long long* dist = <long long*>PyMem_Malloc(n * sizeof(long long))
    cdef Py_ssize_t* q = <Py_ssize_t*>PyMem_Malloc(n * sizeof(Py_ssize_t))
    cdef Py_ssize_t mult[3]
    cdef Py_ssize_t add[3]
    mult[0], mult[1], mult[2] = 7, 13, 29
    add[0], add[1], add[2] = 3, 5, 11
    if not dist or not q:
        PyMem_Free(dist)
        PyMem_Free(q)
        raise MemoryError()
    try:
        for u in range(n):
            dist[u] = -1
        dist[start] = 0
        q[tail] = start
        tail += 1
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
    finally:
        PyMem_Free(dist)
        PyMem_Free(q)


def noop():
    return 0
