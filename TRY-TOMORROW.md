# Test tomorrow: no logout, compiling or sudo

**Historical notes:** the installed test launcher and patched runtime were
removed when pausing development. These instructions are not currently ready
to run. Source/tests are preserved in this separate repository.

From your normal Hyprland desktop, search for **Scrollwork Test** in the launcher.
If the app launcher has not refreshed, run:

```sh
python ~/dev/projects/scrollwork/scripts/try.py
```

This opens a **windowed GNOME desktop with the experimental patched Mutter**.
It does not replace Hyprland, install a system Mutter package, enable anything in
normal GNOME or change your normal GNOME settings. You do not need to select
GNOME at the login screen.

The built runtime is saved at `~/.local/share/scrollwork-test/runtime`, not just
in `/tmp`, so a reboot does not erase it. The launcher checks the runtime hash
and GNOME version before starting. The original build tree is hidden from the
test process, so startup does not depend on that temporary directory surviving.

## First five minutes

1. Two demo windows open automatically. Click inside the nested desktop; its
   viewer requests that Hyprland pass shortcuts through while it is focused.
2. Repeatedly switch focus with **Super+H / L**. Both half-width windows should
   stay fixed, with no few-pixel sideways nudging.
3. Try **Super+D** for half/full width, **Super+Ctrl+H/L** for reordering,
   **Super+G** for floating/tiling, and **Super+Shift+D** for fullscreen.
4. Try **Super+1 / 2** for instant workspace switching and
   **Super+Shift+1 / 2** to move windows without following them.
5. Use **Super+X** to close the demos, then use the **outer viewer's toolbar** to
   open **Discord · test profile** and **OpenCode · test profile**. Use the same
   layout keys on them. The toolbar also offers Ghostty, Files, a deliberately
   oversized minimum-width demo and a calculator-ID floating demo.

The minimum-width demo deliberately requests 16 pixels more than the available
half-width slot. Test it next to another window. The compositor should keep both
slots stable and prevent paint/input spill into the gap. **Check cropped controls:
this patch clips a client that refuses to render smaller; it does not make that
application reflow.** Actual Discord behavior is the important next validation.

The calculator-ID demo should start floating and centered. **Super+G** should
tile it despite its default rule, and toggle it back to floating.

## Separate profiles, not a second copy of your normal login

Discord/OpenCode start with **separate test app profiles**. You may need to log in
again; normal app profiles/API-key environment variables are not copied. Your
test logins/settings persist under `~/.local/share/scrollwork-test/profile` so you
do not have to redo them on every test launch. Those files can contain test login
credentials; treat this directory like other application profile data.

This is not a filesystem security sandbox: the test apps still run as your user
and can access files you explicitly open. Do not expect normal-session audio,
hardware settings, locking, portals or suspend to work in this isolated session.
The test has its own D-Bus/PipeWire/runtime directory and no host system-bus
connection. It is a **layout/input/application-compatibility test**, not a test of
the full GNOME login session. Rendering is software-based, so do not judge final
GPU performance from it.

If layout shortcuts affect Hyprland instead, focus the rendered GNOME desktop
and check the viewer menu's **Inhibit system shortcuts** option.

## Exit and recovery

**Close the outer Mutter Development Kit window.** Hyprland remains running.
The launcher's private process namespace cleans up the test session and its apps.
If the viewer hangs, run from a normal host terminal:

```sh
python ~/dev/projects/scrollwork/scripts/try.py --stop
```

Health check:

```sh
python ~/dev/projects/scrollwork/scripts/try.py --doctor
```

Logs: `~/.local/share/scrollwork-test/profile/state/session.log`.
Only one test session can run at a time. Don't launch more virtual monitors from
the viewer; the extension is intentionally single-monitor.
