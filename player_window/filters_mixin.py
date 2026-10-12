"""Video/audio inspector controls: hwdec, aspect/crop/rotate, filter presets."""
from .common import *  # noqa: F401,F403
import logging

import audio_filters
import mpv_user


class FiltersMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def on_inspector_toggled(self, button):
        visible = button.get_active()
        self.inspector_panel.set_visible(visible)
        if visible:
            self._refresh_inspector_tracks()
            self._refresh_shader_ui()

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

    def _apply_user_mpv_settings(self):
        """Terapkan mpv.conf (allowlist) dan script eksplisit; opsi ditolak dilaporkan."""
        cfg = {k: self._config.get(k) for k in ("use_mpv_conf", "mpv_conf", "mpv_scripts")}
        report = mpv_user.apply_user_settings(self.player, cfg, SHADERS_DIR)
        self._mpv_user_report = report
        for source, reason in report.rejected:
            logging.getLogger("inaa").warning("mpv: diabaikan: %s — %s", source, reason)
        if report.applied or report.rejected or report.scripts:
            GLib.timeout_add(1200, lambda: (self.show_toast(report.summary()), False)[1])

    def _on_use_mpv_conf_changed(self, enabled):
        """Terapkan mpv.conf segera saat dinyalakan; mematikan butuh restart (nilai lama tak bisa dipulihkan)."""
        enabled = bool(enabled)
        if self._config.get("use_mpv_conf") != enabled:
            self._config["use_mpv_conf"] = enabled
            self._save_config_throttled(force=True)
        chk = getattr(self, "mpv_conf_chk", None)
        if chk is not None and chk.get_active() != enabled:
            chk.set_active(enabled)
            return
        if enabled:
            self._apply_user_mpv_settings()
        else:
            self.show_toast("mpv.conf dimatikan (berlaku setelah aplikasi dibuka ulang)")

    def _apply_saved_shaders(self):
        """Menerapkan shader yang tersimpan di config ke libmpv."""
        shaders = self._config.get("custom_shaders", [])
        if not isinstance(shaders, list):
            shaders = []
        report = mpv_user.Report()
        mpv_user.apply_shaders(self.player, shaders, SHADERS_DIR, report)
        for source, reason in report.rejected:
            logging.getLogger("inaa").warning("shader diabaikan: %s — %s", source, reason)

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

        # Refresh available shaders list
        if hasattr(self, "shader_listbox"):
            self._refresh_available_shaders_list()

    def _refresh_available_shaders_list(self):
        """Populate the available shaders list from SHADERS_DIR."""
        child = self.shader_listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.shader_listbox.remove(child)
            child = nxt

        shaders_dir = SHADERS_DIR
        if not shaders_dir.exists():
            shaders_dir.mkdir(parents=True, exist_ok=True)

        current_shaders = set(self._config.get("custom_shaders", []))
        active_names = {os.path.basename(s) for s in current_shaders}

        try:
            for entry in sorted(shaders_dir.iterdir()):
                if entry.is_file() and entry.suffix.lower() in {".glsl", ".hook", ".frag"}:
                    row = Gtk.ListBoxRow()
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    box.set_margin_start(8)
                    box.set_margin_end(8)
                    box.set_margin_top(4)
                    box.set_margin_bottom(4)

                    name = entry.name
                    is_active = name in active_names

                    lbl = Gtk.Label(label=name)
                    lbl.set_xalign(0)
                    lbl.set_hexpand(True)
                    if is_active:
                        lbl.add_css_class("iina-shader-active")
                    box.append(lbl)

                    if is_active:
                        btn = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
                        btn.set_tooltip_text("Nonaktifkan shader ini")
                        btn.set_has_frame(False)
                        def make_remove(n=name, p=str(entry)):
                            return lambda _: self._remove_custom_shader(p)
                        btn.connect("clicked", make_remove())
                    else:
                        btn = Gtk.Button.new_from_icon_name("emblem-default-symbolic")
                        btn.set_tooltip_text("Aktifkan shader ini")
                        btn.set_has_frame(False)
                        def make_add(p=str(entry)):
                            return lambda _: self._add_custom_shader(p)
                        btn.connect("clicked", make_add())
                    btn.set_valign(Gtk.Align.CENTER)
                    box.append(btn)

                    row.set_child(box)
                    self.shader_listbox.append(row)
        except Exception:
            pass

    def _remove_custom_shader(self, shader_path):
        """Menghapus shader dari daftar aktif."""
        current = list(self._config.get("custom_shaders", []))
        if shader_path in current:
            current.remove(shader_path)
            self._config["custom_shaders"] = current
            self._save_config_throttled(force=True)
        try:
            self.player["glsl-shaders"] = current
            self.show_toast(f"Shader dinonaktifkan: {os.path.basename(shader_path)}")
        except Exception as e:
            self.show_toast(f"Gagal menghapus shader: {e}")
        self._refresh_shader_ui()

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
        eq_title = Gtk.Label(label="Audio Equalizer / Efek:")
        eq_title.set_xalign(0)
        eq_title.add_css_class("heading")
        box.append(eq_title)

        eq_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_bass = Gtk.Button(label="Bass+")
        btn_bass.add_css_class("iina-seg-btn")
        btn_bass.connect("clicked", lambda *_: self._set_audio_filter("bassboost"))
        eq_box.append(btn_bass)

        btn_vocal = Gtk.Button(label="Vocal+")
        btn_vocal.add_css_class("iina-seg-btn")
        btn_vocal.connect("clicked", lambda *_: self._set_audio_filter("vocal"))
        eq_box.append(btn_vocal)

        btn_night = Gtk.Button(label="Night Mode")
        btn_night.add_css_class("iina-seg-btn")
        btn_night.connect("clicked", lambda *_: self._set_audio_filter("nightmode"))
        eq_box.append(btn_night)

        btn_full_eq = Gtk.Button(label="Equalizer 10 Band...")
        btn_full_eq.add_css_class("iina-seg-btn")
        def open_full_eq_tab(_b):
            self.filters_popover.popdown()
            self.inspector_panel.set_visible(True)
            self.inspector_btn.set_active(True)
            if hasattr(self, "insp_stack"):
                self.insp_stack.set_visible_child_name("audio")
        btn_full_eq.connect("clicked", open_full_eq_tab)
        eq_box.append(btn_full_eq)
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

    def _apply_audio_filters(self):
        """Menerapkan filter audio dari konfigurasi equalizer dan efek khusus."""
        gains = self._config.get("audio_eq_gains", [0.0] * 10)
        effect = self._config.get("audio_special_effect", "none")
        af_str = audio_filters.compose_af_string(gains, effect)
        try:
            self.player["af"] = af_str
        except Exception as e:
            logging.getLogger("inaa").warning("Gagal menerapkan filter audio: %s", e)

    def _set_audio_eq_band(self, index, gain):
        """Mengubah gain band equalizer tertentu (-12 s/d +12 dB)."""
        if getattr(self, "_is_syncing_eq_ui", False):
            return
        gains = list(self._config.get("audio_eq_gains", [0.0] * 10))
        while len(gains) < 10:
            gains.append(0.0)
        gains[index] = audio_filters.clamp_gain(gain)
        self._config["audio_eq_gains"] = gains
        self._config["audio_eq_preset"] = "custom"
        self._apply_audio_filters()
        self._save_config_throttled()

    def _set_audio_eq_preset(self, preset_name):
        """Menerapkan preset equalizer 10-band (preset bawaan maupun kustom)."""
        custom_presets = self._config.get("audio_custom_presets", {})
        if preset_name in audio_filters.EQ_PRESETS:
            gains = list(audio_filters.EQ_PRESETS[preset_name])
            self._config["audio_eq_gains"] = gains
            self._config["audio_eq_preset"] = preset_name
            self._apply_audio_filters()
            self._save_config_throttled(force=True)
            self._sync_eq_sliders_ui()
            p_label = preset_name.replace("_", " ").title()
            self.show_toast(f"🎚 Equalizer Preset: {p_label}")
        elif preset_name in custom_presets:
            gains = list(custom_presets[preset_name])
            self._config["audio_eq_gains"] = gains
            self._config["audio_eq_preset"] = preset_name
            self._apply_audio_filters()
            self._save_config_throttled(force=True)
            self._sync_eq_sliders_ui()
            self.show_toast(f"🎚 Custom Preset: {preset_name}")

    def _save_custom_eq_preset(self, name):
        """Menyimpan gain equalizer saat ini ke preset kustom dengan nama yang diberikan."""
        name = name.strip()
        if not name or len(name) > 40:
            return False
        reserved = {n.casefold() for n in audio_filters.EQ_PRESETS} | {"custom"}
        reserved |= {n.replace("_", " ").casefold() for n in audio_filters.EQ_PRESETS}
        if name.casefold() in reserved:
            self.show_toast(f"Nama '{name}' dipakai preset bawaan, pilih nama lain")
            return False
        custom_presets = self._config.get("audio_custom_presets", {})
        gains = [audio_filters.clamp_gain(g) for g in self._config.get("audio_eq_gains", [0.0] * 10)]
        custom_presets[name] = gains
        self._config["audio_custom_presets"] = custom_presets
        self._config["audio_eq_preset"] = name
        self._save_config_throttled(force=True)
        if hasattr(self, "_refresh_custom_eq_presets_ui"):
            self._refresh_custom_eq_presets_ui()
        self.show_toast(f"Preset '{name}' disimpan")
        return True

    def _delete_custom_eq_preset(self, name):
        """Menghapus preset kustom yang tersimpan."""
        custom_presets = self._config.get("audio_custom_presets", {})
        if name in custom_presets:
            del custom_presets[name]
            self._config["audio_custom_presets"] = custom_presets
            if self._config.get("audio_eq_preset") == name:
                self._config["audio_eq_preset"] = "custom"
            self._save_config_throttled(force=True)
            if hasattr(self, "_refresh_custom_eq_presets_ui"):
                self._refresh_custom_eq_presets_ui()
            self.show_toast(f"Preset '{name}' dihapus")

    def _set_audio_special_effect(self, effect_name):
        """Menerapkan efek audio khusus (nightmode, karaoke, clarity, atau none)."""
        if effect_name in audio_filters.SPECIAL_AUDIO_EFFECTS:
            self._config["audio_special_effect"] = effect_name
            self._apply_audio_filters()
            self._save_config_throttled(force=True)
            if effect_name == "nightmode":
                self.show_toast("🌙 Efek Audio: Night Mode (Dynamic Range Compression)")
            elif effect_name == "karaoke":
                self.show_toast("🎤 Efek Audio: Karaoke (Vocal Reducer)")
            elif effect_name == "clarity":
                self.show_toast("✨ Efek Audio: Clarity Boost")
            else:
                self.show_toast("Efek Khusus Dinonaktifkan")

    def _sync_eq_sliders_ui(self):
        """Sinkronkan posisi slider EQ di Inspector dengan nilai konfigurasi."""
        if not hasattr(self, "_eq_band_scales"):
            return
        self._is_syncing_eq_ui = True
        try:
            gains = self._config.get("audio_eq_gains", [0.0] * 10)
            for i, scale in enumerate(self._eq_band_scales):
                val = gains[i] if i < len(gains) else 0.0
                scale.set_value(val)
                if hasattr(self, "_eq_band_value_labels") and i < len(self._eq_band_value_labels):
                    self._eq_band_value_labels[i].set_text(f"{val:+.1f}dB" if val != 0 else "0dB")
        finally:
            self._is_syncing_eq_ui = False

    def _set_audio_filter(self, preset):
        # Backward compatibility handler untuk UI popover / inspector lama
        if preset == "bassboost":
            self._set_audio_eq_preset("bass_boost")
        elif preset == "vocal":
            self._set_audio_eq_preset("vocal_boost")
        elif preset == "nightmode":
            self._set_audio_special_effect("nightmode")
        elif preset == "reset":
            self._reset_audio_eq()
        if hasattr(self, "filters_popover"):
            self.filters_popover.popdown()

    def _reset_audio_eq(self):
        """Kembalikan equalizer dan efek audio ke kondisi flat/mati."""
        self._config["audio_eq_preset"] = "flat"
        self._config["audio_eq_gains"] = [0.0] * 10
        self._config["audio_special_effect"] = "none"
        self._apply_audio_filters()
        self._save_config_throttled(force=True)
        self._sync_eq_sliders_ui()
        self.show_toast("Equalizer & Efek Audio Direset")

    def _reset_filters(self):
        try:
            self.player.brightness = 0
            self.player.contrast = 0
            self.player.saturation = 0
            self.player.gamma = 0
        except Exception:
            pass
        self._reset_audio_eq()
        self._rebuild_filters_menu()

