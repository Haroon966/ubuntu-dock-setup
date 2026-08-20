#!/usr/bin/env python3
"""Force Ubuntu Dock running indicators to stay under icons (always bottom).

dash-to-dock rotates BINARY/DOTS/etc. indicators to match dock-position (LEFT/RIGHT/TOP).
There is no gsettings key for this.

Ubuntu loads ubuntu-dock from /usr/share (not ~/.local), so this tool patches the
system appIconIndicators.js (with sudo + a user-owned backup).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXT_ID = "ubuntu-dock@ubuntu.com"
SYSTEM_EXT = Path("/usr/share/gnome-shell/extensions") / EXT_ID
SYSTEM_JS = SYSTEM_EXT / "appIconIndicators.js"
LOCAL_EXT = Path.home() / ".local/share/gnome-shell/extensions" / EXT_ID
BACKUP_DIR = Path.home() / ".local/share/ubuntu-dock-setup" / "backups"
BACKUP_JS = BACKUP_DIR / "appIconIndicators.js.orig"
MARKER = "// ubuntu-dock-setup:indicators-always-bottom"

ROTATION_BLOCK_RE = re.compile(
    r"        // We draw for the bottom case and rotate the canvas for other placements\n"
    r"        // set center of rotatoins to the center\n"
    r"        this\._area\.set_pivot_point\(0\.5, 0\.5\);\n\n"
    r"        switch \(this\._side\) \{.*?\n        \}\n",
    re.DOTALL,
)

PATCHED_BLOCK = """        // We draw for the bottom case and rotate the canvas for other placements
        // set center of rotatoins to the center
        this._area.set_pivot_point(0.5, 0.5);

        // ubuntu-dock-setup:indicators-always-bottom
        // Keep running indicators under the icon for every dock edge.
        this._area.rotation_angle_z = 0;

"""


def _file_has_marker(path: Path) -> bool:
    return path.is_file() and MARKER in path.read_text(encoding="utf-8", errors="ignore")


def active_extension_path() -> str | None:
    try:
        out = subprocess.run(
            ["gnome-extensions", "info", EXT_ID],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
    except FileNotFoundError:
        return None
    for line in out.splitlines():
        if line.strip().startswith("Path:"):
            return line.split(":", 1)[1].strip()
    return None


def is_active() -> bool:
    return _file_has_marker(SYSTEM_JS)


def _write_system_js(text: str) -> None:
    """Write SYSTEM_JS via sudo (Ubuntu Dock is owned by root)."""
    proc = subprocess.run(
        ["sudo", "tee", str(SYSTEM_JS)],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "could not write system Ubuntu Dock file (sudo required).\n"
            f"sudo stderr: {proc.stderr.strip() or '(empty)'}"
        )


def _ensure_backup() -> None:
    if BACKUP_JS.is_file():
        return
    if not SYSTEM_JS.is_file():
        raise FileNotFoundError(SYSTEM_JS)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SYSTEM_JS, BACKUP_JS)


def _cleanup_unused_local_copy() -> None:
    # Local copies are ignored while Ubuntu loads the system extension.
    stamp = LOCAL_EXT / ".ubuntu-dock-setup-managed"
    if stamp.is_file() and LOCAL_EXT.is_dir():
        shutil.rmtree(LOCAL_EXT)


def apply_patch() -> str:
    if not SYSTEM_JS.is_file():
        raise FileNotFoundError(f"system Ubuntu Dock not found at {SYSTEM_JS}")
    if is_active():
        path = active_extension_path() or str(SYSTEM_EXT)
        return (
            "already active on the live Ubuntu Dock.\n"
            f"loaded path: {path}\n"
            "if indicators still follow the dock edge, restart GNOME Shell "
            "(X11: Alt+F2 → r → Enter; Wayland: log out/in)."
        )

    text = SYSTEM_JS.read_text(encoding="utf-8")
    if not ROTATION_BLOCK_RE.search(text):
        raise RuntimeError(
            "could not find indicator rotation block in appIconIndicators.js "
            "(Ubuntu Dock version may differ)"
        )

    _ensure_backup()
    patched = ROTATION_BLOCK_RE.sub(PATCHED_BLOCK, text, count=1)
    _write_system_js(patched)
    _cleanup_unused_local_copy()

    path = active_extension_path() or str(SYSTEM_EXT)
    return (
        "applied to the live system Ubuntu Dock (sudo).\n"
        f"loaded path: {path}\n"
        "running indicators now stay under icons on left/right/top docks.\n"
        "restart GNOME Shell to take effect "
        "(X11: Alt+F2 → r → Enter; Wayland: log out/in)."
    )


def remove_patch() -> str:
    if not is_active() and not BACKUP_JS.is_file():
        _cleanup_unused_local_copy()
        return "nothing to remove (system Ubuntu Dock is unpatched)"

    if BACKUP_JS.is_file():
        _write_system_js(BACKUP_JS.read_text(encoding="utf-8"))
    elif SYSTEM_JS.is_file() and is_active():
        raise RuntimeError(
            f"patched system file has no backup at {BACKUP_JS}; "
            "restore Ubuntu Dock from apt or reinstall gnome-shell-extension-ubuntu-dock"
        )

    _cleanup_unused_local_copy()
    return (
        "restored system Ubuntu Dock indicators (follow dock edge again).\n"
        "restart GNOME Shell to take effect "
        "(X11: Alt+F2 → r → Enter; Wayland: log out/in)."
    )


def status_text() -> str:
    live = active_extension_path() or "(unknown)"
    state = "active" if is_active() else "inactive"
    local_note = ""
    if LOCAL_EXT.is_dir():
        local_note = (
            f"\nnote: unused local copy exists at {LOCAL_EXT} "
            "(Ubuntu is loading the system extension, not this folder)"
        )
    return f"{state}\nloaded path: {live}{local_note}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("status", "apply", "remove"),
        help="status | apply (always under icon) | remove (follow dock edge)",
    )
    args = parser.parse_args()
    try:
        if args.action == "status":
            print(status_text())
        elif args.action == "apply":
            print(apply_patch())
        else:
            print(remove_patch())
    except (OSError, RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
