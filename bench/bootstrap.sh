#!/usr/bin/env bash
# Everything from a bare machine to the built paper, in one command.
#
# The artifact's other scripts each assume their inputs already exist: build_uniform.sh wants a
# compiler, build_all.sh wants cargo and a Codon deployment, build_real.sh wants an LLVM 19 for
# the tier-2 JIT configuration. This fetches all of that, then runs them in the one order that
# works, then measures, then draws.
#
# cinderx-workshop/ is the exception: it ships with the artifact and is never downloaded, because
# the CinderX sources in it carry the ADAPTIVE_STATIC_PYTHON patch RQ4 rests on.
#
#   bash bench/bootstrap.sh --check     what is missing; installs nothing
#   bash bench/bootstrap.sh --deps      fetch toolchains and sources, build nothing
#   bash bench/bootstrap.sh --build     deps, then every interpreter and native artifact
#   bash bench/bootstrap.sh --measure   build, then the full campaign (hours; machine must idle)
#   bash bench/bootstrap.sh --paper     measure, then figures, tables and both PDFs
#   bash bench/bootstrap.sh             the same as --paper
#
# Every stage is idempotent: anything already present is skipped, so a stage that dies part way
# can be re-run. Nothing is deleted. System packages are the one thing this will not install
# behind your back -- it prints the apt line and stops.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PREFIX="${PREFIX:-$HOME/mp-x86}"
UNIFORM="${UNIFORM:-$PREFIX/uniform}"
REAL="${REAL:-$PREFIX/realbuilds}"
CINDER_OUT="${CINDER_OUT:-$PREFIX/cinder}"
PYPY_DIR="${PYPY_DIR:-$PREFIX/pypy}"
CODON_DIR="${CODON_DIR:-$PREFIX/codon}"
LLVM19="${LLVM19:-$HOME/.local/llvm19/bin}"
WORKSHOP="$ROOT/cinderx-workshop"

PYPY_URL="${PYPY_URL:-https://downloads.python.org/pypy/pypy3.11-v7.3.20-linux64.tar.bz2}"
CODON_URL="${CODON_URL:-https://github.com/exaloop/codon/releases/download/v0.19.4/codon-linux-x86_64.tar.gz}"
LLVM19_URL="${LLVM19_URL:-https://github.com/llvm/llvm-project/releases/download/llvmorg-19.1.7/LLVM-19.1.7-Linux-X64.tar.xz}"

APT_PACKAGES="build-essential clang lld llvm pkg-config git curl ca-certificates \
libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
uuid-dev libgdbm-dev tk-dev xz-utils cmake ninja-build"

STAGE="${1:---paper}"
missing=0
did=""
skipped=""

