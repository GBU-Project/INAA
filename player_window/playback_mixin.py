"""Core transport: open/play/pause, volume, speed, chapters, A-B loop, music mode, state polling."""
import os

from gi.repository import GLib, Gtk

from fmt import display_name as _display_name, format_speed, format_time as _format_time
from media_uri import is_allowed_media_uri, is_http_media_uri, normalize_media_uri
from playlist_nav import auto_advance_index

from .media_types import AUDIO_EXTENSIONS


class PlaybackMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    @property
    def player(self):
        return self.gl_area.player

    def open_file(self, path, resume_pos=None):
        path = normalize_media_uri(path)
        if not is_allowed_media_uri(path):
            self.show_toast("URI media tidak diizinkan")
            return
        try:
            self.player["ytdl"] = bool(is_http_media_uri(path))
        except Exception:
            pass
        self._current_path = path

        # Jika resume_pos tidak diberikan secara eksplisit, cari riwayat posisi terakhir dari config
        if resume_pos is None and self._config.get("resume_playback", True):
            recents = self._config.get("recent_files", [])
            for item in recents:
                if item.get("path") == path:
                    saved_p = item.get("position", 0)
                    dur = item.get("duration", 0)
                    if saved_p > 5 and (dur == 0 or saved_p < dur - 5):
                        resume_pos = saved_p
                    break

        self._pending_resume_pos = resume_pos
        if path not in self.playlist:
            self.playlist.append(path)
            # Smart Auto-Load Folder Media (ala IINA: otomatis mengisi daftar putar jika memutar file lokal)
            self._auto_populate_folder_playlist(path)
            self._refresh_sidebar()
        self.playlist_index = self.playlist.index(path)

        # PENTING: pindah ke halaman video/music di display_stack SEBELUM
        # memanggil player.play(). Gtk.Stack tidak me-realize child yang
        # sedang tersembunyi, jadi kalau gl_area (halaman "video") belum
        # terlihat saat play() dipanggil, mpv render context belum ada dan
        # loadfile akan gagal secara senyap ("No render context set").
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS:
            self.set_music_mode(True)
        else:
            if not self.music_toggle_btn.get_active():
                self.set_music_mode(False)
            else:
                self.display_stack.set_visible_child_name("music")

        self.player.play(path)
        self.player.pause = False
        self._has_played_media = False
        self._highlight_current_row()
        self._reset_ab_loop()

        # Bersihkan cache thumbnail untuk file baru
        self._thumb_cache.clear()
        self._thumb_pending.clear()

        self._window_fitted_for = None
        self._reveal_chrome()

        # Update trek, metadata musik, & chapter setelah media dimuat
        GLib.timeout_add(600, self._on_media_loaded)

        # Panggil hook plugin on_file_open
        self._trigger_plugin_hook("on_file_open", path)

    def _on_media_loaded(self):
        self._rebuild_track_menu()
        self._update_chapters()
        self._update_music_metadata()

        # Terapkan resume position jika ada
        if self._pending_resume_pos is not None and self._pending_resume_pos > 0:
            try:
                dur = self.player.duration or 0
                if dur > 0 and self._pending_resume_pos < dur - 2:
                    self.player.seek(self._pending_resume_pos, reference="absolute")
                    self.show_toast(f"Melanjutkan dari {_format_time(self._pending_resume_pos)}")
            except Exception:
                pass
            self._pending_resume_pos = None

        # Catat ke riwayat file terakhir diputar
        try:
            dur = self.player.duration or 0
            pos = self.player.time_pos or 0
            self._record_recent_file(self._current_path, pos=pos, duration=dur)
        except Exception:
            pass

        try:
            meta = self.player.metadata or {}
            media_title = meta.get("title") or (self.player.media_title if hasattr(self.player, "media_title") else None)
            if not media_title and self._current_path:
                media_title = _display_name(self._current_path)
            if media_title:
                self.set_title(f"{media_title} — INAA")
        except Exception:
            pass
        return False

    def _update_music_metadata(self):
        if not self._current_path:
            return
        try:
            meta = self.player.metadata or {}
            title = meta.get("title") or os.path.basename(self._current_path)
            artist = meta.get("artist") or meta.get("album_artist") or "Artis Tidak Diketahui"
            album = meta.get("album")
            if album:
                artist += f" • {album}"
            self.music_title.set_text(title)
            self.music_artist.set_text(artist)
        except Exception:
            self.music_title.set_text(os.path.basename(self._current_path))
            self.music_artist.set_text("—")

    def on_music_mode_toggled(self, button):
        self.set_music_mode(button.get_active())

    def set_music_mode(self, active):
        self._is_music_mode = active
        self.music_toggle_btn.set_active(active)
        if active:
            self.display_stack.set_visible_child_name("music")
            self._update_music_metadata()
        else:
            self.display_stack.set_visible_child_name("video")

    def _update_chapters(self):
        try:
            chapters = self.player.chapter_list or []
            self._chapters = chapters
            self.seekbar.clear_marks()
            duration = self.player.duration or 0

            if chapters and duration > 0:
                self.chapter_menu_btn.set_visible(True)
                self.prev_chapter_btn.set_sensitive(True)
                self.next_chapter_btn.set_sensitive(True)
                for ch in chapters:
                    time = ch.get("time", 0)
                    scale_pos = (time / duration) * 1000.0
                    self.seekbar.add_mark(scale_pos, Gtk.PositionType.BOTTOM, None)
            else:
                self.prev_chapter_btn.set_sensitive(False)
                self.next_chapter_btn.set_sensitive(False)
        except Exception:
            pass

    def on_playpause_clicked(self, button):
        self.player.pause = not self.player.pause
        self._update_playpause_icon()
        if self.player.pause:
            self._reveal_chrome()

    def on_volume_changed(self, scale):
        vol = scale.get_value()
        self.player.volume = vol
        self._config["volume"] = vol
        self._save_config_throttled()

    def on_mute_clicked(self, button):
        try:
            self.player.mute = not self.player.mute
            icon = "audio-volume-muted-symbolic" if self.player.mute else "audio-volume-high-symbolic"
            self.vol_btn.set_icon_name(icon)
        except Exception:
            pass

    def on_fullscreen_clicked(self, button):
        if self.is_fullscreen():
            self.unfullscreen()
            if not self._is_mini:
                self.header.set_visible(True)
        else:
            self.fullscreen()
            self.header.set_visible(False)

    def on_mini_toggled(self, button):
        self._is_mini = button.get_active()
        if self._is_mini:
            self._normal_size = (self.get_width(), self.get_height())
            self.header.set_visible(False)
            self.sidebar.set_visible(False)
            self.inspector_panel.set_visible(False)
            self.set_default_size(360, 220)
            self._set_always_on_top(bool(self._config.get("keep_above_mini", True)))
            self.osd_box.set_visible(True)
            self.osd_box.remove_css_class("hidden")
        else:
            self.header.set_visible(True)
            self.set_default_size(*self._normal_size)
            self._set_always_on_top(False)
            if self.playlist_toggle.get_active():
                self.sidebar.set_visible(True)
            if self.inspector_btn.get_active():
                self.inspector_panel.set_visible(True)

    def _set_always_on_top(self, enabled):
        try:
            native = self.get_native()
            surface = native.get_surface() if native else None
            if surface is not None and hasattr(surface, "set_keep_above"):
                surface.set_keep_above(bool(enabled))
                return
        except Exception:
            pass
        try:
            self.set_keep_above(bool(enabled))
        except Exception:
            pass

    def _update_playpause_icon(self):
        icon_name = "media-playback-pause-symbolic" if not self.player.pause else "media-playback-start-symbolic"
        self.playpause_btn.set_icon_name(icon_name)

    def _poll_mpv_state(self):
        try:
            pos = self.player.time_pos or 0
            duration = self.player.duration or 0
            if not self._seekbar_user_dragging and duration > 0:
                self.seekbar.set_value((pos / duration) * 1000.0)
            self.time_label.set_text(_format_time(pos))
            self.duration_label.set_text(_format_time(duration))
            self._update_playpause_icon()

            # Pastikan tampilan tetap pada video jika memutar stream video
            # (tapi jangan sentuh display_stack kalau video sedang di
            # jendela terpisah/detach — "video" tidak lagi terdaftar di
            # situ, jadi set_visible_child_name akan gagal terus-menerus).
            if not self.player.pause and self._current_path:
                if not self._is_music_mode:
                    if self.display_stack.get_visible_child_name() != "video":
                        self.display_stack.set_visible_child_name("video")
                self.gl_area.queue_render()

                # Simpan posisi periodik ke konfigurasi setiap ~10 detik
                if int(pos) > 0 and int(pos) % 10 == 0:
                    self._update_current_recent_position()

            current_spd = self.player.speed or 1.0
            spd_text = format_speed(current_spd)
            if self.playback_opts_btn.get_label() != spd_text:
                self.playback_opts_btn.set_label(spd_text)

            # Sinkronkan status ke MPRIS (now-playing GNOME/KDE, media keys, dll)
            self.mpris.notify_state_changed()

            # Deteksi pemutaran aktif untuk logika auto-advance playlist
            if pos > 0.5:
                self._has_played_media = True

            if duration > 0 and self._window_fitted_for != self._current_path:
                self._fit_window_to_video()

            # Auto-advance ke trek berikutnya di playlist saat lagu/video selesai
            if self._has_played_media and self._current_path:
                current_mpv_path = None
                try:
                    current_mpv_path = self.player.path
                except Exception:
                    pass

                is_finished = (current_mpv_path is None) or (duration > 0 and pos >= duration - 0.35)
                if is_finished:
                    self._has_played_media = False
                    nxt = auto_advance_index(
                        self.playlist_index,
                        len(self.playlist),
                        self._loop_mode,
                        self._shuffle,
                    )
                    if nxt is not None:
                        next_path = self.playlist[nxt]
                        GLib.idle_add(lambda p=next_path: self.open_file(p))
        except Exception:
            pass
        return True

    def _set_speed(self, speed):
        self.player.speed = speed
        self.playback_opts_btn.set_label(format_speed(speed))
        self.playback_opts_popover.popdown()

    def change_speed(self, delta):
        current = round(self.player.speed or 1.0, 2)
        new_speed = max(0.25, min(4.0, current + delta))
        self.player.speed = new_speed
        self.playback_opts_btn.set_label(format_speed(new_speed))

    def toggle_ab_loop(self):
        if self._ab_state == 0:
            pos = self.player.time_pos or 0
            self.player["ab-loop-a"] = pos
            self.player["ab-loop-b"] = "no"
            self._ab_state = 1
            self.ab_label.set_text(f"[Loop: A {_format_time(pos)} → ?]")
        elif self._ab_state == 1:
            pos = self.player.time_pos or 0
            self.player["ab-loop-b"] = pos
            self._ab_state = 2
            a_pos = self.player["ab-loop-a"] or 0
            self.ab_label.set_text(f"[Loop: {_format_time(a_pos)} ⟲ {_format_time(pos)}]")
        else:
            self._reset_ab_loop()
        self.playback_opts_popover.popdown()

    def _fit_window_to_video(self):
        if not self._config.get("fit_window", True):
            return
        if self._is_mini or self.is_fullscreen() or self._is_music_mode:
            return
        try:
            w = int(self.player.width or 0)
            h = int(self.player.height or 0)
        except Exception:
            return
        if w <= 0 or h <= 0:
            return
        self._window_fitted_for = self._current_path
        try:
            display = self.get_display()
            monitor = display.get_monitor_at_surface(self.get_native().get_surface()) if display else None
            geo = monitor.get_geometry() if monitor else None
            max_w = int((geo.width if geo else 1600) * 0.85)
            max_h = int((geo.height if geo else 900) * 0.85)
        except Exception:
            max_w, max_h = 1600, 900
        chrome_h = 48 if self.header.get_visible() else 0
        extra_w = 0
        if self.sidebar.get_visible():
            extra_w += 240
        if self.inspector_panel.get_visible():
            extra_w += 280
        scale = min(max_w / max(w + extra_w, 1), max_h / max(h + chrome_h, 1), 1.0)
        target_w = max(480, int(w * scale) + extra_w)
        target_h = max(270, int(h * scale) + chrome_h)
        self.set_default_size(target_w, target_h)

    def _reset_ab_loop(self):
        try:
            self.player["ab-loop-a"] = "no"
            self.player["ab-loop-b"] = "no"
        except Exception:
            pass
        self._ab_state = 0
        self.ab_label.set_text("")

    def navigate_chapter(self, delta):
        try:
            current = self.player.chapter
            if current is not None:
                new_ch = current + delta
                if 0 <= new_ch < len(self._chapters):
                    self.player.chapter = new_ch
        except Exception:
            pass

    def _seek_chapter(self, index):
        try:
            self.player.chapter = index
        except Exception:
            pass
        self.chapter_popover.popdown()

    def _rebuild_chapter_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        chapters = self._chapters
        if not chapters:
            label = Gtk.Label(label="Tidak ada data bab pada video ini")
            box.append(label)
        else:
            header_lbl = Gtk.Label(label="Daftar Bab (Chapters)")
            header_lbl.set_xalign(0)
            box.append(header_lbl)
            scroll = Gtk.ScrolledWindow()
            scroll.set_max_content_height(240)
            scroll.set_propagate_natural_height(True)
            list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for idx, ch in enumerate(chapters):
                title = ch.get("title") or f"Bab {idx + 1}"
                time_str = _format_time(ch.get("time", 0))
                btn = Gtk.Button(label=f"{idx + 1}. {title} ({time_str})")
                btn.connect("clicked", lambda b, i=idx: self._seek_chapter(i))
                list_box.append(btn)
            scroll.set_child(list_box)
            box.append(scroll)

        self.chapter_popover.set_child(box)

    def _rebuild_playback_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        # Speed title
        speed_label = Gtk.Label(label="Kecepatan Pemutaran")
        speed_label.set_xalign(0)
        box.append(speed_label)

        grid = Gtk.Grid()
        grid.set_column_spacing(4)
        grid.set_row_spacing(4)

        current_speed = round(self.player.speed or 1.0, 2)
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        for i, s in enumerate(speeds):
            btn = Gtk.Button(label=f"{s}x")
            if abs(current_speed - s) < 0.05:
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda b, val=s: self._set_speed(val))
            grid.attach(btn, i % 3, i // 3, 1, 1)
        box.append(grid)

        # A-B Loop Section
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box.append(sep)

        ab_title = Gtk.Label(label="A-B Loop")
        ab_title.set_xalign(0)
        box.append(ab_title)

        ab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_toggle_ab = Gtk.Button(label="Langkah Loop (l)")
        btn_toggle_ab.connect("clicked", lambda *_: self.toggle_ab_loop())
        ab_box.append(btn_toggle_ab)

        btn_clear_ab = Gtk.Button(label="Reset Loop")
        btn_clear_ab.connect("clicked", lambda *_: self._reset_ab_loop())
        ab_box.append(btn_clear_ab)
        box.append(ab_box)

        self.playback_opts_popover.set_child(box)

