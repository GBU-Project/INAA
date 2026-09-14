#!/usr/bin/env python3
"""
INAA (GTK4 / Wayland-native edition)
A lightweight desktop media player for Linux, inspired by IINA (macOS),
built with GTK4 + libmpv render API (OpenGL). Renders natively on Wayland
(and X11) with no XWayland dependency.

Run: python3 main.py [optional/path/to/video.mp4]
"""
import sys
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib

from player_window import PlayerWindow


class InaaApplication(Gtk.Application):
    def __init__(self, initial_file=None):
        super().__init__(
            application_id="io.github.inaa",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.initial_file = initial_file
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = PlayerWindow(application=self)
        self.window.present()
        if self.initial_file:
            self.window.open_file(self.initial_file)

    def do_open(self, files, n_files, hint):
        self.do_activate()
        if n_files > 0:
            self.window.open_file(files[0].get_path())


def main():
    GLib.set_prgname("io.github.inaa")
    GLib.set_application_name("INAA")
    Gtk.Window.set_default_icon_name("io.github.inaa")
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = InaaApplication(initial_file=initial_file)
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
