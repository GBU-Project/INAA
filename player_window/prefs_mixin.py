from .common import *  # noqa: F401,F403


class PrefsMixin:
    """IINA 1.5.0 macOS-style Settings / Preferences window implementation."""

    def open_preferences(self, _button=None):
        dialog = Gtk.Dialog(
            title="Pengaturan (Preferences)",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons("Tutup", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(720, 520)

        # Style the dialog content area
        content = dialog.get_content_area()
        content.set_margin_start(0)
        content.set_margin_end(0)
        content.set_margin_top(0)
        content.set_margin_bottom(0)
        content.set_spacing(0)
        content.add_css_class("iina-prefs-window")

        # Main 2-column container
        hpaned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        hpaned.set_hexpand(True)
        hpaned.set_vexpand(True)
        content.append(hpaned)

        # ========================================================
        # LEFT COLUMN: macOS Settings Category Sidebar
        # ========================================================
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar_box.add_css_class("iina-prefs-sidebar")
        sidebar_box.set_size_request(200, -1)
        sidebar_box.set_hexpand(False)
        hpaned.append(sidebar_box)

        # Search Bar on top of sidebar
        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text("Cari...")
        search_entry.set_margin_start(4)
        search_entry.set_margin_end(4)
        search_entry.set_margin_top(6)
        sidebar_box.append(search_entry)

        # Category ListBox
        cat_list = Gtk.ListBox()
        cat_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        cat_list.add_css_class("navigation-sidebar")

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_child(cat_list)
        sidebar_scroll.set_vexpand(True)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_box.append(sidebar_scroll)

        # ========================================================
        # RIGHT COLUMN: Content Pages (Stack)
        # ========================================================
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        stack.set_transition_duration(180)
        stack.set_hexpand(True)
        stack.set_vexpand(True)

        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_child(stack)
        content_scroll.set_hexpand(True)
        content_scroll.set_vexpand(True)
        content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_scroll.add_css_class("iina-prefs-content")
        hpaned.append(content_scroll)

        # Category definitions matching IINA 1.5.0
        categories = [
            ("general", "General", "preferences-system-symbolic", self._prefs_general_page()),
            ("interface", "Interface", "preferences-desktop-display-symbolic", self._prefs_interface_page()),
            ("video", "Video", "video-x-generic-symbolic", self._prefs_video_page()),
            ("audio", "Audio", "audio-x-generic-symbolic", self._prefs_audio_page()),
            ("subtitles", "Subtitles", "media-view-subtitles-symbolic", self._prefs_subtitles_page()),
            ("keys", "Key Bindings", "input-keyboard-symbolic", self._prefs_keys_page(dialog)),
            ("plugins", "Plugins", "system-software-install-symbolic", self._prefs_plugins_page(dialog)),
        ]

        row_map = {}
        for cat_id, title, icon_name, page_widget in categories:
            stack.add_named(page_widget, cat_id)

            row = Gtk.ListBoxRow()
            row.add_css_class("iina-prefs-cat-row")
            r_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(16)
            r_box.append(icon)

            lbl = Gtk.Label(label=title)
            lbl.set_xalign(0)
            lbl.set_hexpand(True)
            r_box.append(lbl)

            row.set_child(r_box)
            cat_list.append(row)
            row_map[row] = cat_id

        def on_cat_selected(_lb, selected_row):
            if selected_row in row_map:
                stack.set_visible_child_name(row_map[selected_row])

        cat_list.connect("row-selected", on_cat_selected)

        # Search filter support
        def on_search_changed(entry):
            query = entry.get_text().strip().lower()
            child = cat_list.get_first_child()
            first_visible = None
            while child:
                cat_id = row_map.get(child, "")
                matched = not query or query in cat_id.lower() or query in child.get_child().get_last_child().get_text().lower()
                child.set_visible(matched)
                if matched and not first_visible:
                    first_visible = child
                child = child.get_next_sibling()
            if first_visible:
                cat_list.select_row(first_visible)

        search_entry.connect("search-changed", on_search_changed)

        # Select first category (General) by default
        first_row = cat_list.get_row_at_index(0)
        if first_row:
            cat_list.select_row(first_row)

        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()

    # ========================================================
    # CARD WIDGET HELPERS
    # ========================================================
    def _prefs_card(self):
        """Creates an Apple HIG grouped card container."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("iina-pref-card")
        return card

    def _prefs_section_title(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_xalign(0)
        lbl.add_css_class("iina-prefs-section-header")
        return lbl

    def _prefs_switch_row(self, title, key, default, subtitle=None, on_change=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("iina-pref-card-row")

        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label_box.set_hexpand(True)

        lbl = Gtk.Label(label=title)
        lbl.set_xalign(0)
        label_box.append(lbl)

        if subtitle:
            sub = Gtk.Label(label=subtitle)
            sub.set_xalign(0)
            sub.add_css_class("dim-label")
            sub.set_wrap(True)
            label_box.append(sub)

        row.append(label_box)

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

    # ========================================================
    # CATEGORY PAGES
    # ========================================================
    def _prefs_general_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="General")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Playback"))
        card1 = self._prefs_card()
        card1.append(self._prefs_switch_row(
            "Lanjutkan pemutaran (Resume Playback)",
            "resume_playback",
            True,
            subtitle="Mengingat posisi durasi video saat aplikasi ditutup.",
        ))
        card1.append(self._prefs_switch_row(
            "Sesuaikan jendela ke aspek rasio video",
            "fit_window",
            True,
            subtitle="Otomatis mengatur ukuran jendela sesuai rasio saat memutar.",
        ))
        box.append(card1)

        box.append(self._prefs_section_title("Konfigurasi Tingkat Lanjut"))
        card2 = self._prefs_card()
        card2.append(self._prefs_switch_row(
            "Muat file ~/.config/mpv/mpv.conf",
            "use_mpv_conf",
            False,
            subtitle="Opsi aman diterapkan langsung; mematikannya baru berlaku setelah aplikasi dibuka ulang.",
            on_change=lambda v: self._on_use_mpv_conf_changed(v),
        ))
        box.append(card2)
        return box

    def _prefs_interface_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Interface")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("On-Screen Controller (OSC)"))
        card1 = self._prefs_card()
        card1.append(self._prefs_switch_row(
            "Sembunyikan header & kontrol secara otomatis",
            "auto_hide_chrome",
            True,
            subtitle="Fade-out kontrol melayang saat kursor tidak bergerak.",
        ))

        # Delay Stepper
        delay_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        delay_row.add_css_class("iina-pref-card-row")
        delay_lbl = Gtk.Label(label="Durasi sembunyikan kontrol:")
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
        spin.set_valign(Gtk.Align.CENTER)

        def on_delay(_s):
            self._config["osd_hide_ms"] = int(spin.get_value()) * 1000
            self._save_config_throttled(force=True)

        spin.connect("value-changed", on_delay)
        delay_row.append(spin)
        sec_lbl = Gtk.Label(label="detik")
        sec_lbl.add_css_class("dim-label")
        delay_row.append(sec_lbl)
        card1.append(delay_row)
        box.append(card1)

        box.append(self._prefs_section_title("Mini Player (Picture-in-Picture)"))
        card2 = self._prefs_card()
        card2.append(self._prefs_switch_row(
            "Mini player selalu di atas (Always on Top)",
            "keep_above_mini",
            True,
            subtitle="Jendela mini player tetap mengambang di atas jendela lain.",
            on_change=lambda v: self._is_mini and self._set_always_on_top(v),
        ))
        box.append(card2)
        return box

    def _prefs_video_page(self):
        """Matches the IINA 1.5.0 Video Settings screenshot."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Video")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Decoding"))
        card1 = self._prefs_card()

        # Hardware Decoder Group ala IINA
        hw_lbl = Gtk.Label(label="Hardware decoder")
        hw_lbl.set_xalign(0)
        hw_lbl.add_css_class("heading")
        card1.append(hw_lbl)

        current_hw = getattr(self.player, "hwdec", "auto-safe") if hasattr(self, "player") else "auto-safe"
        if not current_hw or current_hw == "no":
            current_hw = "no"

        options = [
            ("no", "Disabled", "Nonaktifkan akselerasi perangkat keras."),
            ("auto-safe", "Auto", "Gunakan hardware decoder otomatis terbaik yang didukung sistem (VA-API / NVDEC)."),
            ("vaapi", "VA-API", "Akselerasi hardware Intel / AMD di Linux."),
            ("nvdec", "NVDEC", "Akselerasi hardware eksklusif NVIDIA GPU."),
        ]

        hw_buttons = []
        for val, name, desc in options:
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            btn_box.add_css_class("iina-pref-option-box")
            is_active = (current_hw == val)
            if is_active:
                btn_box.add_css_class("active")

            t_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            n_lbl = Gtk.Label(label=f"<b>{name}</b>")
            n_lbl.set_use_markup(True)
            n_lbl.set_xalign(0)
            n_lbl.set_hexpand(True)
            t_box.append(n_lbl)

            # Checkmark indicator
            check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
            check_icon.add_css_class("iina-pref-check")
            check_icon.set_visible(is_active)
            t_box.append(check_icon)

            btn_box.append(t_box)

            d_lbl = Gtk.Label(label=desc)
            d_lbl.set_xalign(0)
            d_lbl.add_css_class("dim-label")
            d_lbl.set_wrap(True)
            btn_box.append(d_lbl)

            # Click gesture for selecting option
            click = Gtk.GestureClick()
            def make_handler(target_val, box_ref, icon_ref):
                def on_click(*_):
                    self._set_hwdec(target_val)
                    for b, ico in hw_buttons:
                        b.remove_css_class("active")
                        ico.set_visible(False)
                    box_ref.add_css_class("active")
                    icon_ref.set_visible(True)
                return on_click

            click.connect("pressed", make_handler(val, btn_box, check_icon))
            btn_box.add_controller(click)
            hw_buttons.append((btn_box, check_icon))
            card1.append(btn_box)

        box.append(card1)

        box.append(self._prefs_section_title("Video Processing"))
        card2 = self._prefs_card()
        card2.append(self._prefs_switch_row(
            "Deinterlace Video",
            "deinterlace",
            False,
            subtitle="Menghilangkan artefak garis interlaced.",
            on_change=lambda v: setattr(self.player, "deinterlace", v) if hasattr(self, "player") else None,
        ))
        box.append(card2)
        return box

    def _prefs_audio_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Audio")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Playlist & Pemutaran"))
        card1 = self._prefs_card()

        card1.append(self._prefs_switch_row(
            "Acak Playlist (Shuffle)",
            "shuffle",
            False,
            subtitle="Memutar daftar lagu/video secara acak.",
            on_change=lambda v: self._set_shuffle(v),
        ))

        # Mode loop row
        loop_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        loop_row.add_css_class("iina-pref-card-row")
        loop_lbl = Gtk.Label(label="Mode Pengulangan (Loop):")
        loop_lbl.set_xalign(0)
        loop_lbl.set_hexpand(True)
        loop_row.append(loop_lbl)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._prefs_loop_buttons = {}
        for mode, label in (("off", "Mati"), ("all", "Semua"), ("one", "Satu")):
            btn = Gtk.Button(label=label)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda _b, m=mode: self._set_loop_mode(m))
            btn_box.append(btn)
            self._prefs_loop_buttons[mode] = btn
        self._sync_prefs_loop_buttons()
        loop_row.append(btn_box)
        card1.append(loop_row)
        box.append(card1)
        return box

    def _sync_prefs_loop_buttons(self):
        """Tandai tombol mode loop yang sedang aktif (dipanggil juga saat mode berubah)."""
        for mode, btn in getattr(self, "_prefs_loop_buttons", {}).items():
            if mode == self._loop_mode:
                btn.add_css_class("iina-seg-active")
            else:
                btn.remove_css_class("iina-seg-active")

    def _prefs_subtitles_page(self):
        """Matches the IINA 1.5.0 Subtitles Settings screenshot."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Subtitles")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Text Subtitles"))
        card1 = self._prefs_card()

        # Font size setting
        size_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        size_row.add_css_class("iina-pref-card-row")
        size_lbl = Gtk.Label(label="Ukuran Font Subtitle:")
        size_lbl.set_xalign(0)
        size_lbl.set_hexpand(True)
        size_row.append(size_lbl)

        cur_size = int(self._config.get("sub_font_size", 55))
        adj = Gtk.Adjustment(value=cur_size, lower=20, upper=120, step_increment=2)
        spin = Gtk.SpinButton()
        spin.set_adjustment(adj)
        spin.set_digits(0)
        spin.set_valign(Gtk.Align.CENTER)
        def on_size(s):
            val = int(s.get_value())
            self._config["sub_font_size"] = val
            self._save_config_throttled(force=True)
            try:
                self.player["sub-font-size"] = val
            except Exception:
                pass
        spin.connect("value-changed", on_size)
        size_row.append(spin)
        card1.append(size_row)

        card1.append(self._prefs_switch_row(
            "Otomatis Muat Subtitle Lokal",
            "auto_load_subtitles",
            True,
            subtitle="Mencari file .srt / .ass yang memiliki nama file sama.",
        ))
        box.append(card1)

        box.append(self._prefs_section_title("Position & Sync"))
        card2 = self._prefs_card()
        # Subtitle delay row
        delay_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        delay_row.add_css_class("iina-pref-card-row")
        delay_lbl = Gtk.Label(label="Reset Delay Subtitle:")
        delay_lbl.set_xalign(0)
        delay_lbl.set_hexpand(True)
        delay_row.append(delay_lbl)

        btn_rst_sub = Gtk.Button(label="Reset (0.0s)")
        btn_rst_sub.add_css_class("iina-seg-btn")
        def on_rst(_b):
            try:
                self.player.sub_delay = 0.0
                if hasattr(self, "insp_sub_delay_scale"):
                    self.insp_sub_delay_scale.set_value(0.0)
                self.show_toast("Subtitle Delay: 0.0s")
            except Exception:
                pass
        btn_rst_sub.connect("clicked", on_rst)
        delay_row.append(btn_rst_sub)
        card2.append(delay_row)
        box.append(card2)
        return box

    def _prefs_keys_page(self, parent_dialog):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Key Bindings")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Pintasan Keyboard"))
        card = self._prefs_card()
        
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("iina-pref-card-row")
        lbl = Gtk.Label(label="Atur tombol pintasan kustom:")
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        row.append(lbl)

        btn = Gtk.Button(label="Buka Editor Pintasan...")
        btn.add_css_class("iina-action-btn")
        def open_keys(_b):
            parent_dialog.destroy()
            self.open_shortcuts_editor()
        btn.connect("clicked", open_keys)
        row.append(btn)
        card.append(row)
        box.append(card)
        return box

    def _prefs_plugins_page(self, _parent_dialog):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        title = Gtk.Label(label="Plugins")
        title.set_xalign(0)
        title.add_css_class("iina-prefs-header-title")
        box.append(title)

        box.append(self._prefs_section_title("Manajemen Plugin"))
        card = self._prefs_card()

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("iina-pref-card-row")
        lbl = Gtk.Label(label="Folder Plugin:")
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        row.append(lbl)

        btn_folder = Gtk.Button(label="Buka Folder Plugin")
        btn_folder.add_css_class("iina-seg-btn")
        def open_pl_dir(_b):
            import subprocess
            PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(PLUGINS_DIR)])
        btn_folder.connect("clicked", open_pl_dir)
        row.append(btn_folder)
        card.append(row)
        box.append(card)
        return box

    def _set_pref_bool(self, key, value):
        self._config[key] = bool(value)
        self._save_config_throttled(force=True)
