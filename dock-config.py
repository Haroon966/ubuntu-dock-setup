#!/usr/bin/env python3
"""GTK UI to configure Ubuntu Dock size, hover, stay, and behavior via gsettings."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCHEMA = "org.gnome.shell.extensions.dash-to-dock"
PRESET_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ubuntu-dock-setup"
PRESET_FILE = PRESET_DIR / "preset.json"
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

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

# Keys the UI can collect / export (stay presets + behavior + look).
EXPORTABLE_KEYS = (
    "dash-max-icon-size",
    "icon-size-fixed",
    "dock-position",
    "dock-fixed",
    "intellihide",
    "intellihide-mode",
    "autohide",
    "extend-height",
    "require-pressure-to-show",
    "show-delay",
    "hide-delay",
    "animation-time",
    "transparency-mode",
    "custom-background-color",
    "background-opacity",
    "background-color",
    "running-indicator-style",
    "click-action",
    "isolate-workspaces",
    "isolate-monitors",
    "multi-monitor",
    "show-apps-at-top",
    "show-show-apps-button",
)

POSITIONS = ("BOTTOM", "LEFT", "RIGHT", "TOP")

CLICK_ACTIONS = (
    ("focus-or-previews", "Focus or previews (default-ish)"),
    ("minimize", "Minimize"),
    ("minimize-or-previews", "Minimize or previews (Windows-like)"),
    ("minimize-or-overview", "Minimize or overview"),
    ("cycle-windows", "Cycle windows"),
    ("previews", "Previews"),
    ("focus-minimize-or-previews", "Focus, minimize, or previews"),
    ("launch", "Launch"),
    ("skip", "Skip"),
    ("quit", "Quit"),
)

INDICATOR_STYLES = (
    "DEFAULT",
    "DOTS",
    "SQUARES",
    "DASHES",
    "SEGMENTED",
    "SOLID",
    "CILIORA",
    "METRO",
    "BINARY",
)

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

# Named style packs layered on top of SCRIPT_DEFAULTS (does not change one-shot apply).
NAMED_PRESETS = (
    (
        "mac",
        "Mac floating",
        {
            **SCRIPT_DEFAULTS,
            "dock-position": "BOTTOM",
            "extend-height": "false",
            "dock-fixed": "false",
            "intellihide": "true",
            "intellihide-mode": "ALL_WINDOWS",
            "autohide": "true",
            "background-opacity": "0.40",
            "background-color": "#1e1e2e",
            "running-indicator-style": "DOTS",
            "click-action": "focus-or-previews",
            "show-apps-at-top": "false",
            "show-show-apps-button": "true",
            "isolate-workspaces": "false",
            "isolate-monitors": "false",
            "multi-monitor": "false",
        },
    ),
    (
        "windows",
        "Windows taskbar-like",
        {
            **SCRIPT_DEFAULTS,
            "dock-position": "BOTTOM",
            "extend-height": "true",
            "dock-fixed": "true",
            "intellihide": "false",
            "autohide": "false",
            "always-center-icons": "false",
            "background-opacity": "0.85",
            "background-color": "#202020",
            "running-indicator-style": "METRO",
            "click-action": "minimize-or-previews",
            "show-apps-at-top": "true",
            "show-show-apps-button": "true",
            "isolate-workspaces": "true",
            "isolate-monitors": "false",
            "multi-monitor": "true",
        },
    ),
    (
        "minimal",
        "Minimal dark",
        {
            **SCRIPT_DEFAULTS,
            "dash-max-icon-size": "28",
            "background-opacity": "0.25",
            "background-color": "#11111b",
            "running-indicator-style": "BINARY",
            "click-action": "cycle-windows",
            "show-show-apps-button": "false",
            "show-apps-at-top": "false",
            "isolate-workspaces": "true",
            "isolate-monitors": "false",
            "multi-monitor": "false",
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


_SCHEMA_KEYS: set[str] | None = None


def schema_keys() -> set[str]:
    global _SCHEMA_KEYS
    if _SCHEMA_KEYS is None:
        out = subprocess.run(
            ["gsettings", "list-keys", SCHEMA],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        _SCHEMA_KEYS = set(out.splitlines())
    return _SCHEMA_KEYS


def schema_has_key(key: str) -> bool:
    return key in schema_keys()


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
        if not schema_has_key(key):
            continue
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
    from gi.repository import Gdk, GLib, Gtk

    if not schema_ok():
        die(f"{SCHEMA} not found — is the Ubuntu Dock extension installed?")

    win = Gtk.Window(title="Ubuntu Dock Config")
    win.set_border_width(12)
    win.set_default_size(520, 640)
    win.connect("destroy", Gtk.main_quit)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    win.add(scroll)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    outer.set_border_width(8)
    scroll.add(outer)

    live_hint = Gtk.Label(
        label="Live apply is on — changes save as you go. Drag sliders (click and hold); "
        "mouse-wheel scrolling on sliders is disabled.",
        xalign=0,
    )
    live_hint.set_line_wrap(True)
    live_hint.get_style_context().add_class("dim-label")
    outer.pack_start(live_hint, False, False, 0)

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
        lab.set_size_request(170, -1)
        h.pack_start(lab, False, False, 0)
        h.pack_start(widget, True, True, 0)
        parent.pack_start(h, False, False, 0)

    suppress_auto = {"on": True}  # ignore signals while hydrating widgets
    auto_timer: dict[str, int | None] = {"id": None}

    def block_scroll(_widget: Gtk.Widget, _event: Gdk.EventScroll) -> bool:
        # Force click-and-drag (or keyboard) — no accidental wheel jumps.
        return True

    def make_scale_with_steppers(
        adj: Gtk.Adjustment,
        digits: int,
        value_label: Gtk.Label | None = None,
    ) -> tuple[Gtk.Box, Gtk.Scale]:
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_digits(digits)
        scale.set_hexpand(True)
        scale.set_draw_value(False)
        scale.set_can_focus(True)
        scale.set_tooltip_text("Click and drag · use ← → keys or − / + for small steps")
        scale.connect("scroll-event", block_scroll)

        minus = Gtk.Button(label="−")
        plus = Gtk.Button(label="+")
        minus.set_tooltip_text("Decrease")
        plus.set_tooltip_text("Increase")
        for b in (minus, plus):
            b.set_can_focus(True)
            b.set_size_request(36, 32)

        step = adj.get_step_increment() or (1 if digits == 0 else 0.01)

        def bump(delta: float, _b: Gtk.Button | None = None) -> None:
            adj.set_value(max(adj.get_lower(), min(adj.get_upper(), adj.get_value() + delta)))

        minus.connect("clicked", lambda _b: bump(-step))
        plus.connect("clicked", lambda _b: bump(step))

        if value_label is not None:

            def sync_label(_a: Gtk.Adjustment | None = None) -> None:
                if digits == 0:
                    value_label.set_text(str(int(adj.get_value())))
                else:
                    value_label.set_text(f"{adj.get_value():.{digits}f}")

            adj.connect("value-changed", sync_label)
            sync_label()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.pack_start(minus, False, False, 0)
        box.pack_start(scale, True, True, 0)
        box.pack_start(plus, False, False, 0)
        if value_label is not None:
            value_label.set_width_chars(5)
            box.pack_start(value_label, False, False, 0)
        return box, scale

    # --- Named presets ---
    preset_box = section("Named presets")
    preset_combo = Gtk.ComboBoxText()
    preset_combo.append("", "(choose a named preset…)")
    for pid, label, _keys in NAMED_PRESETS:
        preset_combo.append(pid, label)
    preset_combo.set_active_id("")
    row(preset_box, "Style pack", preset_combo)
    preset_hint = Gtk.Label(
        label="Applies a full look+behavior pack. Script one-shot defaults stay unchanged.",
        xalign=0,
    )
    preset_hint.set_line_wrap(True)
    preset_box.pack_start(preset_hint, False, False, 0)

    # --- Size ---
    size_box = section("Size")
    icon_adj = Gtk.Adjustment(
        value=float(gget("dash-max-icon-size")),
        lower=16,
        upper=64,
        step_increment=1,
        page_increment=4,
    )
    icon_value = Gtk.Label(label=str(int(icon_adj.get_value())))
    icon_row, icon_scale = make_scale_with_steppers(icon_adj, 0, icon_value)
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

    # --- Behavior ---
    behavior_box = section("Behavior")
    click_combo = Gtk.ComboBoxText()
    for cid, clabel in CLICK_ACTIONS:
        click_combo.append(cid, clabel)
    cur_click = gget("click-action") if schema_has_key("click-action") else "focus-or-previews"
    if cur_click in dict(CLICK_ACTIONS):
        click_combo.set_active_id(cur_click)
    else:
        click_combo.append(cur_click, cur_click)
        click_combo.set_active_id(cur_click)
    row(behavior_box, "Click action", click_combo)

    isolate_ws = Gtk.CheckButton(label="Isolate workspaces (only show apps on current workspace)")
    isolate_ws.set_active(schema_has_key("isolate-workspaces") and gget("isolate-workspaces") == "true")
    behavior_box.pack_start(isolate_ws, False, False, 0)

    isolate_mon = Gtk.CheckButton(label="Isolate monitors (only show apps on current monitor)")
    isolate_mon.set_active(schema_has_key("isolate-monitors") and gget("isolate-monitors") == "true")
    behavior_box.pack_start(isolate_mon, False, False, 0)

    multi_mon = Gtk.CheckButton(label="Show dock on all monitors")
    multi_mon.set_active(schema_has_key("multi-monitor") and gget("multi-monitor") == "true")
    behavior_box.pack_start(multi_mon, False, False, 0)

    apps_top = Gtk.CheckButton(label="Show Apps button at start of dock")
    apps_top.set_active(schema_has_key("show-apps-at-top") and gget("show-apps-at-top") == "true")
    behavior_box.pack_start(apps_top, False, False, 0)

    show_apps = Gtk.CheckButton(label="Show the Show Apps button")
    show_apps.set_active(
        (not schema_has_key("show-show-apps-button")) or gget("show-show-apps-button") == "true"
    )
    behavior_box.pack_start(show_apps, False, False, 0)

    # --- Timing ---
    time_box = section("Hover / animation timing")

    def delay_adj(key: str, lo: float, hi: float) -> Gtk.Adjustment:
        try:
            val = float(gget(key))
        except ValueError:
            val = lo
        return Gtk.Adjustment(value=val, lower=lo, upper=hi, step_increment=0.01, page_increment=0.05)

    show_row, show_delay = make_scale_with_steppers(delay_adj("show-delay", 0.0, 1.0), 2, Gtk.Label())
    hide_row, hide_delay = make_scale_with_steppers(delay_adj("hide-delay", 0.0, 1.0), 2, Gtk.Label())
    anim_row, anim_time = make_scale_with_steppers(delay_adj("animation-time", 0.0, 1.0), 2, Gtk.Label())
    row(time_box, "Show delay (s)", show_row)
    row(time_box, "Hide delay (s)", hide_row)
    row(time_box, "Animation (s)", anim_row)

    # --- Look ---
    look_box = section("Look")
    opacity_row, opacity = make_scale_with_steppers(
        delay_adj("background-opacity", 0.0, 1.0), 2, Gtk.Label()
    )
    row(look_box, "Background opacity", opacity_row)

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

    indicator_combo = Gtk.ComboBoxText()
    for style in INDICATOR_STYLES:
        indicator_combo.append(style, style.capitalize() if style != "DEFAULT" else "Default")
    cur_ind = gget("running-indicator-style") if schema_has_key("running-indicator-style") else "BINARY"
    if cur_ind in INDICATOR_STYLES:
        indicator_combo.set_active_id(cur_ind)
    else:
        indicator_combo.append(cur_ind, cur_ind)
        indicator_combo.set_active_id(cur_ind)
    row(look_box, "Running indicator", indicator_combo)

    indicator_bottom = Gtk.CheckButton(
        label="Always keep window indicators under icons (even if dock is left/right/top)"
    )
    try:
        import indicators_patch as _ind

        indicator_bottom.set_active(_ind.is_active())
    except Exception:
        indicator_bottom.set_active(False)
    look_box.pack_start(indicator_bottom, False, False, 0)

    status = Gtk.Label(label="Ready — live apply enabled.", xalign=0)
    status.set_line_wrap(True)
    outer.pack_start(status, False, False, 0)

    def selected_stay() -> tuple[str, dict[str, str]]:
        for rb, (pid, _label, keys) in zip(stay_group, STAY_PRESETS):
            if rb.get_active():
                return pid, keys
        return STAY_PRESETS[0][0], STAY_PRESETS[0][2]

    def collect_settings() -> dict[str, str]:
        settings: dict[str, str] = {}
        settings["dash-max-icon-size"] = str(int(icon_scale.get_value()))
        settings["icon-size-fixed"] = "true"
        settings["dock-position"] = pos_combo.get_active_id() or "BOTTOM"
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
        settings["running-indicator-style"] = indicator_combo.get_active_id() or "BINARY"
        settings["click-action"] = click_combo.get_active_id() or "focus-or-previews"
        settings["isolate-workspaces"] = "true" if isolate_ws.get_active() else "false"
        settings["isolate-monitors"] = "true" if isolate_mon.get_active() else "false"
        settings["multi-monitor"] = "true" if multi_mon.get_active() else "false"
        settings["show-apps-at-top"] = "true" if apps_top.get_active() else "false"
        settings["show-show-apps-button"] = "true" if show_apps.get_active() else "false"
        return settings

    def apply_indicator_pref() -> str:
        try:
            import indicators_patch as _ind

            if indicator_bottom.get_active():
                return _ind.apply_patch()
            return _ind.remove_patch()
        except Exception as exc:
            return f"Indicator patch: {exc}"

    def auto_apply_now(_source: str = "") -> bool:
        auto_timer["id"] = None
        if suppress_auto["on"]:
            return False
        try:
            settings = collect_settings()
            apply_map(settings)
            msg = f"Live · applied {len(settings)} settings"
            if _source:
                msg += f" ({_source})"
            # Indicator toggle needs sudo — only when that control was the source.
            if _source == "indicators":
                msg += "\n" + apply_indicator_pref()
            status.set_text(msg)
        except subprocess.CalledProcessError as exc:
            status.set_text(f"Live apply failed: {exc}")
        return False

    def schedule_auto_apply(source: str = "", delay_ms: int = 120) -> None:
        if suppress_auto["on"]:
            return
        if auto_timer["id"] is not None:
            GLib.source_remove(auto_timer["id"])
        auto_timer["id"] = GLib.timeout_add(delay_ms, auto_apply_now, source)

    def collect_and_apply(extra: dict[str, str] | None = None) -> None:
        settings = extra if extra is not None else collect_settings()
        apply_map(settings)
        status.set_text(f"Applied {len(settings)} settings.")

    def load_from_gsettings() -> None:
        suppress_auto["on"] = True
        try:
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
            if schema_has_key("running-indicator-style"):
                ind = gget("running-indicator-style")
                if indicator_combo.get_active_id() != ind:
                    if ind not in INDICATOR_STYLES:
                        indicator_combo.append(ind, ind)
                    indicator_combo.set_active_id(ind)
            if schema_has_key("click-action"):
                click = gget("click-action")
                if click_combo.get_active_id() != click:
                    if click not in dict(CLICK_ACTIONS):
                        click_combo.append(click, click)
                    click_combo.set_active_id(click)
            if schema_has_key("isolate-workspaces"):
                isolate_ws.set_active(gget("isolate-workspaces") == "true")
            if schema_has_key("isolate-monitors"):
                isolate_mon.set_active(gget("isolate-monitors") == "true")
            if schema_has_key("multi-monitor"):
                multi_mon.set_active(gget("multi-monitor") == "true")
            if schema_has_key("show-apps-at-top"):
                apps_top.set_active(gget("show-apps-at-top") == "true")
            if schema_has_key("show-show-apps-button"):
                show_apps.set_active(gget("show-show-apps-button") == "true")
            try:
                import indicators_patch as _ind

                indicator_bottom.set_active(_ind.is_active())
            except Exception:
                pass
            status.set_text("Reloaded from current dock settings.")
        finally:
            suppress_auto["on"] = False

    def on_defaults(_b: Gtk.Button) -> None:
        try:
            suppress_auto["on"] = True
            apply_map(SCRIPT_DEFAULTS)
            load_from_gsettings()
            preset_combo.set_active_id("")
            status.set_text("Restored script defaults (same as ./dock.sh apply).")
        except subprocess.CalledProcessError as exc:
            status.set_text(f"Failed: {exc}")
        finally:
            suppress_auto["on"] = False

    def on_reload(_b: Gtk.Button) -> None:
        load_from_gsettings()
        preset_combo.set_active_id("")

    def on_named_preset(_c: Gtk.ComboBoxText) -> None:
        if suppress_auto["on"]:
            return
        pid = preset_combo.get_active_id() or ""
        if not pid:
            return
        for nid, _label, keys in NAMED_PRESETS:
            if nid == pid:
                try:
                    suppress_auto["on"] = True
                    apply_map(keys)
                    load_from_gsettings()
                    status.set_text(f"Applied named preset: {_label}")
                except subprocess.CalledProcessError as exc:
                    status.set_text(f"Failed: {exc}")
                finally:
                    suppress_auto["on"] = False
                return

    preset_combo.connect("changed", on_named_preset)

    def on_export(_b: Gtk.Button) -> None:
        try:
            settings = collect_settings()
            PRESET_DIR.mkdir(parents=True, exist_ok=True)
            payload = {"schema": SCHEMA, "settings": settings}
            PRESET_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            status.set_text(f"Exported to {PRESET_FILE}")
        except OSError as exc:
            status.set_text(f"Export failed: {exc}")

    def on_import(_b: Gtk.Button) -> None:
        if not PRESET_FILE.is_file():
            status.set_text(f"No preset file at {PRESET_FILE} — export first.")
            return
        try:
            data = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
            settings = data.get("settings") if isinstance(data, dict) else None
            if not isinstance(settings, dict):
                status.set_text("Invalid preset file: missing settings object.")
                return
            cleaned = {str(k): str(v) for k, v in settings.items() if str(k) in EXPORTABLE_KEYS}
            suppress_auto["on"] = True
            apply_map(cleaned)
            load_from_gsettings()
            preset_combo.set_active_id("")
            status.set_text(f"Imported {len(cleaned)} keys from {PRESET_FILE}")
        except (OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
            status.set_text(f"Import failed: {exc}")
        finally:
            suppress_auto["on"] = False

    # Wire live apply (sliders debounced; toggles/combos immediate).
    for scale, name in (
        (icon_scale, "size"),
        (show_delay, "timing"),
        (hide_delay, "timing"),
        (anim_time, "timing"),
        (opacity, "look"),
    ):
        scale.connect("value-changed", lambda _s, n=name: schedule_auto_apply(n, 140))

        def _on_release(_s: Gtk.Widget, _e: Gdk.EventButton, n: str = name) -> bool:
            schedule_auto_apply(n, 0)
            return False

        scale.connect("button-release-event", _on_release)

    pos_combo.connect("changed", lambda _c: schedule_auto_apply("position", 0))
    click_combo.connect("changed", lambda _c: schedule_auto_apply("click", 0))
    indicator_combo.connect("changed", lambda _c: schedule_auto_apply("indicator", 0))
    for rb in stay_group:
        rb.connect("toggled", lambda _b: schedule_auto_apply("stay", 0) if _b.get_active() else None)
    for chk, name in (
        (pressure, "pressure"),
        (isolate_ws, "behavior"),
        (isolate_mon, "behavior"),
        (multi_mon, "behavior"),
        (apps_top, "behavior"),
        (show_apps, "behavior"),
    ):
        chk.connect("toggled", lambda _b, n=name: schedule_auto_apply(n, 0))
    indicator_bottom.connect("toggled", lambda _b: schedule_auto_apply("indicators", 0))
    color_btn.connect("color-set", lambda _b: schedule_auto_apply("color", 0))
    color_entry.connect("activate", lambda _e: schedule_auto_apply("color", 0))

    def _color_focus_out(_e: Gtk.Widget, _ev: Gdk.EventFocus) -> bool:
        schedule_auto_apply("color", 0)
        return False

    color_entry.connect("focus-out-event", _color_focus_out)

    buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    buttons.set_homogeneous(False)
    defaults_btn = Gtk.Button(label="Reset to script defaults")
    reload_btn = Gtk.Button(label="Reload")
    export_btn = Gtk.Button(label="Export preset")
    import_btn = Gtk.Button(label="Import preset")
    close_btn = Gtk.Button(label="Close")
    defaults_btn.connect("clicked", on_defaults)
    reload_btn.connect("clicked", on_reload)
    export_btn.connect("clicked", on_export)
    import_btn.connect("clicked", on_import)
    close_btn.connect("clicked", lambda _b: win.destroy())
    buttons.pack_start(defaults_btn, False, False, 0)
    buttons.pack_start(reload_btn, False, False, 0)
    buttons.pack_start(export_btn, False, False, 0)
    buttons.pack_start(import_btn, False, False, 0)
    buttons.pack_end(close_btn, False, False, 0)
    outer.pack_start(buttons, False, False, 0)

    suppress_auto["on"] = False
    win.show_all()
    Gtk.main()


def main() -> None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        die("no graphical session detected (DISPLAY/WAYLAND_DISPLAY missing)")
    ensure_deps()
    build_ui()


if __name__ == "__main__":
    main()
