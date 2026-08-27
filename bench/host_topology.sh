#!/usr/bin/env bash

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/bench/affinity.txt"
OUT_T="$ROOT/bench/affinity-threads.txt"
SYS=/sys/devices/system/cpu

pairs=""
for d in "$SYS"/cpu[0-9]*; do
  n="${d##*/cpu}"
  cap="$(cat "$d/cpu_capacity" 2>/dev/null || echo 0)"
  pairs="$pairs$cap $n"$'\n'
done

top="$(printf '%s' "$pairs" | awk 'NF{if($1>m)m=$1}END{print m+0}')"
bot="$(printf '%s' "$pairs" | awk 'NF{if(m==""||$1<m)m=$1}END{print m+0}')"

collapse() {
  awk 'NR==1 {s=$1; p=$1; next}
       $1==p+1 {p=$1; next}
       {printf "%s%s", (s==p ? s : s "-" p), ","; s=$1; p=$1}
       END {if (NR) printf "%s", (s==p ? s : s "-" p)}'
}

if [ "$top" = "0" ]; then
  echo "no cpu_capacity on this host -- treating all CPUs as one class"
  ranges="$(printf '%s' "$pairs" | awk 'NF{print $2}' | sort -n | collapse)"
  ranges_t="$ranges"
else
  ranges="$(printf '%s' "$pairs" | awk -v m="$top" 'NF && $1==m {print $2}' | sort -n | collapse)"

  if [ "$top" = "$bot" ]; then
    ranges_t="$ranges"
  else
    ranges_t="$(printf '%s' "$pairs" | awk -v b="$bot" 'NF && $1>b {print $2}' | sort -n | collapse)"
  fi
fi

printf '%s\n' "$ranges"   > "$OUT"
printf '%s\n' "$ranges_t" > "$OUT_T"

HOSTJSON="$ROOT/results/host.json"
mkdir -p "$ROOT/results"
{
  printf '{\n'
  printf '  "generated_by": "bench/host_topology.sh",\n'
  printf '  "cpu_model": "%s",\n' \
    "$(grep -m1 '^model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ *//' \
       | sed 's/(R)//g; s/(TM)//g')"
  printf '  "cpu_count": %s,\n' "$(nproc)"
  printf '  "cpu_classes": "%s",\n' \
    "$(printf '%s' "$pairs" | awk 'NF{print $1}' | sort -rn | uniq -c \
       | awk '{printf "%s@cap%s ", $1, $2}' | sed 's/ $//')"
  printf '  "perf_cpus": "%s",\n' "$ranges"
  printf '  "mem_gb": %s,\n' \
    "$(awk '/MemTotal/ {printf "%.1f", $2/1048576}' /proc/meminfo 2>/dev/null || echo 0)"
  printf '  "kernel": "%s",\n' "$(uname -sr)"
  printf '  "distro": "%s",\n' \
    "$(. /etc/os-release 2>/dev/null && printf '%s' "$PRETTY_NAME")"
  printf '  "arch": "%s",\n' "$(uname -m)"
  printf '  "governor": "%s",\n' \
    "$(cat "$SYS"/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u | tr '\n' ' ' | sed 's/ $//')"
  printf '  "turbo": "%s",\n' \
    "$([ "$(cat "$SYS/intel_pstate/no_turbo" 2>/dev/null)" = "1" ] && echo off || echo on)"
  printf '  "aslr": "%s"\n' "$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)"
  printf '}\n'
} > "$HOSTJSON"
echo "    host description -> results/host.json"

echo "=== CPU classes on $(uname -m) $(uname -s)"
printf '%s' "$pairs" | awk 'NF{print $1}' | sort -rn | uniq -c \
  | awk '{printf "    capacity %-6s : %s CPUs\n", $2, $1}'
echo "    performance class      -> $ranges     (bench/affinity.txt, single-threaded suites)"
echo "    all but the slowest    -> $ranges_t   (bench/affinity-threads.txt, thread scaling)"
echo
echo "=== governor / turbo"
printf '    governor : '; cat "$SYS"/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u | tr '\n' ' '; echo
if [ -r "$SYS/intel_pstate/no_turbo" ]; then
  printf '    turbo    : '
  [ "$(cat "$SYS/intel_pstate/no_turbo")" = "1" ] && echo "off" || echo "ON (frequency will drift)"
fi
printf '    aslr     : '
case "$(cat /proc/sys/kernel/randomize_va_space 2>/dev/null)" in
  2) echo "on (full) -- required: per-process layout variance is part of the protocol" ;;
  *) echo "REDUCED -- the 20-process argument is weakened, see the timing protocol in the paper" ;;
esac
