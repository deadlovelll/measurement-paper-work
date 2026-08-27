#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIFORM="${UNIFORM:?set UNIFORM to the install root used by bench/build_uniform.sh}"
PYPERF_VERSION="${PYPERF_VERSION:-2.10.0}"
# The rest of the stack is pinned too. Only pyperf used to be, and an unpinned numpy had
# already drifted to two versions inside one campaign -- 2.4.4 under v314, 2.4.6 everywhere
# else -- which is exactly the kind of difference a cross-implementation comparison cannot
# see and cannot survive.
NUMPY_VERSION="${NUMPY_VERSION:-2.4.6}"
NUMBA_VERSION="${NUMBA_VERSION:-0.66.0}"
CYTHON_VERSION="${CYTHON_VERSION:-3.2.9}"
PYBIND11_VERSION="${PYBIND11_VERSION:-3.0.4}"
THREADPOOLCTL_VERSION="${THREADPOOLCTL_VERSION:-3.6.0}"
MATPLOTLIB_VERSION="${MATPLOTLIB_VERSION:-3.11.1}"
VENVS="$ROOT/bench/venvs"

# Codon's @codon.jit path is a Python package shipped inside the Codon deployment rather than
# on PyPI, and nothing installed it. Without it the three codon_jit rows of b1_compute and the
# three of b2_branchy come back "unavailable" -- honestly recorded in the sidecar, but absent
# from the run the paper reports. Accept either unpack layout, as bootstrap.sh does.
CODON_ROOT="${CODON_DIR:-$HOME/mp-x86/codon}"
for d in "$CODON_ROOT/codon-deploy-linux-x86_64" "$CODON_ROOT"; do
  [ -x "$d/bin/codon" ] && { CODON_ROOT="$d"; break; }
done
mkdir -p "$VENVS"

declare -a PY=(
  "u314:$UNIFORM/v314/bin/python3.14"
  "u313:$UNIFORM/v313/bin/python3.13"
)

for entry in "${PY[@]}"; do
  tag="${entry%%:*}"; exe="${entry#*:}"
  echo "=== $tag ($exe)"
  [ -x "$exe" ] || { echo "MISSING $exe -- run bench/build_uniform.sh first"; continue; }
  "$exe" -m venv "$VENVS/$tag" 2>&1 | tail -2
  P="$VENVS/$tag/bin/python"
  "$P" -m pip install -q --upgrade pip setuptools wheel 2>&1 | tail -2

  "$P" -m pip install -q "pyperf==$PYPERF_VERSION" "numpy==$NUMPY_VERSION" \
      "cython==$CYTHON_VERSION" "pybind11==$PYBIND11_VERSION" \
      "threadpoolctl==$THREADPOOLCTL_VERSION" 2>&1 | tail -3

  if "$P" -m pip install -q "numba==$NUMBA_VERSION" 2>&1 | tail -3; then
    "$P" -c "import numba;print('  $tag numba', numba.__version__)" 2>&1 | tail -1
  else
    echo "  $tag numba UNAVAILABLE"
  fi
  if [ -d "$CODON_ROOT/python" ]; then
    "$P" -m pip install -q "$CODON_ROOT/python" 2>&1 | tail -2
    "$P" -c "import codon; print('  $tag codon-jit', __import__('importlib.metadata', fromlist=['x']).version('codon-jit'))" 2>&1 | tail -1
  else
    echo "  $tag codon-jit UNAVAILABLE: no python/ under $CODON_ROOT"
  fi

  "$P" -c "
import sys, numpy, pyperf
print('  $tag ok', sys.version.split()[0], 'numpy', numpy.__version__, 'pyperf', pyperf.__version__)"
done

for d in "$UNIFORM"/v3*/; do
  py=$(ls "$d"bin/python3.1* 2>/dev/null | grep -v config | head -1)
  [ -x "$py" ] || continue
  "$py" -m pip install -q --disable-pip-version-check "pyperf==$PYPERF_VERSION" 2>&1 | tail -1
  echo -n "  $(basename "$d"): "
  "$py" -c "import sys, pyperf; print(sys.version.split()[0], 'pyperf', pyperf.__version__)"
done

FT=$(ls "$UNIFORM"/v314t/bin/python3.1*t 2>/dev/null | head -1)
if [ -x "$FT" ]; then
  echo "=== free-threaded interpreter: numpy/numba for the pipeline"
  "$FT" -m pip install -q --disable-pip-version-check "numpy==$NUMPY_VERSION" \
      "threadpoolctl==$THREADPOOLCTL_VERSION" 2>&1 | tail -2
  if "$FT" -m pip install -q --disable-pip-version-check "numba==$NUMBA_VERSION" 2>&1 | tail -2; then :; fi
  "$FT" -c "
import sys
for m in ('numpy', 'numba', 'threadpoolctl'):
    try:
        mod = __import__(m); print(f'  v314t {m} {getattr(mod, \"__version__\", \"?\")}')
    except Exception as exc:
        print(f'  v314t {m} UNAVAILABLE: {type(exc).__name__}')"
fi

if [ -n "${REAL:-}" ] && [ -d "$REAL" ]; then
  echo "=== build configurations: pyperf $PYPERF_VERSION"
  for d in "$REAL"/w_*/; do
    py="$d/bin/python3.14"
    [ -x "$py" ] || continue
    "$py" -m ensurepip -q > /dev/null 2>&1
    "$py" -m pip install -q --disable-pip-version-check "pyperf==$PYPERF_VERSION" > /dev/null 2>&1
    printf '  %-24s ' "$(basename "${d%/}")"
    "$py" -c "import pyperf; print('pyperf', pyperf.__version__)" 2>&1 | tail -1
  done
fi

# PyPy runs b1 and b3 unmodified. run_campaign.sh puts pyperf in on the fly but never
# numpy, so a fresh machine reproduces b1_compute-pypy311 with its six numpy rows marked
# unavailable rather than measured -- recorded in the sidecar, but still not the paper's run.
PYPY_BIN="${PYPY:-$HOME/mp-x86/pypy/bin/pypy3}"
if [ -x "$PYPY_BIN" ]; then
  echo "=== pypy ($PYPY_BIN)"
  "$PYPY_BIN" -m ensurepip -q > /dev/null 2>&1 || true
  "$PYPY_BIN" -m pip install -q --disable-pip-version-check \
      "pyperf==$PYPERF_VERSION" "numpy==$NUMPY_VERSION" \
      "threadpoolctl==$THREADPOOLCTL_VERSION" 2>&1 | tail -2
  "$PYPY_BIN" -c "
for m in ('pyperf', 'numpy', 'threadpoolctl'):
    try:
        print(f'  pypy {m}', __import__(m).__version__)
    except Exception as exc:
        print(f'  pypy {m} UNAVAILABLE: {type(exc).__name__}')"
else
  echo "  pypy not found at $PYPY_BIN -- set PYPY to its interpreter"
fi

"$VENVS/u313/bin/python" -m pip install -q "matplotlib==$MATPLOTLIB_VERSION" 2>&1 | tail -2
"$VENVS/u313/bin/python" -c "import matplotlib;print('  matplotlib', matplotlib.__version__)"
echo "=== setup done"
