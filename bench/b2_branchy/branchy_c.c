/* C implementations of the RQ2 branchy kernels (called through ctypes). */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

long long c_tokenize(const unsigned char *data, ptrdiff_t n, long long *checksum) {
    long long tokens = 0, sum = 0;
    int state = 0;
    for (ptrdiff_t i = 0; i < n; ++i) {
        unsigned char ch = data[i];
        if (ch >= 48 && ch <= 57) {
            if (state != 1) { ++tokens; state = 1; }
            sum += ch - 48;
        } else if ((ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122)) {
            if (state != 2) { ++tokens; state = 2; }
            sum += (ch | 32) - 96;
        } else if (ch == 32 || ch == 10 || ch == 9) {
            state = 0;
        } else {
            if (state != 3) { ++tokens; state = 3; }
            sum += 7;
        }
    }
    *checksum = sum;
    return tokens;
}

typedef struct Node {
    struct Node *left;
    struct Node *right;
} Node;

static Node *build(int depth) {
    if (depth == 0) return NULL;
    Node *n = (Node *)malloc(sizeof(Node));
    n->left = build(depth - 1);
    n->right = build(depth - 1);
    return n;
}

static long long check(const Node *n) {
    if (!n) return 0;
    return 1 + check(n->left) + check(n->right);
}

static void destroy(Node *n) {
    if (!n) return;
    destroy(n->left);
    destroy(n->right);
    free(n);
}

long long c_binarytrees(int depth) {
    Node *t = build(depth);
    long long r = check(t);
    destroy(t);
    return r;
}

long long c_bfs(long long n, long long start) {
    long long *dist = (long long *)malloc((size_t)n * sizeof(long long));
    long long *q = (long long *)malloc((size_t)n * sizeof(long long));
    const long long mult[3] = {7, 13, 29};
    const long long add[3] = {3, 5, 11};
    long long head = 0, tail = 0, total = 0;
    for (long long i = 0; i < n; ++i) dist[i] = -1;
    dist[start] = 0;
    q[tail++] = start;
    while (head < tail) {
        long long u = q[head++];
        long long du = dist[u];
        total += du;
        for (int e = 0; e < 3; ++e) {
            long long v = (u * mult[e] + add[e]) % n;
            if (dist[v] < 0) {
                dist[v] = du + 1;
                q[tail++] = v;
            }
        }
    }
    free(dist);
    free(q);
    return total;
}
