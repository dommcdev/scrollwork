# Testing

## Initial baseline (2026-11-10, before floating rules/strict client regression)

- 9 layout tests passed, including the 10,000-operation randomized sequence.
- 14 settings/journal assertions passed in GJS.
- **56 real-compositor integration checks passed in three consecutive fresh
  sessions** on GNOME 51.1; all three runs exited successfully.
- 1 explicit skip per run: the virtual monitor does not advertise 2x scaling.
  Actual 1.25x fractional scaling and portrait rotation both passed.
- Syntax/schema checks, Python compilation and packaging passed. The ZIP was
  verified to contain exactly seven runtime files, compiled schemas, valid
  metadata and no private test bridge.

Artifacts for the repeated runs are under `test-results/repeat-1/` through
`repeat-3/`. Nothing was installed into the live desktop.

## Additional coverage

Verified current results on 2026-11-10:

- Stock compositor: **67 checks passed**, with the strict Electron limitation
  explicitly skipped and 2x output scaling unavailable.
- Experimental staged Mutter: **71 checks passed in two consecutive fresh
  sessions**, including the larger-minimum-width Electron case, paint/input
  boundaries and clip cleanup on disable. Only unavailable 2x scaling was skipped.
- Logs/screenshots/results: `test-results/stock-current/`, `patched-1/`, `patched-2/`.
- No live compositor or system libraries were replaced.

The current unit suite has 18 layout/rule tests plus the 14 GJS settings checks.
It adds exact app-ID/initial-title matching, rule precedence, initial floating
placement, rule validation and repeated focus switching of two half-width slots
across even/odd work areas and different gap sizes.

The stock-compositor integration suite explicitly skips the **known failing**
strict Electron case. `npm run test:strict` makes that case mandatory and currently
fails on stock Mutter; it is not counted as working just because it can float.
The staged experimental compositor runs that regression automatically. See
[patches/README.md](patches/README.md) for its scope and clipping tradeoff.

New real-client checks cover the calculator's actual GTK app ID/default floating
size, manual tiling of a rule-floated app, live title rules, title changes, user
resizing without placement fights, explicit tile rules and invalid live edits.
The strict fixture is a local/offline Electron app with `minWidth=644` for a
628-pixel slot, not Discord running against the user's profile. It checks 40
focus alternations, input picking beyond the slot and screenshot pixels in the
outer gap. These checks distinguish fixed frame geometry from mere visual or
input overflow.

## Reproducible commands

```sh
npm run check
npm test
npm run test:integration
npm run package
```

No live-session installation, sudo, VM image or network download is needed on
the development host (Arch Linux, GNOME Shell/Mutter 51.1).

### Pure layout tests

Node's built-in test runner tests insertion, duplicate insertion, focus/reorder
boundaries, removal, half/full widths, lone-column full width, explicit centering,
negative origins, tiny/resized work areas, and 10,000 seeded randomized lifecycle
operations. Focus must remain visible; geometry must be integer/positive and
columns must not overlap. Opening windows preserves existing widths except for
the intentional lone-column/full-width behavior.

### Settings recovery tests

GJS tests use an in-process memory GSettings backend and temporary state. They
check applying/restoring overrides, unset vs explicit original values, preserving
subsequent user edits, simulated owner-crash recovery, journal cleanup, and
refusing malformed journals without overwriting them or changing settings.

### Actual compositor integration tests

`tests/integration.py` provisions private XDG/HOME directories and launches
headless GNOME on a private session bus. Its system-bus address also points to
that bus. A test-only extension exposes Shell evaluation **only in this isolated
session**. It is not part of the distributable archive.

The test compares assigned rectangles with **actual Meta.Window frame
rectangles after real GTK clients commit**. Predicates must remain true for
250 ms, rather than passing on a transient optimistic geometry update.

Coverage includes:

- First-map size, actual external-constraint invocation, single/full -> multiple
  half-width columns, offscreen real windows and focus scrolling.
- Virtual keyboard input through Mutter's real keybinding path: Super+H/L and
  numbered workspaces. Modifier events are dispatched separately, like physical
  key presses; the overview must not be accidentally activated.
- Pointer positioning, GTK hover and **real GTK button activation** after the
  strip scrolls, not just compositor-side picking.
- Out-of-policy move/resize, app-driven resizing, width changes and reordering.
- Transient dialogs, fullscreen/restore, maximize suppression and optional native
  maximize, minimize/restore and manual floating/retiling.
- A separate Wayland process stopped with SIGSTOP during a resize, followed by
  SIGCONT and successful configure completion. The compositor must stay responsive.
- A GTK minimum-size client that refuses its column width: bounded retries and
  floating fallback, followed by clean removal.
- Native workspace migration/overview, ten numbered workspaces and instant
  switching **while other GNOME animations are enabled**.
- Disable with queued layout work, no remaining constraints/timers, accessible
  offscreen windows, restored native settings/shortcuts, and unconstrained resizing.
- Re-enable over existing windows, five extra disable/re-enable cycles, twelve
  real-client open/resize/reorder/close cycles, and hot-reloaded gap settings.
- Actual display rotation to portrait/back through DisplayConfig and 1.25x
  fractional output scaling. 2x scaling is explicitly skipped if not advertised
  by this 1280x800 virtual monitor.
- PNG screenshot captured by the compositor itself.

