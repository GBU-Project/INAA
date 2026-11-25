"""Kontroller GTK untuk OSC (Phase 2.2): floating / docked atas-bawah / off.

Keputusan murni ada di `chrome_logic.py`. Kelas ini hanya memindahkan `osd_box`
antara `Gtk.Overlay` (floating) dan slot atas/bawah di sekitar video (docked).
`gl_area` TIDAK PERNAH dipindah (render context libmpv rapuh); yang berpindah
parent hanya `osd_box`.
"""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from chrome_logic import auto_hide_flags, osc_auto_hide_allowed, resolve_osc
from layout_config import layout_v2_enabled

_DOCKED_CSS = b"""
.iina-osc-docked {
    margin: 0;
    border-radius: 0;
    border-width: 1px 0 0 0;
    box-shadow: none;
}
"""


class OscController:
    def __init__(self, window, config, osd_box, overlay, slot_top, slot_bottom):
        self.window = window
        self.config = config
        self.osd_box = osd_box
        self.overlay = overlay
        self.slots = {"top": slot_top, "bottom": slot_bottom}
        self._mini = False
        self._fullscreen = False
        self._signature = None

        for slot in self.slots.values():
            slot.set_visible(False)
            slot.set_hexpand(True)

        display = Gdk.Display.get_default()
        if display is not None:
            provider = Gtk.CssProvider()
            provider.load_from_data(_DOCKED_CSS)
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
            )
            self._provider = provider

        self.apply()

    # -- state ---------------------------------------------------------
    @property
    def state(self) -> dict:
        return resolve_osc(
            self.config.get("layout"),
            enabled=layout_v2_enabled(self.config),
            is_mini=self._mini,
            is_fullscreen=self._fullscreen,
        )

    def allows_osd(self) -> bool:
        return bool(self.state["visible"])

    def auto_hide_allowed(self) -> bool:
        return osc_auto_hide_allowed(self.state)

    def chrome_auto_hide(self) -> tuple[bool, bool]:
        """(osd_auto_hide, header_auto_hide) menurut config saat ini."""
        return auto_hide_flags(
            self.config.get("layout"),
            enabled=layout_v2_enabled(self.config),
            legacy_auto_hide=bool(self.config.get("auto_hide_chrome", True)),
            osc_state=self.state,
        )

    def extra_height(self) -> int:
        """Tinggi tambahan untuk fit-window bila OSC docked."""
        return int(self.state["docked_height"])

    def set_mini(self, mini: bool) -> None:
        self._mini = bool(mini)
        self.apply()

    def set_fullscreen(self, fullscreen: bool) -> None:
        self._fullscreen = bool(fullscreen)
        self.apply()

    # -- terapkan --------------------------------------------------------
    def apply(self) -> None:
        state = self.state
        signature = (state["slot"], state["size"], state["visible"], state["always_visible"])
        if signature != self._signature:
            self._mount(state)
            self._signature = signature

    def _detach(self) -> None:
        parent = self.osd_box.get_parent()
        if parent is self.overlay:
            self.overlay.remove_overlay(self.osd_box)
        elif parent is not None:
            parent.remove(self.osd_box)

    def _mount(self, state: dict) -> None:
        self._detach()
        slot = state["slot"]
        for name, widget in self.slots.items():
            widget.set_visible(name == slot and state["visible"])

        if slot is None:
            self.osd_box.remove_css_class("iina-osc-docked")
            self.osd_box.set_halign(Gtk.Align.CENTER)
            self.osd_box.set_valign(Gtk.Align.END)
            self.osd_box.set_size_request(state["width"], -1)
            self.overlay.add_overlay(self.osd_box)
        else:
            self.osd_box.add_css_class("iina-osc-docked")
            self.osd_box.set_halign(Gtk.Align.FILL)
            self.osd_box.set_valign(Gtk.Align.FILL)
            self.osd_box.set_size_request(-1, -1)
            self.slots[slot].append(self.osd_box)

        if not state["visible"]:
            self.osd_box.set_visible(False)
        elif slot is not None or state["always_visible"]:
            self.osd_box.remove_css_class("hidden")
            self.osd_box.set_visible(True)
