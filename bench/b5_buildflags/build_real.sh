#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${SRC:-$ROOT/cinderx-workshop/cpython}"
OUT="${OUT:?set OUT to the install root}"
JOBS="${JOBS:-$(nproc)}"
WORK="$OUT/work"
mkdir -p "$WORK" "$OUT"
[ -x "$SRC/configure" ] || { echo "no configure in $SRC"; exit 1; }

CC_BIN="${CC_BIN:-/usr/bin/clang}"
CXX_BIN="${CXX_BIN:-/usr/bin/clang++}"

unset PKG_CONFIG_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH LD_LIBRARY_PATH \
      CFLAGS CXXFLAGS LDFLAGS CPPFLAGS 2>/dev/null || true
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vE '^/opt/intel|^/opt/nvidia|/oneapi/' | paste -sd: -)"
export PATH

if $CC_BIN -march=native -E -x c /dev/null > /dev/null 2>&1; then
  NATIVE_FLAG="-march=native"
elif $CC_BIN -mcpu=native -E -x c /dev/null > /dev/null 2>&1; then
  NATIVE_FLAG="-mcpu=native"
else
  NATIVE_FLAG=""
  echo "=== warning: this compiler accepts neither -march=native nor -mcpu=native"
fi
echo "=== compiler     : $($CC_BIN --version | head -1)"
echo "=== native flag  : ${NATIVE_FLAG:-none}"
echo "=== jobs         : $JOBS"

build() {
  local name="$1"; shift
  local cflags="$1"; shift
  local prefix="$OUT/$name"
  if [ -x "$prefix/bin/python3.14" ]; then echo "=== $name already built"; return; fi
  echo "=== building $name  cflags='$cflags'  flags: $*"
  rm -rf "$WORK/$name"
  mkdir -p "$WORK/$name"

  ( cd "$SRC" && tar cf - --exclude=cinderx --exclude=.git . ) | ( cd "$WORK/$name" && tar xf - )
  (
    cd "$WORK/$name" || exit 1
    export CC="$CC_BIN" CXX="$CXX_BIN"

    LLVM_PROFDATA="${LLVM_PROFDATA:-$(dirname "$CC")/llvm-profdata}"
    [ -x "$LLVM_PROFDATA" ] || LLVM_PROFDATA="$(command -v llvm-profdata)"
    export LLVM_PROFDATA
    make distclean > /dev/null 2>&1 || true
    env CFLAGS="$cflags" ./configure --prefix="$prefix" --without-ensurepip "$@" \
        > "$OUT/$name.configure.log" 2>&1 || { echo "configure FAILED"; exit 1; }
    make -j"$JOBS" > "$OUT/$name.make.log" 2>&1 || { echo "make FAILED"; exit 1; }
    make altinstall > "$OUT/$name.install.log" 2>&1 || { echo "install FAILED"; exit 1; }
  )
  if [ -x "$prefix/bin/python3.14" ]; then
    echo -n "=== $name OK: "
    "$prefix/bin/python3.14" -c "
import sysconfig as s
ld=(s.get_config_var('PY_CORE_LDFLAGS') or '')+' '+(s.get_config_var('PY_CORE_CFLAGS') or '')
cfg=s.get_config_var('CONFIG_ARGS') or ''
print('lto=', ' '.join(t for t in ld.split() if 'lto' in t) or 'none',
      '| pgo=', 'yes' if 'profile' in ld else 'no',
      '| arch=', ' '.join(t for t in ld.split() if 'march' in t or 'mcpu' in t) or 'none',
      '| jit=', 'yes' if 'experimental-jit' in cfg else 'no')"
  else
    echo "=== $name FAILED (see $OUT/$name.*.log)"
    tail -8 "$OUT/$name.configure.log" "$OUT/$name.make.log" 2>/dev/null | sed 's/^/      /'
  fi
}

build w_plain              ""
build w_pgo                ""               --enable-optimizations
build w_ltothin            ""               --with-lto=thin
build w_ltofull            ""               --with-lto=full
build w_pgo_ltofull        ""               --enable-optimizations --with-lto=full
build w_pgo_ltofull_native "$NATIVE_FLAG"   --enable-optimizations --with-lto=full

LLVM19="${LLVM19:-$HOME/.local/llvm19/bin}"
if [ -x "$LLVM19/clang" ]; then
  echo "=== tier-2 JIT toolchain: $("$LLVM19/clang" --version | head -1)"
  PATH="$LLVM19:$PATH" build w_jit "" --enable-experimental-jit
else
  echo "=== w_jit skipped: no LLVM 19 at $LLVM19"
  echo "    the stencil generator requires LLVM 19 specifically; RQ6b is reported as"
  echo "    unavailable rather than substituted with another toolchain"
fi

echo "=== build_real done"
for d in "$OUT"/w_*/; do [ -x "$d/bin/python3.14" ] && echo "    ${d%/}"; done
