# ubuntu-dock-setup

One script that turns the stock Ubuntu Dock into a floating, translucent bottom bar
that **doesn't steal screen space** from your windows.

The default Ubuntu Dock is a full-height left panel that reserves a strut, so every
maximized window is permanently narrower. GNOME's Settings → Appearance panel only
exposes three of the knobs involved (position: left/bottom/right, icon size, autohide).
The rest live in the `dash-to-dock` GSettings schema. This script sets them all in one
shot and verifies the result.

```bash
git clone git@github.com:codebyshoaib/ubuntu-dock-setup.git
cd ubuntu-dock-setup
./dock.sh              # apply + verify
./dock.sh verify       # check current state matches (exit 1 on drift)
./dock.sh reset        # back to Ubuntu defaults
./dock.sh show         # dump every key in the schema with its current value
```

Idempotent — re-run it any time. No sudo, no files touched outside dconf.

## Requirements

Ubuntu with the Ubuntu Dock extension (`ubuntu-dock@ubuntu.com`, the default on
Ubuntu 20.04+). Works on upstream `dash-to-dock` too — same schema ID. The strut
check in `verify` needs X11 and `xprop`; on Wayland it's skipped and the rest of
the verification still runs.

## What it changes, and why

### Placement

| Key | Value | Why |
| --- | --- | --- |
| `dock-position` | `BOTTOM` | `TOP` is also a valid enum value the Settings UI never offers. |
| `always-center-icons` | `true` | Icons centered rather than packed to one end. |
| `extend-height` | `false` | Floating pill instead of an edge-to-edge panel. |
| `dock-fixed` | `false` | **The important one.** Stops the dock reserving space, so windows extend to the screen edge and the dock floats over them. |
| `intellihide` + `intellihide-mode=ALL_WINDOWS` | on | Dock hides when any window covers it, reveals on hover. |
| `require-pressure-to-show` | `false` | Reveal on hover instead of requiring a push against the edge. |

### Size and spacing

| Key | Value | Why |
| --- | --- | --- |
| `dash-max-icon-size` | `36` | Down from 48. |
| `custom-theme-shrink` | `false` | The only inter-icon spacing lever the schema has — `true` compresses padding, `false` restores it. |

### Look

| Key | Value | Why |
| --- | --- | --- |
| `transparency-mode` | `FIXED` | Constant opacity instead of the adaptive default. |
| `background-opacity` | `0.35` | |
| `custom-background-color` + `background-color` | `#181825` | The stock dock is 80% **white**, which is what makes it look flat on a dark desktop. |
| `apply-glossy-effect` | `false` | Removes the gradient sheen. |
| `running-indicator-style` | `BINARY` | Window count per app, in binary. Also available: `DOTS` `SQUARES` `DASHES` `SEGMENTED` `SOLID` `CILIORA` `METRO`. |

### Declutter and feel

| Key | Value | Why |
| --- | --- | --- |
| `show-trash`, `show-mounts` | `false` | Trash and every mounted volume were consuming dock slots. |
| `animation-time` | `0.10` | Halved from 0.2. |
| `show-delay`, `hide-delay` | `0.05` | |
| `scroll-action` | `cycle-windows` | Scroll over an icon cycles that app's windows. |
| `middle-click-action` | `quit` | |

## Verification

`./dock.sh apply` runs `verify` afterwards, and `verify` is the test:

1. Reads every key back and diffs it against the intended value. Doubles compare
   with a tolerance, because gsettings echoes `0.35` back as `0.34999999999999998`.
2. Asserts the dock reserves no space, by checking `_NET_WORKAREA` reaches the
   bottom of `_NET_DESKTOP_GEOMETRY`. This is the one claim in the whole script
   that a settings read-back cannot prove.

```
$ ./dock.sh verify
OK dock reserves no space (workarea reaches screen bottom)
verify: ok
```

Non-zero exit on any mismatch, so it drops straight into CI or a dotfiles check.

## Shortcuts you already have

The dock ships these on and they're worth knowing:

- Hold **Super** — the dock overlays index numbers on each icon.
- **Super + 1..9** — launch or focus that pinned app.
- **Super + Q** — toggle the dock.

## Variations

Not applied by default; pick if they suit you better.

```bash
d=org.gnome.shell.extensions.dash-to-dock

# Dock visible over background windows, hidden only by the focused app
gsettings set $d intellihide-mode FOCUS_APPLICATION_WINDOWS

# ...or only by maximized ones
gsettings set $d intellihide-mode MAXIMIZED_WINDOWS

# Top edge, under the GNOME panel
gsettings set $d dock-position TOP

# Give the space back: pinned dock that reserves a strut again
gsettings set $d dock-fixed true
```

Attempting `autohide=false` + `intellihide=false` to get a permanently visible
overlapping dock is **not** supported by dash-to-dock — its documented modes are
reserve-space or hide-when-covered, and that combination tends to leave the dock
hidden. `intellihide-mode` is the supported way to control *when* it hides.
