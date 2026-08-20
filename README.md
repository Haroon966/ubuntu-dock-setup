# ubuntu-dock-setup

One script that turns the stock Ubuntu Dock into a floating, translucent bottom bar
that **doesn't steal screen space** from your windows.

The default Ubuntu Dock is a full-height left panel that reserves a strut, so every
maximized window is permanently narrower. GNOME's Settings → Appearance panel only
exposes three of the knobs involved (position: left/bottom/right, icon size, autohide).
The rest live in the `dash-to-dock` GSettings schema. This script sets them all in one
shot and verifies the result.

## One-shot setup

```bash
curl -fsSL https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/dock.sh | bash
```

That command now runs `setup` by default:

- On a graphical desktop (`DISPLAY` / `WAYLAND_DISPLAY`), it opens the config UI first —
  including the common `curl | bash` one-shot path (stdin is a pipe, not a TTY).
- On headless / CI sessions, it applies the default preset (`apply + verify`).

No clone, no sudo, nothing written outside dconf except a cached UI file when needed.
Takes effect immediately — no logout or shell restart.

### Trust the download (recommended)

Prefer reading the script before piping it into a shell. To verify checksums from a clone:

```bash
git clone https://github.com/codebyshoaib/ubuntu-dock-setup.git
cd ubuntu-dock-setup
sha256sum -c SHA256SUMS
./dock.sh
```

Or download `dock.sh`, check it against [SHA256SUMS](SHA256SUMS), then run it locally.
When the UI is fetched into the cache, pin its hash:

```bash
DOCK_SETUP_EXPECT_SHA256='<sha256-of-dock-config.py>' \
  curl -fsSL https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/dock.sh | bash -s -- config
```

Other modes, same way:

```bash
URL=https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/dock.sh
curl -fsSL $URL | bash -s -- verify   # check state matches (exit 1 on drift)
curl -fsSL $URL | bash -s -- reset    # back to Ubuntu defaults
curl -fsSL $URL | bash -s -- show     # dump every key with its current value
curl -fsSL $URL | bash -s -- apply    # apply default preset directly (skip UI)
curl -fsSL $URL | bash -s -- config   # open UI directly
```

Or read it first, which you should before piping anyone's script into your shell:

```bash
git clone https://github.com/codebyshoaib/ubuntu-dock-setup.git
cd ubuntu-dock-setup && ./dock.sh
```

Idempotent — re-run it any time.

## Configure from UI

After cloning the repo, open a GTK dialog to change icon size, position, stay/hide
behavior, click action, workspace isolation, hover delays, and look — without editing
the script:

```bash
./dock.sh config
# or: python3 dock-config.py
```

Needs `python3` and GTK bindings:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0
```

The UI reads the live `dash-to-dock` settings, applies changes immediately via
`gsettings`, and can **Reset to script defaults** (same values as `./dock.sh apply`).

When running from one-shot (`curl | bash`), `dock.sh` auto-downloads `dock-config.py`
to `${XDG_CACHE_HOME:-~/.cache}/ubuntu-dock-setup/` if the file is not present locally.

### Stay / hide presets

| Preset | Effect |
| --- | --- |
| Floating — hide when any window covers | Default floating dock (`intellihide-mode=ALL_WINDOWS`) |
| Floating — hide only for focused app | `FOCUS_APPLICATION_WINDOWS` |
| Floating — hide only for maximized windows | `MAXIMIZED_WINDOWS` |
| Pinned — reserve screen space | `dock-fixed=true` (strut back on) |

Hover vs pressure: leave “Require pressure…” unchecked to reveal on simple edge hover
(`require-pressure-to-show=false`). Timing sliders map to `show-delay`, `hide-delay`,
and `animation-time`.

### Named style packs

The UI also offers named packs (they do **not** change what `./dock.sh apply` installs):

| Pack | Intent |
| --- | --- |
| Mac floating | Bottom floating pill, dots indicator, focus-or-previews |
| Windows taskbar-like | Edge-to-edge pinned bar, `minimize-or-previews`, multi-monitor |
| Minimal dark | Smaller icons, lower opacity, hide Show Apps |

### Export / import

**Export preset** writes the current UI selection to
`${XDG_CONFIG_HOME:-~/.config}/ubuntu-dock-setup/preset.json`.
**Import preset** reloads that file. Useful for dotfiles or moving settings between machines.

`./dock.sh verify` still checks the **script defaults**, not whatever you last chose in
the UI. That is intentional — verify is for the one-shot preset, not a live UI state
lock.

The curl one-shot only downloads `dock.sh`. For the UI, clone the repo (or place
`dock-config.py` next to `dock.sh`), otherwise `dock.sh config` fetches a cached copy.

### One-shot edge-case controls

```bash
# Disable UI path, always apply defaults
DOCK_SETUP_NO_UI=1 curl -fsSL "$URL" | bash

# Force UI path (if desktop env is available)
DOCK_SETUP_FORCE_UI=1 curl -fsSL "$URL" | bash

# Pin UI script source
DOCK_SETUP_UI_URL="https://raw.githubusercontent.com/codebyshoaib/ubuntu-dock-setup/main/dock-config.py" \
curl -fsSL "$URL" | bash

# Require a known sha256 for the cached UI download
DOCK_SETUP_EXPECT_SHA256='…' curl -fsSL "$URL" | bash -s -- config
```

## Requirements

Ubuntu with the Ubuntu Dock extension (`ubuntu-dock@ubuntu.com`, the default on
Ubuntu 20.04+). Works on upstream `dash-to-dock` too — same schema ID. If the schema
isn't installed the script says so and exits 1 rather than half-applying.

Binaries used: `gsettings`, `awk`, `grep`, `xprop` — all present on a stock Ubuntu
desktop. The `xprop` strut check needs X11; on Wayland it's skipped and the remaining
verification still runs. The optional config UI also needs `python3` and `python3-gi`.

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

Prefer `./dock.sh config` for interactive changes. Or set keys by hand:

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
hidden. `intellihide-mode` is the supported way to control *when* it hides. The
config UI only offers the supported stay presets above.
