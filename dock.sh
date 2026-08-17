#!/usr/bin/env bash
# Configure the Ubuntu Dock (dash-to-dock) into a floating, translucent,
# non-space-reserving bottom bar. Idempotent — safe to re-run.
set -euo pipefail

SCHEMA=org.gnome.shell.extensions.dash-to-dock

# key=value, applied in order. See README for what each one does.
SETTINGS=(
  # placement
  "dock-position=BOTTOM"
  "always-center-icons=true"
  "extend-height=false"          # floating pill, not a full-width panel
  "dock-fixed=false"             # do NOT reserve screen space (no strut)
  "intellihide=true"
  "intellihide-mode=ALL_WINDOWS" # hide when any window covers the dock
  "autohide=true"
  "require-pressure-to-show=false"

  # size and spacing
  "dash-max-icon-size=36"
  "icon-size-fixed=true"
  "custom-theme-shrink=false"    # the only padding lever the schema exposes

  # look
  "transparency-mode=FIXED"
  "background-opacity=0.35"
  "custom-background-color=true"
  "background-color='#181825'"
  "apply-glossy-effect=false"
  "running-indicator-style=BINARY"

  # declutter
  "show-trash=false"
  "show-mounts=false"

  # feel
  "animation-time=0.10"
  "show-delay=0.05"
  "hide-delay=0.05"
  "scroll-action=cycle-windows"
  "middle-click-action=quit"
)

require_schema() {
  if ! gsettings list-schemas | grep -qx "$SCHEMA"; then
    echo "error: $SCHEMA not found — is the Ubuntu Dock extension installed?" >&2
    exit 1
  fi
}

apply() {
  for pair in "${SETTINGS[@]}"; do
    gsettings set "$SCHEMA" "${pair%%=*}" "${pair#*=}"
  done
  echo "applied ${#SETTINGS[@]} settings"
}

# gsettings echoes doubles back at full precision (0.35 -> 0.34999999999999998),
# so numbers compare with a tolerance and everything else compares as a string.
same() {
  if [[ $1 =~ ^-?[0-9.]+$ && $2 =~ ^-?[0-9.]+$ ]]; then
    awk -v a="$1" -v b="$2" 'BEGIN { exit !((a - b < 1e-6) && (b - a < 1e-6)) }'
  else
    [[ "$1" == "$2" ]]
  fi
}

# Read every key back and diff against what we asked for. Exits non-zero on
# mismatch, so this doubles as the test.
verify() {
  local fails=0 key want got
  for pair in "${SETTINGS[@]}"; do
    key="${pair%%=*}"; want="${pair#*=}"
    got=$(gsettings get "$SCHEMA" "$key")
    if ! same "${got//\'/}" "${want//\'/}"; then
      printf 'MISMATCH %-30s want=%-14s got=%s\n' "$key" "$want" "$got"
      fails=$((fails + 1))
    fi
  done
  # dock-fixed=false must translate into zero reserved pixels at the bottom.
  if [[ "${XDG_SESSION_TYPE:-}" == x11 ]] && command -v xprop >/dev/null; then
    local geom_h work
    geom_h=$(xprop -root _NET_DESKTOP_GEOMETRY | grep -oE '[0-9]+' | tail -1)
    work=$(xprop -root _NET_WORKAREA | grep -oE '[0-9]+' | sed -n '2p;4p' | paste -sd+ | bc)
    [[ "$work" == "$geom_h" ]] \
      && echo "OK dock reserves no space (workarea reaches screen bottom)" \
      || { echo "MISMATCH dock still reserves space: workarea ${work}px of ${geom_h}px"; fails=$((fails + 1)); }
  fi
  [[ $fails -eq 0 ]] && echo "verify: ok" || { echo "verify: $fails problem(s)" >&2; exit 1; }
}

require_schema
case "${1:-apply}" in
  apply)  apply; verify ;;
  verify) verify ;;
  reset)  gsettings reset-recursively "$SCHEMA"; echo "reset to Ubuntu defaults" ;;
  show)   for k in $(gsettings list-keys "$SCHEMA" | sort); do
            printf '%-42s %s\n' "$k" "$(gsettings get "$SCHEMA" "$k")"; done ;;
  *)      echo "usage: $0 [apply|verify|reset|show]" >&2; exit 2 ;;
esac
