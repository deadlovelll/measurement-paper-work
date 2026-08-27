#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAT="$ROOT/bench/build/native"
OUT="${OUT:-$ROOT/results/codegen_identity.json}"
SO=dylib
case "$(uname -s)" in Linux) SO=so ;; esac
ARCH="$(uname -m)"

VARIANTS="O0 O2 O3 O3native O3native_novec O3native_ffast"
SYMS="_c_arraysum _c_mandelbrot _c_matmul"
[ "$(uname -s)" = "Linux" ] && SYMS="c_arraysum c_mandelbrot c_matmul"

if command -v llvm-objdump > /dev/null 2>&1; then
  OBJDUMP="$(command -v llvm-objdump)"; SYMFLAG="--disassemble-symbols"
else
  OBJDUMP="$(command -v objdump)"; SYMFLAG="--disassemble"
fi
[ -n "$OBJDUMP" ] || { echo "FATAL: no objdump or llvm-objdump on PATH" >&2; exit 2; }

export DEBUGINFOD_URLS=""

norm() {
  "$OBJDUMP" -d "$SYMFLAG=$2" --no-show-raw-insn "$1" \
    | sed -n 's/^[[:space:]]*[0-9a-f]\{1,\}:[[:space:]]*//p' \
    | sed -e 's/;.*$//' -e 's/0x[0-9a-f]* <\([^+>]*\)\(+0x[0-9a-f]*\)\{0,1\}>/<\1\2>/g' \
    | sed -e 's/[[:space:]]\{1,\}/ /g' -e 's/ $//'
}

echo "{"                                            >  "$OUT"
echo " \"generated_by\": \"bench/b1_compute/codegen_diff.sh\"," >> "$OUT"
echo " \"compiler\": \"$(${CC_BIN:-/usr/bin/clang} --version | head -1)\"," >> "$OUT"
echo " \"disassembler\": \"$("$OBJDUMP" --version | head -1)\"," >> "$OUT"
echo " \"arch\": \"$ARCH\","                    >> "$OUT"
echo " \"native_flag\": \"$(cat "$NAT/native_flag.txt" 2>/dev/null)\"," >> "$OUT"
echo " \"kernels\": {"                              >> "$OUT"

ksep=""
for sym in $SYMS; do
  printf '%s  "%s": {\n' "$ksep" "${sym#_}" >> "$OUT"; ksep=","
  echo "=== ${sym#_}"
  vsep=""
  for v in $VARIANTS; do
    lib="$NAT/libkernels_c_$v.$SO"
    [ -f "$lib" ] || { echo "  $v: MISSING $lib"; continue; }
    txt="$(norm "$lib" "$sym")"
    h="$(printf '%s' "$txt" | shasum | cut -c1-12)"
    n="$(printf '%s\n' "$txt" | grep -c .)"

    if [ "$n" -lt 5 ]; then
      echo "FATAL: disassembly of $sym in $(basename "$lib") produced $n instructions;" >&2
      echo "       objdump or the symbol name is wrong for this platform." >&2
      exit 2
    fi

    case "$ARCH" in
      x86_64)

        fp="$(printf '%s\n' "$txt" | grep -cE '^v?(add|sub|mul|div)[sp][sd]|^vfn?m(add|sub)[0-9]*[sp][sd]')"
        simd="$(printf '%s\n' "$txt" | grep -cE '%[yz]mm[0-9]+|^v?(add|sub|mul|div|max|min|sqrt)p[sd]|^vfn?m(add|sub)[0-9]*p[sd]')"
        ldq="$(printf '%s\n' "$txt" | grep -cE '^v?mov[au]p[sd]|^vmovdq[au]')" ;;
      *)
        fp="$(printf '%s\n' "$txt" | grep -cE '^(fadd|fmul|fmadd|fsub|fmla)')"
        simd="$(printf '%s\n' "$txt" | grep -cE 'v[0-9]+\.(2d|4s|2s|16b)|\.(2d|4s)[[:space:]]')"
        ldq="$(printf '%s\n' "$txt" | grep -cE '^ldp?[[:space:]]+q')" ;;
    esac
    printf '%s   "%s": {"hash": "%s", "instructions": %s, "fp_ops": %s, "simd_ops": %s, "q_loads": %s}\n' \
      "$vsep" "$v" "$h" "$n" "$fp" "$simd" "$ldq" >> "$OUT"; vsep=","
    printf '  %-16s hash=%s instrs=%-4s fp=%-3s simd=%-3s qloads=%s\n' "$v" "$h" "$n" "$fp" "$simd" "$ldq"
  done
  echo "  }" >> "$OUT"
done
echo " }" >> "$OUT"
echo "}"   >> "$OUT"

echo
echo "=== identity groups (same hash = same machine code)"
python3 - "$OUT" <<'PY'
import json, sys, collections
d = json.load(open(sys.argv[1]))
for kern, vs in d["kernels"].items():
    groups = collections.OrderedDict()
    for v, info in vs.items():
        groups.setdefault(info["hash"], []).append(v)
    print(f"  {kern}:")
    for h, members in groups.items():
        print(f"    {h}  {' = '.join(members)}")
PY
echo "=== wrote $OUT"
