"""Kontroller header bar (Phase 2.3): full / auto-hide / hidden.

Keputusan mode ada di `chrome_logic.resolve_header_mode` (murni). Mode `hidden`
TIDAK memakai `set_decorated(False)`: jendela tetap punya titlebar kecil
transparan berisi `Gtk.WindowHandle` + `Gtk.WindowControls`, sehingga geser
(drag) dan resize tetap ditangani GTK/compositor di Wayland. Tombol jendela
muncul saat kursor menyentuh strip atas.

Header asli tetap disimpan (tidak dimusnahkan) agar bisa dipasang kembali saat
mode berubah tanpa restart.
"""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from chrome_logic import resolve_header_mode
from layout_config import layout_v2_enabled

DRAGBAR_HEIGHT = 26

_HIDDEN_CSS = b"""
.iina-hidden-titlebar {
    background: transparent;
    border: none;
    box-shadow: none;
    min-height: 26px;
}
"""


class HeaderController:
    def __init__(self, window, config, header):
        self.window = window
        self.config = config
        self.header = header
        self._mode = None
        self.dragbar = self._build_dragbar()
        self._install_css()
        self.apply()

    # -- konstruksi ------------------------------------------------------
    def _install_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(_HIDDEN_CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )

    def _build_dragbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.add_css_class("iina-hidden-titlebar")
        bar.set_size_request(-1, DRAGBAR_HEIGHT)

        handle = Gtk.WindowHandle()
        handle.set_hexpand(True)
        bar.append(handle)

        self._controls = Gtk.WindowControls(side=Gtk.PackType.END)
        self._controls.set_visible(False)
        bar.append(self._controls)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self._controls.set_visible(True))
        motion.connect("leave", lambda *_: self._controls.set_visible(False))
        bar.add_controller(motion)
        return bar

    # -- keadaan ---------------------------------------------------------
    def mode(self) -> str:
        return resolve_header_mode(
            self.config.get("layout"),
            enabled=layout_v2_enabled(self.config),
            legacy_auto_hide=bool(self.config.get("auto_hide_chrome", True)),
        )

    def is_hidden(self) -> bool:
        return self.mode() == "hidden"

    def chrome_height(self) -> int:
        """Tinggi chrome atas untuk perhitungan fit-window."""
        if self._mode == "hidden":
            return DRAGBAR_HEIGHT
        return 48 if self.header.get_visible() else 0

    # -- tampilkan / sembunyikan -----------------------------------------
    def show_header(self) -> None:
        """Tampilkan header; diabaikan pada mode hidden (header tidak terpasang)."""
        if self._mode != "hidden":
            self.header.set_visible(True)

    def hide_header(self) -> None:
        if self._mode != "hidden":
            self.header.set_visible(False)

    def apply(self) -> None:
        """Pasang titlebar sesuai mode efektif."""
        mode = self.mode()
        previous, self._mode = self._mode, mode

        if mode == "hidden":
            if self.window.get_titlebar() is not self.dragbar:
                self.window.set_titlebar(self.dragbar)
            self.header.set_visible(False)
        else:
            if self.window.get_titlebar() is not self.header:
                self.window.set_titlebar(self.header)
            if previous == "hidden" or not getattr(self.window, "_is_mini", False):
                self.header.set_visible(True)


__all__ = ["DRAGBAR_HEIGHT", "HeaderController"]
