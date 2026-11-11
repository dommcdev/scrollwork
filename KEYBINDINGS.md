# Hyprland bindings in GNOME

Version 4 uses portable commands from `~/.config/hypr/keybindings.lua`.
Native shortcut, Super-only overview, hot-corner and mouse-modifier changes
are journaled/restored on disable. Hyprland/app configs are not edited.

## Apps and launcher

| Shortcut | Action |
|---|---|
| Ctrl+apostrophe | Vicinae toggle |
| Super+Return | New Ghostty window |
| Super+B / Super+Shift+B | Chrome / incognito |
| Super+F / Super+Shift+F | Files / Yazi in Ghostty |
| Super+N | Obsidian |
| Super+T | Calculator (qalc) |
| Super+R | Audio mixer (wiremix) |
| Super+E | Bluetooth TUI (bluetui) |
| Super+U | System monitor (btop) |
| Super+W | WiFi TUI (wlctl) |
| Super+Shift+W | Restart NetworkManager, only when explicitly pressed |
| Alt+G | Existing GrandOrgue launcher script |
| Super+I / Super+Shift+I | Gemini / ChatGPT web app |
| Super+Y / Super+Shift+Y | Parabolic / YouTube Watch Later |
| Super+Shift+comma | GNOME Settings |

The TUI app IDs retain floating rules. Vicinae's native Wayland app ID
`vicinae` floats/centers rather than entering the strip. Its existing enabled
user service is used; Scrollwork does not start a second server.

## GNOME equivalents for shell-owned operations

| Shortcut | Action |
|---|---|
| Super alone | Nothing (no overview toggle) |
| Super+Q | Lock; Alt+Tab remains the native app switcher |
| Print / Super+S | Full screenshot using GNOME |
| Shift+Print / Super+Shift+S | GNOME screenshot-selection UI |
| Super+Alt+S | GNOME screenshot UI; Noctalia annotation is not reproduced |
| Super+Shift+P | GNOME color picker; hex color copied to clipboard |
| Super+A | Dismiss the current notification banner |
| Super+Shift+A | Focus the active notification using GNOME's handler |
| Super+left/right mouse drag | Native move/resize for floating windows |

Noctalia is **not** launched in GNOME. Volume/brightness/media/power keys stay
owned by GNOME. The Hyprland power script uses `uwsm stop` and is deliberately
not installed as a GNOME power-key handler.

Hex keeps its own shortcuts-portal bindings and press/release behavior on
Super+Space, Super+Shift+Space and the Copilot key. GNOME input-source conflicts
are released, but Scrollwork does not synthesize recording events or replace a
hold shortcut with a toggle. Check Hex's portal registration in the real session;
no dictation or recording was started by automated tests.

## Window management

Super+H/L focus, Ctrl+Super+H/L reorder, Super+D width, Super+C center,
Super+G float, Super+Shift+D fullscreen, Super+X close, and numbered workspaces
are unchanged. **Only directional/workspace focus bindings can warp the pointer.**
Click/hover/app activation, edge clicks, reordering and width changes never
initiate a warp. Edge clicks preserve the exact pointer position.

Hyprland-only vertical stacks/J/K/O, scratchpad Z bindings, continuous arrow-key
resizing of tiled columns and Super+wheel workspace navigation remain unimplemented.
