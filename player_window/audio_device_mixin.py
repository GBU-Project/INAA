"""Perangkat output audio: dropdown di tab Audio inspector + penerapan saat start."""
import logging

import audio_devices

from .common import *  # noqa: F401,F403


class AudioDeviceMixin:
    """Mixed into PlayerWindow. Logika murni ada di audio_devices.py."""

    def _read_audio_devices(self):
        try:
            return audio_devices.parse_device_list(self.player.audio_device_list)
        except Exception as exc:
            logging.getLogger("inaa").warning("Gagal membaca daftar perangkat audio: %s", exc)
            return audio_devices.parse_device_list(None)

    def _apply_saved_audio_device(self):
        """Dipanggil saat start. Perangkat yang hilang -> 'auto' (config tidak ditimpa)."""
        saved = self._config.get("audio_device", audio_devices.AUTO)
        target = audio_devices.choose_device(saved, self._read_audio_devices())
        if target == audio_devices.AUTO and saved == audio_devices.AUTO:
            return  # sudah default
        try:
            self.player["audio-device"] = target
        except Exception as exc:
            logging.getLogger("inaa").warning("Gagal memilih perangkat audio: %s", exc)

    def _build_audio_device_section(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label="Perangkat Output Audio:")
        title.set_xalign(0)
        title.add_css_class("iina-sec-title")
        box.append(title)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._audio_device_model = Gtk.StringList()
        self.audio_device_dropdown = Gtk.DropDown(model=self._audio_device_model)
        self.audio_device_dropdown.set_hexpand(True)
        self.audio_device_dropdown.connect("notify::selected", self._on_audio_device_selected)
        row.append(self.audio_device_dropdown)

        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text("Muat ulang daftar perangkat (mis. setelah mencolok headphone)")
        refresh.connect("clicked", lambda *_: self._refresh_audio_devices(toast=True))
        row.append(refresh)
        box.append(row)

        self._audio_device_names = []
        self._audio_device_syncing = False
        self._refresh_audio_devices()
        return box

    def _refresh_audio_devices(self, toast=False):
        devices = self._read_audio_devices()
        current = audio_devices.choose_device(self._config.get("audio_device"), devices)
        self._audio_device_syncing = True
        try:
            self._audio_device_names = [n for n, _ in devices]
            self._audio_device_model.splice(0, self._audio_device_model.get_n_items(), [l for _, l in devices])
            self.audio_device_dropdown.set_selected(self._audio_device_names.index(current))
        finally:
            self._audio_device_syncing = False
        if toast:
            self.show_toast(f"{len(devices) - 1} perangkat audio ditemukan")

    def _on_audio_device_selected(self, dropdown, _pspec):
        if self._audio_device_syncing:
            return
        index = dropdown.get_selected()
        if not (0 <= index < len(self._audio_device_names)):
            return
        self._set_audio_device(self._audio_device_names[index])

    def _set_audio_device(self, name):
        """Hanya nama yang ada di daftar mpv yang diterima."""
        devices = self._read_audio_devices()
        if audio_devices.choose_device(name, devices) != name:
            self.show_toast("Perangkat audio tidak tersedia")
            return False
        try:
            self.player["audio-device"] = name
        except Exception as exc:
            self.show_toast(f"Gagal memilih perangkat audio: {exc}")
            return False
        self._config["audio_device"] = name
        self._save_config_throttled(force=True)
        label = dict(devices).get(name, name)
        self.show_toast(f"Output audio: {label}")
        return True
