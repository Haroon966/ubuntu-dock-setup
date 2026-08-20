#!/usr/bin/env bash
# Configure the Ubuntu Dock (dash-to-dock) into a floating, translucent,
# non-space-reserving bottom bar. Idempotent — safe to re-run.
set -euo pipefail

SCHEMA=org.gnome.shell.extensions.dash-to-dock
UI_RAW_URL_DEFAULT="https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/dock-config.py"
UI_PATCH_URL_DEFAULT="https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/indicators_patch.py"
UI_CACHE_DIR_DEFAULT="${XDG_CACHE_HOME:-$HOME/.cache}/ubuntu-dock-setup"
UI_CACHE_FILE_DEFAULT="$UI_CACHE_DIR_DEFAULT/dock-config.py"
UI_PATCH_CACHE_DEFAULT="$UI_CACHE_DIR_DEFAULT/indicators_patch.py"

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
# Note: verify checks the *script defaults* (SETTINGS), not live UI tweaks.
verify() {
  local fails=0 key want got
  echo "verify: checking script defaults (not live UI state)"
  for pair in "${SETTINGS[@]}"; do
    key="${pair%%=*}"; want="${pair#*=}"
    got=$(gsettings get "$SCHEMA" "$key")
    if ! same "${got//\'/}" "${want//\'/}"; then
      printf 'MISMATCH %-30s want=%-14s got=%s\n' "$key" "$want" "$got"
      fails=$((fails + 1))
    fi
  done
  # Sanity hint: floating dock without intellihide often looks "stuck".
  local fixed intellihide
  fixed=$(gsettings get "$SCHEMA" dock-fixed)
  intellihide=$(gsettings get "$SCHEMA" intellihide)
  if [[ "$fixed" == "false" && "$intellihide" != "true" ]]; then
    echo "WARN floating dock without intellihide — dock may stay stuck visible/hidden" >&2
    echo "hint: ./dock.sh apply, or toggle the extension after suspend/unlock (known dash-to-dock issue)" >&2
  fi
  # dock-fixed=false must translate into zero reserved pixels at the bottom.
  if [[ "${XDG_SESSION_TYPE:-}" == x11 ]] && command -v xprop >/dev/null; then
    local geom_h work
    geom_h=$(xprop -root _NET_DESKTOP_GEOMETRY | grep -oE '[0-9]+' | tail -1)
    # _NET_WORKAREA is x,y,w,h — y + h should land on the screen bottom.
    work=$(xprop -root _NET_WORKAREA | grep -oE '[0-9]+' | awk 'NR==2{y=$1} NR==4{print y+$1}')
    [[ "$work" == "$geom_h" ]] \
      && echo "OK dock reserves no space (workarea reaches screen bottom)" \
      || { echo "MISMATCH dock still reserves space: workarea ${work}px of ${geom_h}px"; fails=$((fails + 1)); }
  else
    # Wayland (or no xprop): cannot prove strut via _NET_WORKAREA.
    echo "OK Wayland/non-X11: strut pixel check skipped; dock-fixed=${fixed} (gsettings only)"
  fi
  [[ $fails -eq 0 ]] && echo "verify: ok" || { echo "verify: $fails problem(s)" >&2; exit 1; }
}

