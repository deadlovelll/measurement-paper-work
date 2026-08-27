#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1
CINDER="${CINDER:?set CINDER to the install root used by build_cinderx.sh}"
LOGS="$ROOT/logs/pyperf"
mkdir -p "$LOGS" "$ROOT/results/pyperf"

PY="$CINDER/venv-cinder-adaptive/bin/python"
B6="bench/b6_cinderx/run_b6.py"
PROC="-p 10 -n 3 -w 1"
AFF=""
[ -s "$ROOT/bench/affinity.txt" ] && AFF="--affinity $(cat "$ROOT/bench/affinity.txt")"

CONFIGS_ALL="
default|
no_specialized_opcodes|CINDERX_JIT_SPECIALIZED_OPCODES=0
compile_at_first_call|CINDERX_JIT_ALL=1|--jit-compile-after=-1
no_jit|CINDERX_JIT_DISABLE=1
no_simplifier|CINDERX_JIT_SIMPLIFY_NEW_BLOCK_LIMIT=1
no_stable_frame|CINDERX_JIT_STABLE_FRAME=0
no_attr_caches|CINDERX_JIT_ATTR_CACHES=0
no_inliner|CINDERX_JIT_HIR_INLINER_COST_LIMIT=0
split_code_sections|CINDERX_JIT_MULTIPLE_CODE_SECTIONS=1
split_code_sections_hugepages|CINDERX_JIT_MULTIPLE_CODE_SECTIONS=1 CINDERX_JIT_COLD_CODE_HUGE_PAGES=1
"

want="${*:-all}"
echo "=== RQ4c JIT options: $(uname -m) $(uname -s), affinity='${AFF:-none}', $PROC"
if [ ! -x "$PY" ]; then echo "  no interpreter at $PY"; exit 1; fi

printf '%s\n' "$CONFIGS_ALL" | while IFS='|' read -r name env extra; do
  [ -z "$name" ] && continue
  case "$want" in
    all) ;;
    *) case " $want " in *" $name "*) ;; *) continue ;; esac ;;
  esac
  log="$LOGS/b6-jitopt_$name.log"
  printf '  %-32s ' "$name"

  names=""; expect=""
  for assign in $env; do
    names="${names:+$names,}${assign%%=*}"
    expect="${expect:+$expect,}$assign"
  done
  inherit=""; [ -n "$names" ] && inherit="--inherit-environ=$names"
  expect_arg=""; [ -n "$expect" ] && expect_arg="--expect-jit-env=$expect"

  if env $env "$PY" "$B6" --label "jitopt_$name" --cinderx --jit $PROC $AFF \
       $inherit $expect_arg ${extra:-} > "$log" 2>&1; then
    n=$(grep -cE "Mean \+- std dev|Median" "$log" || true)
    echo "ok  ($n benchmarks)  -> $log"
  else
    echo "FAILED -> $log"; tail -8 "$log" | sed 's/^/      /'
  fi
done

echo "=== jitopts done"
ls -1 "$ROOT/results/pyperf"/b6_cinderx-jitopt_*.json 2>/dev/null | wc -l \
  | xargs echo "  configuration result files:"
