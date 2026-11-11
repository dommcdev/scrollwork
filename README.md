# Scrollwork

Development is paused. This project stays in its own repository; GNOME/GDM
provisioning is saved separately in the dotfiles `gnome` branch. Generated test
launchers, patched runtimes, builds and results were cleaned up, and the installed
prototype was disabled. Historical windowed-test setup instructions below need
their runtime rebuilt before use; the stock-Mutter source remains ready to develop.

An experimental GNOME 51 scrolling extension, aimed at reproducing Dominic's
Hyprland workflow while retaining GNOME Shell's actual desktop UI.

**This is a tested prototype, not yet a daily-driver replacement for Hyprland.**
**Stock Mutter does not yet pass the strict Electron minimum-width regression.**
Default floating rules and gap arithmetic are fixed, but those fixes alone do
not solve Discord refusing a requested width. `npm run test:strict` reproduces
that limitation; the experimental compositor work is separate from the ZIP.
The [staged Mutter experiment](patches/README.md) passes that regression and
enforces paint/input boundaries, but clips a client that refuses the requested
size. It is not installed system-wide and is not a finished Discord solution.
Single monitor only. Stock Mutter is the supported everyday path; the optional
strict-layout patch remains a separate experiment. No custom shell, compositor
fork, window clones, or replacement overview. Geometry changes are immediate;
short texture translations ease window movement without animating configure sizes. Keyboard
workspace changes and the end of native workspace gestures have no animation;
the rest of GNOME's effects are left alone.

## Try it in a window

On this development machine, launch **Scrollwork Test** from Hyprland, or run:

```sh
python ~/dev/projects/scrollwork/scripts/try.py
```

The prebuilt patched runtime persists outside `/tmp`; no logout or sudo is
needed. Settings and app profiles are separate. See [TRY-TOMORROW.md](TRY-TOMORROW.md)
for the short test checklist, clipping caveat and safe exit instructions.
This software-rendered session is for layout testing, not GPU benchmarking.

## Current behavior

- Windows in a horizontal strip, one window per column, on native workspaces.
- Half/full-width presets; a lone column automatically fills the work area.
  Half widths reserve the gap **before** dividing, so two halves fit without
  focus-dependent nudging, including odd logical-pixel budgets.
- Focus scrolls a column into view, with no wraparound. Columns can be reordered
  and explicitly centered.
- Outer gaps of 8 logical pixels; 8 pixels between columns (Hyprland `gaps_in=4`
  on both facing edges).
- Application maximize requests suppressed, matching the existing Hyprland rule.
  Native fullscreen remains available. Maximize suppression is configurable.
- Dialogs/transients are not constrained. Manual floating and a bounded floating
  fallback for clients that cannot fit the requested size.
- Pointer movement focuses windows without raising them. Directional/workspace keyboard focus
  changes move the pointer into the destination once geometry and movement settle;
  an already-inside pointer is left alone. Clicks, hover, app activation and edge
  clicks never warp. Reordering/width changes do not initiate a warp either.
- Newly floating windows and transient/modal dialogs are centered in the monitor's
  work area, not their parent's column. Attached GNOME modal sheets are temporarily
  disabled. Initial placement accommodates asynchronous size commits; user
  move/resize grabs cancel placement rather than being fought.
- Window textures use 15px rounded corners, a 3px inside border (purple focused,
  dark inactive), and 97% inactive opacity, following the Hyprland palette.
  Fullscreen bypasses the effect. This is visual clipping, not an input-shape
  change: transparent corner pixels can still belong to the window's input region.
- Same-size window moves ease out over 150ms; numbered workspaces stay instant.
  No resize stretching, clones, blur, or titlebar removal is added.
- Move within 24px of a work-area side to reveal a narrow, clickable hint for the
  nearest off-screen column. Click to focus/scroll it into view without moving
  the pointer away from the screen edge.
  Hover alone does not scroll or change focus. The hint occupies the outer gap
  (a 2px visual line with a transparent 3–8px click target), hides away from the edge, and is suppressed during overview,
  fullscreen, modal dialogs and window dragging. Disable with `edge-hints=false`.
- Default per-app floating/initial placement follows the Hyprland profile:
  calculator, audio/network/Bluetooth/system-monitor TUIs, calendar, power menu,
  Nautilus previews, file dialogs and the selected GrandOrgue dialogs. Other
  normal windows, including Discord and OpenCode, default to tiling.
- Real window position/size policy enforced through `Meta.ExternalConstraint`.
  Client surface commits are audited; this API alone cannot force an arbitrary
  Wayland client to produce an exact-size surface. See [DESIGN.md](DESIGN.md).
- Zero or multiple logical monitors suspend tiling rather than spill windows onto
  another display. Previously offscreen windows are brought back into view on
  disable/release.

## Bindings

See [KEYBINDINGS.md](KEYBINDINGS.md) for version 4's Vicinae/app/TUI bindings,
native GNOME screenshot/lock/settings equivalents and unsupported Hyprland-only
actions. Super alone and hot corners no longer open overview.

These follow `~/.config/hypr/keybindings.lua`, not PaperWM defaults:

| Binding | Action |
| --- | --- |
| Super+H / L | Focus left / right |
| Super+Ctrl+H / L | Move column left / right |
| Super+D | Cycle half/full column width |
| Super+C | Center current column |
| Super+G | Toggle floating |
| Super+Shift+D | Toggle native fullscreen |
| Super+X | Close window |
| Super+1…9, 0 | Switch to workspace 1…10 |
| Super+Shift+1…9, 0 | Move window to workspace 1…10 without following |

