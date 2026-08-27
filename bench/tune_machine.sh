#!/usr/bin/env bash
# Put the machine into the state the published numbers were measured on, and back again.
#
# host_topology.sh records the governor and the turbo bit but never set them; they were set
# by hand, and a reboot returns this hardware to powersave with turbo on. A campaign run that
# way measures the frequency governor as much as it measures the interpreter, which is the one
# error the significance tests cannot see: every implementation is wrong by a different amount.
#
#   bash bench/tune_machine.sh show      what the machine is set to now
#   bash bench/tune_machine.sh apply     performance governor, turbo off (needs root)
#   bash bench/tune_machine.sh restore   put back exactly what apply found
#
# apply records the previous state before touching anything, so restore returns the machine
# instead of guessing at defaults.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYS=/sys/devices/system/cpu
STATE="$ROOT/bench/build/machine-state"

have() { command -v "$1" > /dev/null 2>&1; }

write_sys() {
  # write_sys <value> <file> -- one sysfs poke, through sudo when we are not root
  local value="$1" file="$2"
  [ -e "$file" ] || return 1
  if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' "$value" > "$file" 2>/dev/null
  elif have sudo; then
    printf '%s\n' "$value" | sudo tee "$file" > /dev/null 2>&1
  else
    return 1
  fi
}

governor_now() { cat "$SYS"/cpu0/cpufreq/scaling_governor 2>/dev/null || echo unknown; }

turbo_now() {
  if [ -r "$SYS/intel_pstate/no_turbo" ]; then
    if [ "$(cat "$SYS/intel_pstate/no_turbo")" = "1" ]; then echo off; else echo on; fi
  elif [ -r "$SYS/cpufreq/boost" ]; then
    if [ "$(cat "$SYS/cpufreq/boost")" = "0" ]; then echo off; else echo on; fi
  else
    echo unknown
  fi
}

set_governor() {
  local want="$1" n=0 f
  for f in "$SYS"/cpu*/cpufreq/scaling_governor; do
    write_sys "$want" "$f" && n=$((n + 1))
  done
  printf '%s' "$n"
}

set_turbo() {
  # set_turbo off|on -- intel_pstate calls it no_turbo, everyone else calls it boost
  local want="$1"
  if [ -e "$SYS/intel_pstate/no_turbo" ]; then
    if [ "$want" = off ]; then write_sys 1 "$SYS/intel_pstate/no_turbo"
    else write_sys 0 "$SYS/intel_pstate/no_turbo"; fi
  elif [ -e "$SYS/cpufreq/boost" ]; then
    if [ "$want" = off ]; then write_sys 0 "$SYS/cpufreq/boost"
    else write_sys 1 "$SYS/cpufreq/boost"; fi
  else
    return 1
  fi
}

show() {
  printf '    driver   : %s\n' "$(cat "$SYS"/cpu0/cpufreq/scaling_driver 2>/dev/null || echo unknown)"
  printf '    governor : %s\n' "$(governor_now)"
  printf '    turbo    : %s\n' "$(turbo_now)"
}

case "${1:-show}" in
  show)
    echo "=== machine now"
    show
    ;;

  apply)
    echo "=== before"
    show
    mkdir -p "$(dirname "$STATE")"
    [ -f "$STATE" ] || printf 'governor=%s\nturbo=%s\n' "$(governor_now)" "$(turbo_now)" > "$STATE"

    n="$(set_governor performance)"
    set_turbo off || echo "    no turbo control on this machine"

    echo "=== after ($n cpu(s) set)"
    show
    if [ "$(governor_now)" != performance ]; then
      echo "    FAILED: governor is still $(governor_now) -- run as root, or with sudo available"
      exit 1
    fi
    if [ "$(turbo_now)" = on ]; then
      echo "    FAILED: turbo is still on"
      exit 1
    fi
    echo "    ok -- previous state saved in $STATE"
    ;;

  restore)
    [ -f "$STATE" ] || { echo "nothing to restore: no saved state at $STATE"; exit 1; }
    # shellcheck disable=SC1090
    . "$STATE"
    set_governor "$governor" > /dev/null
    set_turbo "$turbo" || true
    rm -f "$STATE"
    echo "=== restored"
    show
    ;;

  *)
    echo "usage: $(basename "$0") [show|apply|restore]"
    exit 2
    ;;
esac
