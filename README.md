# Scrollwork

A scrolling-layout GNOME Shell extension that brings a Hyprland-style workflow
to stock GNOME 51, while keeping GNOME's own panel, overview, dialogs and
workspaces. Single monitor only; this is a prototype.

- Windows sit in a horizontal strip, one per column, on ten static workspaces.
  Half/full column widths; a lone column fills the screen.
- Focus scrolls the focused column into view. Columns can be reordered and centered.
- Hover focus without raising. Keyboard focus/workspace changes warp the pointer
  into the destination window; clicks and hover never do.
- Dialogs and floating windows are centered on the screen. Per-app floating rules.
- Rounded corners, focus borders and inactive opacity, with short fades.
- Thin clickable hints at the screen edges for off-screen columns.

See [DESIGN.md](DESIGN.md) for how it works and its known limits.

## Install

```sh
curl -LO https://github.com/dommcdev/scrollwork/releases/latest/download/scrollwork@dommcdev.github.io.shell-extension.zip
gnome-extensions install --force scrollwork@dommcdev.github.io.shell-extension.zip
gnome-extensions enable scrollwork@dommcdev.github.io
```

Log out and back in after installing or updating: GNOME caches extension code.

## Bindings

| Shortcut | Action |
| --- | --- |
| Super+H / L | Focus left / right |
| Super+Ctrl+H / L | Move column left / right |
| Super+D | Cycle half/full column width |
| Super+C | Center column |
| Super+G | Toggle floating |
| Super+Shift+D | Fullscreen |
| Super+X | Close window |
| Super+1…0 | Switch to workspace 1…10 |
| Super+Shift+1…0 | Move window to workspace 1…10 |

App launchers (terminal, browser, files, etc.) are also defined as shortcuts in
the schema. All bindings can be changed with `gsettings`/`dconf` under
`/org/gnome/shell/extensions/scrollwork/`.

While enabled, Scrollwork overrides GNOME settings that conflict with it
(e.g. Super+H/L, Super+numbers, dynamic workspaces). The originals are saved to
`~/.local/state/scrollwork/settings-backup.json` and restored on disable. If
GNOME crashes and you want them back without re-enabling the extension, run
`gjs -m scripts/restore-settings.js` from this repo.

## Settings

Tunable keys: `gap`, `inner-gap`, `suppress-maximize`, `hover-focus`,
`warp-pointer`, `edge-hints`, `movement-duration`, `border-fade-duration`,
`focus-fade-duration`, `style-windows`, `corner-radius`, `border-width`,
`active-border`, `inactive-border`, `inactive-opacity` and `window-rules`.

`window-rules` takes a JSON array of extra floating rules; the last match wins
over the built-in profile in `rules.js`:

```json
[
  {"appId": "com.example.Utility", "mode": "float", "center": true, "size": [0.5, 0.5]},
  {"appId": "com.dominic.calc", "mode": "tile"}
]
```

`appId` matches an exact app ID/WM class (or any in an array); `initialTitle` is
an optional regex on the first window title. Sizes are work-area fractions (≤ 1)
or logical pixels (≥ 1). Rules set initial geometry only.

## Not implemented

Vertical stacks, scratchpad, continuous resizing of tiled columns,
Super+scroll workspace navigation, per-app workspace rules, titlebar removal,
multi-monitor, and persisting the layout across sessions.

## Development

Requires GNOME Shell/Mutter 51, GJS, Node.js and Python GObject bindings.

```sh
npm run check             # syntax + schema check
npm test                  # unit tests
npm run test:integration  # headless GNOME Shell with real GTK clients
npm run package           # build dist/*.shell-extension.zip
```

The integration test runs a private headless GNOME Shell with its own D-Bus and
HOME; it never touches your session. Logs go to `test-results/`.

To release, push a tag (`git tag v0.2 && git push origin v0.2`). GitHub Actions
builds the zip and attaches it to a release.
