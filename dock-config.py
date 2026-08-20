#!/usr/bin/env python3
"""GTK UI to configure Ubuntu Dock size, hover, and stay behavior via gsettings."""
from __future__ import annotations

import shutil
import subprocess
import sys

SCHEMA = "org.gnome.shell.extensions.dash-to-dock"

# Matches dock.sh SETTINGS for "Reset to script defaults".
SCRIPT_DEFAULTS = {
    "dock-position": "BOTTOM",
    "always-center-icons": "true",
    "extend-height": "false",
    "dock-fixed": "false",
    "intellihide": "true",
    "intellihide-mode": "ALL_WINDOWS",
    "autohide": "true",
    "require-pressure-to-show": "false",
    "dash-max-icon-size": "36",
    "icon-size-fixed": "true",
    "custom-theme-shrink": "false",
    "transparency-mode": "FIXED",
    "background-opacity": "0.35",
    "custom-background-color": "true",
    "background-color": "#181825",
    "apply-glossy-effect": "false",
    "running-indicator-style": "BINARY",
    "show-trash": "false",
    "show-mounts": "false",
    "animation-time": "0.10",
    "show-delay": "0.05",
    "hide-delay": "0.05",
    "scroll-action": "cycle-windows",
    "middle-click-action": "quit",
}

POSITIONS = ("BOTTOM", "LEFT", "RIGHT", "TOP")

STAY_PRESETS = (
    (
        "floating_all",
        "Floating — hide when any window covers",
        {
            "dock-fixed": "false",
            "intellihide": "true",
            "intellihide-mode": "ALL_WINDOWS",
            "autohide": "true",
            "extend-height": "false",
        },
    ),
    (
        "floating_focus",
        "Floating — hide only for focused app",
        {
            "dock-fixed": "false",
            "intellihide": "true",
            "intellihide-mode": "FOCUS_APPLICATION_WINDOWS",
            "autohide": "true",
            "extend-height": "false",
        },
    ),
    (
        "floating_max",
        "Floating — hide only for maximized windows",
        {
            "dock-fixed": "false",
            "intellihide": "true",
            "intellihide-mode": "MAXIMIZED_WINDOWS",
            "autohide": "true",
            "extend-height": "false",
        },
    ),
    (
        "pinned",
        "Pinned — reserve screen space",
        {
            "dock-fixed": "true",
            "intellihide": "false",
            "autohide": "false",
        },
    ),
)


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_deps() -> None:
    if not shutil.which("gsettings"):
        die("gsettings not found")
    try:
        import gi  # noqa: F401
    except ImportError:
        die("PyGObject missing — install with: sudo apt install python3-gi")
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
    except (ValueError, ImportError) as exc:
        die(f"GTK 3 not available ({exc}) — install with: sudo apt install python3-gi gir1.2-gtk-3.0")


