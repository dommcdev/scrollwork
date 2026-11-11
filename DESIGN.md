# Design and evidence

## Boundary

Keep GNOME Shell/Mutter and the native panel, overview, dialogs, services and
workspaces. Replace only the window-placement policy. `layout.js` is a pure
column/viewport model; `extension.js` connects it to real `Meta.Window`s.

Each eligible window gets a `GObject` implementing `Meta.ExternalConstraint`.
Its synchronous vfunc only replaces the proposed rectangle with a precomputed
target through `info.set_rect(new Mtk.Rectangle(target))`. It does not schedule
layout, request another move, or mutate column state from inside Mutter's
constraint solver. Mutter 51's introspectable setter is required.

Normal layout changes compute targets and request `move_resize_frame()`. This
is not equivalent to using that method alone: the external constraint also runs
when another geometry operation enters Mutter's solver. There is no
`position-changed` repair loop and no cloned-window animation layer.

## What real tests disproved

The external-constraint API is **not complete authority over client buffers**.
A real GTK `set_default_size()` request can lead to a client-committed surface
size different from the compositor's target, despite the vfunc being called.
Likewise, a client with a minimum width larger than its assigned column can
continue producing the larger surface. Calling the API is not proof of final
window geometry.

The implementation consequently observes size commits and audits outstanding
configures after 250 ms. A target gets at most four retry attempts, paced by the
audit timer; a nonconforming window is released to floating rather than creating
an endless configure loop. A newly changed target resets the budget. The timer
is one-shot, not continuous polling. All sources/constraints/signals are released
on disable or window destruction. Native fullscreen bypasses column geometry.

This is still a hybrid policy/commit adapter, not the claim that an extension can
force every Wayland client to behave. A client-dependent size transition may be
visible. Smooth synchronized transactions, client tiling-state/decorations, or
eliminating every such transition might require small Mutter changes later.

### Strict client regression and native experiment

A later offline Electron test with a minimum width 16 pixels larger than its
half-screen slot reproduced the user's more important failure mode. Stock Mutter
explicitly discards constrained sizes on ordinary client commits. Tiled-edge hints
alone did not fix that. The experimental [Mutter patch](patches/README.md) gives
external layouts authoritative frame rectangles on those commits and clips
oversized client painting/input to the slot. It does **not** pretend the client
rendered a narrower UI; cropping is a real tradeoff. It is opt-in, outside the
extension ZIP, and not ready for system-wide installation.

The independent gap bug is fixed in `layout.js`: a half-width slot is
`floor((usableWidth - innerGap) / 2)`, not `usableWidth / 2`. The unused odd pixel,
if any, stays unused; focus never reallocates it. Unit tests alternate focus across
even/odd sizes and different gaps, and real-client tests alternate focus 40 times.

The first map must also schedule layout: constraining the first configure alone
did not reliably resize a newly mapped GTK surface. Actual tests caught this.
Transient/type hints can arrive after `window-created`, so eligibility is checked
again at layout time rather than trusting only the creation signal.

## Native behavior and minimal overrides

Column placement is instantaneous. Two narrowly scoped, reversible GNOME 51
workspace-animation hooks complete keyboard transitions immediately and remove
gesture-end settling duration. The native overview and interactive gesture path
are otherwise retained. These private hooks need checking when GNOME changes.

Keyboard conflicts and ten static workspaces require native setting overrides.
`settings.js` journals original typed values before changes and conditionally
restores them. It preserves unset values and does not overwrite subsequent user
edits. Recovery uses the same conditional restoration after a shell crash.

Only one logical monitor is supported. A second monitor releases constraints;
there is no untested output clipping, input clipping or workspace emulation.
The optional native experiment clips individual tiled slots on this one monitor;
it is not multi-monitor output ownership support.

## Floating policy

`rules.js` compiles the ported Hyprland profile plus custom JSON rules. Application
IDs are exact matches; initial-title expressions are snapshotted once mapped.
Metadata may arrive after creation, so rules are reconsidered at map/identity
changes. Last match wins. A manual floating/tiling choice overrides a rule, but
the nonconforming-client safety fallback still wins until explicitly toggled.
Rules set initial geometry once per matching rule, never on every focus change.
Live invalid rule edits retain the last successfully compiled rule set.

## Next implementation priorities

1. Exercise Ghostty, Chrome/Electron, Nautilus, dialogs and GrandOrgue in a nested
   interactive GNOME session; address actual incompatibilities.
2. Match the user's stacking/resizing/floating rules and scratchpad usage.
3. Add direct user input/drag tests for those behaviors before implementing more
   features. Retain instant workspace changes and fast column switching.
4. Only patch Mutter when a failing real-client test demonstrates an API gap;
   keep such patches small and independent of GNOME UI code.
