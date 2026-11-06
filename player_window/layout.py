"""Kontroller GTK untuk dockable panes (Phase 1).

Model/validasi tetap di `layout_config.py` (murni, tanpa GTK). Kelas di sini
hanya menyusun rantai `Gtk.Paned` di sekitar area video, menyimpan lebar
pane saat di-drag, dan menyinkronkan tombol toggle yang sudah ada.

Saat feature flag `ui_layout_v2` mati, controller memakai perilaku lama:
playlist selalu di kiri, inspector di kanan, keduanya tersembunyi sampai
tombolnya ditekan. Pane tetap bisa di-resize, tetapi edge/lebar tidak
dipersistensikan.
"""
from __future__ import annotations

from gi.repository import GLib, Gtk

from layout_config import (
    DEFAULT_EDGES,
    DOCK_NAMES,
    dock_sides,
    layout_v2_enabled,
    sanitize_layout,
)

_HANDLE_FALLBACK = 8


class DockLayout:
    """Menyusun sidebar/inspector sebagai `Gtk.Paned` dock."""

    def __init__(self, window, config, sidebar, inspector, center):
        self.window = window
        self.config = config
        self.widgets = {"playlist": sidebar, "inspector": inspector}
        self.center = center
        self.root = None

        self._enabled = layout_v2_enabled(config)
        self._legacy_visible = {"playlist": False, "inspector": False}
        self._suppressed = False
        self._applying = False
        self._suspend_persist = 0
        self._persist_ready = False
        self._panes: dict[str, tuple[Gtk.Paned, str]] = {}
        self._signature = None

        if self._enabled:
            state = self.state
            self._legacy_visible = {name: bool(state[name]["visible"]) for name in DOCK_NAMES}

        self.apply_config(force=True)

    # -- state ---------------------------------------------------------
    @property
    def state(self) -> dict:
        return sanitize_layout(self.config.get("layout"))

    def _effective_state(self, state: dict | None = None) -> dict:
        state = self.state if state is None else state
        if not self._enabled:
            for name in DOCK_NAMES:
                state[name]["edge"] = DEFAULT_EDGES[name]
                state[name]["visible"] = self._legacy_visible[name]
        if self._suppressed:
            for name in DOCK_NAMES:
                state[name]["visible"] = False
        return state

    def visible_width(self, name: str) -> int:
        """Lebar dock jika sedang tampil, selain itu 0 (untuk fit-window)."""
        state = self._effective_state()
        section = state[name]
        if section["visible"] and section["edge"] != "hidden":
            return int(section["width"])
        return 0

    # -- API untuk mixin -------------------------------------------------
    def apply_config(self, force: bool = False) -> None:
        """Baca ulang config dan terapkan ke widget."""
        enabled = layout_v2_enabled(self.config)
        if enabled != self._enabled:
            self._enabled = enabled
            if enabled:
                state = self.state
                self._legacy_visible = {
                    name: bool(state[name]["visible"]) for name in DOCK_NAMES
                }
            force = True

        state = self._effective_state()
        self._sync_buttons(state)
        self._sync_visibility(state)

        signature = dock_sides(state)
        if force or signature != self._signature:
            self._rebuild(state, signature)
        self._signature = signature

    def set_dock_visible(self, name: str, visible: bool) -> None:
        """Dipanggil oleh handler tombol toggle playlist/inspector."""
        if self._applying:
            return
        if not self._enabled:
            self._legacy_visible[name] = bool(visible)
            state = self._effective_state()
            self._sync_visibility(state)
            signature = dock_sides(state)
            if signature != self._signature:
                self._rebuild(state, signature)
                self._signature = signature
            return
        state = self.state
        if visible and state[name]["edge"] == "hidden":
            state[name]["edge"] = DEFAULT_EDGES[name]
        state[name]["visible"] = bool(visible)
        self._commit(state)

    def set_edge(self, name: str, edge: str) -> None:
        state = self.state
        state[name]["edge"] = edge
        if edge == "hidden":
            state[name]["visible"] = False
        self._commit(state)

    def set_width(self, name: str, width: int) -> None:
        state = self.state
        state[name]["width"] = width
        state = sanitize_layout(state)
        self.config["layout"] = state
        self._apply_width(name, state[name]["width"])
        self._save()

    def set_suppressed(self, suppressed: bool) -> None:
        """Sembunyikan semua dock tanpa mengubah preferensi (mini player)."""
        self._suppressed = bool(suppressed)
        self._sync_visibility(self._effective_state())

    def reset(self) -> None:
        from layout_config import default_layout

        self.config["layout"] = default_layout()
        if self._enabled:
            self._legacy_visible = {
                name: bool(self.config["layout"][name]["visible"]) for name in DOCK_NAMES
            }
        self.apply_config(force=True)

    # -- internal --------------------------------------------------------
    def _commit(self, state: dict) -> None:
        state = sanitize_layout(state)
        self.config["layout"] = state
        self._applying = True
        try:
            self._sync_buttons(self._effective_state(state))
            self._sync_visibility(self._effective_state(state))
            signature = dock_sides(state)
            if signature != self._signature:
                self._rebuild(self._effective_state(state), signature)
                self._signature = signature
        finally:
            self._applying = False
        self._save()

    def _save(self) -> None:
        save = getattr(self.window, "_save_config_throttled", None)
        if save is not None:
            save()

    def _sync_buttons(self, state: dict) -> None:
        for name, attr in (("playlist", "playlist_toggle"), ("inspector", "inspector_btn")):
            button = getattr(self.window, attr, None)
            if button is None:
                continue
            want = bool(state[name]["visible"]) and state[name]["edge"] != "hidden"
            if button.get_active() != want:
                self._applying = True
                try:
                    button.set_active(want)
                finally:
                    self._applying = False

    def _sync_visibility(self, state: dict) -> None:
        for name in DOCK_NAMES:
            widget = self.widgets[name]
            section = state[name]
            widget.set_visible(
                bool(section["visible"])
                and section["edge"] != "hidden"
                and not self._suppressed
            )

    def _rebuild(self, state: dict, signature: tuple[list[str], list[str]]) -> None:
        self._applying = True
        self._suspend_persist += 1
        self._persist_ready = False
        try:
            for widget in (*self.widgets.values(), self.center):
                if widget.get_parent() is not None:
                    widget.unparent()
            self._panes.clear()

            left, right = signature
            child = self.center
            for name in reversed(left):
                child = self._make_pane(name, state[name]["width"], "left", child)
            for name in right:
                child = self._make_pane(name, state[name]["width"], "right", child)

            self.root = child
            self.window.set_child(child)
        finally:
            self._sync_visibility(state)
            self._applying = False
            self._suspend_persist -= 1
        GLib.timeout_add(150, self._mark_persist_ready)

    def _mark_persist_ready(self) -> bool:
        self._persist_ready = True
        return False

    def _make_pane(self, name: str, width: int, side: str, child):
        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.set_wide_handle(True)
        paned.add_css_class("iina-dock-paned")

        if side == "left":
            paned.set_start_child(self.widgets[name])
            paned.set_end_child(child)
            paned.set_resize_start_child(False)
            paned.set_shrink_start_child(False)
            paned.set_resize_end_child(True)
            paned.set_shrink_end_child(True)
            paned.set_position(int(width))
        else:
            paned.set_start_child(child)
            paned.set_end_child(self.widgets[name])
            paned.set_resize_start_child(True)
            paned.set_shrink_start_child(False)
            paned.set_resize_end_child(False)
            paned.set_shrink_end_child(False)
            paned.set_position(-1)
            self._pin_right(paned, int(width))

        paned.connect(
            "notify::position",
            lambda widget, _pspec, n=name, s=side: self._on_position(n, s, widget),
        )
        self._panes[name] = (paned, side)
        return paned

    def _pin_right(self, paned: Gtk.Paned, width: int) -> None:
        """Set posisi awal pane kanan setelah alokasi pertama."""
        done = {"value": False}

        def on_width(widget, _pspec):
            if done["value"] or widget.get_width() <= 0:
                return
            done["value"] = True
            self._suspend_persist += 1
            try:
                widget.set_position(max(1, widget.get_width() - width))
            finally:
                self._suspend_persist -= 1

        paned.connect("notify::width", on_width)

    def _on_position(self, name: str, side: str, paned: Gtk.Paned) -> None:
        if (
            not self._enabled
            or self._applying
            or self._suppressed
            or not self._persist_ready
            or self._suspend_persist
        ):
            return
        position = paned.get_position()
        if side == "left":
            width = position
        else:
            total = paned.get_width()
            if total <= 0:
                return
            width = total - position
        if width <= 0:
            return

        state = self.state
        probe = {**state, name: {**state[name], "width": int(width)}}
        clean = sanitize_layout(probe)
        if clean[name]["width"] == state[name]["width"]:
            return
        self.config["layout"] = clean
        self._save()

    def _apply_width(self, name: str, width: int) -> None:
        entry = self._panes.get(name)
        if entry is None:
            return
        paned, side = entry
        self._suspend_persist += 1
        try:
            if side == "left":
                paned.set_position(int(width))
            elif paned.get_width() > 0:
                paned.set_position(max(1, paned.get_width() - int(width)))
        finally:
            self._suspend_persist -= 1
