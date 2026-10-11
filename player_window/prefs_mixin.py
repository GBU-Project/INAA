from .common import *  # noqa: F401,F403


class PrefsMixin:
    def open_preferences(self, _button=None):
        dialog = Gtk.Dialog(
            title="Pengaturan",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons("Tutup", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(520, 460)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_spacing(8)

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(stack)
        switcher.set_halign(Gtk.Align.CENTER)
        content.append(switcher)

        stack.add_titled(self._prefs_general_page(), "general", "Umum")
        stack.add_titled(self._prefs_playlist_page(), "playlist", "Playlist")
        stack.add_titled(self._prefs_keys_page(dialog), "keys", "Pintasan")

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(stack)
        content.append(scroll)

        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()

    def _prefs_switch_row(self, title, key, default, on_change=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        lbl = Gtk.Label(label=title)
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        row.append(lbl)
        sw = Gtk.Switch()
        sw.set_active(bool(self._config.get(key, default)))
        sw.set_valign(Gtk.Align.CENTER)

        def on_notify(widget, _pspec):
            value = widget.get_active()
            self._config[key] = value
            self._save_config_throttled(force=True)
            if on_change:
                on_change(value)

        sw.connect("notify::active", on_notify)
        row.append(sw)
        return row

    def _prefs_general_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)

        box.append(self._prefs_switch_row(
            "Sembunyikan header & kontrol saat video diputar",
            "auto_hide_chrome",
            True,
        ))
        box.append(self._prefs_switch_row(
            "Sesuaikan jendela ke rasio video",
            "fit_window",
            True,
        ))
        box.append(self._prefs_switch_row(
            "Lanjutkan pemutaran dari posisi terakhir",
            "resume_playback",
            True,
        ))
        box.append(self._prefs_switch_row(
            "Mini player selalu di atas",
            "keep_above_mini",
            True,
            on_change=lambda v: self._is_mini and self._set_always_on_top(v),
        ))
        box.append(self._prefs_switch_row(
            "Muat ~/.config/mpv/mpv.conf",
            "use_mpv_conf",
            False,
        ))

        delay_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        delay_row.set_margin_top(8)
        delay_lbl = Gtk.Label(label="Sembunyikan kontrol setelah (detik)")
        delay_lbl.set_xalign(0)
        delay_lbl.set_hexpand(True)
        delay_row.append(delay_lbl)
        adj = Gtk.Adjustment(
            value=max(1, int(self._config.get("osd_hide_ms", 3000)) / 1000),
            lower=1,
            upper=10,
            step_increment=1,
        )
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        spin.set_digits(0)

        def on_delay(_s):
            self._config["osd_hide_ms"] = int(spin.get_value()) * 1000
            self._save_config_throttled(force=True)

        spin.connect("value-changed", on_delay)
        delay_row.append(spin)
        box.append(delay_row)
        return box

    def _prefs_playlist_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)

        loop_lbl = Gtk.Label(label="Mode pengulangan")
        loop_lbl.set_xalign(0)
        loop_lbl.add_css_class("iina-sec-title")
        box.append(loop_lbl)

        loop_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for mode, label in (("off", "Mati"), ("all", "Semua"), ("one", "Satu")):
            btn = Gtk.Button(label=label)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda _b, m=mode: self._set_loop_mode(m))
            loop_row.append(btn)
        box.append(loop_row)

        box.append(self._prefs_switch_row(
            "Acak playlist",
            "shuffle",
            False,
            on_change=lambda v: self._set_shuffle(v),
        ))
        return box

    def _prefs_keys_page(self, parent_dialog):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(16)
        hint = Gtk.Label(label="Ubah pintasan keyboard lewat editor visual.")
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        box.append(hint)
        btn = Gtk.Button(label="Sunting pintasan...")
        btn.add_css_class("iina-action-btn")
        btn.set_halign(Gtk.Align.START)

        def open_keys(_b):
            parent_dialog.destroy()
            self.open_shortcuts_editor()

        btn.connect("clicked", open_keys)
        box.append(btn)
        return box

    def _set_pref_bool(self, key, value):
        self._config[key] = bool(value)
        self._save_config_throttled(force=True)