config() {
  local here script ui_url cache_file patch_url patch_cache
  here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  script="$here/dock-config.py"
  ui_url="${DOCK_SETUP_UI_URL:-$UI_RAW_URL_DEFAULT}"
  cache_file="${DOCK_SETUP_UI_CACHE_FILE:-$UI_CACHE_FILE_DEFAULT}"
  patch_url="${DOCK_SETUP_PATCH_URL:-$UI_PATCH_URL_DEFAULT}"
  patch_cache="${DOCK_SETUP_PATCH_CACHE_FILE:-$UI_PATCH_CACHE_DEFAULT}"

  download_file() {
    local url="$1" dest="$2"
    if command -v curl >/dev/null; then
      curl -fsSL "$url" -o "$dest"
    elif command -v wget >/dev/null; then
      wget -qO "$dest" "$url"
    else
      return 1
    fi
  }

  # one-shot support: if dock-config.py isn't local, fetch/cached copy.
  if [[ ! -f "$script" ]]; then
    script="$cache_file"
    if [[ ! -f "$script" ]]; then
      mkdir -p "$(dirname "$script")"
      if ! download_file "$ui_url" "$script"; then
        echo "error: failed to download dock-config.py from $ui_url" >&2
        echo "hint: run './dock.sh apply' or clone this repo to use local UI." >&2
        return 1
      fi
      if [[ -n "${DOCK_SETUP_EXPECT_SHA256:-}" ]]; then
        local got_hash
        if command -v sha256sum >/dev/null; then
          got_hash=$(sha256sum "$script" | awk '{print $1}')
        elif command -v shasum >/dev/null; then
          got_hash=$(shasum -a 256 "$script" | awk '{print $1}')
        else
          echo "error: DOCK_SETUP_EXPECT_SHA256 set but sha256sum/shasum not found" >&2
          rm -f "$script"
          return 1
        fi
        if [[ "$got_hash" != "$DOCK_SETUP_EXPECT_SHA256" ]]; then
          echo "error: dock-config.py checksum mismatch" >&2
          echo "  want: $DOCK_SETUP_EXPECT_SHA256" >&2
          echo "  got:  $got_hash" >&2
          rm -f "$script"
          return 1
        fi
        echo "OK dock-config.py sha256 matches DOCK_SETUP_EXPECT_SHA256"
      fi
      chmod +x "$script" || true
    fi
    # Companion patch module for "indicators under icons".
    if [[ ! -f "$patch_cache" ]]; then
      mkdir -p "$(dirname "$patch_cache")"
      download_file "$patch_url" "$patch_cache" || true
    fi
  fi
  if ! command -v python3 >/dev/null; then
    echo "error: python3 not found" >&2
    return 1
  fi
  python3 "$script"
}

indicators_patch() {
  local here patch
  here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  patch="$here/indicators_patch.py"
  if [[ ! -f "$patch" ]]; then
    echo "error: indicators_patch.py not found next to dock.sh" >&2
    return 1
  fi
  python3 "$patch" "$@"
}

should_launch_ui() {
  # User override to disable UI path in one-shot.
  if [[ "${DOCK_SETUP_NO_UI:-}" == "1" ]]; then
    return 1
  fi
  # Force UI path if explicitly requested.
  if [[ "${DOCK_SETUP_FORCE_UI:-}" == "1" ]]; then
    return 0
  fi
  # Skip known CI / non-desktop automation environments.
  if [[ "${CI:-}" == "true" || -n "${GITHUB_ACTIONS:-}" || -n "${GITLAB_CI:-}" ]]; then
    return 1
  fi
  # One-shot is usually `curl | bash`, so stdin is a pipe (not a TTY).
  # Decide from graphical session env instead of tty checks.
  [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]] || return 1
  return 0
}

setup() {
  if should_launch_ui; then
    echo "interactive desktop detected — launching dock config UI..."
    if ! config; then
      echo "warning: UI failed; applying default dock preset instead." >&2
      apply
      verify
    fi
  else
    apply
    verify
  fi
}

require_schema
case "${1:-setup}" in
  setup)  setup ;;
  apply)  apply; verify ;;
  verify) verify ;;
  reset)  gsettings reset-recursively "$SCHEMA"; echo "reset to Ubuntu defaults" ;;
  show)   for k in $(gsettings list-keys "$SCHEMA" | sort); do
            printf '%-42s %s\n' "$k" "$(gsettings get "$SCHEMA" "$k")"; done ;;
  config) config ;;
  indicators-bottom) indicators_patch apply ;;
  indicators-edge)   indicators_patch remove ;;
  indicators-status) indicators_patch status ;;
  *)      echo "usage: dock.sh [setup|apply|verify|reset|show|config|indicators-bottom|indicators-edge|indicators-status]" >&2; exit 2 ;;
esac
