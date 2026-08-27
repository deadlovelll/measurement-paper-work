#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/bench/venvs/u313/bin/python}"
UNIFORM="${UNIFORM:-$HOME/mp-x86/uniform}"

[ -x "$PY" ] || { echo "set PY to an interpreter with matplotlib (u314 does not have it)"; exit 2; }

pass=0
fail=0
skipped=0

run() {
  local name="$1"; shift
  printf '%-22s ' "$name"
  local out
  if out=$("$@" 2>&1); then
    echo "pass"
    pass=$((pass + 1))
  else
    echo "FAIL"
    echo "$out" | sed 's/^/    /' | tail -25
    fail=$((fail + 1))
  fi
}

skip() {
  printf '%-22s skipped -- %s\n' "$1" "$2"
  skipped=$((skipped + 1))
}

echo "=== paper gates"

run "lint"        ruff check .
run "parity"      "$PY" bench/plots/check_parity.py
run "seams"       "$PY" bench/plots/check_seams.py
run "bibliography" "$PY" bench/plots/check_biblio.py ${BIBLIO_ONLINE:+--online}
run "tables"      "$PY" bench/plots/check_tables.py
run "protocol"    "$PY" bench/plots/check_protocol.py
run "numbers"     "$PY" bench/plots/check_meas.py
run "phantom"     "$PY" bench/plots/phantom.py
run "layout en"   "$PY" bench/plots/check_overlaps.py
run "layout ru"   "$PY" bench/plots/check_overlaps.py --ru

if [ -d "$UNIFORM" ]; then
  run "provenance" "$PY" bench/check_provenance.py "$UNIFORM"
else
  skip "provenance" "set UNIFORM to the interpreter install root ($UNIFORM not found)"
fi

if command -v tectonic > /dev/null; then
  for lang in paper paper-ru; do
    printf '%-22s ' "build $lang"
    if (cd paper && tectonic -X compile "$lang.tex" --print > /dev/null 2>&1); then
      unresolved=$(pdftotext "paper/$lang.pdf" - 2> /dev/null | grep -c '??')
      if [ "$unresolved" = "0" ]; then
        echo "pass"
        pass=$((pass + 1))
      else
        echo "FAIL -- $unresolved unresolved reference(s)"
        fail=$((fail + 1))
      fi
    else
      echo "FAIL -- tectonic error"
      fail=$((fail + 1))
    fi
  done
  rm -f paper/*.log
else
  skip "build" "tectonic not on PATH"
fi

echo
echo "=== campaign verdicts (advisory, not a gate)"
"$PY" bench/plots/verify_campaign.py 2>&1 | tail -3

echo
echo "$pass passed, $fail failed, $skipped skipped"
exit "$fail"
