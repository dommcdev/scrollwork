#!/usr/bin/env python3
"""Real headless GNOME + real GTK clients; never install in the user's session."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
UUID = "scrollwork@local"


def prepare(root):
    for name in ["home", "config", "cache", "data", "state", "runtime"]:
        (root / name).mkdir(mode=0o700)
    extensions = root / "data/gnome-shell/extensions"
    target = extensions / UUID
    target.mkdir(parents=True)
    for name in [
        "extension.js",
        "layout.js",
        "settings.js",
        "rules.js",
        "appearance.js",
        "edges.js",
        "animation.js",
        "keybindings.js",
        "metadata.json",
    ]:
        shutil.copy(REPO / name, target / name)
    shutil.copytree(REPO / "schemas", target / "schemas")
    subprocess.run(
        ["glib-compile-schemas", "--strict", str(target / "schemas")], check=True
    )
    bridge = extensions / "scrollwork-test@local"
    bridge.mkdir()
    (bridge / "metadata.json").write_text(
        json.dumps(
            {
                "uuid": bridge.name,
                "name": "Private test bridge",
                "description": "Only installed in an isolated test session",
                "shell-version": ["51"],
            }
        )
    )
    (bridge / "extension.js").write_text("""
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
export default class Bridge extends Extension {
    enable() { global.context.unsafe_mode = true; global.scrollworkTestMain = Main; }
    disable() { global.context.unsafe_mode = false; delete global.scrollworkTestMain; }
}
""")


def launch():
    results = REPO / "test-results"
    results.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="scrollwork-", dir="/tmp/opencode"))
    prepare(root)
    env = os.environ.copy()
    for key in [
        "DBUS_SESSION_BUS_ADDRESS",
        "DBUS_STARTER_ADDRESS",
        "DBUS_STARTER_BUS_TYPE",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "GNOME_SHELL_SESSION_MODE",
    ]:
        env.pop(key, None)
    env.update(
        {
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_RUNTIME_DIR": str(root / "runtime"),
            "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
            "XDG_CONFIG_DIRS": "/etc/xdg",
            "XDG_CURRENT_DESKTOP": "GNOME",
            "XDG_SESSION_TYPE": "wayland",
            "GSETTINGS_BACKEND": "keyfile",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "NO_AT_BRIDGE": "1",
            "GTK_A11Y": "none",
        }
    )
    print(f"Isolated session: {root}", flush=True)
    prefix = os.environ.get("SCROLLWORK_MUTTER_PREFIX")
    if prefix:
        print(f"Testing staged Mutter: {prefix}", flush=True)
    try:
        result = subprocess.run(
            ["dbus-run-session", "--", sys.executable, __file__, "--inside", str(root)],
            env=env,
            timeout=180,
        )
        return result.returncode
    finally:
        for name in [
            "shell.log",
            "results.json",
            "screenshot.png",
            "electron.log",
            "electron-pair.png",
            "edge-hint.png",
        ]:
            if (root / name).exists():
                shutil.copy(root / name, results / name)
            else:
                (results / name).unlink(missing_ok=True)
        # Keep the small sandbox and logs for diagnosing failures. No live settings changed.


def inside(root):
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib

    baseline = []
    for schema, key in [
        ("org.gnome.mutter", "dynamic-workspaces"),
        ("org.gnome.desktop.wm.preferences", "num-workspaces"),
        ("org.gnome.desktop.wm.keybindings", "minimize"),
        ("org.gnome.settings-daemon.plugins.media-keys", "screensaver"),
        ("org.gnome.shell.keybindings", "switch-to-application-1"),
        ("org.gnome.desktop.wm.preferences", "focus-mode"),
        ("org.gnome.mutter", "attach-modal-dialogs"),
        ("org.gnome.mutter", "center-new-windows"),
        ("org.gnome.mutter", "overlay-key"),
        ("org.gnome.desktop.wm.preferences", "mouse-button-modifier"),
        ("org.gnome.desktop.wm.preferences", "resize-with-right-button"),
        ("org.gnome.desktop.wm.keybindings", "switch-applications"),
        ("org.gnome.desktop.wm.keybindings", "switch-input-source"),
        ("org.gnome.shell.keybindings", "screenshot"),
        ("org.gnome.shell.keybindings", "show-screenshot-ui"),
        ("org.gnome.shell.keybindings", "focus-active-notification"),
    ]:
        settings = Gio.Settings.new(schema)
        baseline.append(
            (settings, key, settings.get_value(key), settings.get_user_value(key))
        )

    # Even system-bus activation is confined to the private test bus.
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    subprocess.run(
        [
            "gsettings",
            "set",
            "org.gnome.shell",
            "enabled-extensions",
            "['scrollwork-test@local', 'scrollwork@local']",
        ],
        check=True,
    )
    # New virtual pointers start at (0, 0); do not trigger the overview hot corner.
    subprocess.run(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.interface",
            "enable-hot-corners",
            "false",
        ],
        check=True,
    )
    subprocess.run(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.interface",
            "enable-animations",
            "false",
        ],
        check=True,
    )
    log = (root / "shell.log").open("w")
    shell = subprocess.Popen(
        [
            "gnome-shell",
            "--headless",
            "--no-x11",
            "--virtual-monitor=1280x800",
            "--wayland-display=scrollwork-test",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    os.environ["WAYLAND_DISPLAY"] = "scrollwork-test"
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    context = GLib.MainContext.default()
    checks = []
    windows = []
    slow_client = None
    electron_client = None
    applications = []
    clicks = []
    pointer_events = []
    skipped = []

    def pump():
        while context.pending():
            context.iteration(False)

    def evaluate(code):
        result = bus.call_sync(
            "org.gnome.Shell",
            "/org/gnome/Shell",
            "org.gnome.Shell",
            "Eval",
            GLib.Variant("(s)", (code,)),
            GLib.VariantType.new("(bs)"),
            Gio.DBusCallFlags.NONE,
            3000,
            None,
        )
        ok, value = result.unpack()
        if not ok:
            raise RuntimeError(f"Eval failed: {value}\n{code}")
        return json.loads(value) if value else None

    def wait(description, predicate, timeout=10, stable_for=0):
        start = time.monotonic()
        last = None
        true_since = None
        while time.monotonic() - start < timeout:
            if shell.poll() is not None:
                raise RuntimeError(
                    f"GNOME exited ({shell.returncode}); see {root / 'shell.log'}"
                )
            pump()
            try:
                last = predicate()
                if last:
                    if true_since is None:
                        true_since = time.monotonic()
                    if time.monotonic() - true_since >= stable_for:
                        return last
                else:
                    true_since = None
            except (GLib.Error, RuntimeError) as error:
                last = str(error)
                true_since = None
            time.sleep(0.02)
        raise AssertionError(f"Timeout: {description}; last result: {last}")

    def check(description, predicate):
        wait(description, predicate, stable_for=0.25)
        checks.append(description)
        print(f"PASS {description}", flush=True)

    def shortcut(key, shift=False, control=False, super_key=True):
        # Give Mutter a main-loop turn between events, like a physical keyboard.
        # Enqueuing the complete chord at once can also fire the Super overlay key.
        modifiers = ["Super_L"] if super_key else []
        if shift:
            modifiers.append("Shift_L")
        if control:
            modifiers.append("Control_L")
        sequence = (
            [(name, True) for name in modifiers]
            + [(key, True), (key, False)]
            + [(name, False) for name in reversed(modifiers)]
        )
        for name, pressed in sequence:
            evaluate(f"""(()=>{{const {{C,keyboard}}=global.scrollworkTestInput;
                keyboard.notify_keyval(0,C.KEY_{name},C.KeyState.{"PRESSED" if pressed else "RELEASED"});
                return true;}})()""")
            wait("dispatch virtual key event", lambda: True, stable_for=0.06)

    ext = (
        "global.scrollworkTestMain.extensionManager.lookup('scrollwork@local').stateObj"
    )
    find = lambda title: (
        f"global.get_window_actors().map(a=>a.meta_window).find(w=>w.title==={json.dumps(title)})"
    )

    def state():
        return evaluate(f"""(() => {{ const e={ext}; return {{
            suspended:e.suspended, externalTiledAPI:e.tiledStateSupported, focus:global.display.focus_window?.title,
            strips:[...e.strips.values()].map(s=>({{focus:s.focused?.title,columns:s.columns.map(c=>c.id.title)}})),
            targets:[...e.targets].map(([w,r])=>({{
                title:w.title, target:r, actual:(()=>{{ const a=w.get_frame_rect();
                    return {{x:a.x,y:a.y,width:a.width,height:a.height}}; }})(),
                calls:e.windows.get(w).constraint.calls,
                retries:e.windows.get(w).retries, repairSource:e.windows.get(w).repairSource,
                maximized:w.is_maximized(),fullscreen:w.is_fullscreen(),
            }})), watched:e.windows.size,
            clients:[...e.windows].map(([w,r])=>({{title:w.title,wmClass:w.get_wm_class(),
                gtkAppId:w.get_gtk_application_id(),floating:r.floating}})),
            edges:e.edges ? Object.fromEntries(Object.entries(e.edges.buttons).map(([side,b])=>[side,{{
                visible:b.visible,mapped:b.mapped,x:b.x,y:b.y,width:b.width,height:b.height,
                line:b.get_child() ? {{x:b.get_child().x,y:b.get_child().y,width:b.get_child().width,
                    height:b.get_child().height,mapped:b.get_child().mapped}} : null}}])) : null,
            errors:global.scrollworkTestMain.extensionManager.lookup('scrollwork@local').errors,
        }}; }})()""")

    def settled(title=None):
        items = state()["targets"]
        if title:
            items = [i for i in items if i["title"] == title]
        return bool(items) and all(i["actual"] == i["target"] for i in items)

    def screenshot(path):
        evaluate(f"""(async()=>{{ await import('resource:///org/gnome/shell/ui/screenshot.js');
            const Shell=(await import('gi://Shell')).default;
            const Gio=(await import('gi://Gio')).default;
            const stream=Gio.File.new_for_path({json.dumps(str(path))}).replace(null,false,Gio.FileCreateFlags.NONE,null);
            await new Shell.Screenshot().screenshot(false,stream);stream.close(null);return true;}})()""")

    def create(title, parent=None, minimum=None, app_id=None, wayland_id=None):
        if app_id:
            app = Gtk.Application(
                application_id=app_id, flags=Gio.ApplicationFlags.NON_UNIQUE
            )
            app.register(None)
            applications.append(app)
            window = Gtk.ApplicationWindow(
                application=app, title=title, default_width=320, default_height=240
            )
        else:
            window = Gtk.Window(title=title, default_width=320, default_height=240)
        if parent:
            window.set_transient_for(parent)
            window.set_modal(True)
        label = Gtk.Button(label=title)
        label.connect("clicked", lambda _button: clicks.append(title))
        gesture = Gtk.GestureClick()
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect(
            "pressed",
            lambda _g, _n, x, y: pointer_events.append((title, "press", x, y)),
        )
        gesture.connect(
            "released",
            lambda _g, _n, x, y: pointer_events.append((title, "release", x, y)),
        )
        window.add_controller(gesture)
        if minimum:
            label.set_size_request(*minimum)
        window.set_child(label)
        windows.append(window)
        window.present()
        if wayland_id:
            gi.require_version("GdkWayland", "4.0")
            from gi.repository import GdkWayland

            GdkWayland.WaylandToplevel.set_application_id(
                window.get_surface(), wayland_id
            )
        return window

    try:
        wait(
            "private GNOME test bridge",
            lambda: evaluate("!!global.scrollworkTestMain"),
            35,
        )
        check(
            "extension enables without errors",
            lambda: evaluate(
                "global.scrollworkTestMain.extensionManager.lookup('scrollwork@local').state === 1"
            ),
        )
        from gi.repository import Gtk

        Gtk.init()
        wait(
            "GNOME startup complete",
            lambda: evaluate("!global.scrollworkTestMain.layoutManager._startingUp"),
        )
        evaluate("global.scrollworkTestMain.overview.hide(); true")
        evaluate("""(async()=>{ const C=(await import('gi://Clutter')).default;
            const seat=global.stage.context.get_backend().get_default_seat();
            global.scrollworkTestInput={C,
                keyboard:seat.create_virtual_device(C.InputDeviceType.KEYBOARD_DEVICE),
                pointer:seat.create_virtual_device(C.InputDeviceType.POINTER_DEVICE)};
            global.scrollworkTestEvents=[];
            global.stage.connect('captured-event',(_s,e)=>{
                if(e.type()===C.EventType.BUTTON_PRESS || e.type()===C.EventType.BUTTON_RELEASE)
                    global.scrollworkTestEvents.push([e.type(),e.get_button(),e.get_coords()]);
                return C.EVENT_PROPAGATE;
            });
            return true; })()""")
        a = create("SW-A")
        check(
            "real GTK window receives exact assigned geometry", lambda: settled("SW-A")
        )
        check(
            "constraint vfunc runs inside Mutter",
            lambda: state()["targets"][0]["calls"] > 0,
        )
        width_a = state()["targets"][0]["target"]["width"]
        b = create("SW-B")
        check(
            "second window restores half-width columns from the lone full-width column",
            lambda: (
                settled()
                and next(i for i in state()["targets"] if i["title"] == "SW-A")[
                    "target"
                ]["width"]
                == (width_a - 8) // 2
            ),
        )
        pair = {item["title"]: item["actual"] for item in state()["targets"]}
        for index in range(40):
            title = "SW-A" if index % 2 == 0 else "SW-B"
            evaluate(f"{find(title)}.activate(global.get_current_time()); true")
            wait(
                "alternate focus in half-width pair",
                lambda: (
                    evaluate("global.display.focus_window?.title") == title
                    and settled()
                ),
            )
            assert {
                item["title"]: item["actual"] for item in state()["targets"]
            } == pair
        check(
            "forty focus switches between two half-width windows produce zero geometry drift",
            settled,
        )

        calculator = create("SW-calculator", app_id="com.dominic.calc")
        check(
            "Hyprland calculator app ID floats by default without a constraint",
            lambda: evaluate(
                f"{ext}.windows.get({find('SW-calculator')})?.floating && !{ext}.windows.get({find('SW-calculator')})?.attached"
            ),
        )
        check(
            "default floating calculator receives its initial centered size",
            lambda: evaluate(f"""(()=>{{
            const r={find("SW-calculator")}.get_frame_rect();
            return r.x===448 && r.y===224 && r.width===384 && r.height===384;}})()"""),
        )
        evaluate(f"{find('SW-calculator')}.activate(global.get_current_time()); true")
        wait(
            "focus floating calculator",
            lambda: evaluate("global.display.focus_window?.title") == "SW-calculator",
        )
        shortcut("g")
        check(
            "Super+G can tile an app that defaults to floating",
            lambda: settled("SW-calculator"),
        )
        shortcut("g")
        check(
            "Super+G returns the same app to floating",
            lambda: evaluate(
                f"{ext}.windows.get({find('SW-calculator')})?.floating && !{ext}.targets.has({find('SW-calculator')})"
            ),
        )
        calculator.destroy()
        wait(
            "calculator closes",
            lambda: (
                len(state()["targets"]) == 2 and state()["watched"] == 2 and settled()
            ),
        )

        launcher = create("SW-launcher", wayland_id="vicinae")
        check(
            "Vicinae app ID floats and centers instead of joining the strip",
            lambda: (
                evaluate(f"""(()=>{{const w={find("SW-launcher")};if(!w)return false;
                const r=w.get_frame_rect();return {ext}.windows.get(w)?.floating && !{ext}.targets.has(w) &&
                    Math.abs(r.x+r.width/2-640)<=1 && Math.abs(r.y+r.height/2-416)<=1;}})()""")
            ),
        )
        launcher.destroy()
        wait("launcher fixture closes", lambda: state()["watched"] == 2)

        ruled = create("SW-rule")
        wait("rule test window maps", lambda: settled("SW-rule"))
        custom = [
            {
                "initialTitle": "^SW-rule$",
                "mode": "float",
                "center": True,
                "size": [0.4, 0.4],
            }
        ]
        evaluate(
            f"{ext}.settings.set_string('window-rules',{json.dumps(json.dumps(custom))}); true"
        )
        check(
            "hot-reloaded title rule floats an existing ordinary window",
            lambda: evaluate(
                f"{ext}.windows.get({find('SW-rule')})?.floating && !{ext}.targets.has({find('SW-rule')})"
            ),
        )
        ruled.set_title("SW-rule-renamed")
        check(
            "initial-title rules survive later document/title changes",
            lambda: evaluate(f"{ext}.windows.get({find('SW-rule-renamed')})?.floating"),
        )
        evaluate(
            f"{find('SW-rule-renamed')}.move_resize_frame(false,100,100,400,300); true"
        )
        check(
            "floating placement is initial-only and does not fight later user resizing",
            lambda: evaluate(
                f"{find('SW-rule-renamed')}.get_frame_rect().width===400 && {find('SW-rule-renamed')}.get_frame_rect().x===100"
            ),
        )
        custom.append({"initialTitle": "^SW-rule$", "mode": "tile"})
        evaluate(
            f"{ext}.settings.set_string('window-rules',{json.dumps(json.dumps(custom))}); true"
        )
        check(
            "last matching tile rule overrides a default floating rule",
            lambda: settled("SW-rule-renamed"),
        )
        evaluate(f"{ext}.settings.set_string('window-rules','{{'); true")
        check(
            "invalid rules keep the last valid rules without disabling the extension",
            lambda: evaluate(f"!!{ext}.ruleError") and settled("SW-rule-renamed"),
        )
        evaluate(f"{ext}.settings.reset('window-rules'); true")
        ruled.destroy()
        wait(
            "rule test window closes",
            lambda: (
                len(state()["targets"]) == 2 and state()["watched"] == 2 and settled()
            ),
        )

        strict_clients = (
            state()["externalTiledAPI"]
            or os.environ.get("SCROLLWORK_STRICT_CLIENTS") == "1"
        )
        if shutil.which("electron"):
            evaluate(f"{find('SW-B')}.minimize(); true")
            wait(
                "hide B for the Electron pair test",
                lambda: len(state()["targets"]) == 1,
            )
            electron_log = (root / "electron.log").open("w")
            electron_client = subprocess.Popen(
                [
                    "electron",
                    "--ozone-platform=wayland",
                    "--disable-gpu",
                    str(REPO / "tests/electron-client.cjs"),
                ],
                stdout=electron_log,
                stderr=subprocess.STDOUT,
                env=dict(
                    os.environ,
                    **(
                        {}
                        if strict_clients
                        else {"SCROLLWORK_ELECTRON_MIN_WIDTH": "400"}
                    ),
                ),
            )
            check(
                (
                    "Electron minimum-width client remains tiled at the exact half-width slot"
                    if strict_clients
                    else "ordinary Electron client tiles and renders with stock Mutter"
                ),
                lambda: settled("SW-electron"),
            )
            electron_pair = {
                item["title"]: item["actual"] for item in state()["targets"]
            }
            for index in range(40):
                title = "SW-A" if index % 2 == 0 else "SW-electron"
                evaluate(f"{find(title)}.activate(global.get_current_time()); true")
                wait(
                    "alternate Electron/GTK focus",
                    lambda: (
                        evaluate("global.display.focus_window?.title") == title
                        and settled()
                    ),
                )
                assert {
                    item["title"]: item["actual"] for item in state()["targets"]
                } == electron_pair
            check(
                (
                    "Electron with a larger minimum width does not move either window on focus"
                    if strict_clients
                    else "ordinary Electron/GTK focus changes do not cause geometry drift"
                ),
                settled,
            )
            if strict_clients:
                check(
                    "Electron surface cannot receive input outside its slot",
                    lambda: evaluate(f"""(()=>{{
                const w={find("SW-electron")},r=w.get_frame_rect();
                const C=global.scrollworkTestInput.C;
                let a=global.stage.get_actor_at_pos(C.PickMode.REACTIVE,r.x+r.width+4,r.y+r.height/2);
                while(a){{if(a.meta_window===w)return false;a=a.get_parent();}}return true;}})()"""),
                )
            screenshot(root / "electron-pair.png")
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf

            image = GdkPixbuf.Pixbuf.new_from_file(str(root / "electron-pair.png"))
            pixels = image.get_pixels()
            offset = 400 * image.get_rowstride() + 1276 * image.get_n_channels()
            red, green, blue = pixels[offset : offset + 3]
            assert not (red > 200 and green < 60 and blue < 60), (
                "Electron painted red beyond its assigned slot"
            )
            checks.append("Electron surface does not paint into the outer gap")
            electron_client.terminate()
            electron_client.wait(timeout=5)
            electron_log.close()
            evaluate(f"{find('SW-B')}.unminimize(); true")
            wait(
                "restore original pair",
                lambda: (
                    len(state()["targets"]) == 2
                    and state()["watched"] == 2
                    and settled()
                ),
            )
            evaluate(f"{find('SW-B')}.activate(global.get_current_time()); true")
            wait(
                "focus restored B",
                lambda: evaluate("global.display.focus_window?.title") == "SW-B",
            )
            if not strict_clients:
                skipped.append(
                    "KNOWN LIMITATION: strict oversized Electron geometry still requires the optional patch"
                )
        elif strict_clients:
            raise RuntimeError("Strict minimum-width regression requires electron")
        else:
            skipped.append(
                "KNOWN LIMITATION: stock Mutter fails the strict Electron minimum-width regression; run npm run test:strict to reproduce"
            )
        c = create("SW-C")
        check(
            "third window scrolls while all real geometries remain authoritative",
            lambda: len(state()["targets"]) == 3 and settled(),
        )
        check(
            "focused column is fully inside the work area",
            lambda: evaluate(f"""(() => {{
            const w={find("SW-C")}, r=w.get_frame_rect();
            return r.x>=0 && r.x+r.width<=1280;
        }})()"""),
        )

        def edge_pointer(x):
            evaluate(
                f"""(()=>{{global.scrollworkTestInput.pointer.notify_absolute_motion(0,{x},400);return true;}})()"""
            )

        def edge_click():
            for state_name in ["PRESSED", "RELEASED"]:
                evaluate(f"""(()=>{{const {{C,pointer}}=global.scrollworkTestInput;
                    pointer.notify_button(0,1,C.ButtonState.{state_name});return true;}})()""")
                wait("edge button dispatch", lambda: True, stable_for=0.08)

        evaluate(f"{find('SW-C')}.activate(global.get_current_time());true")
        wait(
            "keyboard/new-window pointer warp completes before edge test",
            lambda: evaluate(
                f"!{ext}.warpSource && global.display.focus_window?.title==='SW-C'"
            ),
            stable_for=0.25,
        )
        edge_pointer(1)
        check(
            "left edge reveals a hint for the nearest hidden column without focusing it",
            lambda: evaluate(
                f"{ext}.edges.buttons.left.visible && {ext}.edges.targets.left?.title==='SW-A' && global.display.focus_window?.title==='SW-C'"
            ),
        )
        screenshot(root / "edge-hint.png")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        edge_image = GdkPixbuf.Pixbuf.new_from_file(str(root / "edge-hint.png"))
        edge_pixels = edge_image.get_pixels()

        def edge_pixel(x):
            offset = 400 * edge_image.get_rowstride() + x * edge_image.get_n_channels()
            return tuple(edge_pixels[offset : offset + 3])

        check(
            "edge hint paints only a two-pixel line, not the wider click target",
            lambda: (
                all(abs(a - b) < 8 for a, b in zip(edge_pixel(0), (203, 166, 247)))
                and any(abs(a - b) > 20 for a, b in zip(edge_pixel(4), (203, 166, 247)))
            ),
        )
        edge_click()
        check(
            "real click on the left edge hint scrolls the hidden window into view",
            lambda: (
                settled() and evaluate("global.display.focus_window?.title==='SW-A'")
            ),
        )
        check(
            "left edge click leaves the cursor exactly at the screen edge",
            lambda: evaluate(
                f"!{ext}.warpSource && global.get_pointer()[0]===1 && global.get_pointer()[1]===400"
            ),
        )
        wait("left edge click warp completes", lambda: evaluate(f"!{ext}.warpSource"))
        edge_pointer(1279)
        check(
            "right edge reveals the nearest hidden column without hover scrolling",
            lambda: evaluate(
                f"{ext}.edges.buttons.right.visible && {ext}.edges.targets.right?.title==='SW-C' && global.display.focus_window?.title==='SW-A'"
            ),
        )
        edge_click()
        check(
            "real click on the right edge hint scrolls back to that window",
            lambda: (
                settled() and evaluate("global.display.focus_window?.title==='SW-C'")
            ),
        )
        check(
            "right edge click leaves the cursor exactly at the screen edge",
            lambda: evaluate(
                f"!{ext}.warpSource && global.get_pointer()[0]===1279 && global.get_pointer()[1]===400"
            ),
        )
        wait("right edge click warp completes", lambda: evaluate(f"!{ext}.warpSource"))
        edge_pointer(950)
        check(
            "edge hints disappear away from the screen edges",
            lambda: evaluate(
                f"!{ext}.edges.buttons.left.visible && !{ext}.edges.buttons.right.visible"
            ),
        )
        shortcut("h")
        check(
            "real Super+h keyboard binding focuses the previous column",
            lambda: evaluate("global.display.focus_window?.title") == "SW-B",
        )
        shortcut("l")
        check(
            "real Super+l keyboard binding focuses the next column",
            lambda: (
                evaluate("global.display.focus_window?.title") == "SW-C" and settled()
            ),
        )
        check(
            "window-management shortcuts do not open the GNOME overview",
            lambda: evaluate("!global.scrollworkTestMain.overview.visible"),
        )
        shortcut("Super_L", super_key=False)
        check(
            "Super alone no longer opens the GNOME overview",
            lambda: evaluate(
                "!global.scrollworkTestMain.overview.visible && new (imports.gi.Gio.Settings)({schema_id:'org.gnome.mutter'}).get_string('overlay-key')===''"
            ),
        )
        evaluate(
            f"global.scrollworkOriginalLaunch={ext}._launchCommand;{ext}._launchCommand=argv=>{{global.scrollworkLastLaunch=argv;}};true"
        )
        shortcut("apostrophe", control=True, super_key=False)
        check(
            "real Ctrl+apostrophe binding dispatches Vicinae toggle",
            lambda: evaluate(
                'JSON.stringify(global.scrollworkLastLaunch)===\'["vicinae","toggle"]\''
            ),
        )
        shortcut("Return")
        check(
            "real Super+Return binding dispatches a new Ghostty window",
            lambda: evaluate(
                'JSON.stringify(global.scrollworkLastLaunch)===\'["ghostty","+new-window"]\''
            ),
        )
        check(
            "native screenshot, lock and Hex shortcut conflicts are configured",
            lambda: evaluate("""(()=>{const S=imports.gi.Gio.Settings;
                const shell=new S({schema_id:'org.gnome.shell.keybindings'});
                const media=new S({schema_id:'org.gnome.settings-daemon.plugins.media-keys'});
                const wm=new S({schema_id:'org.gnome.desktop.wm.keybindings'});
                return shell.get_strv('screenshot').includes('<Super>s') &&
                    media.get_strv('screensaver').includes('<Super>q') &&
                    !wm.get_strv('switch-input-source').some(k=>k.toLowerCase()==='<super>space') &&
                    wm.get_strv('switch-applications').includes('<Alt>Tab');})()"""),
        )
        evaluate(
            f"{ext}._launchCommand=global.scrollworkOriginalLaunch;delete global.scrollworkOriginalLaunch;delete global.scrollworkLastLaunch;true"
        )
        check(
            "keyboard focus warps the pointer into the settled window",
            lambda: evaluate(f"""(()=>{{
            const r={find("SW-C")}.get_frame_rect(), [x,y]=global.get_pointer();
            return !{ext}.warpSource && x>=r.x && x<r.x+r.width && y>=r.y && y<r.y+r.height;
        }})()"""),
        )
        evaluate(f"""(()=>{{const r={find("SW-B")}.get_frame_rect();
            global.scrollworkTestInput.pointer.notify_absolute_motion(0,r.x+r.width/2,r.y+r.height/2);return true;}})()""")
        check(
            "pointer movement focuses a tiled window without clicking",
            lambda: evaluate("global.display.focus_window?.title") == "SW-B",
        )
        evaluate(f"""(()=>{{const r={find("SW-C")}.get_frame_rect();
            global.scrollworkTestInput.pointer.notify_absolute_motion(0,r.x+r.width/2,r.y+r.height/2);return true;}})()""")
        check(
            "hover focus follows the pointer back without a keyboard warp",
            lambda: evaluate("global.display.focus_window?.title") == "SW-C",
        )
        evaluate(f"""(()=>{{global.scrollworkPointerBefore=global.get_pointer().slice(0,2);
            {find("SW-B")}.activate(global.get_current_time());return true;}})()""")
        check(
            "non-keyboard application focus changes never warp the pointer",
            lambda: evaluate(
                f"!{ext}.warpSource && JSON.stringify(global.get_pointer().slice(0,2))===JSON.stringify(global.scrollworkPointerBefore)"
            ),
        )
        evaluate(f"{find('SW-C')}.activate(global.get_current_time());true")
        check(
            "window effects attach to the real actors",
            lambda: evaluate(f"""(()=>{{
            return ['SW-B','SW-C'].every(t=>{{const w=global.get_window_actors().find(a=>a.meta_window.title===t);
                return !!w.get_effect('scrollwork-appearance');}});
        }})()"""),
        )
        evaluate(f"""(()=>{{const {{C,pointer}}=global.scrollworkTestInput;
            const r={find("SW-C")}.get_frame_rect();
            global.stage.context.get_backend().get_default_seat().warp_pointer(r.x+r.width/2,r.y+r.height/2);
            return true;}})()""")
        wait(
            "pointer enters client",
            lambda: evaluate(f"""(()=>{{const r={find("SW-C")}.get_frame_rect();
            const [x,y]=global.get_pointer();return Math.abs(x-r.x-r.width/2)<2 && Math.abs(y-r.y-r.height/2)<2;}})()"""),
            stable_for=0.15,
        )
        evaluate(f"""(()=>{{const {{pointer}}=global.scrollworkTestInput;
            const r={find("SW-C")}.get_frame_rect();
            pointer.notify_absolute_motion(0,r.x+r.width/2,r.y+r.height/2);return true;}})()""")
        wait("pointer motion reaches the Wayland client", lambda: True, stable_for=0.15)
        check(
            "pointer hover reaches the real GTK widget after scrolling",
            lambda: bool(c.get_child().get_state_flags() & Gtk.StateFlags.PRELIGHT),
        )
        evaluate("""(()=>{const {C,pointer}=global.scrollworkTestInput;
            pointer.notify_button(0,1,C.ButtonState.PRESSED);return true;})()""")
        wait(
            "GTK receives a real pointer press",
            lambda: bool(c.get_child().get_state_flags() & Gtk.StateFlags.ACTIVE),
        )
        evaluate("""(()=>{const {C,pointer}=global.scrollworkTestInput;
            pointer.notify_button(0,1,C.ButtonState.RELEASED);return true;})()""")
        check(
            "pointer click activates the correct real GTK button after scrolling",
            lambda: "SW-C" in clicks,
        )
        evaluate(f"{find('SW-A')}.move_resize_frame(false, 100, 100, 222, 222); true")
        check(
            "compositor rejects an out-of-policy move/resize", lambda: settled("SW-A")
        )
        a.set_default_size(100, 100)
        check(
            "application resize cannot take geometry ownership", lambda: settled("SW-A")
        )
        evaluate(f"{ext}.focus(-1); true")
        check(
            "focus-left activates the previous column",
            lambda: evaluate("global.display.focus_window?.title") == "SW-B",
        )
        check("focus change scrolls geometry into place", settled)
        previous = next(
            i["target"]["width"] for i in state()["targets"] if i["title"] == "SW-B"
        )
        evaluate(f"{ext}.cycleWidth(); true")
        check(
            "width cycling updates actual client geometry",
            lambda: (
                settled("SW-B")
                and next(
                    i["target"]["width"]
                    for i in state()["targets"]
                    if i["title"] == "SW-B"
                )
                > previous
            ),
        )
        evaluate(f"{ext}.move(-1); true")
        check(
            "column reordering reaches real windows",
            lambda: (
                settled()
                and evaluate(f"{ext}._activeStrip().columns.map(c=>c.id.title)")
                == ["SW-B", "SW-A", "SW-C"]
            ),
        )
        dialog = create("SW-dialog", b)
        check(
            "transient dialog is not tiled or constrained",
            lambda: evaluate(
                f"!!{find('SW-dialog')} && !{ext}.targets.has({find('SW-dialog')}) && !{ext}.windows.get({find('SW-dialog')})?.attached"
            ),
        )
        check(
            "transient dialog is centered on the monitor, not on its parent column",
            lambda: (
                evaluate(f"""(()=>{{const w={find("SW-dialog")},r=w.get_frame_rect();
                const a=w.get_workspace().get_work_area_for_monitor(0);
                return Math.abs(r.x+r.width/2-a.x-a.width/2)<=1 && Math.abs(r.y+r.height/2-a.y-a.height/2)<=1;
            }})()""")
            ),
        )
        chooser = Gtk.FileChooserDialog(
            title="SW-file-chooser",
            transient_for=b,
            action=Gtk.FileChooserAction.OPEN,
            modal=True,
        )
        windows.append(chooser)
        chooser.present()
        check(
            "real GTK file chooser floats and centers independently of its parent",
            lambda: (
                evaluate(f"""(()=>{{const w={find("SW-file-chooser")};if(!w)return false;
                const r=w.get_frame_rect(), a=w.get_workspace().get_work_area_for_monitor(0);
                return !{ext}.targets.has(w) && {ext}.windows.get(w)?.floating &&
                    Math.abs(r.x+r.width/2-a.x-a.width/2)<=1 && Math.abs(r.y+r.height/2-a.y-a.height/2)<=1;
            }})()""")
            ),
        )
        chooser.destroy()
        dialog.destroy()
        shortcut("d", shift=True)
        check(
            "real Super+Shift+D binding enters fullscreen",
            lambda: evaluate(f"{find('SW-B')}.is_fullscreen()"),
        )
        shortcut("d", shift=True)
        check(
            "real Super+Shift+D binding restores tiling",
            lambda: evaluate(f"!{find('SW-B')}.is_fullscreen()") and settled("SW-B"),
        )
        b.fullscreen()
        check(
            "native fullscreen is an unconstrained escape hatch",
            lambda: evaluate(
                f"{find('SW-B')}.is_fullscreen() && {find('SW-B')}.get_frame_rect().width === 1280"
            ),
        )
        b.unfullscreen()
        check("leaving fullscreen restores column geometry", lambda: settled("SW-B"))
        b.maximize()
        check(
            "application maximize is suppressed like the Hyprland rule",
            lambda: evaluate(f"!{find('SW-B')}.is_maximized()") and settled("SW-B"),
        )
        evaluate(f"{ext}.settings.set_boolean('suppress-maximize',false); true")
        b.maximize()
        check(
            "native maximize is allowed",
            lambda: evaluate(f"{find('SW-B')}.is_maximized()"),
        )
        b.unmaximize()
        check("unmaximize restores column geometry", lambda: settled("SW-B"))
        evaluate(f"{ext}.settings.reset('suppress-maximize'); true")
        evaluate(f"{find('SW-B')}.minimize(); true")
        check(
            "minimized window releases its constraint",
            lambda: evaluate(
                f"!{ext}.targets.has({find('SW-B')}) && !{ext}.windows.get({find('SW-B')}).attached"
            ),
        )
        evaluate(f"{find('SW-B')}.unminimize(); true")
        check("unminimized window is managed again", lambda: settled("SW-B"))
        evaluate(f"{find('SW-B')}.activate(global.get_current_time()); true")
        evaluate(f"{ext}.toggleFloating(); true")
        check(
            "manual floating removes the geometry constraint",
            lambda: evaluate(
                f"{ext}.windows.get({find('SW-B')}).floating && !{ext}.targets.has({find('SW-B')})"
            ),
        )
        evaluate(f"{ext}.toggleFloating(); true")
        check("manual retiling reacquires geometry", lambda: settled("SW-B"))
        slow_client = subprocess.Popen(
            [sys.executable, str(REPO / "tests/slow-client.py")]
        )
        check("separate Wayland client maps into the strip", lambda: settled("SW-slow"))
        evaluate(f"{find('SW-slow')}.activate(global.get_current_time()); true")
        wait(
            "slow client gets focus",
            lambda: evaluate("global.display.focus_window?.title") == "SW-slow",
        )
        slow_client.send_signal(signal.SIGSTOP)
        evaluate(f"{ext}.cycleWidth(); true")
        check(
            "paused client does not block the compositor or lose its constraint immediately",
            lambda: evaluate(
                f"{ext}.windows.get({find('SW-slow')}).attached && !{ext}.windows.get({find('SW-slow')}).floating"
            ),
        )
        slow_client.send_signal(signal.SIGCONT)
        check(
            "resumed Wayland client completes the pending resize",
            lambda: settled("SW-slow"),
        )
        slow_client.terminate()
        slow_client.wait(timeout=5)
        check(
            "separate client exit releases its state",
            lambda: len(state()["targets"]) == 3 and settled(),
        )
        difficult = create("SW-minimum", minimum=(900, 300))
        if state()["externalTiledAPI"]:
            check(
                "patched compositor keeps a minimum-size GTK client in its fixed slot",
                lambda: settled("SW-minimum"),
            )
        else:
            check(
                "oversized minimum-size client falls back to floating, not a resize loop",
                lambda: evaluate(
                    f"!!{find('SW-minimum')} && {ext}.windows.get({find('SW-minimum')}).floating && !{ext}.windows.get({find('SW-minimum')}).attached"
                ),
            )
        difficult.destroy()
        check(
            "remaining layout settles after a nonconforming client closes",
            lambda: len(state()["targets"]) == 3 and settled(),
        )
        check(
            "ten numbered workspaces remain available",
            lambda: evaluate("global.workspace_manager.n_workspaces===10"),
        )
        interface_settings = Gio.Settings.new("org.gnome.desktop.interface")
        interface_settings.set_boolean("enable-animations", True)
        wait(
            "native animations enabled for the instant-workspace test",
            lambda: evaluate("global.scrollworkTestMain.wm._shouldAnimate()"),
        )
        evaluate(f"{find('SW-C')}.activate(global.get_current_time());true")
        check("layout settles before the movement-animation test", settled)
        animated = evaluate(f"""(()=>{{const e={ext},s=e._activeStrip();
            const w=s.columns[0].id;w.activate(global.get_current_time());s.focus(w);e._layout();
            global.scrollworkFadeWindow=w;
            return [...e.windows.keys()].some(w=>!!w.get_compositor_private()?.get_transition('translation-x'));
        }})()""")
        if not animated:
            raise AssertionError(
                "Scrolling with animations enabled did not create a movement transition"
            )
        wait(
            "focus opacity is interpolated rather than switching instantly",
            lambda: (
                evaluate(f"""(()=>{{const a={ext}.windows.get(global.scrollworkFadeWindow).appearance;
                return !!a.animationSource && a.visual.opacity>0.97001 && a.visual.opacity<0.99999;}})()""")
            ),
            stable_for=0,
        )
        check(
            "focus border/opacity fade finishes on the configured values",
            lambda: (
                evaluate(f"""(()=>{{const a={ext}.windows.get(global.scrollworkFadeWindow).appearance;
                return !a.animationSource && Math.abs(a.visual.opacity-1)<0.000001 &&
                    Math.abs(a.visual.color[0]-203/255)<0.000001;}})()""")
            ),
        )
        check(
            "short movement animation settles to real geometry without leftover transforms",
            lambda: (
                settled()
                and evaluate(f"""[...{ext}.windows.keys()].every(w=>{{const a=w.get_compositor_private();
                return !a.get_transition('translation-x') && Math.abs(a.translation_x)<0.01 && Math.abs(a.translation_y)<0.01;}})""")
            ),
        )
        shortcut("2")
        check(
            "Super+2 switches native workspaces without an animation group",
            lambda: evaluate(
                "global.workspace_manager.get_active_workspace_index()===1 && !global.scrollworkTestMain.wm._switchInProgress && !global.scrollworkTestMain.wm._workspaceAnimation._switchData"
            ),
        )
        shortcut("1")
        check(
            "Super+1 returns instantly while other GNOME animations remain enabled",
            lambda: evaluate(
                "global.workspace_manager.get_active_workspace_index()===0 && global.scrollworkTestMain.wm._shouldAnimate() && !global.scrollworkTestMain.wm._workspaceAnimation._switchData"
            ),
        )
        interface_settings.set_boolean("enable-animations", False)
        evaluate(f"{find('SW-C')}.activate(global.get_current_time()); true")
        wait(
            "focus C for workspace move",
            lambda: evaluate("global.display.focus_window?.title") == "SW-C",
        )
        shortcut("2", shift=True)
        check(
            "real Super+Shift+2 moves the window without following it",
            lambda: evaluate(
                f"{find('SW-C')}.get_workspace().index()===1 && global.workspace_manager.get_active_workspace_index()===0"
            ),
        )
        check(
            "native workspace migration updates strip membership",
            lambda: evaluate(f"{ext}.strips.size === 2") and settled(),
        )
        evaluate(f"global.scrollworkTestMain.overview.show(); true")
        check(
            "native GNOME overview still opens",
            lambda: evaluate("global.scrollworkTestMain.overview.visible"),
        )
        evaluate("global.scrollworkTestMain.overview.hide(); true")
        check("overview closes without losing geometry", settled)
        # Deliberately disable while an idle layout is queued.
        evaluate(f"""(async () => {{ global.scrollworkTestRecords=[...{ext}.windows.values()]; {ext}._queue();
            global.scrollworkTestMain.extensionManager.disableExtension('scrollwork@local');
            return true; }})()""")
        check(
            "disable removes constraints, sources, windows and targets",
            lambda: evaluate(
                f"{ext}.windows.size === 0 && {ext}.targets.size === 0 && {ext}.pending === 0 && !{ext}.pointerWatch && !{ext}.warpSource && !{ext}.edges && global.scrollworkTestRecords.every(r=>!r.attached && !r.repairSource && !r.placementSource && !r.appearance?.animationSource && r.constraint.owner===null)"
            ),
        )
        check(
            "disable removes visual effects and restores actor transforms",
            lambda: evaluate("""
            global.get_window_actors().every(a=>!a.get_effect('scrollwork-appearance') &&
                a.translation_x===0 && a.translation_y===0)
        """),
        )
        check(
            "disable brings offscreen windows back onto the desktop",
            lambda: evaluate(
                "global.get_window_actors().every(a=>a.meta_window.get_frame_rect().x>=0)"
            ),
        )
        check(
            "disable removes external tiled state and its rendering/input clips",
            lambda: evaluate("""
            global.get_window_actors().every(a=>!a.meta_window.is_external_tiled?.() && !a.has_clip)"""),
        )
        check(
            "disable restores native shortcuts and workspace settings including unset values",
            lambda: all(
                settings.get_value(key).equal(value)
                and ((settings.get_user_value(key) is None) == (user_value is None))
                for settings, key, value, user_value in baseline
            ),
        )
        evaluate(f"{find('SW-A')}.move_resize_frame(false, 100, 100, 400, 300); true")
        check(
            "window geometry is no longer constrained after disable",
            lambda: evaluate(f"{find('SW-A')}.get_frame_rect().width === 400"),
        )
        evaluate(
            "global.scrollworkTestMain.extensionManager.enableExtension('scrollwork@local')"
        )
        check(
            "re-enable adopts existing windows without GType conflicts",
            lambda: len(state()["targets"]) == 3 and settled(),
        )
        c.destroy()
        check(
            "closing a window removes all associated state",
            lambda: len(state()["targets"]) == 2 and state()["watched"] == 2,
        )
        for index in range(5):
            evaluate(
                "global.scrollworkTestMain.extensionManager.disableExtension('scrollwork@local')"
            )
            wait(f"disable cycle {index}", lambda: evaluate(f"{ext}.windows.size===0"))
            evaluate(
                "global.scrollworkTestMain.extensionManager.enableExtension('scrollwork@local')"
            )
            wait(
                f"enable cycle {index}",
                lambda: len(state()["targets"]) == 2 and settled(),
                stable_for=0.15,
            )
        check(
            "five extra disable/re-enable cycles leave no extension errors",
            lambda: not state().get("errors"),
        )
        for index in range(12):
            temporary = create(f"SW-stress-{index}")
            wait(
                f"stress window {index} maps",
                lambda: len(state()["targets"]) == 3 and settled(),
            )
            evaluate(f"{ext}.cycleWidth(); {ext}.move(-1); true")
            wait(f"stress window {index} resizes", settled)
            temporary.destroy()
            wait(
                f"stress window {index} closes",
                lambda: len(state()["targets"]) == 2 and settled(),
            )
        check(
            "twelve real-client open/resize/reorder/close cycles settle without errors",
            lambda: not state().get("errors"),
        )
        evaluate(f"{ext}.settings.set_int('gap',24); true")
        check(
            "live gap settings reconfigure real clients",
            lambda: (
                settled() and all(i["target"]["y"] == 56 for i in state()["targets"])
            ),
        )
        evaluate(f"{ext}.settings.reset('gap'); true")
        check(
            "resetting gap settings restores layout",
            lambda: (
                settled() and all(i["target"]["y"] == 40 for i in state()["targets"])
            ),
        )

        def display_state():
            return bus.call_sync(
                "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig",
                "org.gnome.Mutter.DisplayConfig",
                "GetCurrentState",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            ).unpack()

        def configure_display(scale=1.0, transform=0):
            serial, monitors, _logical, _properties = display_state()
            connector = monitors[0][0][0]
            mode = next(
                (m for m in monitors[0][1] if m[6].get("is-current")), monitors[0][1][0]
            )
            config = [(0, 0, scale, transform, True, [(connector, mode[0], {})])]
            bus.call_sync(
                "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig",
                "org.gnome.Mutter.DisplayConfig",
                "ApplyMonitorsConfig",
                GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (serial, 1, config, {})),
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            )

        configure_display(transform=1)
        check(
            "portrait display rotation recomputes the work area and client geometry",
            lambda: (
                settled()
                and evaluate(
                    "global.scrollworkTestMain.layoutManager.primaryMonitor.width===800"
                )
            ),
        )
        configure_display()
        check(
            "restoring landscape restores usable geometry",
            lambda: (
                settled()
                and evaluate(
                    "global.scrollworkTestMain.layoutManager.primaryMonitor.width===1280"
                )
            ),
        )
        supported_scales = display_state()[1][0][1][0][5]
        for scale in [1.25, 2.0]:
            if scale not in supported_scales:
                skipped.append(
                    f"output scale {scale} is not exposed by this virtual monitor"
                )
                continue
            configure_display(scale=scale)
            check(
                f"output scale {scale} preserves settled client geometry",
                lambda: (
                    settled()
                    and evaluate(
                        f"global.scrollworkTestMain.layoutManager.primaryMonitor.width==={round(1280 / scale)}"
                    )
                ),
            )
            configure_display()
            wait("restore 1x scale", settled, stable_for=0.2)
        # Leave a screenshot from the actual compositor, not a mock rendering.
        screenshot(root / "screenshot.png")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        wait(
            "compositor screenshot is complete",
            lambda: (root / "screenshot.png").exists(),
        )
        image = GdkPixbuf.Pixbuf.new_from_file(str(root / "screenshot.png"))
        pixels = image.get_pixels()

        def pixel(x, y):
            index = int(y) * image.get_rowstride() + int(x) * image.get_n_channels()
            return tuple(pixels[index : index + 3])

        focus = state()["focus"]
        for item in state()["targets"]:
            r = item["actual"]
            if r["x"] < 0 or r["x"] + r["width"] > image.get_width():
                continue
            expected = (203, 166, 247) if item["title"] == focus else (30, 30, 46)
            side = pixel(r["x"] + 1, r["y"] + r["height"] * 0.7)
            corner = pixel(r["x"] + 1, r["y"] + r["height"] - 2)
            check(
                f"{item['title']} screenshot has the correct focus-border color",
                lambda: all(abs(a - b) < 14 for a, b in zip(side, expected)),
            )
            check(
                f"{item['title']} screenshot clips the rounded bottom corner",
                lambda: any(abs(a - b) > 20 for a, b in zip(corner, expected)),
            )
        check(
            "no JavaScript exceptions or builtin keybinding registration collisions",
            lambda: (
                not any(
                    message in (root / "shell.log").read_text()
                    for message in [
                        "JS ERROR:",
                        "has been already disposed",
                        "Shader compilation failed",
                        "Trying to re-add keybinding",
                        "Trying to remove builtin keybinding",
                    ]
                )
            ),
        )
        (root / "results.json").write_text(
            json.dumps(
                {"passed": checks, "skipped": skipped, "final": state()}, indent=2
            )
        )
        return 0
    except Exception:
        traceback.print_exc()
        try:
            print("FAILURE STATE", json.dumps(state(), indent=2), flush=True)
            print("POINTER", evaluate("global.get_pointer()"), flush=True)
            print(
                "PICK",
                evaluate("""(()=>{const [x,y]=global.get_pointer();
                let a=global.stage.get_actor_at_pos(global.scrollworkTestInput.C.PickMode.REACTIVE,x,y);
                const names=[];while(a){names.push(a.toString());a=a.get_parent();}return names;})()"""),
                flush=True,
            )
            print(
                "GTK WIDGETS",
                [
                    (
                        w.get_title(),
                        w.get_child().get_width(),
                        w.get_child().get_height(),
                        int(w.get_child().get_state_flags()),
                    )
                    for w in windows
                ],
                "CLICKS",
                clicks,
                flush=True,
            )
            print("POINTER EVENTS", pointer_events, flush=True)
            print("STAGE EVENTS", evaluate("global.scrollworkTestEvents"), flush=True)
            print(
                "ACTORS",
                evaluate(
                    "global.get_window_actors().map(a=>({title:a.meta_window.title,type:a.meta_window.get_window_type()}))"
                ),
                flush=True,
            )
        except Exception:
            traceback.print_exc()
        (root / "results.json").write_text(
            json.dumps({"passed": checks, "failure": traceback.format_exc()}, indent=2)
        )
        return 1
    finally:
        if electron_client and electron_client.poll() is None:
            electron_client.terminate()
            try:
                electron_client.wait(timeout=5)
            except subprocess.TimeoutExpired:
                electron_client.kill()
                electron_client.wait()
        if slow_client and slow_client.poll() is None:
            slow_client.send_signal(signal.SIGCONT)
            slow_client.terminate()
            try:
                slow_client.wait(timeout=5)
            except subprocess.TimeoutExpired:
                slow_client.kill()
                slow_client.wait()
        for window in windows:
            window.destroy()
        pump()
        shell.terminate()
        try:
            shell.wait(timeout=10)
        except subprocess.TimeoutExpired:
            shell.kill()
            shell.wait()
        log.close()


if __name__ == "__main__":
    prefix = os.environ.get("SCROLLWORK_MUTTER_PREFIX")
    if prefix and not os.environ.get("SCROLLWORK_MUTTER_OVERLAY"):
        library_dir = next(
            (
                Path(prefix) / name
                for name in ["lib", "lib64"]
                if (Path(prefix) / name / "libmutter-51.so.0").exists()
            ),
            None,
        )
        if library_dir is None:
            raise RuntimeError(f"No staged Mutter 51 library under {prefix}")
        system_libdir = Path(
            subprocess.check_output(
                ["pkg-config", "--variable=libdir", "libmutter-51"], text=True
            ).strip()
        )
        env = dict(os.environ, SCROLLWORK_MUTTER_OVERLAY="1", RUNNING_UNDER_RR="1")
        # GI prepends hard-coded library paths: LD_LIBRARY_PATH alone can load
        # two copies of Cogl and crash. Overlay the matching libraries/typelibs
        # at those paths in a PRIVATE mount namespace, never in the host /usr.
        sys.exit(
            subprocess.run(
                [
                    "bwrap",
                    "--die-with-parent",
                    "--dev-bind",
                    "/",
                    "/",
                    "--tmpfs",
                    "/dev/dri",
                    "--ro-bind",
                    str(library_dir / "mutter-51"),
                    str(system_libdir / "mutter-51"),
                    "--ro-bind",
                    str((library_dir / "libmutter-51.so.0").resolve()),
                    str((system_libdir / "libmutter-51.so.0").resolve()),
                    "--",
                    sys.executable,
                    __file__,
                ],
                env=env,
            ).returncode
        )
    sys.exit(
        inside(Path(sys.argv[2]))
        if len(sys.argv) > 1 and sys.argv[1] == "--inside"
        else launch()
    )
