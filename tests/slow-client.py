#!/usr/bin/env python3
"""A separate real Wayland client, so the integration test can suspend its event loop."""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

Gtk.init()
window = Gtk.Window(title="SW-slow", default_width=320, default_height=240)
window.set_child(Gtk.Label(label="Suspended/resumed configure test"))
window.present()
GLib.MainLoop().run()
