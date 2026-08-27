"""Canonical semantics + pure-Python implementations of the RQ2 (branchy) kernels."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any, Optional, TypedDict


class Params(TypedDict):
    """Problem sizes for the three irregular kernels."""

    tok_n: int
    tree_depth: int
    bfs_n: int


Kernel = Callable[[], Any]

DIGIT, ALPHA, OTHER = 1, 2, 3


def make_bytes(n: int) -> bytes:
    """Deterministic pseudo-random mix of digits, letters, spaces and punctuation."""
    out = bytearray(n)
    x = 123456789
    for i in range(n):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        r = x % 100
        if r < 35:
            out[i] = 97 + (x >> 7) % 26
        elif r < 60:
            out[i] = 48 + (x >> 7) % 10
        elif r < 80:
            out[i] = 32
        else:
            out[i] = 33 + (x >> 7) % 14
    return bytes(out)


def tokenize_py(data: bytes, n: int) -> tuple[int, int]:
    tokens = 0
    checksum = 0
    state = 0
    for i in range(n):
        ch = data[i]
        if 48 <= ch <= 57:
            if state != DIGIT:
                tokens += 1
                state = DIGIT
            checksum += ch - 48
        elif (65 <= ch <= 90) or (97 <= ch <= 122):
            if state != ALPHA:
                tokens += 1
                state = ALPHA
            checksum += (ch | 32) - 96
        elif ch == 32 or ch == 10 or ch == 9:
            state = 0
        else:
            if state != OTHER:
                tokens += 1
                state = OTHER
            checksum += 7
    return tokens, checksum


class Node:
    __slots__ = ("left", "right")
    left: Optional[Node]
    right: Optional[Node]

    def __init__(self, left: Optional[Node], right: Optional[Node]) -> None:
        self.left = left
        self.right = right


def _build(depth: int) -> Optional[Node]:
    if depth == 0:
        return None
    return Node(_build(depth - 1), _build(depth - 1))


def _check(node) -> int:
    if node is None:
        return 0
    return 1 + _check(node.left) + _check(node.right)


def binarytrees_py(depth: int) -> int:
    return _check(_build(depth))


def bfs_py(n: int, start: int) -> int:
    dist = [-1] * n
    dist[start] = 0
    q = deque((start,))
    total = 0
    while q:
        u = q.popleft()
        du = dist[u]
        total += du
        for m, a in ((7, 3), (13, 5), (29, 11)):
            v = (u * m + a) % n
            if dist[v] < 0:
                dist[v] = du + 1
                q.append(v)
    return total


def bfs_py_flat(n: int, start: int) -> int:
    """The same traversal with the queue as a preallocated flat list."""
    dist = [-1] * n
    dist[start] = 0
    q = [0] * n
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


def reference(params: Params) -> dict[str, Any]:
    data = make_bytes(params["tok_n"])
    return {
        "tokenize": tokenize_py(data, params["tok_n"]),
        "binarytrees": binarytrees_py(params["tree_depth"]),
        "bfs": bfs_py(params["bfs_n"], 0),
    }
