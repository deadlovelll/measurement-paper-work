#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAT="$ROOT/bench/build/native"
OUT="$ROOT/results/codegen"
mkdir -p "$OUT"
ARCH="$(uname -m)"
SO=dylib
PRE=_
case "$(uname -s)" in Linux) SO=so; PRE="" ;; esac

if command -v llvm-objdump > /dev/null 2>&1; then
  OBJDUMP="$(command -v llvm-objdump)"; SYMFLAG="--disassemble-symbols"
else
  OBJDUMP="$(command -v objdump)"; SYMFLAG="--disassemble"
fi

export DEBUGINFOD_URLS=""

case "$ARCH" in
  x86_64|amd64)

    BR='j(e|ne|z|nz|l|le|g|ge|b|be|a|ae|s|ns|o|no|p|np|rcxz|ecxz)'
    SEL='cmov[a-z]+|set[a-z]+' ;;
  arm64|aarch64)
    BR='b\.(eq|ne|lt|le|gt|ge|lo|ls|hi|hs)|cbz|cbnz|tbz|tbnz'
    SEL='csel|cinc|csinc|cset|ccmp' ;;
  *)
    BR='NEVERMATCHES'; SEL='NEVERMATCHES'
    echo "warning: no branch/select mnemonics known for $ARCH" >&2 ;;
esac

dump() {
  "$OBJDUMP" -d "$SYMFLAG=$2" --no-show-raw-insn "$NAT/$1" > "$OUT/$3" 2>/dev/null \
    || "$OBJDUMP" -d --no-show-raw-insn "$NAT/$1" > "$OUT/$3" 2>/dev/null
}

dump "libbranchy_c.$SO"  "${PRE}c_tokenize"  "c_tokenize.asm"
dump "libmpkernels.$SO"  "${PRE}rs_tokenize" "rs_tokenize.asm"

dump "libkernels_c_O3native.$SO" "${PRE}c_matmul" "c_matmul.asm"
dump "libmpkernels.$SO"          "${PRE}rs_matmul" "rs_matmul.asm"

count() {
  local n; n="$(grep -cE "^[[:space:]]*[0-9a-f]+:[[:space:]]*($2)" "$OUT/$1" 2>/dev/null)" || true
  printf '%s' "${n:-0}"
}
instrs() {
  local n; n="$(grep -cE "^[[:space:]]*[0-9a-f]+:" "$OUT/$1" 2>/dev/null)" || true
  printf '%s' "${n:-0}"
}

{
  printf '{\n  "generated_by": "bench/b2_branchy/codegen_check.sh",\n'
  printf '  "arch": "%s",\n  "disassembler": "%s",\n' \
    "$ARCH" "$("$OBJDUMP" --version | head -1)"
  printf '  "branch_pattern": "%s",\n  "select_pattern": "%s",\n' "$BR" "$SEL"
  printf '  "symbols": {\n'
  sep=""
  for f in c_tokenize rs_tokenize c_matmul rs_matmul; do
    printf '%s    "%s": {"instructions": %s, "cond_branches": %s, "cond_selects": %s}\n' \
      "$sep" "$f" "$(instrs "$f.asm")" "$(count "$f.asm" "$BR")" "$(count "$f.asm" "$SEL")"
    sep=","
  done
  printf '  }\n}\n'
} > "$OUT/summary.json"

printf '%-16s %12s %14s %14s\n' symbol instructions cond.branches cond.selects
for f in c_tokenize rs_tokenize c_matmul rs_matmul; do
  printf '%-16s %12s %14s %14s\n' "$f" \
    "$(instrs "$f.asm")" "$(count "$f.asm" "$BR")" "$(count "$f.asm" "$SEL")"
done
echo "arch=$ARCH  (listings in results/codegen/, counts in results/codegen/summary.json)"
