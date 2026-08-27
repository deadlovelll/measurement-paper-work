#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIFORM="${UNIFORM:?set UNIFORM to the install root used by bench/build_uniform.sh}"
PYPERF_VERSION="${PYPERF_VERSION:-2.10.0}"
VENVS="$ROOT/bench/venvs"
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

  "$P" -m pip install -q "pyperf==$PYPERF_VERSION" numpy cython pybind11 threadpoolctl 2>&1 | tail -3

  if "$P" -m pip install -q numba 2>&1 | tail -3; then
    "$P" -c "import numba;print('  $tag numba', numba.__version__)" 2>&1 | tail -1
  else
    echo "  $tag numba UNAVAILABLE"
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
  "$FT" -m pip install -q --disable-pip-version-check numpy threadpoolctl 2>&1 | tail -2
  if "$FT" -m pip install -q --disable-pip-version-check numba 2>&1 | tail -2; then :; fi
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

"$VENVS/u313/bin/python" -m pip install -q matplotlib 2>&1 | tail -2
"$VENVS/u313/bin/python" -c "import matplotlib;print('  matplotlib', matplotlib.__version__)"
echo "=== setup done"
