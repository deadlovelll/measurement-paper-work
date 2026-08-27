//! Rust kernels for the measurement study, exposed as a plain C ABI and called from
//! Python through ctypes, so one shared object serves every CPython version.

use std::collections::VecDeque;

#[no_mangle]
pub unsafe extern "C" fn rs_arraysum(a: *const f64, n: isize) -> f64 {
    let s = std::slice::from_raw_parts(a, n as usize);
    let mut acc = 0.0f64;

    for &v in s.iter() {
        acc += v;
    }
    acc
}

#[no_mangle]
pub extern "C" fn rs_mandelbrot(w: i32, h: i32, maxiter: i32) -> i64 {
    let mut total: i64 = 0;
    for py in 0..h {
        let y0 = -1.25 + 2.5 * py as f64 / h as f64;
        for px in 0..w {
            let x0 = -2.0 + 3.0 * px as f64 / w as f64;
            let mut x = 0.0f64;
            let mut y = 0.0f64;
            let mut it = 0i32;
            while x * x + y * y <= 4.0 && it < maxiter {
                let xt = x * x - y * y + x0;
                y = 2.0 * x * y + y0;
                x = xt;
                it += 1;
            }
            total += it as i64;
        }
    }
    total
}

#[no_mangle]
pub unsafe extern "C" fn rs_matmul(a: *const f64, b: *const f64, c: *mut f64, n: isize) {
    let nn = n as usize;
    let a = std::slice::from_raw_parts(a, nn * nn);
    let b = std::slice::from_raw_parts(b, nn * nn);
    let c = std::slice::from_raw_parts_mut(c, nn * nn);
    for i in 0..nn {
        let row = i * nn;
        for j in 0..nn {
            let mut s = 0.0f64;
            for k in 0..nn {
                s += a[row + k] * b[k * nn + j];
            }
            c[row + j] = s;
        }
    }
}

#[no_mangle]
pub extern "C" fn rs_noop() -> i32 {
    0
}

/// Branch-heavy byte classifier. Returns tokens, writes the checksum through `checksum`.
#[no_mangle]
pub unsafe extern "C" fn rs_tokenize(data: *const u8, n: isize, checksum: *mut i64) -> i64 {
    let d = std::slice::from_raw_parts(data, n as usize);
    let mut tokens: i64 = 0;
    let mut sum: i64 = 0;
    let mut state: u8 = 0;
    for &ch in d.iter() {
        if (48..=57).contains(&ch) {
            if state != 1 {
                tokens += 1;
                state = 1;
            }
            sum += (ch - 48) as i64;
        } else if (65..=90).contains(&ch) || (97..=122).contains(&ch) {
            if state != 2 {
                tokens += 1;
                state = 2;
            }
            sum += ((ch | 32) - 96) as i64;
        } else if ch == 32 || ch == 10 || ch == 9 {
            state = 0;
        } else {
            if state != 3 {
                tokens += 1;
                state = 3;
            }
            sum += 7;
        }
    }
    *checksum = sum;
    tokens
}

struct Node {
    left: Option<Box<Node>>,
    right: Option<Box<Node>>,
}

fn build(depth: i32) -> Option<Box<Node>> {
    if depth == 0 {
        None
    } else {
        Some(Box::new(Node {
            left: build(depth - 1),
            right: build(depth - 1),
        }))
    }
}

fn check(node: &Option<Box<Node>>) -> i64 {
    match node {
        None => 0,
        Some(n) => 1 + check(&n.left) + check(&n.right),
    }
}

/// Real heap allocation + recursion: build a binary tree of `depth`, fold it, drop it.
#[no_mangle]
pub extern "C" fn rs_binarytrees(depth: i32) -> i64 {
    let t = build(depth);
    check(&t)
}

/// BFS over a deterministic 3-out-degree graph, returns the sum of distances.
#[no_mangle]
pub extern "C" fn rs_bfs(n: i64, start: i64) -> i64 {
    let n = n as usize;
    let mut dist = vec![-1i64; n];
    let mut q = VecDeque::with_capacity(n);
    dist[start as usize] = 0;
    q.push_back(start as usize);
    let mut total: i64 = 0;
    while let Some(u) = q.pop_front() {
        total += dist[u];
        let du = dist[u];
        for &(m, a) in &[(7i64, 3i64), (13, 5), (29, 11)] {
            let v = ((u as i64 * m + a).rem_euclid(n as i64)) as usize;
            if dist[v] < 0 {
                dist[v] = du + 1;
                q.push_back(v);
            }
        }
    }
    total
}
