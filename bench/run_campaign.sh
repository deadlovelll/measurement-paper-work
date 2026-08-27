#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
UNIFORM="${UNIFORM:?set UNIFORM to the install root used by bench/build_uniform.sh}"
LOGS="$ROOT/logs/pyperf"
mkdir -p "$LOGS" "$ROOT/results/pyperf"

[ -s "$ROOT/bench/affinity.txt" ] || bash "$ROOT/bench/host_topology.sh" > /dev/null 2>&1 || true
AFF=""; AFF_T=""
[ -s "$ROOT/bench/affinity.txt" ]         && AFF="--affinity $(cat "$ROOT/bench/affinity.txt")"
[ -s "$ROOT/bench/affinity-threads.txt" ] && AFF_T="--affinity $(cat "$ROOT/bench/affinity-threads.txt")"

AFF_ACTIVE="$AFF"

V310="$UNIFORM/v310/bin/python3.10"
V311="$UNIFORM/v311/bin/python3.11"
V312="$UNIFORM/v312/bin/python3.12"
V313="$UNIFORM/v313/bin/python3.13"
V314="$UNIFORM/v314/bin/python3.14"
V314T="$UNIFORM/v314t/bin/python3.14t"

U314="$ROOT/bench/venvs/u314/bin/python"
U313="$ROOT/bench/venvs/u313/bin/python"

PHASES="${*:-compute branchy versions spec threads builds pipeline cinderx pypy}"

HEAVY="-p 10 -n 3 -w 1"
VHEAVY="-p 5 -n 3 -w 1"

say() { printf '\n=== %s\n' "$*"; }

run2() {
  local name="$1" script="$2" py="$3"; shift 3
  local out="$ROOT/results/pyperf/${name}.json"
  local log="$LOGS/$name.log"
  [ -x "$py" ] || { echo "  skip $name: no interpreter at $py"; return; }
  rm -f "$out"
  printf '  %-30s ' "$name (2 passes)"

  if "$py" "$script" "$@" $AFF_ACTIVE -o "$out" > "$log" 2>&1 \
     && "$py" "$script" "$@" $AFF_ACTIVE --reverse --append "$out" >> "$log" 2>&1; then
    local warn; warn=$(grep -cE "WARNING|unstable|Not enough" "$log" || true)
    echo "ok  ($warn stability warnings)  -> $log"
  else
    echo "FAILED -> $log"; tail -12 "$log" | sed 's/^/      /'
  fi
}

run() {
  local name="$1"; shift
  local script="$1"; shift
  local py="$1"; shift
  local log="$LOGS/$name.log"
  if [ ! -x "$py" ]; then echo "  skip $name: no interpreter at $py"; return; fi
  printf '  %-30s ' "$name"

  if "$py" "$script" "$@" $AFF_ACTIVE > "$log" 2>&1; then
    local n; n=$(grep -cE "Mean \+- std dev|Median" "$log" || true)
    local warn; warn=$(grep -cE "WARNING|unstable|Not enough" "$log" || true)
    echo "ok  ($n benchmarks, $warn stability warnings)  -> $log"
  else
    echo "FAILED -> $log"; tail -12 "$log" | sed 's/^/      /'
  fi
}

discover() {
  local name="$1" script="$2" py="$3" lab="$4"
  local log="$LOGS/$name.discover.log"
  [ -x "$py" ] || { echo "  skip $name discovery: no $py"; return 1; }
  printf '  %-30s ' "$name discovery"
  if "$py" "$script" --discover --label "$lab" > "$log" 2>&1; then
    echo "$(grep -c '  ok ' "$log") ok, $(grep -cE 'WRONG|unavailable|error ' "$log") problems"
    grep -E "WRONG|unavailable|error " "$log" | sed 's/^/      /' || true
  else
    echo "FAILED -> $log"; tail -8 "$log" | sed 's/^/      /'; return 1
  fi
}

for phase in $PHASES; do
case "$phase" in
compute)
  say "compute-bound kernels and the flag study (reference interpreter: v314)"
  bash bench/b1_compute/codegen_diff.sh > "$LOGS/codegen_diff.log" 2>&1 \
    && echo "  codegen identity map -> results/codegen_identity.json" \
    || echo "  codegen_diff FAILED -> $LOGS/codegen_diff.log"
  discover b1_compute bench/b1_compute/run_b1.py "$U314" 314 \
    && run2 b1_compute-314 bench/b1_compute/run_b1.py "$U314" --label 314 $HEAVY
  discover b1_flags bench/b1_compute/run_flags.py "$U314" 314 \
    && run2 b1_flags-314 bench/b1_compute/run_flags.py "$U314" --label 314 $HEAVY
  run b1_breakeven bench/b1_compute/breakeven.py "$U314" --label 314 $HEAVY
  ;;

branchy)
  say "branchy, allocating and pointer-chasing kernels (v314)"
  discover b2_branchy bench/b2_branchy/run_b2.py "$U314" 314 \
    && run2 b2_branchy-314 bench/b2_branchy/run_b2.py "$U314" --label 314 $HEAVY
  ;;

