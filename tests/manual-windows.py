#!/usr/bin/env python3
"""Simple real GTK windows for a human's first layout/floating test."""

import argparse
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

parser = argparse.ArgumentParser()
parser.add_argument("--single", action="store_true")
parser.add_argument("--calculator", action="store_true")
args = parser.parse_args()
Gtk.init()
loop = GLib.MainLoop()
windows = []
app = None
if args.calculator:
    app = Gtk.Application(
        application_id="com.dominic.calc", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.register(None)


def close(window):
    if window in windows:
        windows.remove(window)
    if not windows:
        loop.quit()
    return False


for index in range(1 if args.single or args.calculator else 2):
    title = (
        "Floating calculator demo"
        if args.calculator
        else ("Scrollwork Demo" if index == 0 else "Scrollwork Demo 2")
    )
    kwargs = {"title": title, "default_width": 400, "default_height": 300}
    window = (
        Gtk.ApplicationWindow(application=app, **kwargs)
        if app
        else Gtk.Window(**kwargs)
    )
    label = Gtk.Label(
        label="Scrollwork · patched GNOME test\n\n"
        "Super+H / L: focus left / right\nSuper+Ctrl+H / L: reorder\n"
        "Super+D: half / full width\nSuper+G: float / tile\n"
        "Super+1…9 / 0: instant workspaces\nSuper+X: close this window\n\n"
        "Use the outer toolbar to open apps.\nClose the outer Devkit window to exit safely."
    )
    label.set_wrap(True)
    label.set_margin_start(24)
    label.set_margin_end(24)
    window.set_child(label)
    window.connect("close-request", close)
    windows.append(window)
    window.present()
loop.run()
