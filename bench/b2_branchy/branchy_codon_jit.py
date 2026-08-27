"""Codon's JIT path for the RQ2 branchy kernels: the same kernels, compiled at run time."""

from __future__ import annotations

import codon


@codon.jit
def tokenize(data, n):
    tokens = 0
    checksum = 0
    state = 0
    for i in range(n):
        ch = int(data[i])
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
    return (tokens, checksum)


@codon.jit
def binarytrees(depth):
    class Node:
        left: Optional[Node]  # noqa: F821
        right: Optional[Node]  # noqa: F821

        def __init__(self, left: Optional[Node], right: Optional[Node]):  # noqa: F821
            self.left = left
            self.right = right

    def _build(d: int) -> Optional[Node]:  # noqa: F821
        if d == 0:
            return None
        return Node(_build(d - 1), _build(d - 1))

    def _check(node: Optional[Node]) -> int:  # noqa: F821
        if node is None:
            return 0
        return 1 + _check(node.left) + _check(node.right)

    return _check(_build(depth))


@codon.jit
def bfs(n, start):
    dist = [-1 for _ in range(n)]
    q = [0 for _ in range(n)]
    dist[start] = 0
    q[0] = start
    head = 0
    tail = 1
    total = 0
    while head < tail:
        u = q[head]
        head += 1
        du = dist[u]
        total += du
        for m, a in ((7, 3), (13, 5), (29, 11)):
            v = (u * m + a) % n
            if dist[v] < 0:
                dist[v] = du + 1
                q[tail] = v
                tail += 1
    return total