versions)
  say "runtime operation suite and start-up, 3.10 -> 3.14 (identical builds)"
  for pair in "v310:$V310" "v311:$V311" "v312:$V312" "v313:$V313" "v314:$V314" "v314t:$V314T"; do
    lab="${pair%%:*}"; py="${pair#*:}"
    run "b3_runtime-$lab" bench/b3_runtime/run_b3.py "$py" --label "$lab"
    run "b3_startup-$lab" bench/b3_runtime/run_startup.py "$py" --label "$lab"
  done
  ;;

spec)
  say "specialisation warm-up, 3.10 -> 3.14 (fixed loops: one call is microseconds)"
  for pair in "v310:$V310" "v311:$V311" "v312:$V312" "v313:$V313" "v314:$V314"; do
    lab="${pair%%:*}"; py="${pair#*:}"
    run "b3_spec-$lab" bench/b3_runtime/run_spec.py "$py" --label "$lab" -l 200
  done
  ;;

threads)
  say "thread scaling: GIL, free-threaded with the GIL forced on, free-threaded"

  AFF_ACTIVE="$AFF_T"
  echo "  affinity for this phase: ${AFF_ACTIVE:-none}"
  run b4_threads-gil bench/b4_threads/run_b4.py "$V314" --label gil $VHEAVY
  if [ -x "$V314T" ]; then
    printf '  %-30s ' "b4_threads-ft_gil"

    if PYTHON_GIL=1 "$V314T" bench/b4_threads/run_b4.py --label ft_gil $VHEAVY $AFF_ACTIVE \
         > "$LOGS/b4_threads-ft_gil.log" 2>&1; then echo "ok"; else
      echo "FAILED"; tail -8 "$LOGS/b4_threads-ft_gil.log" | sed 's/^/      /'; fi
    run b4_threads-ft bench/b4_threads/run_b4.py "$V314T" --label ft $VHEAVY
  fi
  AFF_ACTIVE="$AFF"
  ;;

builds)
  say "build configurations of one CPython 3.14.6 source tree, one compiler"
  REAL="${REAL:?set REAL to the build-configuration install root}"
  for cfg in plain pgo ltothin ltofull pgo_ltofull pgo_ltofull_native jit; do
    py="$REAL/w_$cfg/bin/python3.14"
    run "b5_buildcfg-$cfg" bench/b3_runtime/run_b3.py "$py" \
      --label "$cfg" --suite-name b5_buildcfg
    run "b5_startup-$cfg" bench/b3_runtime/run_startup.py "$py" --label "$cfg" \
      --suite-name b5_startup
  done
  ;;

pipeline)
  say "mixed-stage pipeline: the same stack under the GIL and free-threaded"

  discover b7_pipeline-gil bench/b7_pipeline/run_b7.py "$U314" gil \
    && run b7_pipeline-gil bench/b7_pipeline/run_b7.py "$U314" --label gil $HEAVY
  if [ -x "$V314T" ]; then
    discover b7_pipeline-ft bench/b7_pipeline/run_b7.py "$V314T" ft \
      && run b7_pipeline-ft bench/b7_pipeline/run_b7.py "$V314T" --label ft $HEAVY
  fi
  ;;

cinderx)
  say "the Cinder fork and CinderX, natively on this host"

  CINDER="${CINDER:?set CINDER to the install root used by bench/b6_cinderx/build_cinderx.sh}"
  CINDER="$CINDER" bash bench/b6_cinderx/run_b6_native.sh
  ;;

pypy)
  say "PyPy: the same suites, unmodified pure-Python code"
  PYPY="${PYPY:-$ROOT/logs/pypy/bin/pypy3}"
  if [ -x "$PYPY" ]; then
    if ! "$PYPY" -c "import pyperf" 2>/dev/null; then
      echo "  installing pyperf into PyPy (builds psutil from source, takes a minute)"
      "$PYPY" -m ensurepip -q > /dev/null 2>&1 || true
      "$PYPY" -m pip install --disable-pip-version-check "pyperf==2.10.0" \
        > "$LOGS/pypy-pyperf-install.log" 2>&1 \
        || { echo "  pyperf install FAILED -> $LOGS/pypy-pyperf-install.log"
             tail -5 "$LOGS/pypy-pyperf-install.log" | sed 's/^/      /'; }
    fi
    if "$PYPY" -c "import pyperf" 2>/dev/null; then
      run b3_runtime-pypy bench/b3_runtime/run_b3.py "$PYPY" --label pypy311
      run b3_startup-pypy bench/b3_runtime/run_startup.py "$PYPY" --label pypy311
      discover b1_compute-pypy bench/b1_compute/run_b1.py "$PYPY" pypy311 \
        && run2 b1_compute-pypy311 bench/b1_compute/run_b1.py "$PYPY" --label pypy311 $HEAVY
      discover b2_branchy-pypy bench/b2_branchy/run_b2.py "$PYPY" pypy311 \
        && run2 b2_branchy-pypy311 bench/b2_branchy/run_b2.py "$PYPY" --label pypy311 $HEAVY
    else
      echo "  skip pypy: pyperf could not be installed into $PYPY"
    fi
  else
    echo "  skip pypy: no interpreter at $PYPY"
  fi
  ;;

*) echo "unknown phase: $phase" ;;
esac
done

say "campaign done; results in results/pyperf, logs in $LOGS"
ls -1 "$ROOT/results/pyperf"/*.json 2>/dev/null | wc -l | xargs echo "  result files:"
