"""Video/audio inspector controls: hwdec, aspect/crop/rotate, filter presets."""
from .common import *  # noqa: F401,F403


class FiltersMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def on_inspector_toggled(self, button):
        visible = button.get_active()
        self.inspector_panel.set_visible(visible)
        if visible:
            self._refresh_inspector_tracks()

    def _set_hwdec(self, mode):
        try:
            self.player.hwdec = mode
            mode_lbl = "Auto" if mode == "auto-safe" else mode.upper() if mode != "no" else "Nonaktif"
            self.show_toast(f"⚡ Hardware Acceleration: {mode_lbl}")
        except Exception:
            pass

    def _set_aspect_ratio(self, val):
        try:
            self.player.video_aspect_override = val
        except Exception:
            pass

    def _set_crop(self, crop_ratio):
        try:
            if crop_ratio in ("none", "no", None):
                # Hapus filter crop. Catatan: saat ini "vf" hanya pernah diisi
                # oleh fitur crop ini sendiri, jadi menimpa dengan string
                # kosong aman. Kalau nanti ada fitur video-filter lain yang
                # juga menulis ke "vf", baris ini perlu diubah supaya hanya
                # menghapus komponen crop-nya saja, bukan seluruh chain.
                self.player["vf"] = ""
                self.show_toast("Video Crop: Dinonaktifkan")
            else:
                # Terapkan filter crop aspect ratio
                # 16:9 -> 16/9, 21:9 -> 21/9, dll
                parts = crop_ratio.split(":")
                if len(parts) == 2:
                    w_r, h_r = float(parts[0]), float(parts[1])
                    ratio_val = w_r / h_r
                    # Gunakan crop filter FFmpeg: memotong bagian luar agar rasio pas
                    self.player["vf"] = f"crop=w='min(iw,ih*{ratio_val})':h='min(ih,iw/{ratio_val})'"
                    self.show_toast(f"✂ Video Crop: {crop_ratio}")
        except Exception:
            pass

    def _set_video_rotate(self, val):
        try:
            self.player.video_rotate = val
        except Exception:
            pass

    def _apply_saved_shaders(self):
        """Menerapkan shader yang tersimpan di config ke libmpv."""
        shaders = self._config.get("custom_shaders", [])
        valid_shaders = [s for s in shaders if os.path.isfile(s)]
        try:
            self.player["glsl-shaders"] = valid_shaders
        except Exception:
            pass

    def _add_custom_shader(self, shader_path):
        """Menambahkan shader GLSL ke mpv dan menyimpannya di config."""
        if not os.path.isfile(shader_path):
            self.show_toast("File shader tidak ditemukan")
            return
        current = list(self._config.get("custom_shaders", []))
        if shader_path not in current:
            current.append(shader_path)
            self._config["custom_shaders"] = current
            self._save_config_throttled(force=True)
        try:
            self.player["glsl-shaders"] = current
            name = os.path.basename(shader_path)
            self.show_toast(f"Shader aktif: {name}")
        except Exception as e:
            self.show_toast(f"Gagal memuat shader: {e}")
        self._refresh_shader_ui()

    def _clear_custom_shaders(self):
        """Menghapus semua custom shader."""
        self._config["custom_shaders"] = []
        self._save_config_throttled(force=True)
        try:
            self.player["glsl-shaders"] = []
            self.show_toast("Semua shader dinonaktifkan")
        except Exception:
            pass
        self._refresh_shader_ui()

    def _open_shader_chooser(self, _button):
        """Dialog pemilih file shader .hook atau .glsl."""
        dialog = Gtk.FileChooserDialog(
            title="Pilih Custom GLSL Shader",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Pilih", Gtk.ResponseType.OK,
        )
        f_filter = Gtk.FileFilter()
        f_filter.set_name("GLSL / mpv Shaders (*.hook, *.glsl)")
        f_filter.add_pattern("*.hook")
        f_filter.add_pattern("*.glsl")
        dialog.add_filter(f_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("Semua Berkas")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        def on_response(dlg, response):
            if response == Gtk.ResponseType.OK:
                gfile = dlg.get_file()
                if gfile:
                    path = gfile.get_path()
                    if path:
                        self._add_custom_shader(path)
            dlg.destroy()

        dialog.connect("response", on_response)
        dialog.show()

    def _refresh_shader_ui(self):
        if hasattr(self, "insp_shader_status_label"):
            shaders = self._config.get("custom_shaders", [])
            if shaders:
                names = ", ".join(os.path.basename(s) for s in shaders)
                self.insp_shader_status_label.set_text(names)
            else:
                self.insp_shader_status_label.set_text("Tidak ada shader aktif")

    def _rebuild_filters_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_size_request(240, -1)

        title = Gtk.Label(label="Filter Video Real-time")
        title.set_xalign(0)
        title.add_css_class("heading")
        box.append(title)

        # Sliders: Brightness, Contrast, Saturation, Gamma
        sliders_def = [
            ("Kecerahan (Brightness)", "brightness", -100, 100),
            ("Kontras (Contrast)", "contrast", -100, 100),
            ("Saturasi (Saturation)", "saturation", -100, 100),
            ("Gamma", "gamma", -100, 100),
        ]

        for lbl, prop, min_val, max_val in sliders_def:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            cur_val = getattr(self.player, prop, 0.0) or 0.0
            l = Gtk.Label(label=f"{lbl}: {int(cur_val)}")
            l.set_xalign(0)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_val, max_val, 1)
            scale.set_value(cur_val)
            scale.set_draw_value(False)
            scale.connect("value-changed", lambda sc, p=prop, lb=l, name=lbl: self._on_filter_changed(p, sc.get_value(), lb, name))
            row.append(l)
            row.append(scale)
            box.append(row)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        # Equalizer audio preset
        eq_title = Gtk.Label(label="Audio Equalizer / Efek")
        eq_title.set_xalign(0)
        box.append(eq_title)

        eq_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_bass = Gtk.Button(label="Bass Boost")
        btn_bass.connect("clicked", lambda *_: self._set_audio_filter("bassboost"))
        eq_box.append(btn_bass)

        btn_vocal = Gtk.Button(label="Vocal Boost")
        btn_vocal.connect("clicked", lambda *_: self._set_audio_filter("vocal"))
        eq_box.append(btn_vocal)

        btn_night = Gtk.Button(label="Night Mode")
        btn_night.connect("clicked", lambda *_: self._set_audio_filter("nightmode"))
        eq_box.append(btn_night)
        box.append(eq_box)

        # Reset button
        reset_btn = Gtk.Button(label="Reset Semua Filter")
        reset_btn.connect("clicked", lambda *_: self._reset_filters())
        box.append(reset_btn)

        self.filters_popover.set_child(box)

    def _on_filter_changed(self, prop, val, label, name):
        try:
            setattr(self.player, prop, val)
            label.set_text(f"{name}: {int(val)}")
        except Exception:
            pass

    def _set_audio_filter(self, preset):
        try:
            if preset == "bassboost":
                self.player["af"] = "equalizer=f=64:t=q:w=1:g=8"
                self.show_toast("🎵 Efek Audio: Bass Boost")
            elif preset == "vocal":
                self.player["af"] = "equalizer=f=1000:t=q:w=1:g=6"
                self.show_toast("🎙 Efek Audio: Vocal Boost")
            elif preset == "nightmode":
                self.player["af"] = "lavfi=[loudnorm=I=-16:TP=-1.5:LRA=11]"
                self.show_toast("🌙 Efek Audio: Night Mode (Dynamic Range Normalization)")
            elif preset == "reset":
                self.player["af"] = ""
                self.show_toast("Efek Audio Dinonaktifkan")
        except Exception:
            pass
        self.filters_popover.popdown()

    def _reset_filters(self):
        try:
            self.player.brightness = 0
            self.player.contrast = 0
            self.player.saturation = 0
            self.player.gamma = 0
            self.player["af"] = ""
        except Exception:
            pass
        self._rebuild_filters_menu()

