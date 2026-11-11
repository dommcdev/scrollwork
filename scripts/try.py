#!/usr/bin/env python3
"""Launch patched GNOME in a window, with persistent, separate test profiles."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
UUID = "scrollwork@local"
EMBEDDED_PREFIX = "/tmp/opencode/mutter-scrollwork-install"
BASE = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local/share/scrollwork-test"
RUNTIME = BASE / "runtime"
PROFILE = BASE / "profile"
DESKTOP = (
    Path(pwd.getpwuid(os.getuid()).pw_dir)
    / ".local/share/applications/dev.dominic.ScrollworkTest.desktop"
)
RUNTIME_FILES = [
    "extension.js",
    "layout.js",
    "settings.js",
    "rules.js",
    "appearance.js",
    "edges.js",
    "animation.js",
    "keybindings.js",
    "metadata.json",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install():
    source = Path(EMBEDDED_PREFIX)
    if not (source / "libexec/mutter-devkit").is_file():
        raise RuntimeError(
            "The patched runtime needs to be built with -Ddevkit=enabled first"
        )
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if RUNTIME.exists():
        if not (BASE / "runtime.json").exists():
            raise RuntimeError(
                f"Refusing to overwrite an unrecognized runtime: {RUNTIME}"
            )
        previous = json.loads((BASE / "runtime.json").read_text())
        if previous["sha256"] != digest(source / "lib/libmutter-51.so.0.0.0"):
            raise RuntimeError(
                "A different test runtime exists; update it deliberately, not by overwriting it"
            )
    else:
        shutil.copytree(source, RUNTIME, symlinks=True)
        (BASE / "runtime.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "gnome": "51.1",
                    "embedded_prefix": EMBEDDED_PREFIX,
                    "sha256": digest(RUNTIME / "lib/libmutter-51.so.0.0.0"),
                    "mdk_sha256": digest(RUNTIME / "libexec/mutter-devkit"),
                },
                indent=2,
            )
        )
    text = f'''[Desktop Entry]
Type=Application
Name=Scrollwork Test
Comment=Patched GNOME in a window; separate settings and app profiles
Exec=/usr/bin/python "{Path(__file__).resolve()}"
Icon=preferences-desktop
Terminal=false
Categories=Development;
StartupNotify=false
StartupWMClass=org.gnome.Mutter.Mdk
'''
    DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    if DESKTOP.exists() and DESKTOP.read_text() != text:
        raise RuntimeError(f"Refusing to overwrite a different launcher: {DESKTOP}")
    DESKTOP.write_text(text)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(DESKTOP.parent)], check=True)
    print(f"Installed launcher: {DESKTOP}\nPersistent runtime: {RUNTIME}")


def doctor():
    for executable in [
        "bwrap",
        "dbus-run-session",
        "pipewire",
        "wireplumber",
        "gnome-shell",
        "glib-compile-schemas",
    ]:
        if shutil.which(executable) is None:
            raise RuntimeError(f"Missing required program: {executable}")
    manifest = json.loads((BASE / "runtime.json").read_text())
    if digest(RUNTIME / "lib/libmutter-51.so.0.0.0") != manifest["sha256"]:
        raise RuntimeError("The saved patched runtime does not match its manifest")
    if digest(RUNTIME / "libexec/mutter-devkit") != manifest.get("mdk_sha256"):
        raise RuntimeError(
            "The saved viewer does not match its keyboard-capture manifest"
        )
    version = subprocess.check_output(["gnome-shell", "--version"], text=True).strip()
    if version != "GNOME Shell 51.1":
        raise RuntimeError(
            f"This test runtime was validated with GNOME Shell 51.1, not {version}"
        )
    if not (RUNTIME / "libexec/mutter-devkit").exists():
        raise RuntimeError("Saved runtime is missing its windowed development kit")
    print(
        f"OK: {version}, patched runtime verified, no compilation/sudo required",
        flush=True,
    )


def stop():
    lock_path = BASE / "session.lock"
    if not lock_path.exists():
        print("No Scrollwork test session is running")
        return
    with lock_path.open() as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("No Scrollwork test session is running")
            return
        except BlockingIOError:
            pass
        record = json.loads(lock.read())
    pid = record["pid"]
    proc = Path(f"/proc/{pid}")
    command = (proc / "cmdline").read_bytes().decode().split("\0")
    script = Path(command[1]) if len(command) > 1 else Path("/")
    if not script.is_absolute():
        script = (proc / "cwd").resolve() / script
    if (
        proc.stat().st_uid != os.getuid()
        or script.resolve() != Path(__file__).resolve()
    ):
        raise RuntimeError("Refusing to stop a process that is not this test launcher")
    if (proc / "stat").read_text().split()[21] != record["started"]:
        raise RuntimeError("Refusing to stop a reused PID")
    os.kill(pid, signal.SIGTERM)
    print("Stopped Scrollwork Test; its private process namespace will close")


def prepare(smoke):
    for name in ["home", "config", "cache", "data", "state"]:
        (PROFILE / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    target = PROFILE / f"data/gnome-shell/extensions/{UUID}"
    (target / "schemas").mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_FILES:
        shutil.copy2(REPO / name, target / name)
    schema = "org.gnome.shell.extensions.scrollwork.gschema.xml"
    shutil.copy2(REPO / "schemas" / schema, target / "schemas" / schema)
    subprocess.run(
        ["glib-compile-schemas", "--strict", str(target / "schemas")], check=True
    )
    if smoke:
        (PROFILE / "state/scrollwork/interactive-probe.json").unlink(missing_ok=True)
        probe = (
            PROFILE / "data/gnome-shell/extensions/scrollwork-interactive-probe@local"
        )
        probe.mkdir(parents=True, exist_ok=True)
        (probe / "metadata.json").write_text(
            json.dumps(
                {
                    "uuid": probe.name,
                    "name": "Read-only interactive smoke probe",
                    "description": "Private test profile only; no arbitrary evaluation interface",
                    "shell-version": ["51"],
                }
            )
        )
        shutil.copy2(REPO / "tests/interactive-probe.js", probe / "extension.js")
    helper = PROFILE / "data/gnome-shell/extensions/scrollwork-test-session@local"
    helper.mkdir(parents=True, exist_ok=True)
    (helper / "metadata.json").write_text(
        json.dumps(
            {
                "uuid": helper.name,
                "name": "Scrollwork windowed test startup",
                "description": "Show test windows after startup",
                "shell-version": ["51"],
            }
        )
    )
    shutil.copy2(REPO / "scripts/test-session.js", helper / "extension.js")
    apps = PROFILE / "data/applications"
    apps.mkdir(exist_ok=True)
    definitions = [
        (
            "terminal",
            "Ghostty",
            "/usr/bin/ghostty +new-window",
            "com.mitchellh.ghostty",
        ),
        (
            "discord",
            "Discord · test profile",
            "/usr/bin/discord --ozone-platform=wayland --disable-gpu",
            "discord",
        ),
        (
            "opencode",
            "OpenCode · test profile",
            "/usr/bin/opencode-desktop",
            "utilities-terminal",
        ),
        ("files", "Files", "/usr/bin/nautilus --new-window", "org.gnome.Nautilus"),
        (
            "minimum",
            "Minimum-width demo",
            f"/usr/bin/electron --ozone-platform=wayland --disable-gpu {REPO}/tests/electron-client.cjs",
            "applications-development",
        ),
        (
            "calculator",
            "Floating demo",
            f"/usr/bin/python {REPO}/tests/manual-windows.py --calculator",
            "accessories-calculator",
        ),
        (
            "windows",
            "Two test windows",
            f"/usr/bin/python {REPO}/tests/manual-windows.py",
            "preferences-system-windows",
        ),
    ]
    for key, name, command, icon in definitions:
        (apps / f"scrollwork-{key}.desktop").write_text(f"""[Desktop Entry]
