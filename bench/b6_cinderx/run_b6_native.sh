#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1
CINDER="${CINDER:?set CINDER to the install root used by build_cinderx.sh}"
LOGS="$ROOT/logs/pyperf"
mkdir -p "$LOGS" "$ROOT/results/pyperf"

STOCK="$CINDER/stock314/bin/python3"
FORK="$CINDER/venv-cinder/bin/python"
FORKA="$CINDER/venv-cinder-adaptive/bin/python"
B6="bench/b6_cinderx/run_b6.py"
B6S="bench/b6_cinderx/run_b6_static.py"

PROC="-p 10 -n 3 -w 1"
AFF=""
[ -s "$ROOT/bench/affinity.txt" ] && AFF="--affinity $(cat "$ROOT/bench/affinity.txt")"

CONFIGS="${*:-stock fork cinderx jit static cinderx_adaptive jit_adaptive static_adaptive}"

run() {
  local name="$1" py="$2"; shift 2
  local log="$LOGS/b6-$name.log"
  if [ ! -x "$py" ]; then echo "  skip $name: no interpreter at $py"; return; fi
  printf '  %-26s ' "$name"

  if "$py" "$@" > "$log" 2>&1; then
    local n warn
    n=$(grep -cE "Mean \+- std dev|Median" "$log" || true)
    warn=$(grep -cE "WARNING|unstable|Not enough" "$log" || true)
    echo "ok  ($n benchmarks, $warn stability warnings)  -> $log"
  else
    echo "FAILED -> $log"; tail -12 "$log" | sed 's/^/      /'
  fi
}

run_static() {
  local name="$1" py="$2"
  local plan="results/pyperf/b6_static-$name.plan.json"
  if [ ! -x "$py" ]; then echo "  skip $name: no interpreter at $py"; return; fi
  printf '  %-26s ' "$name discovery"
  if "$py" "$B6S" --discover --label "$name" > "$LOGS/b6-$name.discover.log" 2>&1; then
    echo "ok"
  else
    echo "FAILED -> $LOGS/b6-$name.discover.log"
    tail -8 "$LOGS/b6-$name.discover.log" | sed 's/^/      /'; return
  fi

  run "$name" "$py" "$B6S" --label "$name" --plan "$plan" $PROC $AFF
}

echo "=== RQ4 native: $(uname -m) $(uname -s), affinity='${AFF:-none}', $PROC"

for cfg in $CONFIGS; do
case "$cfg" in
  stock)   run stock "$STOCK" "$B6" --label stock --features $PROC $AFF ;;
  fork)    run fork  "$FORK"  "$B6" --label fork  --features $PROC $AFF ;;

  cinderx) run fork_cinderx "$FORK" "$B6" --label fork_cinderx --cinderx --features $PROC $AFF ;;
  jit)     run fork_jit     "$FORK" "$B6" --label fork_jit     --cinderx --jit      $PROC $AFF ;;
  static)  run_static fork_static "$FORK" ;;

  cinderx_adaptive)
    run fork_cinderx_adaptive "$FORKA" "$B6" --label fork_cinderx_adaptive --cinderx --features $PROC $AFF ;;
  jit_adaptive)
    run fork_jit_adaptive     "$FORKA" "$B6" --label fork_jit_adaptive     --cinderx --jit      $PROC $AFF ;;
  static_adaptive)
    run_static fork_static_adaptive "$FORKA" ;;

  *) echo "unknown configuration: $cfg" ;;
esac
done

echo "=== b6 done"
ls -1 "$ROOT/results/pyperf"/b6_*.json 2>/dev/null | wc -l | xargs echo "  b6 result files:"