While enabled, Scrollwork uses ten static native workspaces and temporarily
releases GNOME shortcuts that conflict with its own (notably minimize/lock on
Super+H/L and launching favorite apps on Super+numbers). These settings are
restored on disable, including whether a value was originally unset. Changes
made by the user while enabled are not overwritten during restoration.

Original settings are journaled **before** being changed, under
`$XDG_STATE_HOME/scrollwork/settings-backup.json` (normally `~/.local/state`). An
abandoned journal is recovered at the next enable. If GNOME crashes and you
want to recover without enabling the extension, first ensure it is disabled,
then run from this checkout:

```sh
gjs -m scripts/restore-settings.js
```

It does not rewrite the Hyprland config. Portable app launch shortcuts are
registered by the extension; screenshots/locking/media/polkit and the bar remain
GNOME/session responsibilities.

## Test without installing

Requirements: GNOME Shell/Mutter 51 with the external-constraint rectangle
setter, GJS, GTK 4 and Python GObject bindings, Node.js, `dbus-run-session`,
`gsettings`, and `glib-compile-schemas`. No npm dependencies or root privileges.
The strict client regression additionally requires Electron.

```sh
npm run check
npm test
npm run test:integration
```

The integration test starts a **real headless GNOME Shell and real GTK Wayland
clients** with a virtual monitor, software rendering, private D-Bus, private
runtime directory, and isolated HOME/XDG settings. The simulated system bus also
points at the private bus, not the host. It neither installs nor enables the
extension in your live desktop. It requires no VM because it exercises the actual
installed compositor directly, isolated from the live graphical session.

Logs, JSON results and a compositor screenshot are copied to `test-results/`.
Individual sandboxes are retained under `/tmp/opencode/scrollwork-*` for debugging.
See [TESTING.md](TESTING.md) for actual coverage and limitations.

## Build and optionally install

```sh
npm run package
# Only when ready to try this in a GNOME session:
gnome-extensions install --force dist/scrollwork@local.shell-extension.zip
# Log out/in if GNOME has not discovered the extension yet.
gnome-extensions enable scrollwork@local
```

Disable with `gnome-extensions disable scrollwork@local`. Never install the
`scrollwork-test@local` bridge from the test sandbox into a real session. The
packager explicitly excludes all test tooling.

Version 2 adds the stock-Mutter interaction/appearance changes. After updating
the installed ZIP, **log out and back into GNOME**: disable/enable alone does not
reload GNOME's cached JavaScript modules. The previous installed version is
backed up locally at `dist/scrollwork-v1-backup.shell-extension.zip`.
Version 3 adds the clickable edge hints; it likewise needs a new GNOME session
to load the new JavaScript. A local version-2 ZIP backup is kept in `dist/`.
Version 4 corrects edge-click pointer behavior, thins the visual hints, adds
Hyprland-curve focus fades and launcher/system bindings. Existing v3 is backed
up in `dist/` before installation; log out/in to load new code.

Settings/shortcuts are defined in `schemas/`; there is no preferences window yet.

The new behavior can be tuned with the extension's GSettings keys:
`hover-focus`, `warp-pointer`, `movement-duration` (0 disables movement easing),
`style-windows`, `corner-radius`, `border-width`, `active-border`,
`inactive-border`, and `inactive-opacity`. Defaults follow the Hyprland profile.
`border-fade-duration` defaults to 539ms (`easeOutQuint`), and
`focus-fade-duration` to 303ms (`quick`). Focus opacity changes only from 1 to
0.97, not a full fade-out. Rapid focus changes retarget from the current value;
reduced-motion settings and disable/destroy cancel animation timers.
These changes do not edit Ghostty, OpenCode or GTK configuration files.

## Floating rules

`Super+G` overrides the default for an individual normal window in either
direction. Rules set an **initial** size/position; they do not continually fight
later user moves/resizes. Transient dialogs remain outside the strip regardless.

The ported profile is in `rules.js`. Extra rules can be supplied as a JSON array
in the `window-rules` string setting; last match wins over the profile. For example:

```json
[
  {"appId": "com.example.Utility", "mode": "float", "center": true, "size": [0.5, 0.5]},
  {"appId": "com.dominic.calc", "mode": "tile"}
]
```

`appId` matches an exact GTK application ID, Wayland app ID/WM class or class
instance (or any of a supplied array). `initialTitle` is an optional regular
expression against the initial window title. Both matchers must match if both
are present. Sizes are either two work-area fractions at most 1, or two logical
pixel dimensions at least 1. Initial sizes are clamped to the usable work area.
Invalid live rule edits retain the last valid rule set and log an error.

The profile does not implement Hyprland's `stay_focused` or `dim_around` options.

## Remaining parity work

The current Hyprland config is the requirements source, not a mandate to rebuild
everything it offers. In particular, these are **not implemented yet**:

- Vertical stacks and Super+J/K/O behavior; currently one window per column.
- Continuous arrow-key resizing, Super+mouse drag/resize, Super+scroll workspace
  navigation, and exact Hyprland gestures. Hover sampling is 30ms and movement
  easing is an approximation, not Hyprland's renderer/animation implementation.
- Per-app workspace rules, GrandOrgue's workspace-9 master layout and the special
  scratchpad workspace. Floating/initial-size rules are implemented.
- Compositor-controlled decoration/titlebar policy. GTK headerbars are still
  application content; the constraint API does not remove them.
- Exact Hyprland squircle rounding power, blur and input-corner clipping.
- Persisted column order/widths across shell sessions or extension disable.

No animation framework is planned. The next priority is real-app compatibility
and the specific missing workflow above, not eye candy or multi-monitor support.
