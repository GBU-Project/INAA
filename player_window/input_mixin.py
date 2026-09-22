"""Mouse/keyboard/gesture handling, seekbar scrubbing, thumbnail previews."""
from .common import *  # noqa: F401,F403


class InputMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def _on_video_left_click(self, gesture, n_press, x, y):
        if n_press == 1:
            self.on_playpause_clicked(None)
        elif n_press == 2:
            if self._is_mini:
                self.mini_btn.set_active(False)
            else:
                self.on_fullscreen_clicked(None)

    def _on_video_drag_begin(self, gesture, start_x, start_y):
        self._drag_start_pos = (start_x, start_y)

    def _on_video_drag_end(self, gesture, offset_x, offset_y):
        # Jika mouse ditarik keluar atau lebih dari 120px, detach window
        dist = (offset_x**2 + offset_y**2)**0.5
        if dist > 120 and not self.is_fullscreen() and not self._is_mini:
            self.detach_video_window()
        self._drag_start_pos = None

    def _on_video_scroll(self, controller, dx, dy):
        """IINA-style trackpad / mouse gesture:
        Scroll vertikal: Naik/turunkan volume
        Scroll horizontal: Seek mundur/maju
        """
        # Tangani scroll vertikal (Volume)
        if abs(dy) >= 0.1:
            step = -dy * 2.0  # Scroll ke atas dy < 0 -> volume bertambah
            cur_vol = self.volume_scale.get_value()
            new_vol = max(0.0, min(100.0, cur_vol + step))
            self.volume_scale.set_value(new_vol)
            self.show_toast(f"🔊 Volume: {int(new_vol)}%", duration_ms=1200)
            return True

        # Tangani scroll horizontal (Seeking)
        if abs(dx) >= 0.1:
            seek_delta = dx * 2.0  # Scroll ke kanan dx > 0 -> maju
            try:
                self.player.seek(seek_delta, reference="relative")
                pos = self.player.time_pos or 0
                dur = self.player.duration or 0
                self.show_toast(f"⏩ {_format_time(pos)} / {_format_time(dur)}", duration_ms=1200)
            except Exception:
                pass
            return True

        return False

    def on_key_press(self, controller, keyval, keycode, state):
        name = Gdk.keyval_name(keyval)
        if name == "Escape":
            if self._is_mini:
                self.mini_btn.set_active(False)
                return True
            elif self.is_fullscreen():
                self.unfullscreen()
                return True
        elif name == "space":
            self.on_playpause_clicked(None)
            return True
        elif name == "i":  # Inspector toggle
            if not self._is_mini:
                self.inspector_btn.set_active(not self.inspector_btn.get_active())
                return True
        elif name == "Right":
            self.player.seek(SEEK_STEP_SECONDS, reference="relative")
            return True
        elif name == "Left":
            self.player.seek(-SEEK_STEP_SECONDS, reference="relative")
            return True
        elif name == "Up":
            self.volume_scale.set_value(min(100, self.volume_scale.get_value() + VOLUME_STEP))
            return True
        elif name == "Down":
            self.volume_scale.set_value(max(0, self.volume_scale.get_value() - VOLUME_STEP))
            return True
        elif name == "f":
            self.on_fullscreen_clicked(None)
            return True
        elif name == "bracketleft":  # [ kurangi speed
            self.change_speed(-0.25)
            return True
        elif name == "bracketright":  # ] tambah speed
            self.change_speed(0.25)
            return True
        elif name in ("backslash", "BackSpace"):  # reset speed 1.0x
            self._set_speed(1.0)
            return True
        elif name == "l":  # A-B loop toggle
            self.toggle_ab_loop()
            return True
        elif name == "m":  # mute toggle
            self.on_mute_clicked(None)
            return True
        elif name == "s":  # screenshot / capture frame
            self.take_screenshot()
            return True
        elif name == "d":  # detach / separate video window
            self.detach_video_window()
            return True
        elif name == "Page_Up":  # previous chapter
            self.navigate_chapter(-1)
            return True
        elif name == "Page_Down":  # next chapter
            self.navigate_chapter(1)
            return True
        return False

    def on_drop(self, drop_target, gfile, x, y):
        path = gfile.get_path() if gfile else None
        if not path or not os.path.isfile(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext in SUBTITLE_EXTENSIONS:
            self._add_and_select_subtitle(path)
            return True
        self.add_to_playlist(path)
        self.open_file(path)
        return True

    def _on_video_motion(self, controller, x, y):
        # Tampilkan OSD saat kursor bergerak
        if not self.osd_box.get_visible():
            self.osd_box.set_visible(True)

        if self._osd_hide_timeout_id:
            GLib.source_remove(self._osd_hide_timeout_id)
            self._osd_hide_timeout_id = None

        # Sembunyikan OSD jika video sedang play dan tidak sedang drag seekbar setelah 3 detik
        if not self.player.pause and not self._seekbar_user_dragging and not self._is_mini:
            self._osd_hide_timeout_id = GLib.timeout_add(3000, self._hide_osd_callback)

    def _hide_osd_callback(self):
        if not self.player.pause and not self._seekbar_user_dragging and not self._is_mini:
            self.osd_box.set_visible(False)
        self._osd_hide_timeout_id = None
        return False

    def _on_seekbar_motion(self, controller, x, y):
        try:
            duration = self.player.duration or 0
            alloc_width = self.seekbar.get_width()
            if duration > 0 and alloc_width > 0:
                fraction = max(0.0, min(1.0, x / alloc_width))
                hover_time = fraction * duration
                time_str = _format_time(hover_time)
                self.thumb_label.set_text(time_str)

                rect = Gdk.Rectangle()
                rect.x = int(x)
                rect.y = 0
                rect.width = 1
                rect.height = 1
                self.thumb_popover.set_pointing_to(rect)
                self.thumb_popover.popup()

                # Request thumbnail frame jika bukan URL online dan bukan file audio
                if is_local_media_file(self._current_path):
                    ext = os.path.splitext(self._current_path)[1].lower()
                    if ext not in AUDIO_EXTENSIONS:
                        self._request_thumbnail(int(hover_time))
        except Exception:
            pass

    def _on_seekbar_leave(self, controller):
        self.thumb_popover.popdown()

    def _request_thumbnail(self, sec):
        path = self._current_path
        if not is_local_media_file(path):
            return
        if sec in self._thumb_cache:
            self.thumb_picture.set_filename(self._thumb_cache[sec])
            return
        if sec in self._thumb_pending:
            return

        self._thumb_pending.add(sec)
        media_path = os.path.realpath(path)
        stamp = int(sec)

        def extract():
            out_file = os.path.join(self._thumb_temp_dir, f"thumb_{stamp}.jpg")
            try:
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-nostdin",
                    "-protocol_whitelist", "file",
                    "-ss", str(stamp),
                    "-i", media_path,
                    "-vframes", "1",
                    "-s", "160x90",
                    "-f", "image2",
                    "-y", out_file,
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                if os.path.isfile(out_file):
                    self._thumb_cache[stamp] = out_file
                    GLib.idle_add(lambda: self._on_thumbnail_ready(stamp, out_file))
            except Exception:
                pass
            finally:
                self._thumb_pending.discard(stamp)

        threading.Thread(target=extract, daemon=True).start()

    def _on_thumbnail_ready(self, sec, file_path):
        if self.thumb_popover.get_visible():
            self.thumb_picture.set_filename(file_path)

    def _set_dragging(self, value):
        self._seekbar_user_dragging = value

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self._apply_seek()
        self._seekbar_user_dragging = False

    def _on_seekbar_value_changed(self, scale):
        if self._seekbar_user_dragging:
            self._apply_seek()

    def _apply_seek(self):
        fraction = self.seekbar.get_value() / 1000.0
        try:
            duration = self.player.duration or 0
            if duration > 0:
                self.player.seek(fraction * duration, reference="absolute")
        except Exception:
            pass