Type=Application
Name={name}
Exec={command}
Icon={icon}
Terminal=false
""")


def outer(args):
    doctor()
    BASE.mkdir(parents=True, exist_ok=True)
    with (BASE / "session.lock").open("a+") as lock:
        return run_outer(args, lock)


def run_outer(args, lock):
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("A Scrollwork test session is already open") from None
    lock.seek(0)
    lock.truncate()
    lock.write(
        json.dumps(
            {
                "pid": os.getpid(),
                "started": Path("/proc/self/stat").read_text().split()[21],
            }
        )
    )
    lock.flush()
    prepare(args.smoke_test)
    host_runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    display = os.environ.get("WAYLAND_DISPLAY")
    if not display:
        raise RuntimeError("Start this launcher from your normal Wayland desktop")
    outer_socket = (
        Path(display) if Path(display).is_absolute() else host_runtime / display
    )
    if not outer_socket.exists():
        raise RuntimeError(f"Cannot find the parent compositor socket: {outer_socket}")
    # Do not pass API keys, harness variables, activation endpoints or session
    # services from the normal desktop to the separate application profiles.
    user = pwd.getpwuid(os.getuid())
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "USER": user.pw_name,
        "LOGNAME": user.pw_name,
        "SHELL": user.pw_shell,
        "HOME": str(PROFILE / "home"),
        "XDG_CONFIG_HOME": str(PROFILE / "config"),
        "XDG_CACHE_HOME": str(PROFILE / "cache"),
        "XDG_DATA_HOME": str(PROFILE / "data"),
        "XDG_STATE_HOME": str(PROFILE / "state"),
        "XDG_DATA_DIRS": "/usr/local/share:/usr/share",
        "XDG_CONFIG_DIRS": "/etc/xdg",
        "XDG_CURRENT_DESKTOP": "GNOME",
        "XDG_SESSION_TYPE": "wayland",
        "GSETTINGS_BACKEND": "keyfile",
        "WAYLAND_DISPLAY": str(outer_socket),
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "GSK_RENDERER": "cairo",
        "GTK_A11Y": "none",
        "NO_AT_BRIDGE": "1",
        "RUNNING_UNDER_RR": "1",
    }
    with tempfile.TemporaryDirectory(
        prefix="scrollwork-interactive-", dir=host_runtime
    ) as temporary:
        env["XDG_RUNTIME_DIR"] = temporary
        command = [
            "bwrap",
            "--die-with-parent",
            "--unshare-pid",
            "--dev-bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--tmpfs",
            "/tmp/opencode",
            "--tmpfs",
            "/dev/dri",
            "--ro-bind",
            str(RUNTIME),
            EMBEDDED_PREFIX,
            "--ro-bind",
            str(RUNTIME / "lib/mutter-51"),
            "/usr/lib/mutter-51",
            "--ro-bind",
            str(RUNTIME / "lib/libmutter-51.so.0.0.0"),
            "/usr/lib/libmutter-51.so.0.0.0",
            "--",
            "dbus-run-session",
            "--",
            sys.executable,
            str(Path(__file__).resolve()),
            "--inside",
            "--size",
            args.size,
        ]
        if args.smoke_test:
            command.append("--smoke-test")
            command.extend(["--smoke-hold", str(getattr(args, "smoke_hold", 0))])
        log_path = PROFILE / "state/session.log"
        print(f"Log: {log_path}", flush=True)
        with log_path.open("w") as log:
            result = subprocess.run(
                command, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        if result.returncode:
            raise RuntimeError(
                f"Test session exited with {result.returncode}. See {log_path}"
            )


def inside(args):
    import gi
    from gi.repository import Gio, GLib

    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    extensions = [UUID, "scrollwork-test-session@local"] + (
        ["scrollwork-interactive-probe@local"] if args.smoke_test else []
    )
    Gio.Settings.new("org.gnome.shell").set_strv("enabled-extensions", extensions)
    interface = Gio.Settings.new("org.gnome.desktop.interface")
    interface.set_boolean("enable-hot-corners", False)
    interface.set_string("color-scheme", "prefer-dark")
    launchers = [
        ("desktop", f"scrollwork-{key}", "")
        for key in [
            "terminal",
            "discord",
            "opencode",
            "files",
            "minimum",
            "calculator",
            "windows",
        ]
    ]
    Gio.Settings.new("org.gnome.mutter.devkit").set_value(
        "launchers", GLib.Variant("a(sss)", launchers)
    )
    Gio.Settings.sync()
    pipewire = subprocess.Popen(["pipewire"])
    shell = None
    viewer = None
    wireplumber = None
    clients = []
    context = GLib.MainContext.default()
    started = time.monotonic()
    try:
        while not (Path(os.environ["XDG_RUNTIME_DIR"]) / "pipewire-0").exists():
            if pipewire.poll() is not None or time.monotonic() - started > 10:
                raise RuntimeError("The private PipeWire daemon did not start")
            time.sleep(0.05)
        wireplumber = subprocess.Popen(["wireplumber"])
        shell = subprocess.Popen(
            [
                "gnome-shell",
                "--headless",
                "--devkit",
                "--no-x11",
                "--wayland-display=scrollwork-interactive",
            ]
        )
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        ready = False
        passed_at = None
        while shell.poll() is None:
            if viewer is not None and viewer.poll() is not None:
                return viewer.returncode
            while context.pending():
                context.iteration(False)
            if not ready:
                if time.monotonic() - started > 45:
                    raise RuntimeError(
                        "GNOME/Scrollwork did not become ready within 45 seconds"
                    )
                try:
                    if viewer is None:
                        # Start the viewer ourselves with the ORIGINAL parent
                        # socket. Mutter 51.1's automatic viewer captures the
                        # already-replaced WAYLAND_DISPLAY and can connect to
                        # its own, monitor-less compositor instead of Hyprland.
                        bus.call_sync(
                            "org.gnome.Mutter.Devkit",
                            "/org/gnome/Mutter/Devkit",
                            "org.freedesktop.DBus.Properties",
                            "Get",
                            GLib.Variant("(ss)", ("org.gnome.Mutter.Devkit", "Env")),
                            None,
                            Gio.DBusCallFlags.NONE,
                            1000,
                            None,
                        )
                        viewer = subprocess.Popen(
                            [
                                str(RUNTIME / "libexec/mutter-devkit"),
                                f"--monitor-size={args.size}",
                            ],
                        )
                    info = bus.call_sync(
                        "org.gnome.Shell",
                        "/org/gnome/Shell",
                        "org.gnome.Shell.Extensions",
                        "GetExtensionInfo",
                        GLib.Variant("(s)", (UUID,)),
                        None,
                        Gio.DBusCallFlags.NONE,
                        1000,
                        None,
                    ).unpack()[0]
                    if info.get("state") != 1:
                        time.sleep(0.1)
                        continue
                    display = bus.call_sync(
                        "org.gnome.Mutter.DisplayConfig",
                        "/org/gnome/Mutter/DisplayConfig",
                        "org.gnome.Mutter.DisplayConfig",
                        "GetCurrentState",
                        None,
                        None,
                        Gio.DBusCallFlags.NONE,
                        1000,
                        None,
                    ).unpack()
                    if not display[2]:
                        time.sleep(0.1)
                        continue
                    bus.call_sync(
                        "org.freedesktop.DBus",
                        "/org/freedesktop/DBus",
                        "org.freedesktop.DBus",
                        "UpdateActivationEnvironment",
                        GLib.Variant(
                            "(a{ss})",
                            (
                                {
                                    "WAYLAND_DISPLAY": "scrollwork-interactive",
                                    "XDG_CURRENT_DESKTOP": "GNOME",
                                },
                            ),
                        ),
                        None,
                        Gio.DBusCallFlags.NONE,
                        1000,
                        None,
                    )
                    child_env = dict(
                        os.environ, WAYLAND_DISPLAY="scrollwork-interactive"
                    )
                    demo = [sys.executable, str(REPO / "tests/manual-windows.py")]
                    if args.smoke_test:
                        demo.append("--single")
                    clients.append(subprocess.Popen(demo, env=child_env))
                    if args.smoke_test:
                        clients.append(
                            subprocess.Popen(
                                [
                                    "electron",
                                    "--ozone-platform=wayland",
                                    "--disable-gpu",
                                    str(REPO / "tests/electron-client.cjs"),
                                ],
                                env=child_env,
                            )
                        )
                    ready = True
                    print(
                        "READY: Scrollwork active; private profiles; host shortcut inhibition requested",
                        flush=True,
                    )
                except GLib.Error:
                    time.sleep(0.1)
                    continue
            if args.smoke_test and ready:
                path = PROFILE / "state/scrollwork/interactive-probe.json"
                if path.exists():
                    report = json.loads(path.read_text())
                    names = {
                        w["title"] for w in report.get("windows", []) if w["settled"]
                    }
                    if (
                        report.get("patched")
                        and not report.get("overview")
                        and report.get("monitors") == 1
                        and {"Scrollwork Demo", "SW-electron"} <= names
                    ):
                        if passed_at is None:
                            passed_at = time.monotonic()
                            print(
                                "PASS: windowed devkit, patched compositor, extension and real GTK/Electron geometry",
                                flush=True,
                            )
                        if time.monotonic() - passed_at >= args.smoke_hold:
                            return 0
                if time.monotonic() - started > 65:
                    raise RuntimeError(
                        "Interactive minimum-width smoke check did not settle"
                    )
            time.sleep(0.05)
        return shell.returncode
    finally:
        for process in [*clients, viewer, shell, wireplumber, pipewire]:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-hold", type=float, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--size", default="1600x900")
    args = parser.parse_args()
    if args.install:
        install()
    elif args.doctor:
        doctor()
    elif args.stop:
        stop()
    elif args.inside:
        return inside(args)
    else:
        outer(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Scrollwork Test: {error}", file=sys.stderr)
        if (
            "--inside" not in sys.argv
            and "--smoke-test" not in sys.argv
            and shutil.which("notify-send")
        ):
            subprocess.run(
                [
                    "notify-send",
                    "-u",
                    "critical",
                    "Scrollwork Test could not start",
                    str(error),
                ],
                check=False,
            )
        sys.exit(1)