Virtual pointer creation starts at the hot corner, so hot corners are disabled
in the **private test settings only** to prevent accidental overview activation.
Expected warnings about missing GDM/logind/colord/polkit, unavailable GPUs and
screen locking are consequences of isolation, not evidence that those services
were tested. The oversized-client fallback emits its own expected warning.

## Windowed test launcher (2026-11-10)

`npm run test:interactive` starts the saved patched runtime through a namespace,
with the original temporary build directory masked. It verifies one active
monitor, startup outside overview, and matching actual/assigned rectangles for
real GTK and oversized Electron clients. The viewer is a real Wayland window
in Hyprland, fed through private PipeWire plus WirePlumber. Both 1280×800 and
default 1600×900 initial-size requests passed; the parent tiling compositor can
resize the viewer, and the nested output follows that actual size.

Also verified: duplicate-launch refusal preserves the running session's lock;
`--stop` identifies and terminates the owned launcher even when started with a
relative script path; the viewer disappears and Hyprland remains responsive.
Five launcher unit tests cover mount ordering, persistent runtime selection,
profile/environment isolation and explicit smoke-only instrumentation.

The normal session enables a small private startup helper to dismiss overview,
not an Eval bridge. Its settings and application profiles persist separately.
The viewer's shortcut-capture default has its own one-line MDK patch; physical
keyboard pass-through and actual toolbar-button interaction remain human checks.
Actual Discord/OpenCode compatibility is not inferred from the offline fixture.
See [TRY-TOMORROW.md](TRY-TOMORROW.md).

## Stock-Mutter interaction/appearance iteration

On 2026-11-11, **83 checks passed on stock Mutter 51.1**, including an ordinary
Electron client alongside GTK. The oversized strict-client case and unavailable
2x monitor scaling remain explicit skips, not claimed passes.
The 83-check run passed again after adding pointer-following for column
reordering/centering and packaging version 2. Node/GJS/launcher unit tests,
syntax/schema checks, Python compilation and ZIP contents validation also passed.
Version 2 is installed on disk; the live session was deliberately left on its
loaded version 1 pending the user's next logout/login.

The extension now includes pointer-movement focus (without raising), settled
focus-change pointer warping, monitor-centered floating/dialog placement,
uniform texture rounding/focus borders/inactive opacity, and short window
movement easing. Workspace animation remains disabled. No compositor patch is
used for this path and GTK/app titlebars are unchanged.

New isolated integration checks cover real pointer hover focus in both
directions, keyboard pointer warping, a real GTK file chooser, centering
transients independently of their parent, creation/completion of movement
transitions, effect/transform/timer cleanup, and restoration of the added native
setting leases. Screenshots verify active/inactive border pixels and clipped
corners. The log gate also rejects disposed-actor access and shader failures.

Rounding is visual only: stock Mutter still owns rectangular input regions.
The border is drawn inside the frame. Hyprland's squircle power/blur and exact
animation timing are not reproduced. Actual GPU performance and prolonged daily
use remain manual checks.

## Edge hints (version 3, 2026-11-11)

**88 checks passed on stock Mutter 51.1**. Five new real-pointer checks verify
left/right hint reveal without focus changes, actual primary-button clicks
scrolling each hidden window into view, and hiding hints away from the edges.
Disable cleanup now also verifies removal of the edge controller/chrome.
Two pure layout tests cover nearest hidden columns, fitting pairs, partial
visibility and negative monitor origins. Unit, syntax and schema checks pass.

Titlebars and application configuration are unchanged.

## Version 4: pointer semantics, fades and bindings (2026-11-11)

**98 checks passed on stock Mutter 51.1.** The new screenshot check verifies
the hint's 2px visual line independently of its larger transparent click target.
Real pointer checks assert exact unchanged coordinates after left/right edge
clicks and no pointer warp after ordinary app activation. Super-only overview
is disabled; virtual-key tests verify Ctrl+apostrophe dispatches Vicinae and
Super+Return dispatches Ghostty, with subprocess launch stubbed in the isolated
test session rather than opening real user apps. Native screenshot/lock/Hex
conflict settings and their restoration are checked too.

The GTK fixture can send an explicit Wayland app ID, verifying that Vicinae's
`vicinae` ID floats/centers. The real existing Vicinae service responds to ping;
actual launcher UI interactions remain a user-session check. Focus fade tests
observe intermediate opacity values and completion at the exact configured
color/opacity. Disable/destroy and reduced-motion settings stop animation timers.
Pure tests cover Hyprland cubic curves and canonical shortcut-conflict matching.

Only directional/workspace focus actions initiate pointer warps. Noctalia's
desktop-specific commands use native GNOME equivalents; layout-only features
not yet implemented are listed in [KEYBINDINGS.md](KEYBINDINGS.md). No recording,
locking, network restart or user-app launch was triggered by automated tests.

## Remaining manual coverage

- Everyday usability and latency on the physical GPU/display/trackpad.
- Xwayland, Qt, actual Discord/Chrome, OpenCode, Ghostty and GrandOrgue
  compatibility. Automated clients use GTK 4 and the offline Electron fixture,
  not the user's real applications or profiles.
- Lock/unlock, login manager, polkit prompts, screen sharing, suspend/resume,
  real monitor hotplug, or actual three-finger gestures.
- Visual fidelity to Hyprland or removal of application-drawn headerbars.
- Robustness against malicious clients or arbitrary GNOME extension combinations.
- Behavior on GNOME versions other than 51.1.

These are not described as passing just because GNOME owns those components.
The first deliverable is a tested architectural prototype, not a claim of
complete Hyprland parity.