def schema_ok() -> bool:
    out = subprocess.run(
        ["gsettings", "list-schemas"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return SCHEMA in out.splitlines()


def gget(key: str) -> str:
    raw = subprocess.run(
        ["gsettings", "get", SCHEMA, key],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw
    return raw


def gset(key: str, value: str) -> None:
    subprocess.run(["gsettings", "set", SCHEMA, key, value], check=True)


def apply_map(settings: dict[str, str]) -> None:
    for key, value in settings.items():
        gset(key, value)


def detect_stay_preset() -> str:
    fixed = gget("dock-fixed") == "true"
    if fixed:
        return "pinned"
    mode = gget("intellihide-mode")
    for pid, _label, keys in STAY_PRESETS:
        if pid == "pinned":
            continue
        if keys.get("intellihide-mode") == mode:
            return pid
    return "floating_all"


def build_ui() -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gtk

    if not schema_ok():
        die(f"{SCHEMA} not found — is the Ubuntu Dock extension installed?")

    win = Gtk.Window(title="Ubuntu Dock Config")
    win.set_border_width(16)
    win.set_default_size(480, 520)
    win.connect("destroy", Gtk.main_quit)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    win.add(outer)

    def section(title: str) -> Gtk.Box:
        frame = Gtk.Frame(label=title)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(10)
        frame.add(box)
        outer.pack_start(frame, False, False, 0)
        return box

    def row(parent: Gtk.Box, label: str, widget: Gtk.Widget) -> None:
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lab = Gtk.Label(label=label, xalign=0)
        lab.set_size_request(160, -1)
        h.pack_start(lab, False, False, 0)
        h.pack_start(widget, True, True, 0)
        parent.pack_start(h, False, False, 0)

    # --- Size ---
    size_box = section("Size")
    icon_adj = Gtk.Adjustment(
        value=float(gget("dash-max-icon-size")),
        lower=16,
        upper=64,
        step_increment=1,
        page_increment=4,
    )
    icon_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=icon_adj)
    icon_scale.set_digits(0)
    icon_scale.set_hexpand(True)
    icon_value = Gtk.Label(label=str(int(icon_adj.get_value())))

    def on_icon(_s: Gtk.Scale) -> None:
        icon_value.set_text(str(int(icon_scale.get_value())))

    icon_scale.connect("value-changed", on_icon)
    icon_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    icon_row.pack_start(icon_scale, True, True, 0)
    icon_row.pack_start(icon_value, False, False, 0)
    row(size_box, "Icon size", icon_row)

    # --- Position ---
    pos_box = section("Position")
    pos_combo = Gtk.ComboBoxText()
    for p in POSITIONS:
        pos_combo.append(p, p.capitalize())
    cur_pos = gget("dock-position")
    if cur_pos in POSITIONS:
        pos_combo.set_active_id(cur_pos)
    else:
        pos_combo.set_active(0)
    row(pos_box, "Dock position", pos_combo)

    # --- Stay / hide ---
    stay_box = section("Stay / hide behavior")
    stay_group: list[Gtk.RadioButton] = []
    current_preset = detect_stay_preset()
    for i, (pid, label, _keys) in enumerate(STAY_PRESETS):
        if i == 0:
            rb = Gtk.RadioButton.new_with_label(None, label)
        else:
            rb = Gtk.RadioButton.new_with_label_from_widget(stay_group[0], label)
        rb.set_name(pid)
        if pid == current_preset:
            rb.set_active(True)
        stay_group.append(rb)
        stay_box.pack_start(rb, False, False, 0)

    pressure = Gtk.CheckButton(label="Require pressure at edge to show (instead of simple hover)")
    pressure.set_active(gget("require-pressure-to-show") == "true")
    stay_box.pack_start(pressure, False, False, 0)

    # --- Timing ---
    time_box = section("Hover / animation timing")

    def delay_scale(key: str, lo: float, hi: float) -> Gtk.Scale:
        try:
            val = float(gget(key))
        except ValueError:
            val = lo
        adj = Gtk.Adjustment(value=val, lower=lo, upper=hi, step_increment=0.01, page_increment=0.05)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_digits(2)
        scale.set_hexpand(True)
        return scale

    show_delay = delay_scale("show-delay", 0.0, 1.0)
    hide_delay = delay_scale("hide-delay", 0.0, 1.0)
    anim_time = delay_scale("animation-time", 0.0, 1.0)
    row(time_box, "Show delay (s)", show_delay)
    row(time_box, "Hide delay (s)", hide_delay)
    row(time_box, "Animation (s)", anim_time)

    # --- Look ---
    look_box = section("Look")
    opacity = delay_scale("background-opacity", 0.0, 1.0)
    row(look_box, "Background opacity", opacity)

    color_entry = Gtk.Entry()
    bg = gget("background-color")
    if not bg.startswith("#"):
        bg = f"#{bg}" if bg else "#181825"
    color_entry.set_text(bg)

    color_btn = Gtk.ColorButton()
    try:
        rgba = Gdk.RGBA()
        if rgba.parse(bg):
            color_btn.set_rgba(rgba)
    except Exception:
        pass

    def on_color_picked(_b: Gtk.ColorButton) -> None:
        rgba = color_btn.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        color_entry.set_text(hex_color)

    color_btn.connect("color-set", on_color_picked)
    color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    color_row.pack_start(color_entry, True, True, 0)
    color_row.pack_start(color_btn, False, False, 0)
    row(look_box, "Background color", color_row)

    status = Gtk.Label(label="", xalign=0)
    outer.pack_start(status, False, False, 0)

    def selected_stay() -> tuple[str, dict[str, str]]:
        for rb, (pid, _label, keys) in zip(stay_group, STAY_PRESETS):
            if rb.get_active():
                return pid, keys
        return STAY_PRESETS[0][0], STAY_PRESETS[0][2]

    def collect_and_apply(extra: dict[str, str] | None = None) -> None:
        settings: dict[str, str] = {}
        if extra:
            settings.update(extra)
        else:
            settings["dash-max-icon-size"] = str(int(icon_scale.get_value()))
            settings["icon-size-fixed"] = "true"
            pos_id = pos_combo.get_active_id() or "BOTTOM"
            settings["dock-position"] = pos_id
            _pid, stay_keys = selected_stay()
            settings.update(stay_keys)
            settings["require-pressure-to-show"] = "true" if pressure.get_active() else "false"
            settings["show-delay"] = f"{show_delay.get_value():.2f}"
            settings["hide-delay"] = f"{hide_delay.get_value():.2f}"
            settings["animation-time"] = f"{anim_time.get_value():.2f}"
            settings["transparency-mode"] = "FIXED"
            settings["custom-background-color"] = "true"
            settings["background-opacity"] = f"{opacity.get_value():.2f}"
            color = color_entry.get_text().strip()
            if color and not color.startswith("#"):
                color = f"#{color}"
            settings["background-color"] = color or "#181825"
        apply_map(settings)
        status.set_text(f"Applied {len(settings)} settings.")

    def load_from_gsettings() -> None:
        icon_scale.set_value(float(gget("dash-max-icon-size")))
        cur = gget("dock-position")
        if cur in POSITIONS:
            pos_combo.set_active_id(cur)
        preset = detect_stay_preset()
        for rb, (pid, _l, _k) in zip(stay_group, STAY_PRESETS):
            rb.set_active(pid == preset)
        pressure.set_active(gget("require-pressure-to-show") == "true")
        show_delay.set_value(float(gget("show-delay")))
        hide_delay.set_value(float(gget("hide-delay")))
        anim_time.set_value(float(gget("animation-time")))
        opacity.set_value(float(gget("background-opacity")))
        bg_now = gget("background-color")
        if not bg_now.startswith("#"):
            bg_now = f"#{bg_now}"
        color_entry.set_text(bg_now)
        rgba = Gdk.RGBA()
        if rgba.parse(bg_now):
            color_btn.set_rgba(rgba)
        status.set_text("Reloaded from current dock settings.")

    def on_apply(_b: Gtk.Button) -> None:
        try:
            collect_and_apply()
        except subprocess.CalledProcessError as exc:
            status.set_text(f"Failed to apply: {exc}")

    def on_defaults(_b: Gtk.Button) -> None:
        try:
            apply_map(SCRIPT_DEFAULTS)
            load_from_gsettings()
            status.set_text("Restored script defaults (same as ./dock.sh apply).")
        except subprocess.CalledProcessError as exc:
            status.set_text(f"Failed: {exc}")

    def on_reload(_b: Gtk.Button) -> None:
        load_from_gsettings()

    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    apply_btn = Gtk.Button(label="Apply")
    apply_btn.get_style_context().add_class("suggested-action")
    defaults_btn = Gtk.Button(label="Reset to script defaults")
    reload_btn = Gtk.Button(label="Reload")
    close_btn = Gtk.Button(label="Close")
    apply_btn.connect("clicked", on_apply)
    defaults_btn.connect("clicked", on_defaults)
    reload_btn.connect("clicked", on_reload)
    close_btn.connect("clicked", lambda _b: win.destroy())
    buttons.pack_end(close_btn, False, False, 0)
    buttons.pack_end(apply_btn, False, False, 0)
    buttons.pack_start(defaults_btn, False, False, 0)
    buttons.pack_start(reload_btn, False, False, 0)
    outer.pack_start(buttons, False, False, 0)

    win.show_all()
    Gtk.main()


def main() -> None:
    ensure_deps()
    build_ui()


if __name__ == "__main__":
    main()
