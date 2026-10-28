"""Recent files, folder auto-discovery, sidebar playlist and config persistence."""
import datetime
import os
import time

from gi.repository import Gtk, Pango

from fmt import display_name as _display_name, format_time as _format_time
from m3u_parser import export_m3u, parse_m3u
from media_uri import is_allowed_media_uri, is_local_media_file, normalize_media_uri
from playlist_nav import next_playlist_index

from .common import _save_config
from .media_types import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS


class PlaylistMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def _populate_recent_files(self):
        # Bersihkan isi listbox terlebih dahulu
        child = self.recent_listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.recent_listbox.remove(child)
            child = nxt

        recents = self._config.get("recent_files", [])[:8]
        if not recents:
            empty_lbl = Gtk.Label(label="Belum ada file yang diputar")
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_valign(Gtk.Align.CENTER)
            empty_lbl.set_vexpand(True)
            self.recent_listbox.append(empty_lbl)
            return

        for item in recents:
            path = item.get("path")
            if not path:
                continue

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("iina-recent-row")

            # Icon video/audio
            icon_name = "audio-x-generic-symbolic" if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS else "video-x-generic-symbolic"
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(20)
            row.append(img)

            # Text info
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            title_txt = item.get("title") or _display_name(path)
            t_lbl = Gtk.Label(label=title_txt)
            t_lbl.set_halign(Gtk.Align.START)
            t_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            t_lbl.add_css_class("iina-recent-title")
            info_box.append(t_lbl)

            pos = item.get("position", 0)
            dur = item.get("duration", 0)
            if dur > 0 and pos > 0:
                time_str = f"Lanjutkan dari {_format_time(pos)} / {_format_time(dur)}"
            elif dur > 0:
                time_str = f"Durasi: {_format_time(dur)}"
            else:
                time_str = path
            s_lbl = Gtk.Label(label=time_str)
            s_lbl.set_halign(Gtk.Align.START)
            s_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            s_lbl.add_css_class("iina-recent-sub")
            info_box.append(s_lbl)

            row.append(info_box)

            # Play button on right
            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_has_frame(False)
            play_btn.set_valign(Gtk.Align.CENTER)
            row.append(play_btn)

            # Gesture click to open and resume
            missing = "://" not in path and not os.path.exists(path)
            if missing:
                row.set_opacity(0.55)
                play_btn.set_sensitive(False)
                s_lbl.set_text("File tidak ditemukan")
                gesture = Gtk.GestureClick()
                gesture.connect("released", lambda *_: self.show_toast("File tidak ditemukan"))
            else:
                gesture = Gtk.GestureClick()
                ext = os.path.splitext(path)[1].lower()
                r_pos = None if ext in AUDIO_EXTENSIONS else pos
                gesture.connect("released", lambda _g, _n, _x, _y, p=path, resume_pos=r_pos: self.open_file(p, resume_pos=resume_pos))
            row.add_controller(gesture)

            self.recent_listbox.append(row)

    def _clear_recent_files(self):
        self._config["recent_files"] = []
        _save_config(self._config)
        self._populate_recent_files()

    def _record_recent_file(self, path, pos=0, duration=0):
        if not path:
            return
        recents = self._config.get("recent_files", [])
        # Hapus duplikat path yang sama jika sudah ada
        recents = [r for r in recents if r.get("path") != path]

        title = os.path.basename(path)
        try:
            meta = self.player.metadata or {}
            media_title = meta.get("title") or (self.player.media_title if hasattr(self.player, "media_title") else None)
            if media_title:
                title = media_title
        except Exception:
            pass

        now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        recents.insert(0, {
            "path": path,
            "title": title,
            "position": round(pos, 1) if pos else 0,
            "duration": round(duration, 1) if duration else 0,
            "last_played": now_ts,
        })
        # Simpan hingga 100 riwayat pemutaran (ala IINA)
        self._config["recent_files"] = recents[:100]
        self._save_config_throttled(force=True)
        # Update tampilan jika welcome view sedang aktif
        if hasattr(self, "recent_listbox"):
            self._populate_recent_files()

    def _update_current_recent_position(self):
        if not self._current_path:
            return
        try:
            pos = self.player.time_pos or 0
            dur = self.player.duration or 0
            if dur > 0 and pos > 0:
                recents = self._config.get("recent_files", [])
                now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                for item in recents:
                    if item.get("path") == self._current_path:
                        item["position"] = round(pos, 1)
                        item["duration"] = round(dur, 1)
                        item["last_played"] = now_ts
                        break
                self._save_config_throttled()
        except Exception:
            pass

    def _save_config_throttled(self, force=False):
        now = time.monotonic()
        if not force and (now - self._last_config_save) < 8.0:
            return
        self._last_config_save = now
        _save_config(self._config)

    def _auto_populate_folder_playlist(self, current_file_path):
        """Mendeteksi berkas media lain di folder yang sama dan menambahkannya
        secara berurutan ke playlist (fitur Smart Next Episode ala IINA)."""
        try:
            if not is_local_media_file(current_file_path):
                return
            folder = os.path.dirname(current_file_path)
            if not os.path.isdir(folder):
                return

            valid_extensions = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
            entries = []
            for item in sorted(os.listdir(folder)):
                full_p = os.path.join(folder, item)
                if os.path.isfile(full_p):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in valid_extensions:
                        entries.append(full_p)

            # Tambahkan berkas yang belum ada di playlist dengan urutan rapi
            for p in entries:
                if p not in self.playlist:
                    self.playlist.append(p)
        except Exception:
            pass

    def add_to_playlist(self, path):
        path = normalize_media_uri(path)
        if not is_allowed_media_uri(path):
            return
        if path and path not in self.playlist:
            self.playlist.append(path)
            self._refresh_sidebar()

    def play_relative(self, delta):
        if not self.playlist:
            return
        new_index = next_playlist_index(
            self.playlist_index,
            len(self.playlist),
            delta,
            self._loop_mode,
            self._shuffle,
        )
        if new_index is not None:
            self.open_file(self.playlist[new_index])

    def _set_loop_mode(self, mode):
        if mode not in ("off", "all", "one"):
            mode = "off"
        self._loop_mode = mode
        self._config["loop_mode"] = mode
        self._save_config_throttled(force=True)
        self._update_loop_button()
        self._sync_prefs_loop_buttons()
        labels = {"off": "Ulangi: Mati", "all": "Ulangi: Semua", "one": "Ulangi: Satu"}
        self.show_toast(labels[mode])

    def cycle_loop_mode(self, _button=None):
        self._set_loop_mode({"off": "all", "all": "one", "one": "off"}.get(self._loop_mode, "all"))

    def _set_shuffle(self, enabled, from_ui=False):
        enabled = bool(enabled)
        if getattr(self, "_updating_shuffle_ui", False):
            return
        changed = self._shuffle != enabled
        self._shuffle = enabled
        self._config["shuffle"] = enabled
        if changed:
            self._save_config_throttled(force=True)
        self._update_shuffle_buttons()
        if from_ui and changed:
            self.show_toast("Acak: Aktif" if enabled else "Acak: Mati")

    def _update_shuffle_buttons(self):
        self._updating_shuffle_ui = True
        try:
            for btn in (getattr(self, "shuffle_btn", None), getattr(self, "osd_shuffle_btn", None)):
                if btn is not None and btn.get_active() != self._shuffle:
                    btn.set_active(self._shuffle)
        finally:
            self._updating_shuffle_ui = False

    def _update_loop_button(self):
        icons = {
            "off": "media-playlist-consecutive-symbolic",
            "all": "media-playlist-repeat-symbolic",
            "one": "media-playlist-repeat-song-symbolic",
        }
        tips = {
            "off": "Ulangi: Mati (klik untuk Semua)",
            "all": "Ulangi: Semua (klik untuk Satu)",
            "one": "Ulangi: Satu trek (klik untuk Mati)",
        }
        icon = icons.get(self._loop_mode, icons["off"])
        tip = tips.get(self._loop_mode, tips["off"])
        for btn in (getattr(self, "loop_btn", None), getattr(self, "osd_loop_btn", None)):
            if btn is None:
                continue
            btn.set_icon_name(icon)
            btn.set_tooltip_text(tip)

    def _refresh_sidebar(self):
        child = self.sidebar_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.sidebar_list.remove(child)
            child = nxt
        for path in self.playlist:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=_display_name(path))
            label.set_xalign(0)
            label.set_margin_start(8)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            row.set_child(label)
            self.sidebar_list.append(row)
        self._highlight_current_row()

    def _highlight_current_row(self):
        row = self.sidebar_list.get_row_at_index(self.playlist_index)
        if row is not None:
            self.sidebar_list.select_row(row)

    def on_playlist_toggled(self, button):
        self.sidebar.set_visible(button.get_active())

    def on_playlist_row_activated(self, listbox, row):
        index = row.get_index()
        if 0 <= index < len(self.playlist):
            self.open_file(self.playlist[index])

    def load_m3u_file(self, m3u_path):
        """Memuat daftar putar dari berkas .m3u / .m3u8."""
        entries = parse_m3u(m3u_path)
        if not entries:
            self.show_toast("Daftar putar kosong atau tidak valid")
            return
        self.playlist = entries
        self.playlist_index = 0
        self._refresh_sidebar()
        self.open_file(self.playlist[0])
        self.show_toast(f"Memuat {len(entries)} trek dari playlist")

    def _open_m3u_dialog(self, _button=None):
        dialog = Gtk.FileChooserDialog(
            title="Buka Playlist M3U",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Buka", Gtk.ResponseType.OK,
        )
        f_filter = Gtk.FileFilter()
        f_filter.set_name("Playlist (*.m3u, *.m3u8)")
        f_filter.add_pattern("*.m3u")
        f_filter.add_pattern("*.m3u8")
        dialog.add_filter(f_filter)

        def on_response(dlg, resp):
            if resp == Gtk.ResponseType.OK:
                gfile = dlg.get_file()
                if gfile:
                    path = gfile.get_path()
                    if path:
                        self.load_m3u_file(path)
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _export_m3u_dialog(self, _button=None):
        if not self.playlist:
            self.show_toast("Playlist saat ini kosong")
            return
        dialog = Gtk.FileChooserDialog(
            title="Simpan Playlist M3U",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Simpan", Gtk.ResponseType.OK,
        )
        dialog.set_current_name("playlist.m3u")

        def on_response(dlg, resp):
            if resp == Gtk.ResponseType.OK:
                gfile = dlg.get_file()
                if gfile:
                    path = gfile.get_path()
                    if path:
                        if not path.endswith(".m3u") and not path.endswith(".m3u8"):
                            path += ".m3u"
                        if export_m3u(path, self.playlist):
                            self.show_toast("Playlist berhasil disimpan")
                        else:
                            self.show_toast("Gagal menyimpan playlist")
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _clear_playlist(self, _button=None):
        self.playlist = []
        self.playlist_index = -1
        self._refresh_sidebar()
        self.show_toast("Playlist dikosongkan")

