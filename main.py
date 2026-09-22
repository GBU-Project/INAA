#!/usr/bin/env python3
"""
INAA (GTK4 / Wayland-native edition)
A lightweight desktop media player for Linux, inspired by IINA (macOS),
built with GTK4 + libmpv render API (OpenGL). Renders natively on Wayland
(and X11) with no XWayland dependency.

Run: python3 main.py [optional/path/to/video.mp4]
"""
import sys

from logging_setup import install_excepthook, setup_logging, guard

log = setup_logging()
install_excepthook(log)

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio, GLib
except Exception:
    log.exception("Gagal memuat GTK4 (gi.repository) — periksa instalasi GTK4/PyGObject")
    print(
        "INAA gagal start: GTK4 (PyGObject) tidak ditemukan atau versinya tidak cocok.\n"
        "Pastikan paket seperti 'gir1.2-gtk-4.0' dan 'python3-gi' sudah terpasang.\n"
        f"Detail lengkap ada di log: {log.handlers[0].baseFilename if log.handlers else '(lihat konsol)'}",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from player_window import PlayerWindow
except Exception:
    log.exception("Gagal memuat player_window (kemungkinan libmpv tidak ditemukan)")
    print(
        "INAA gagal start: modul player gagal dimuat, kemungkinan libmpv tidak "
        "terpasang (paket 'libmpv2' atau 'libmpv1').\n"
        f"Detail lengkap ada di log: {log.handlers[0].baseFilename if log.handlers else '(lihat konsol)'}",
        file=sys.stderr,
    )
    sys.exit(1)


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
            try:
                self.window = PlayerWindow(application=self)
            except Exception:
                log.exception(
                    "Gagal membuat PlayerWindow (kemungkinan libmpv tidak "
                    "ditemukan, atau OpenGL/GLArea tidak tersedia di sesi ini)"
                )
                dialog = Gtk.MessageDialog(
                    transient_for=None,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CLOSE,
                    text="INAA tidak bisa dijalankan di sistem ini",
                    secondary_text=(
                        "Kemungkinan penyebab: libmpv tidak terpasang, atau tidak "
                        "ada dukungan OpenGL yang memadai pada sesi grafis ini.\n\n"
                        f"Detail teknis dicatat di:\n{log.handlers[0].baseFilename}"
                    ),
                )
                dialog.connect("response", lambda d, r: self.quit())
                dialog.present()
                return
        self.window.present()
        if self.initial_file:
            self.window.open_file(self.initial_file)

    @guard(log)
    def do_open(self, files, n_files, hint):
        self.do_activate()
        paths = []
        for gfile in files:
            if not gfile:
                continue
            path = gfile.get_path() or gfile.get_uri()
            if path:
                paths.append(path)
        for path in paths:
            self.window.add_to_playlist(path)
        if paths:
            self.window.open_file(paths[0])


def main():
    GLib.set_prgname("io.github.inaa")
    GLib.set_application_name("INAA")
    Gtk.Window.set_default_icon_name("io.github.inaa")
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = InaaApplication(initial_file=initial_file)
    try:
        return app.run(sys.argv[:1])
    except Exception:
        log.exception("INAA berhenti karena exception tak tertangani di main loop")
        return 1


if __name__ == "__main__":
    sys.exit(main())
