#!/usr/bin/env bash

set -u
OUT="${OUT:?set OUT to the install root}"
VERSIONS="${VERSIONS:-3.10.18 3.11.6 3.12.12 3.13.5 3.14.6 3.14.6t}"
JOBS="${JOBS:-$(nproc)}"
SRCDIR="${SRCDIR:-$OUT/src}"
mkdir -p "$OUT" "$SRCDIR"

scrub_env() {
  unset PKG_CONFIG_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH LD_LIBRARY_PATH \
        CFLAGS CXXFLAGS LDFLAGS CPPFLAGS ACLOCAL_PATH MANPATH INFOPATH 2>/dev/null || true

  PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vE '^/opt/intel|^/opt/nvidia|/oneapi/' \
          | paste -sd: -)"
  export PATH
}
scrub_env
echo "=== environment scrubbed: PKG_CONFIG_PATH and vendor PATH entries removed"

export CC="${CC_BIN:-/usr/bin/clang}"
export CXX="${CXX_BIN:-/usr/bin/clang++}"

export LLVM_PROFDATA="${LLVM_PROFDATA:-$(dirname "$CC")/llvm-profdata}"
[ -x "$LLVM_PROFDATA" ] || LLVM_PROFDATA="$(command -v llvm-profdata)"
export LLVM_PROFDATA

echo "=== uniform interpreter set"
echo "    CC            = $CC  ($($CC --version | head -1))"
echo "    LLVM_PROFDATA = $LLVM_PROFDATA"
echo "    configure     = --enable-optimizations --with-ensurepip=install [--disable-gil]"

for spec in $VERSIONS; do
  ft=""; v="$spec"
  case "$spec" in *t) ft="--disable-gil"; v="${spec%t}";; esac
  mm="${v%.*}"
  short="v${mm//./}"
  [ -n "$ft" ] && short="${short}t"
  prefix="$OUT/$short"
  exe="$prefix/bin/python$mm"
  [ -n "$ft" ] && exe="$prefix/bin/python${mm}t"
  if [ -x "$exe" ]; then
    echo "=== $spec already built ($short)"; continue
  fi
  tgz="$SRCDIR/Python-$v.tgz"
  if [ ! -s "$tgz" ]; then
    echo "=== downloading $v"
    curl -sL -o "$tgz" "https://www.python.org/ftp/python/$v/Python-$v.tgz" \
      || { echo "=== $spec download FAILED"; continue; }
  fi
  echo "=== building $spec -> $short  (PGO${ft:+, free-threaded})"
  rm -rf "$SRCDIR/$short"
  mkdir -p "$SRCDIR/$short"
  tar xzf "$tgz" -C "$SRCDIR/$short" --strip-components=1
  (
    cd "$SRCDIR/$short" || exit 1
    ./configure --prefix="$prefix" --enable-optimizations --with-ensurepip=install $ft \
      > "$OUT/$short.configure.log" 2>&1 || { echo "configure FAILED"; exit 1; }
    make -j"$JOBS" > "$OUT/$short.make.log" 2>&1 || { echo "make FAILED"; exit 1; }
    make altinstall > "$OUT/$short.install.log" 2>&1 || { echo "install FAILED"; exit 1; }
  )
  if [ -x "$exe" ]; then
    echo -n "=== $spec OK: $("$exe" -VV | head -c 90) | "
    "$exe" -c "
import sysconfig as s
f=(s.get_config_var('PY_CORE_CFLAGS') or '')+' '+(s.get_config_var('PY_CORE_LDFLAGS') or '')
print('pgo=', 'yes' if 'profile-use' in f or 'fprofile' in f else 'no',
      'lto=', ' '.join(t for t in f.split() if 'lto' in t) or 'none',
      'gil=', s.get_config_var('Py_GIL_DISABLED') or 0)"
  else
    echo "=== $spec FAILED (see $OUT/$short.*.log)"
    tail -5 "$OUT/$short.configure.log" "$OUT/$short.make.log" 2>/dev/null | tail -12
  fi
done
echo "=== build_uniform done"
ls -d "$OUT"/v3* 2>/dev/null
