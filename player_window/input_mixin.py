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
        if not name:
            return False

        # Escape punya arti kontekstual (keluar mini-player / keluar fullscreen)
        # yang tidak cocok dimodelkan sebagai satu "action" tetap, jadi tetap
        # ditangani terpisah dari skema shortcut yang bisa dikonfigurasi.
        if name == "Escape":
            if self._is_mini:
                self.mini_btn.set_active(False)
                return True
            if self.is_fullscreen():
                self.unfullscreen()
                return True
            return False

        # Alias lama yang tidak masuk skema default (Backspace juga mereset speed).
        if name == "BackSpace":
            self._set_speed(1.0)
            return True

        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        alt = bool(state & Gdk.ModifierType.ALT_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        combo = combo_from_event(name, ctrl=ctrl, alt=alt, shift=shift)
        if not combo:
            return False

        shortcuts = merge_shortcuts(self._config.get("shortcuts"))
        action = invert_shortcuts(shortcuts).get(combo)
        if not action:
            return False

        handler = self._shortcut_actions().get(action)
        if not handler:
            # Action dikenal (mis. "history"/"edit_shortcuts") tapi belum ada
            # UI/handler untuk itu. Sengaja dibiarkan tidak melakukan apa-apa
            # daripada berpura-pura menangani sesuatu yang belum ada.
            return False
        handler()
        return True

    def _shortcut_actions(self):
        """Peta nama action (lihat keybindings.DEFAULT_SHORTCUTS) ke handler.

        Dibangun ulang tiap panggilan (murah) supaya selalu memakai method
        yang sudah ter-bind ke instance saat ini, tanpa perlu disimpan di
        __init__.
        """
        return {
            "play_pause": lambda: self.on_playpause_clicked(None),
            "seek_forward": lambda: self.player.seek(SEEK_STEP_SECONDS, reference="relative"),
            "seek_backward": lambda: self.player.seek(-SEEK_STEP_SECONDS, reference="relative"),
            "volume_up": lambda: self.volume_scale.set_value(
                min(100, self.volume_scale.get_value() + VOLUME_STEP)
            ),
            "volume_down": lambda: self.volume_scale.set_value(
                max(0, self.volume_scale.get_value() - VOLUME_STEP)
            ),
            "fullscreen": lambda: self.on_fullscreen_clicked(None),
            "inspector": self._toggle_inspector_shortcut,
            "mute": lambda: self.on_mute_clicked(None),
            "screenshot": self.take_screenshot,
            "mini_player": self.detach_video_window,
            "speed_down": lambda: self.change_speed(-0.25),
            "speed_up": lambda: self.change_speed(0.25),
            "speed_reset": lambda: self._set_speed(1.0),
            "ab_loop": self.toggle_ab_loop,
            "chapter_prev": lambda: self.navigate_chapter(-1),
            "chapter_next": lambda: self.navigate_chapter(1),
            "open_file": lambda: self.on_open_clicked(None),
            "open_url": lambda: self.on_open_url_clicked(None),
            "history": lambda: self.open_history_dialog(None),
            "edit_shortcuts": lambda: self.open_shortcuts_editor(None),
            "preferences": lambda: self.open_preferences(None),
        }

    def _toggle_inspector_shortcut(self):
        if not self._is_mini:
            self.inspector_btn.set_active(not self.inspector_btn.get_active())

    def on_drop(self, drop_target, gfile, x, y):
        path = gfile.get_path() if gfile else None
        if not path or not os.path.isfile(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext in (".m3u", ".m3u8"):
            self.load_m3u_file(path)
            return True
        if ext in SUBTITLE_EXTENSIONS:
            self._add_and_select_subtitle(path)
            return True
        self.add_to_playlist(path)
        self.open_file(path)
        return True

    def _on_video_motion(self, controller, x, y):
        self._reveal_chrome()
        if self._osd_hide_timeout_id:
            GLib.source_remove(self._osd_hide_timeout_id)
            self._osd_hide_timeout_id = None
        if self._should_auto_hide_chrome():
            delay = max(500, int(self._config.get("osd_hide_ms", 3000)))
            self._osd_hide_timeout_id = GLib.timeout_add(delay, self._hide_osd_callback)

    def _should_auto_hide_chrome(self):
        if not self._config.get("auto_hide_chrome", True):
            return False
        if self._is_mini or self._is_music_mode:
            return False
        if self._seekbar_user_dragging:
            return False
        try:
            if self.player.pause:
                return False
        except Exception:
            return False
        name = self.display_stack.get_visible_child_name()
        return name == "video" and bool(self._current_path)

    def _reveal_chrome(self):
        self._chrome_visible = True
        self.osd_box.set_visible(True)
        self.osd_box.remove_css_class("hidden")
        if not self._is_mini and not self.is_fullscreen():
            self.header.set_visible(True)

    def _hide_osd_callback(self):
        if self._should_auto_hide_chrome():
            self._chrome_visible = False
            self.osd_box.add_css_class("hidden")
            if not self._is_mini:
                self.header.set_visible(False)
            GLib.timeout_add(230, self._finish_hide_osd)
        self._osd_hide_timeout_id = None
        return False

    def _finish_hide_osd(self):
        if not self._chrome_visible and not self._is_mini:
            self.osd_box.set_visible(False)
        return False

    def _on_video_leave(self, controller):
        if self._osd_hide_timeout_id:
            GLib.source_remove(self._osd_hide_timeout_id)
            self._osd_hide_timeout_id = None
        if self._should_auto_hide_chrome():
            self._osd_hide_timeout_id = GLib.timeout_add(400, self._hide_osd_callback)

    def _on_seekbar_motion(self, controller, x, y):
        try:
            duration = self.player.duration or 0
            alloc_width = self.seekbar.get_width()
            if duration > 0 and alloc_width > 0:
                fraction = max(0.0, min(1.0, x / alloc_width))
                hover_time = fraction * duration
                time_str = _format_time(hover_time)
                self.thumb_time_label.set_text(time_str)

                rect = Gdk.Rectangle()
                rect.x = int(x)
                rect.y = 0
                rect.width = 1
                rect.height = 1
                self.thumb_popover.set_pointing_to(rect)
                self.thumb_popover.popup()

                # Request thumbnail grid if local video file
                if is_local_media_file(self._current_path):
                    ext = os.path.splitext(self._current_path)[1].lower()
                    if ext not in AUDIO_EXTENSIONS:
                        self._request_thumbnail_grid(int(hover_time))
        except Exception:
            pass

    def _on_seekbar_leave(self, controller):
        self.thumb_popover.popdown()

    def _request_thumbnail_grid(self, hover_sec):
        """Generate a 5x5 thumbnail grid centered around hover_sec using ffmpeg."""
        path = self._current_path
        if not is_local_media_file(path):
            return

        # Generate grid key based on the center time (rounded to 10-second intervals for caching)
        grid_center = (hover_sec // 10) * 10
        grid_key = f"grid_{grid_center}"

        if grid_key in self._thumb_cache:
            self._populate_thumb_grid(self._thumb_cache[grid_key])
            return
        if grid_key in self._thumb_pending:
            return

        self._thumb_pending.add(grid_key)
        media_path = os.path.realpath(path)

        def extract_grid():
            # Extract 25 frames: 12 before, center, 12 after (each ~2 seconds apart = ~50s window)
            # Using ffmpeg's tile filter to create a single image with 5x5 grid
            out_file = os.path.join(self._thumb_temp_dir, f"{grid_key}.jpg")
            try:
                # Calculate start time (center - 24 seconds, but not less than 0)
                start_sec = max(0, grid_center - 24)
                # Use fps=1/2 to get a frame every 2 seconds, then tile 5x5
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-nostdin",
                    "-protocol_whitelist", "file",
                    "-ss", str(start_sec),
                    "-i", media_path,
                    "-vf", "fps=1/2,scale=160:90,tile=5x5",
                    "-vframes", "1",
                    "-f", "image2",
                    "-y", out_file,
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                if os.path.isfile(out_file):
                    self._thumb_cache[grid_key] = out_file
                    GLib.idle_add(lambda: self._populate_thumb_grid(out_file))
            except Exception:
                pass
            finally:
                self._thumb_pending.discard(grid_key)

        threading.Thread(target=extract_grid, daemon=True).start()

    def _populate_thumb_grid(self, grid_image_path):
        """Populate the FlowBox with 25 thumbnails sliced from the grid image."""
        try:
            # Clear existing children
            child = self.thumb_grid.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                self.thumb_grid.remove(child)
                child = nxt

            # Load the grid image and slice into 5x5
            from gi.repository import GdkPixbuf
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(grid_image_path)
            if not pixbuf:
                return

            grid_w = pixbuf.get_width()
            grid_h = pixbuf.get_height()
            thumb_w = grid_w // 5
            thumb_h = grid_h // 5

            duration = self.player.duration or 0
            if duration <= 0:
                return

            grid_center = (int(self.thumb_time_label.get_text().split(':')[-1]) // 10) * 10 if ':' in self.thumb_time_label.get_text() else 0
            start_sec = max(0, grid_center - 24)

            for row in range(5):
                for col in range(5):
                    idx = row * 5 + col
                    sec = start_sec + idx * 2
                    if sec > duration:
                        break

                    # Create sub-pixbuf for this thumbnail
                    sub_pixbuf = GdkPixbuf.Pixbuf.new_subpixbuf(
                        pixbuf,
                        col * thumb_w,
                        row * thumb_h,
                        thumb_w,
                        thumb_h
                    )

                    picture = Gtk.Picture()
                    picture.set_pixbuf(sub_pixbuf)
                    picture.set_size_request(160, 90)
                    picture.add_css_class("iina-thumb-grid-item")

                    # Add time label overlay
                    time_label = Gtk.Label(label=_format_time(sec))
                    time_label.add_css_class("iina-thumb-time-label")
                    time_label.set_halign(Gtk.Align.END)
                    time_label.set_valign(Gtk.Align.END)
                    time_label.set_margin_end(4)
                    time_label.set_margin_bottom(4)

                    # Wrap in overlay for time label
                    overlay = Gtk.Overlay()
                    overlay.set_child(picture)
                    overlay.add_overlay(time_label)

                    # Click to seek
                    gesture = Gtk.GestureClick()
                    gesture.connect("released", lambda *_, s=sec: self._seek_to_time(s))
                    overlay.add_controller(gesture)

                    self.thumb_grid.append(overlay)
        except Exception:
            pass

    def _seek_to_time(self, sec):
        """Seek to a specific time and close the thumbnail popover."""
        try:
            self.player.seek(sec, reference="absolute", precision="exact")
            self.thumb_popover.popdown()
        except Exception:
            pass

    # Legacy single thumbnail methods (kept for compatibility)
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

