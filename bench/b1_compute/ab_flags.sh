#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
PY="${PY:?set PY to the interpreter}"
ROUNDS="${ROUNDS:-10}"
CASE="${1:?case}"; A="${2:?variant A}"; B="${3:?variant B}"
OUT="$ROOT/results/pyperf/ab_${CASE}_${A}_vs_${B}"
PLAN="$ROOT/results/pyperf/b1_flags-314.plan.json"
rm -f "$OUT-a.json" "$OUT-b.json"

for r in $(seq 1 "$ROUNDS"); do
  if [ $((r % 2)) -eq 1 ]; then order="$A $B"; else order="$B $A"; fi
  for v in $order; do
    case "$v" in "$A") f="$OUT-a.json";; *) f="$OUT-b.json";; esac
    "$PY" bench/b1_compute/run_flags.py --label 314 --plan "$PLAN" \
      --only "$CASE:$v" -p 2 -n 3 -w 1 -q --append "$f" > /dev/null 2>&1
  done
  printf '.'
done
echo

"$PY" - "$OUT-a.json" "$OUT-b.json" "$A" "$B" <<'PY'
import statistics, sys
import pyperf
from pyperf._utils import is_significant
a = list(pyperf.BenchmarkSuite.load(sys.argv[1]).get_benchmarks())[0]
b = list(pyperf.BenchmarkSuite.load(sys.argv[2]).get_benchmarks())[0]
va, vb = a.get_values(), b.get_values()
sig, t = is_significant(va, vb)
print(f"  {sys.argv[3]:<16} median {statistics.median(va)*1e3:8.4f} ms  "
      f"({len(va)} values, {a.get_nrun()} processes)")
print(f"  {sys.argv[4]:<16} median {statistics.median(vb)*1e3:8.4f} ms  "
      f"({len(vb)} values, {b.get_nrun()} processes)")
print(f"  ratio {statistics.median(vb)/statistics.median(va):.4f}x   "
      f"significant={sig} (t={t:.2f})")
PY
