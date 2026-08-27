#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/build"
NAT="$BUILD/native"
mkdir -p "$NAT"

CC_BIN=${CC_BIN:-/usr/bin/clang}
CXX_BIN=${CXX_BIN:-/usr/bin/clang++}

if $CC_BIN -mcpu=native -E -x c /dev/null >/dev/null 2>&1; then
  NATIVE_FLAG="-mcpu=native"
elif $CC_BIN -mcpu=apple-m3 -E -x c /dev/null >/dev/null 2>&1; then
  NATIVE_FLAG="-mcpu=apple-m3"
else
  NATIVE_FLAG="-march=native"
fi
echo "[build] native tuning flag: $NATIVE_FLAG"
echo "$NATIVE_FLAG" > "$NAT/native_flag.txt"

SO=dylib

LINK_UNDEF=()
case "$(uname -s)" in
  Linux)  SO=so ;;
  Darwin) LINK_UNDEF=(-undefined dynamic_lookup) ;;
esac

build_c_variants() {
  local variants="O0|-O0
O2|-O2
O3|-O3
O3native|-O3 $NATIVE_FLAG
O3native_novec|-O3 $NATIVE_FLAG -fno-vectorize -fno-slp-vectorize
O3native_ffast|-O3 $NATIVE_FLAG -ffast-math"
  local line name flags out
  while IFS= read -r line; do
    name="${line%%|*}"; flags="${line#*|}"
    out="$NAT/libkernels_c_$name.$SO"

    $CC_BIN $flags -shared -fPIC "$ROOT/b1_compute/kernels_c.c" -o "$out" 2>&1 | head -5
    [ -f "$out" ] && echo "[build] $(basename "$out") <- clang $flags"
  done <<< "$variants"
  $CC_BIN -O3 $NATIVE_FLAG -shared -fPIC "$ROOT/b2_branchy/branchy_c.c" -o "$NAT/libbranchy_c.$SO"
  echo "[build] libbranchy_c.$SO"

  $CC_BIN -O2 -shared -fPIC "$ROOT/b1_compute/accum_c.c" -o "$NAT/libaccum_c.$SO"
  echo "[build] libaccum_c.$SO <- clang -O2 (no fast-math, on purpose)"
}

build_rust() {
  if ! command -v cargo >/dev/null; then echo "[build] cargo missing, skipping Rust"; return; fi
  ( cd "$ROOT/native_rs" && RUSTFLAGS="-C target-cpu=native" cargo build --release 2>&1 | tail -3 )
  for f in "$ROOT/native_rs/target/release/libmpkernels."*; do
    case "$f" in *.dylib|*.so) cp "$f" "$NAT/" && echo "[build] $(basename "$f")" ;; esac
  done
}

build_for_venv() {
  local tag="$1" py="$2"
  [ -x "$py" ] || { echo "[build] $tag: no interpreter at $py"; return; }
  local out="$BUILD/$tag"
  mkdir -p "$out"

  local extsuf
  extsuf="$("$py" -c 'import importlib.machinery as m; print(m.EXTENSION_SUFFIXES[0])' 2>/dev/null)"
  [ -n "$extsuf" ] || extsuf=".so"

  local pyinc numpyinc
  local -a inc=()
  pyinc="$("$py" -c 'import sysconfig;print(sysconfig.get_paths()["include"])')"
  [ -n "$pyinc" ] && inc+=(-I"$pyinc")
  numpyinc="$("$py" -c 'import numpy;print(numpy.get_include())' 2>/dev/null || true)"
  [ -n "$numpyinc" ] && inc+=(-I"$numpyinc")

  for mod in b1_compute/kernels_cy b2_branchy/branchy_cy; do
    local base; base="$(basename "$mod")"
    if "$py" -m cython -3 "$ROOT/$mod.pyx" -o "$out/$base.c" > "$out/$base.cython.log" 2>&1; then
      if $CC_BIN -O3 $NATIVE_FLAG -shared -fPIC "${LINK_UNDEF[@]}" "${inc[@]}" \
            "$out/$base.c" -o "$out/$base$extsuf" > "$out/$base.cc.log" 2>&1; then
        echo "[build] $tag/$base$extsuf"
      else
        echo "[build] $tag/$base FAILED (see $out/$base.cc.log)"; tail -3 "$out/$base.cc.log"
      fi
    else
      echo "[build] $tag/$base cython FAILED"; tail -5 "$out/$base.cython.log"
    fi
  done

  local pbinc
  pbinc="$("$py" -c 'import pybind11;print(pybind11.get_include())' 2>/dev/null || true)"
  if [ -n "$pbinc" ]; then
    $CC_BIN -O3 $NATIVE_FLAG -c -fPIC "$ROOT/b1_compute/kernels_c.c" -o "$out/kernels_c.o" \
        > "$out/kernels_c.log" 2>&1

    if $CXX_BIN -O3 $NATIVE_FLAG -std=c++17 -shared -fPIC "${LINK_UNDEF[@]}" \
          -I"$pbinc" "${inc[@]}" "$ROOT/b1_compute/kernels_pb.cpp" "$out/kernels_c.o" \
          -o "$out/kernels_pb$extsuf" > "$out/kernels_pb.log" 2>&1; then
      echo "[build] $tag/kernels_pb$extsuf"
    else
      echo "[build] $tag/kernels_pb FAILED (see $out/kernels_pb.log)"
      tail -5 "$out/kernels_pb.log"
    fi
  else
    echo "[build] $tag: pybind11 unavailable"
  fi

  local codon="${CODON_DIR:-}"
  [ -z "$codon" ] && [ -x "$HOME/mp-x86/codon/codon-deploy-linux-x86_64/bin/codon" ] \
      && codon="$HOME/mp-x86/codon/codon-deploy-linux-x86_64"
  if [ -n "$codon" ] && [ -x "$codon/bin/codon" ]; then
    for mod in b1_compute/kernels_codon b2_branchy/branchy_codon; do
      local cbase; cbase="$(basename "$mod")"
      if "$codon/bin/codon" build -pyext -release --relocation-model=pic \
            -module "$cbase" -o "$out/$cbase.o" \
            "$ROOT/$mod.codon" > "$out/$cbase.log" 2>&1 \
         && $CC_BIN -shared "$out/$cbase.o" -o "$out/$cbase$extsuf" \
            -L"$codon/lib/codon" -lcodonrt -Wl,-rpath,"$codon/lib/codon" \
            >> "$out/$cbase.log" 2>&1; then
        echo "[build] $tag/$cbase$extsuf"
      else
        echo "[build] $tag/$cbase FAILED (see $out/$cbase.log)"
        tail -5 "$out/$cbase.log"
      fi
    done
  else
    echo "[build] $tag: codon unavailable (set CODON_DIR to the deployment root)"
  fi
}

build_c_variants
build_rust

declare -a VENVS=(
  "314:$ROOT/venvs/u314/bin/python"
  "313:$ROOT/venvs/u313/bin/python"
)

PYPY="${PYPY:-$HOME/mp-x86/pypy/bin/pypy3}"
[ -x "$PYPY" ] && VENVS+=("pypy-311:$PYPY")
want="${1:-}"
for entry in "${VENVS[@]}"; do
  tag="${entry%%:*}"; py="${entry#*:}"
  if [ -z "$want" ] || [ "$want" = "$tag" ]; then build_for_venv "$tag" "$py"; fi
done
echo "[build] done"