say()  { printf '\n=== %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
have() { command -v "$1" > /dev/null 2>&1; }

want() {
  # want <name> <test-command...> -- record whether a prerequisite is satisfied
  local name="$1"; shift
  if "$@" > /dev/null 2>&1; then
    printf '  %-22s present\n' "$name"
    return 0
  fi
  printf '  %-22s MISSING\n' "$name"
  missing=$((missing + 1))
  return 1
}

fetch_tar() {
  # fetch_tar <url> <destination-dir> <strip-components>
  local url="$1" dest="$2" strip="${3:-1}"
  [ -d "$dest" ] && { skipped="$skipped $dest"; return 0; }
  mkdir -p "$dest"
  note "fetching $(basename "$url")"
  curl -fsSL "$url" | tar -x --strip-components="$strip" -C "$dest" || {
    echo "    FAILED: $url"; rm -rf "$dest"; return 1
  }
  did="$did $dest"
}

# ---------------------------------------------------------------- inventory

say "what this machine already has"
want "C toolchain"      have clang
want "cmake"            have cmake
want "git"              have git
want "curl"             have curl
want "cargo (Rust)"     have cargo
want "tectonic"         have tectonic
want "PyPy"             test -x "$PYPY_DIR/bin/pypy3"
want "Codon"            test -x "$CODON_DIR/bin/codon"
want "LLVM 19"          test -x "$LLVM19/clang"
want "Cinder workshop"  test -d "$WORKSHOP/cinder"
want "six interpreters" test -x "$UNIFORM/v314/bin/python3.14"
want "seven builds"     test -d "$REAL/w_plain"
want "CinderX built"    test -d "$CINDER_OUT/fork314"

if [ "$STAGE" = "--check" ]; then
  echo
  if [ "$missing" -eq 0 ]; then
    echo "nothing missing: bash bench/bootstrap.sh --measure would go straight to the campaign"
  else
    echo "$missing item(s) missing. Run without --check to fetch what can be fetched."
    echo "System packages are not installed automatically; if the C toolchain is missing:"
    echo "  sudo apt-get install -y $APT_PACKAGES"
  fi
  exit 0
fi

if ! have clang || ! have cmake; then
  say "system packages are missing and this script will not install them for you"
  echo "  sudo apt-get install -y $APT_PACKAGES"
  echo
  echo "Re-run this script once that finishes."
  exit 1
fi

# ---------------------------------------------------------------- toolchains

say "toolchains and sources"

if ! have cargo; then
  note "installing Rust through rustup (default toolchain, no nightly)"
  curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path \
    && . "$HOME/.cargo/env" && did="$did rust"
else
  skipped="$skipped rust"
fi

fetch_tar "$PYPY_URL"    "$PYPY_DIR"  1
fetch_tar "$CODON_URL"   "$CODON_DIR" 1
fetch_tar "$LLVM19_URL"  "$(dirname "$LLVM19")" 1

if [ -d "$WORKSHOP/cinder" ] && [ -d "$WORKSHOP/cpython" ]; then
  skipped="$skipped cinderx-workshop"
else
  say "cinderx-workshop is missing"
  echo "  It ships with this artifact rather than being fetched: it holds the Cinder fork, the"
  echo "  CPython tree the seven build configurations are cut from, and the CinderX sources with"
  echo "  the ADAPTIVE_STATIC_PYTHON patch that RQ4 rests on. Without it the cinderx phase and"
  echo "  the builds phase cannot run."
  echo
  echo "  Expected at: $WORKSHOP"
  exit 1
fi

if ! have tectonic; then
  note "tectonic not found: the PDFs cannot be built"
  note "install it with:  cargo install tectonic   (needs libssl-dev, libfontconfig-dev)"
fi

[ "$STAGE" = "--deps" ] && { say "deps done"; echo "  fetched:$did"; echo "  skipped:$skipped"; exit 0; }

# ---------------------------------------------------------------- builds

say "1/6  host topology, affinity masks and results/host.json"
bash bench/host_topology.sh > /dev/null || note "host_topology failed"

say "2/6  six interpreters from release tarballs, one compiler, one configure line"
OUT="$UNIFORM" bash bench/build_uniform.sh || note "build_uniform failed"

say "3/6  venvs on those interpreters (build_all.sh builds into them, so this comes first)"
UNIFORM="$UNIFORM" bash bench/setup_env.sh || note "setup_env failed"

say "4/6  native artifacts: Cython, pybind11, Codon, C flag variants, ladder, Rust"
CODON_DIR="$CODON_DIR" PYPY="$PYPY_DIR/bin/pypy3" bash bench/build_all.sh || note "build_all failed"

say "5/6  seven build configurations of one 3.14.6 tree"
OUT="$REAL" LLVM19="$LLVM19" bash bench/b5_buildflags/build_real.sh || note "build_real failed"

say "5b/6 pyperf into those seven: they are configured without pip, so this pass follows"
REAL="$REAL" bash bench/setup_env.sh || note "setup_env (REAL) failed"

say "6/6  Cinder fork and CinderX"
OUT="$CINDER_OUT" bash bench/b6_cinderx/build_cinderx.sh || note "build_cinderx failed"

say "gates before anything is measured"
"$ROOT/bench/venvs/u313/bin/python" bench/check_provenance.py "$UNIFORM" || note "provenance gate FAILED"
bash bench/b1_compute/codegen_diff.sh > /dev/null  || note "codegen_diff failed"
bash bench/b2_branchy/codegen_check.sh > /dev/null || note "codegen_check failed"

[ "$STAGE" = "--build" ] && { say "build done"; exit 0; }

# ---------------------------------------------------------------- measurement

say "the campaign -- hours, and the machine must be otherwise idle"
note "a background job that only touches other cores is still visible in a parallel benchmark"
UNIFORM="$UNIFORM" REAL="$REAL" PYPY="$PYPY_DIR/bin/pypy3" CINDER="$CINDER_OUT" \
  bash bench/run_campaign.sh || note "run_campaign failed"

say "the two sets the cinderx phase does not cover"
CINDER="$CINDER_OUT" bash bench/b6_cinderx/run_jitopts.sh || note "run_jitopts failed"
"$CINDER_OUT/venv-cinder-adaptive/bin/python" bench/b6_cinderx/run_gc_scale.py --label gcscale \
  || note "run_gc_scale failed"

say "does the data deserve to reach the paper?"
"$ROOT/bench/venvs/u313/bin/python" bench/plots/verify_campaign.py

[ "$STAGE" = "--measure" ] && { say "measurement done"; exit 0; }

# ---------------------------------------------------------------- the paper

PY="$ROOT/bench/venvs/u313/bin/python"

say "figures and tables, both languages"
"$PY" bench/plots/make_figures.py    || note "make_figures failed"
"$PY" bench/plots/make_tables.py     || note "make_tables failed"
"$PY" bench/plots/make_figures_ru.py || note "make_figures_ru failed"
"$PY" bench/plots/make_tables_ru.py  || note "make_tables_ru failed"

say "the paper"
if have tectonic; then
  ( cd paper && tectonic -X compile paper.tex && tectonic -X compile paper-ru.tex )
else
  note "tectonic missing; skipping the PDFs"
fi

say "every gate"
UNIFORM="$UNIFORM" BIBLIO_ONLINE=1 bash bench/check_paper.sh
gates=$?

say "done"
echo "  fetched:$did"
echo "  already present:$skipped"
echo "  gates failing: $gates"
exit "$gates"
