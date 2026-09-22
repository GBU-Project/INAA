"""Recent files, folder auto-discovery, sidebar playlist and config persistence."""
from .common import *  # noqa: F401,F403


class PlaylistMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def _populate_recent_files(self):
        # Bersihkan isi listbox terlebih dahulu
        child = self.recent_listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.recent_listbox.remove(child)
            child = nxt

        recents = self._config.get("recent_files", [])
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
            gesture = Gtk.GestureClick()
            gesture.connect("released", lambda _g, _n, _x, _y, p=path, resume_pos=pos: self.open_file(p, resume_pos=resume_pos))
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

        recents.insert(0, {
            "path": path,
            "title": title,
            "position": round(pos, 1) if pos else 0,
            "duration": round(duration, 1) if duration else 0,
        })
        # Batasi riwayat maksimal 10 file
        self._config["recent_files"] = recents[:10]
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
                for item in recents:
                    if item.get("path") == self._current_path:
                        item["position"] = round(pos, 1)
                        item["duration"] = round(dur, 1)
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
        new_index = self.playlist_index + delta
        if 0 <= new_index < len(self.playlist):
            self.open_file(self.playlist[new_index])

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

