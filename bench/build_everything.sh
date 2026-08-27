#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
ROOT_OUT="${ROOT_OUT:-$HOME/mp-x86}"
UNIFORM="$ROOT_OUT/uniform"
REAL="$ROOT_OUT/realbuilds"
CINDER="$ROOT_OUT/cinder"
LOGS="$ROOT/logs"
mkdir -p "$LOGS" "$ROOT_OUT"

step() { printf '\n########## %s  [%s]\n' "$*" "$(date +%H:%M:%S)"; }

while pgrep -f "build_uniform.sh" > /dev/null 2>&1; do sleep 20; done

step "1/6 interpreters"
if [ -x "$UNIFORM/v314t/bin/python3.14t" ]; then
  echo "already built"
else
  OUT="$UNIFORM" JOBS="$(nproc)" bash bench/build_uniform.sh > "$LOGS/build_uniform.log" 2>&1
  echo "exit=$?  -> logs/build_uniform.log"
fi

step "2/6 venvs and third-party packages"
UNIFORM="$UNIFORM" bash bench/setup_env.sh > "$LOGS/setup_env.log" 2>&1
echo "exit=$?  -> logs/setup_env.log"
tail -14 "$LOGS/setup_env.log" | sed 's/^/    /'

step "3/6 native artifacts (C flag variants, accumulator ladder, Rust)"
bash bench/build_all.sh > "$LOGS/build_all.log" 2>&1
echo "exit=$?  -> logs/build_all.log"
grep -E "FAILED|unavailable" "$LOGS/build_all.log" | sed 's/^/    /' || echo "    no failures"

step "4/6 seven build configurations of one 3.14.6 tree"
OUT="$REAL" JOBS="$(nproc)" bash bench/b5_buildflags/build_real.sh > "$LOGS/build_real.log" 2>&1
echo "exit=$?  -> logs/build_real.log"
grep -E "^=== w_.*(OK|FAILED|skipped)" "$LOGS/build_real.log" | sed 's/^/    /'

step "4b/6 pyperf into the seven build configurations"
REAL="$REAL" bash bench/setup_env.sh > "$LOGS/setup_env_real.log" 2>&1
echo "exit=$?  -> logs/setup_env_real.log"
tail -8 "$LOGS/setup_env_real.log" | sed 's/^/    /'

step "5/6 Cinder fork and CinderX"
OUT="$CINDER" JOBS="$(nproc)" bash bench/b6_cinderx/build_cinderx.sh > "$LOGS/build_cinderx.log" 2>&1
echo "exit=$?  -> logs/build_cinderx.log"
grep -E "^=== (stock314|fork314|CinderX).*(OK|FAILED)|^=== continuing" "$LOGS/build_cinderx.log" \
  | sed 's/^/    /' || true

step "6/6 gates"
echo "--- interpreter provenance (must PASS: one configure line for all six)"
python3 bench/check_provenance.py "$UNIFORM" 2>&1 | sed 's/^/    /'
prov=${PIPESTATUS[0]}
echo "--- build configurations (differences here are the experiment)"
python3 bench/check_provenance.py "$REAL" --expect-differences 2>&1 | sed 's/^/    /'
echo "--- codegen identity map"
bash bench/b1_compute/codegen_diff.sh > "$LOGS/codegen_diff.log" 2>&1
echo "    exit=$? -> results/codegen_identity.json"
sed -n '/identity groups/,$p' "$LOGS/codegen_diff.log" | sed 's/^/    /'

step "done"
echo "provenance gate exit: $prov  (0 = one configure line for the whole version sweep)"
