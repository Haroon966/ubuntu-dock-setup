#!/usr/bin/env python3
"""Force Ubuntu Dock running indicators to stay under icons (always bottom).

dash-to-dock rotates BINARY/DOTS/etc. indicators to match dock-position (LEFT/RIGHT/TOP).
There is no gsettings key for this. This helper installs a user-local copy of
ubuntu-dock and disables that rotation.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

EXT_ID = "ubuntu-dock@ubuntu.com"
SYSTEM_EXT = Path("/usr/share/gnome-shell/extensions") / EXT_ID
LOCAL_EXT = Path.home() / ".local/share/gnome-shell/extensions" / EXT_ID
TARGET = LOCAL_EXT / "appIconIndicators.js"
STAMP = LOCAL_EXT / ".ubuntu-dock-setup-managed"
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


def is_active() -> bool:
    return TARGET.is_file() and MARKER in TARGET.read_text(encoding="utf-8", errors="ignore")


def _ensure_local_copy() -> None:
    if not SYSTEM_EXT.is_dir():
        raise FileNotFoundError(f"system Ubuntu Dock not found at {SYSTEM_EXT}")
    if LOCAL_EXT.exists() and not STAMP.exists() and not is_active():
        raise RuntimeError(
            f"local extension already exists at {LOCAL_EXT} and is not managed by this tool; "
            "remove it first or apply the patch manually"
        )
    if STAMP.exists() or not LOCAL_EXT.exists():
        if LOCAL_EXT.exists():
            shutil.rmtree(LOCAL_EXT)
        shutil.copytree(SYSTEM_EXT, LOCAL_EXT)
        STAMP.write_text("managed-by-ubuntu-dock-setup\n", encoding="utf-8")


def apply_patch() -> str:
    if is_active():
        return "already active: running indicators stay under icons"
    _ensure_local_copy()
    text = TARGET.read_text(encoding="utf-8")
    if not ROTATION_BLOCK_RE.search(text):
        raise RuntimeError(
            "could not find indicator rotation block in appIconIndicators.js "
            "(Ubuntu Dock version may differ)"
        )
    TARGET.write_text(ROTATION_BLOCK_RE.sub(PATCHED_BLOCK, text, count=1), encoding="utf-8")
    return (
        "applied: running indicators now stay under icons on left/right/top docks.\n"
        "restart GNOME Shell to take effect (X11: Alt+F2, type r, Enter; Wayland: log out/in)."
    )


def remove_patch() -> str:
    if not LOCAL_EXT.exists():
        return "nothing to remove (using system Ubuntu Dock)"
    if STAMP.exists():
        shutil.rmtree(LOCAL_EXT)
        return (
            "removed local override; indicators follow dock edge again.\n"
            "restart GNOME Shell to take effect (X11: Alt+F2, type r, Enter; Wayland: log out/in)."
        )
    if is_active():
        # Unmanaged local tree but still patched — restore rotation from system file.
        system_js = SYSTEM_EXT / "appIconIndicators.js"
        if not system_js.is_file():
            raise FileNotFoundError(system_js)
        TARGET.write_text(system_js.read_text(encoding="utf-8"), encoding="utf-8")
        return "restored appIconIndicators.js from system copy; restart GNOME Shell."
    return "local extension present but not patched by this tool"


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
            print("active" if is_active() else "inactive")
        elif args.action == "apply":
            print(apply_patch())
        else:
            print(remove_patch())
    except (OSError, RuntimeError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
