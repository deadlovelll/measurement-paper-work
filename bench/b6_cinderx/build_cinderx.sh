#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${OUT:?set OUT to the install root}"
JOBS="${JOBS:-$(nproc)}"
CC_BIN="${CC_BIN:-/usr/bin/clang}"
CXX_BIN="${CXX_BIN:-/usr/bin/clang++}"
PYPERF_VERSION="${PYPERF_VERSION:-2.10.0}"

unset PKG_CONFIG_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH LD_LIBRARY_PATH \
      CFLAGS CXXFLAGS LDFLAGS CPPFLAGS 2>/dev/null || true
PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vE '^/opt/intel|^/opt/nvidia|/oneapi/' | paste -sd: -)"
export PATH

SRC_CPY="$ROOT/cinderx-workshop/cpython"
SRC_FORK="$ROOT/cinderx-workshop/cinder"
if [ -d "$ROOT/cinderx-workshop/cinderx" ]; then
  SRC_CX="$ROOT/cinderx-workshop/cinderx"
else
  SRC_CX="$SRC_CPY/cinderx"
fi
WORK="$OUT/src"
LOGS="$OUT/logs"
mkdir -p "$OUT" "$WORK" "$LOGS"

PYCONF="--with-ensurepip=install --enable-loadable-sqlite-extensions"

echo "=== RQ4 native build"
echo "    CC       = $CC_BIN ($($CC_BIN --version | head -1))"
echo "    configure= $PYCONF   (identical for stock and fork)"
echo "    jobs     = $JOBS"
echo "    out      = $OUT"

fail() { echo "=== FAILED: $*" >&2; exit 1; }

stage() {
  local src="$1" dst="$2"
  [ -d "$dst" ] && { echo "=== staged already: $(basename "$dst")"; return; }
  echo "=== staging $(basename "$dst")"
  mkdir -p "$dst"

  ( cd "$src" && tar cf - --exclude=./.git --exclude='*.o' --exclude=./build . ) \
    | ( cd "$dst" && tar xf - ) || fail "staging $dst"
}

build_py() {
  local name="$1" src="$2" prefix="$3"
  if [ -x "$prefix/bin/python3" ]; then echo "=== $name already built"; return 0; fi
  echo "=== building $name -> $prefix"
  (
    cd "$src" || exit 1
    export CC="$CC_BIN" CXX="$CXX_BIN"
    make distclean > /dev/null 2>&1 || true

    ./configure --prefix="$prefix" $PYCONF > "$LOGS/$name.configure.log" 2>&1 \
      || { echo "configure FAILED"; exit 1; }
    make -j"$JOBS" > "$LOGS/$name.make.log" 2>&1 || { echo "make FAILED"; exit 1; }
    make install > "$LOGS/$name.install.log" 2>&1 || { echo "install FAILED"; exit 1; }
  ) || { tail -15 "$LOGS/$name."*.log 2>/dev/null | sed 's/^/      /'; fail "$name"; }
  echo -n "=== $name OK: "
  "$prefix/bin/python3" -VV || fail "$name produced no working interpreter"
}

stage "$SRC_CPY"  "$WORK/cpython"
stage "$SRC_FORK" "$WORK/cinder"
build_py stock314 "$WORK/cpython" "$OUT/stock314"
build_py fork314  "$WORK/cinder"  "$OUT/fork314"

if grep -q '^uint8_t _PyOpcode_Caches\[256\]' "$WORK/cinder/Include/internal/pycore_opcode_metadata.h"; then
  echo "=== fork carries the de-const opcode-table patch (adaptive configuration can build)"
else
  echo "=== WARNING: fork's _PyOpcode_Caches is still const; the adaptive build will fail"
fi

build_cinderx() {
  local tag="$1" adaptive="$2"
  local venv="$OUT/venv-$tag"
  local cxsrc="$WORK/cinderx-$tag"

  if "$venv/bin/python" -c "import cinderx" > /dev/null 2>&1; then
    echo "=== cinderx/$tag already installed"; return 0
  fi
  echo "=== CinderX [$tag]  ENABLE_ADAPTIVE_STATIC_PYTHON=$adaptive"

  [ -d "$venv" ] || "$OUT/fork314/bin/python3" -m venv "$venv" || fail "venv $tag"
  "$venv/bin/python" -m pip install -q --upgrade pip setuptools wheel > /dev/null 2>&1

  rm -rf "$cxsrc"
  stage "$SRC_CX" "$cxsrc"
  rm -rf "$cxsrc/scratch" "$cxsrc"/*.egg-info

  (
    cd "$cxsrc" || exit 1
    CC="$CC_BIN" CXX="$CXX_BIN" \
    ENABLE_ADAPTIVE_STATIC_PYTHON="$adaptive" \
    ENABLE_EVAL_HOOK=0 \
    ENABLE_GENERATOR_AWAITER=0 \
    "$venv/bin/python" -m pip install . --force-reinstall --no-deps \
      > "$LOGS/cinderx-$tag.log" 2>&1
  )
  local rc=$?
  echo "    compiler errors in log: $(grep -c 'error:' "$LOGS/cinderx-$tag.log" || true)"
  if [ $rc -ne 0 ]; then
    echo "=== CinderX [$tag] BUILD FAILED -> $LOGS/cinderx-$tag.log"
    grep -E "error:" "$LOGS/cinderx-$tag.log" | head -12 | sed 's/^/      /'
    return 1
  fi

  "$venv/bin/python" - <<'PY' || { echo "=== CinderX [$tag] imports but does not initialise"; return 1; }
import cinderx
cinderx.init()
cinderx.install_frame_evaluator()
import cinderx.jit as J
print(f"    cinderx {getattr(cinderx, '__version__', '?')}  "
      f"jit_enabled={getattr(J, 'is_enabled', lambda: '?')()}")
PY
  echo "=== CinderX [$tag] OK"
}

build_cinderx cinder          0 || echo "=== continuing without the plain CinderX configuration"
build_cinderx cinder-adaptive 1 || echo "=== continuing without the adaptive CinderX configuration"

echo "=== pyperf $PYPERF_VERSION"
for p in "$OUT/stock314/bin/python3" "$OUT/venv-cinder/bin/python" \
         "$OUT/venv-cinder-adaptive/bin/python"; do
  [ -x "$p" ] || continue
  "$p" -m pip install -q --disable-pip-version-check "pyperf==$PYPERF_VERSION" > /dev/null 2>&1
  printf '    %-42s ' "$p"
  "$p" -c "import pyperf, sys; print(sys.version.split()[0], 'pyperf', pyperf.__version__)" \
    || echo "pyperf MISSING"
done

echo "=== build_cinderx done"
for d in stock314 fork314 venv-cinder venv-cinder-adaptive; do
  [ -d "$OUT/$d" ] && echo "    $OUT/$d"
done
