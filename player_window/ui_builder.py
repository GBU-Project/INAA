"""Widget construction: header bar, welcome screen, music view, inspector tabs, drag&drop, signal wiring."""
from .common import *  # noqa: F401,F403
from .gl_area import MpvGLArea


class UIBuilderMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def _build_ui(self):
        self.header = Gtk.HeaderBar()
        self.set_titlebar(self.header)

        open_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        open_btn.set_tooltip_text("Buka file video/audio")
        open_btn.connect("clicked", self.on_open_clicked)
        self.header.pack_start(open_btn)

        open_url_btn = Gtk.Button.new_from_icon_name("insert-link-symbolic")
        open_url_btn.set_tooltip_text("Buka dari URL (YouTube, dll.)")
        open_url_btn.connect("clicked", self.on_open_url_clicked)
        self.header.pack_start(open_url_btn)

        self.playlist_toggle = Gtk.ToggleButton()
        self.playlist_toggle.set_icon_name("view-list-symbolic")
        self.playlist_toggle.set_tooltip_text("Playlist")
        self.playlist_toggle.connect("toggled", self.on_playlist_toggled)
        self.header.pack_start(self.playlist_toggle)

        # Chapter menu button
        self.chapter_menu_btn = Gtk.MenuButton()
        self.chapter_menu_btn.set_icon_name("media-playlist-consecutive-symbolic")
        self.chapter_menu_btn.set_tooltip_text("Bab / Chapters")
        self.chapter_popover = Gtk.Popover()
        self.chapter_popover.connect("show", lambda *_: self._rebuild_chapter_menu())
        self.chapter_menu_btn.set_popover(self.chapter_popover)
        self.header.pack_start(self.chapter_menu_btn)

        # Video & Audio Filters button
        self.filters_btn = Gtk.MenuButton()
        self.filters_btn.set_icon_name("camera-photo-symbolic")
        self.filters_btn.set_tooltip_text("Filter Video & Equalizer Audio")
        self.filters_popover = Gtk.Popover()
        self.filters_popover.connect("show", lambda *_: self._rebuild_filters_menu())
        self.filters_btn.set_popover(self.filters_popover)
        self.header.pack_start(self.filters_btn)

        # Inspector Panel Button (macOS IINA style)
        self.inspector_btn = Gtk.ToggleButton()
        self.inspector_btn.set_icon_name("preferences-other-symbolic")
        self.inspector_btn.set_tooltip_text("Pengaturan / Inspector (i)")
        self.inspector_btn.connect("toggled", self.on_inspector_toggled)
        self.header.pack_end(self.inspector_btn)

        # Audio / Subtitle popover button
        self.track_menu_btn = Gtk.MenuButton()
        self.track_menu_btn.set_icon_name("preferences-desktop-locale-symbolic")
        self.track_menu_btn.set_tooltip_text("Audio & Subtitle Track / Unduh Subtitle")
        self.track_popover = Gtk.Popover()
        self.track_popover.connect("show", lambda *_: self._rebuild_track_menu())
        self.track_menu_btn.set_popover(self.track_popover)
        self.header.pack_end(self.track_menu_btn)

        # Playback Speed & A-B Loop popover button
        self.playback_opts_btn = Gtk.MenuButton()
        self.playback_opts_btn.set_label("1.0x")
        self.playback_opts_btn.set_tooltip_text("Kecepatan Pemutaran & A-B Loop")
        self.playback_opts_popover = Gtk.Popover()
        self.playback_opts_popover.connect("show", lambda *_: self._rebuild_playback_menu())
        self.playback_opts_btn.set_popover(self.playback_opts_popover)
        self.header.pack_end(self.playback_opts_btn)

        # Music Mode Toggle Button
        self.music_toggle_btn = Gtk.ToggleButton()
        self.music_toggle_btn.set_icon_name("audio-x-generic-symbolic")
        self.music_toggle_btn.set_tooltip_text("Music Mode (Tampilan Musik / Album)")
        self.music_toggle_btn.connect("toggled", self.on_music_mode_toggled)
        self.header.pack_end(self.music_toggle_btn)

        self.mini_btn = Gtk.ToggleButton()
        self.mini_btn.set_icon_name("view-restore-symbolic")
        self.mini_btn.set_tooltip_text("Mini Player")
        self.mini_btn.connect("toggled", self.on_mini_toggled)
        self.header.pack_end(self.mini_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root)

        # Playlist sidebar (Kiri)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.set_size_request(220, -1)
        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.connect("row-activated", self.on_playlist_row_activated)
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_child(self.sidebar_list)
        sidebar_scroll.set_vexpand(True)
        self.sidebar.append(sidebar_scroll)
        self.sidebar.set_visible(False)
        root.append(self.sidebar)

        # Main video area with Overlay for Floating OSD
        self.video_overlay = Gtk.Overlay()
        self.video_overlay.set_hexpand(True)
        self.video_overlay.set_vexpand(True)
        root.append(self.video_overlay)

        # Stack to switch between Video (MpvGLArea) and Music View
        self.display_stack = Gtk.Stack()
        self.display_stack.set_hexpand(True)
        self.display_stack.set_vexpand(True)
        self.display_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Page 1: Video GLArea
        self.gl_area = MpvGLArea()
        self.gl_area.set_hexpand(True)
        self.gl_area.set_vexpand(True)

        # Left click gesture: single click play/pause, double click toggle fullscreen / restore mini player
        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(1)
        click_gesture.connect("released", self._on_video_left_click)
        self.gl_area.add_controller(click_gesture)

        # Right click gesture: show context menu (Mini Player toggle, Fullscreen, Play/Pause)
        right_click_gesture = Gtk.GestureClick()
        right_click_gesture.set_button(3)
        right_click_gesture.connect("pressed", self._on_video_right_click)
        self.gl_area.add_controller(right_click_gesture)

        # Drag gesture to detach video when dragged outward
        video_drag_gesture = Gtk.GestureDrag()
        video_drag_gesture.set_button(1)
        video_drag_gesture.connect("drag-begin", self._on_video_drag_begin)
        video_drag_gesture.connect("drag-end", self._on_video_drag_end)
        self.gl_area.add_controller(video_drag_gesture)

        # Trackpad / Mouse Scroll Gesture (IINA-style: Vertical = Volume, Horizontal = Seeking)
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self._on_video_scroll)
        self.gl_area.add_controller(scroll_controller)

        # Video context menu popover
        self.video_context_popover = Gtk.Popover()
        self.video_context_popover.set_parent(self.gl_area)
        self.video_context_popover.set_has_arrow(False)

        self.display_stack.add_named(self.gl_area, "video")

        # Page 2: Music View
        self.music_view = self._build_music_view()
        self.display_stack.add_named(self.music_view, "music")

        # Page 3: Welcome Screen (macOS IINA Style)
        self.welcome_view = self._build_welcome_view()
        self.display_stack.add_named(self.welcome_view, "welcome")
        self.display_stack.set_visible_child_name("welcome")

        self.video_overlay.set_child(self.display_stack)

        # ----------------- FLOATING OSD (macOS IINA Style) -----------------
        self.osd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.osd_box.add_css_class("iina-osd-panel")
        self.osd_box.set_valign(Gtk.Align.END)
        self.osd_box.set_halign(Gtk.Align.CENTER)
        self.osd_box.set_size_request(440, -1)
        self.osd_box.set_visible(False)

        # Seekbar row
        seek_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.time_label = Gtk.Label(label="00:00")
        self.time_label.add_css_class("iina-time-label")
        self.seekbar = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self.seekbar.set_draw_value(False)
        self.seekbar.set_hexpand(True)
        self.duration_label = Gtk.Label(label="00:00")
        self.duration_label.add_css_class("iina-time-label")
        seek_row.append(self.time_label)
        seek_row.append(self.seekbar)
        seek_row.append(self.duration_label)
        self.osd_box.append(seek_row)

        # Popover thumbnail preview saat hover seekbar
        self.thumb_popover = Gtk.Popover()
        self.thumb_popover.set_parent(self.seekbar)
        self.thumb_popover.set_position(Gtk.PositionType.TOP)
        self.thumb_popover.set_autohide(False)
        self.thumb_picture = Gtk.Picture()
        self.thumb_picture.set_size_request(160, 90)
        self.thumb_label = Gtk.Label(label="00:00")
        thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        thumb_box.append(self.thumb_picture)
        thumb_box.append(self.thumb_label)
        self.thumb_popover.set_child(thumb_box)

        # Buttons row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Volume section (kiri)
        vol_btn = Gtk.Button.new_from_icon_name("audio-volume-high-symbolic")
        vol_btn.set_has_frame(False)
        vol_btn.set_tooltip_text("Bisu / Suara (m)")
        vol_btn.connect("clicked", self.on_mute_clicked)
        btn_row.append(vol_btn)
        self.vol_btn = vol_btn

        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_size_request(80, -1)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        btn_row.append(self.volume_scale)

        spacer_left = Gtk.Box()
        spacer_left.set_hexpand(True)
        btn_row.append(spacer_left)

        # Playback control (tengah)
        self.prev_btn = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self.prev_btn.set_tooltip_text("File Sebelumnya")
        self.prev_btn.connect("clicked", lambda *_: self.play_relative(-1))
        btn_row.append(self.prev_btn)

        self.playpause_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.playpause_btn.set_tooltip_text("Putar / Jeda (Spasi)")
        self.playpause_btn.connect("clicked", self.on_playpause_clicked)
        btn_row.append(self.playpause_btn)

        self.next_btn = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self.next_btn.set_tooltip_text("File Berikutnya")
        self.next_btn.connect("clicked", lambda *_: self.play_relative(1))
        btn_row.append(self.next_btn)

        spacer_right = Gtk.Box()
        spacer_right.set_hexpand(True)
        btn_row.append(spacer_right)

        # Action section (kanan)
        self.ab_label = Gtk.Label(label="")
        self.ab_label.add_css_class("iina-time-label")
        btn_row.append(self.ab_label)

        # Chapter nav
        self.prev_chapter_btn = Gtk.Button.new_from_icon_name("media-seek-backward-symbolic")
        self.prev_chapter_btn.set_tooltip_text("Bab Sebelumnya (PgUp)")
        self.prev_chapter_btn.connect("clicked", lambda *_: self.navigate_chapter(-1))
        btn_row.append(self.prev_chapter_btn)

        self.next_chapter_btn = Gtk.Button.new_from_icon_name("media-seek-forward-symbolic")
        self.next_chapter_btn.set_tooltip_text("Bab Berikutnya (PgDn)")
        self.next_chapter_btn.connect("clicked", lambda *_: self.navigate_chapter(1))
        btn_row.append(self.next_chapter_btn)

        fullscreen_btn = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        fullscreen_btn.set_tooltip_text("Layar Penuh (f)")
        fullscreen_btn.connect("clicked", self.on_fullscreen_clicked)
        btn_row.append(fullscreen_btn)

        screenshot_btn = Gtk.Button.new_from_icon_name("camera-photo-symbolic")
        screenshot_btn.set_tooltip_text("Ambil Cuplikan Gambar / Screenshot (s)")
        screenshot_btn.connect("clicked", lambda *_: self.take_screenshot())
        btn_row.append(screenshot_btn)

        self.osd_box.append(btn_row)
        self.video_overlay.add_overlay(self.osd_box)

        # Toast notification OSD (Cuplikan layar, bookmark, dll.)
        self.toast_label = Gtk.Label(label="")
        self.toast_label.add_css_class("iina-toast")
        self.toast_label.set_halign(Gtk.Align.CENTER)
        self.toast_label.set_valign(Gtk.Align.START)
        self.toast_label.set_visible(False)
        self.video_overlay.add_overlay(self.toast_label)
        self._toast_timeout_id = None

        # ----------------- INSPECTOR PANEL (Kanan - macOS IINA Style) -----------------
        self.inspector_panel = self._build_inspector_panel()
        self.inspector_panel.set_visible(False)
        root.append(self.inspector_panel)

        # Key controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self.add_controller(key_controller)

        # Simpan ukuran jendela saat ditutup
        self.connect("close-request", self._on_close_request)

    def _build_music_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        self.music_art = Gtk.Image()
        self.music_art.set_pixel_size(180)
        self.music_art.set_from_icon_name("audio-x-generic-symbolic")
        box.append(self.music_art)

        self.music_title = Gtk.Label(label="Tidak Ada Musik Diputar")
        self.music_title.add_css_class("title-1")
        box.append(self.music_title)

        self.music_artist = Gtk.Label(label="—")
        self.music_artist.add_css_class("dim-label")
        box.append(self.music_artist)

        return box

    def _build_welcome_view(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.add_css_class("iina-welcome-screen")
        root_box.set_hexpand(True)
        root_box.set_vexpand(True)

        # Center container
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_vexpand(True)
        center_box.set_hexpand(True)
        center_box.set_margin_top(32)
        center_box.set_margin_bottom(32)

        # Header branding: App Icon + Name + Subtitle
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header_box.set_halign(Gtk.Align.CENTER)

        app_icon = Gtk.Image.new_from_icon_name("io.github.inaa")
        app_icon.set_pixel_size(72)
        header_box.append(app_icon)

        title_lbl = Gtk.Label(label="INAA")
        title_lbl.add_css_class("title-1")
        title_lbl.set_markup("<span size='xx-large' weight='bold'>INAA</span>")
        header_box.append(title_lbl)

        sub_lbl = Gtk.Label(label="Pemutar media modern & elegan untuk Linux")
        sub_lbl.add_css_class("dim-label")
        header_box.append(sub_lbl)

        center_box.append(header_box)

        # Main content grid: Quick Actions (Left/Top) and Recent Files (Right/Bottom)
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        content_box.set_halign(Gtk.Align.CENTER)

        # --- Quick Actions Column ---
        actions_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        actions_card.add_css_class("iina-welcome-card")
        actions_card.set_size_request(260, -1)
        actions_card.set_valign(Gtk.Align.START)

        actions_title = Gtk.Label(label="Mulai Menonton")
        actions_title.set_halign(Gtk.Align.START)
        actions_title.add_css_class("heading")
        actions_card.append(actions_title)

        # Open File Button
        btn_open = Gtk.Button()
        btn_open.add_css_class("iina-action-btn")
        btn_open.add_css_class("primary")
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon_file = Gtk.Image.new_from_icon_name("document-open-symbolic")
        lbl_file = Gtk.Label(label="Buka File...")
        b_box.append(icon_file)
        b_box.append(lbl_file)
        btn_open.set_child(b_box)
        btn_open.connect("clicked", lambda *_: self.on_open_clicked(None))
        actions_card.append(btn_open)

        # Open URL Button
        btn_url = Gtk.Button()
        btn_url.add_css_class("iina-action-btn")
        u_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon_url = Gtk.Image.new_from_icon_name("insert-link-symbolic")
        lbl_url = Gtk.Label(label="Buka URL / Stream...")
        u_box.append(icon_url)
        u_box.append(lbl_url)
        btn_url.set_child(u_box)
        btn_url.connect("clicked", lambda *_: self.on_open_url_clicked(None))
        actions_card.append(btn_url)

        # Drag hint
        hint_lbl = Gtk.Label(label="atau seret & lepas file ke sini")
        hint_lbl.add_css_class("dim-label")
        hint_lbl.set_margin_top(8)
        actions_card.append(hint_lbl)

        content_box.append(actions_card)

        # --- Recent Files Column ---
        recent_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        recent_card.add_css_class("iina-welcome-card")
        recent_card.set_size_request(340, 260)

        recent_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        recent_title = Gtk.Label(label="Terakhir Diputar")
        recent_title.set_halign(Gtk.Align.START)
        recent_title.set_hexpand(True)
        recent_title.add_css_class("heading")
        recent_header.append(recent_title)

        btn_clear_recent = Gtk.Button()
        btn_clear_recent.set_icon_name("edit-clear-symbolic")
        btn_clear_recent.set_has_frame(False)
        btn_clear_recent.set_tooltip_text("Bersihkan riwayat")
        btn_clear_recent.connect("clicked", lambda *_: self._clear_recent_files())
        recent_header.append(btn_clear_recent)

        recent_card.append(recent_header)

        # Scrolled list of recents
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.recent_listbox = Gtk.ListBox()
        self.recent_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(self.recent_listbox)
        recent_card.append(scroll)

        content_box.append(recent_card)
        center_box.append(content_box)
        root_box.append(center_box)

        self._populate_recent_files()
        return root_box

    def _build_inspector_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(280, -1)
        panel.add_css_class("iina-inspector")
        panel.set_margin_start(0)

        # Header switcher (VIDEO / AUDIO / SUBTITLE)
        self.insp_stack = Gtk.Stack()
        self.insp_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.insp_stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_margin_top(10)
        switcher.set_margin_bottom(6)
        panel.append(switcher)

        # Tab 1: VIDEO
        tab_video = self._build_video_tab()
        self.insp_stack.add_titled(tab_video, "video", "VIDEO")

        # Tab 2: AUDIO
        tab_audio = self._build_audio_tab()
        self.insp_stack.add_titled(tab_audio, "audio", "AUDIO")

        # Tab 3: SUBTITLE
        tab_sub = self._build_sub_tab()
        self.insp_stack.add_titled(tab_sub, "subtitles", "SUBTITLE")

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.insp_stack)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        panel.append(scroll)

        return panel

    def _build_video_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        # Hardware Decoding (hwdec)
        lbl_hw = Gtk.Label(label="Hardware Acceleration:")
        lbl_hw.set_xalign(0)
        lbl_hw.add_css_class("iina-sec-title")
        box.append(lbl_hw)

        hw_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for hw_val, hw_txt in [("auto-safe", "Auto"), ("vaapi", "VA-API"), ("nvdec", "NVDEC"), ("no", "Off")]:
            btn = Gtk.Button(label=hw_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=hw_val: self._set_hwdec(v))
            hw_box.append(btn)
        box.append(hw_box)

        # Aspect Ratio
        lbl_ar = Gtk.Label(label="Aspect Ratio:")
        lbl_ar.set_xalign(0)
        lbl_ar.add_css_class("iina-sec-title")
        box.append(lbl_ar)

        ar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for ar_val, ar_txt in [("no", "Default"), ("4:3", "4:3"), ("16:9", "16:9"), ("16:10", "16:10"), ("2.35:1", "2.35")]:
            btn = Gtk.Button(label=ar_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=ar_val: self._set_aspect_ratio(v))
            ar_box.append(btn)
        box.append(ar_box)

        # Video Crop / Black Bar Removal (ala IINA)
        lbl_crop = Gtk.Label(label="Video Crop (Black Bars):")
        lbl_crop.set_xalign(0)
        lbl_crop.add_css_class("iina-sec-title")
        box.append(lbl_crop)

        crop_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for c_val, c_txt in [("none", "None"), ("16:9", "16:9"), ("4:3", "4:3"), ("2.35:1", "2.35"), ("21:9", "21:9")]:
            btn = Gtk.Button(label=c_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=c_val: self._set_crop(v))
            crop_box.append(btn)
        box.append(crop_box)

        # Rotation
        lbl_rot = Gtk.Label(label="Rotation:")
        lbl_rot.set_xalign(0)
        lbl_rot.add_css_class("iina-sec-title")
        box.append(lbl_rot)

        rot_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for rot in [0, 90, 180, 270]:
            btn = Gtk.Button(label=f"{rot}°")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, r=rot: self._set_video_rotate(r))
            rot_box.append(btn)
        box.append(rot_box)

        # Speed
        lbl_spd = Gtk.Label(label="Playback Speed:")
        lbl_spd.set_xalign(0)
        lbl_spd.add_css_class("iina-sec-title")
        box.append(lbl_spd)

        spd_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_spd_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.25, 4.0, 0.25)
        self.insp_spd_scale.set_value(1.0)
        self.insp_spd_scale.set_hexpand(True)
        self.insp_spd_label = Gtk.Label(label="1.0x")
        def on_spd_changed(s):
            val = round(s.get_value(), 2)
            self._set_speed(val)
            self.insp_spd_label.set_text(f"{val:.2f}x".rstrip("0").rstrip(".") + "x")
        self.insp_spd_scale.connect("value-changed", on_spd_changed)
        spd_row.append(self.insp_spd_scale)
        spd_row.append(self.insp_spd_label)
        box.append(spd_row)

        # Deinterlace
        self.deinterlace_chk = Gtk.CheckButton(label="Deinterlace Video")
        self.deinterlace_chk.set_margin_top(6)
        def on_deint_toggled(chk):
            try:
                self.player.deinterlace = chk.get_active()
            except Exception:
                pass
        self.deinterlace_chk.connect("toggled", on_deint_toggled)
        box.append(self.deinterlace_chk)

        # Equalizer Video sliders (Brightness, Contrast, Saturation)
        lbl_adj = Gtk.Label(label="Penyesuaian Video:")
        lbl_adj.set_xalign(0)
        lbl_adj.add_css_class("iina-sec-title")
        box.append(lbl_adj)

        for prop, name in [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation")]:
            adj_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -100, 100, 1)
            sc.set_value(0)
            sc.set_hexpand(True)
            sc_lbl = Gtk.Label(label=f"{name}: 0")
            sc_lbl.set_size_request(95, -1)
            sc_lbl.set_xalign(0)
            sc.connect("value-changed", lambda s, p=prop, l=sc_lbl, n=name: self._on_filter_changed(p, s.get_value(), l, n))
            adj_row.append(sc_lbl)
            adj_row.append(sc)
            box.append(adj_row)

        return box

    def _build_audio_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        lbl_track = Gtk.Label(label="Audio Track:")
        lbl_track.set_xalign(0)
        lbl_track.add_css_class("iina-sec-title")
        box.append(lbl_track)

        self.insp_audio_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_audio_track_box)

        # Audio delay slider (-5s s/d +5s)
        lbl_delay = Gtk.Label(label="Audio Delay:")
        lbl_delay.set_xalign(0)
        lbl_delay.add_css_class("iina-sec-title")
        box.append(lbl_delay)

        del_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_audio_delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -5.0, 5.0, 0.1)
        self.insp_audio_delay_scale.set_value(0.0)
        self.insp_audio_delay_scale.set_hexpand(True)
        self.insp_audio_delay_label = Gtk.Label(label="0.0s")
        def on_adelay_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.audio_delay = val
            except Exception:
                pass
            self.insp_audio_delay_label.set_text(f"{val:+.1f}s")
        self.insp_audio_delay_scale.connect("value-changed", on_adelay_changed)
        del_row.append(self.insp_audio_delay_scale)
        del_row.append(self.insp_audio_delay_label)
        box.append(del_row)

        # Audio Equalizer Presets
        lbl_eq = Gtk.Label(label="Audio Presets:")
        lbl_eq.set_xalign(0)
        lbl_eq.add_css_class("iina-sec-title")
        box.append(lbl_eq)

        eq_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_bb = Gtk.Button(label="Bass Boost")
        btn_bb.add_css_class("iina-seg-btn")
        btn_bb.connect("clicked", lambda *_: self._set_audio_filter("bassboost"))
        eq_row.append(btn_bb)

        btn_voc = Gtk.Button(label="Vocal Boost")
        btn_voc.add_css_class("iina-seg-btn")
        btn_voc.connect("clicked", lambda *_: self._set_audio_filter("vocal"))
        eq_row.append(btn_voc)

        btn_night = Gtk.Button(label="Night Mode")
        btn_night.add_css_class("iina-seg-btn")
        btn_night.set_tooltip_text("Normalisasi volume dialog dan suara ledakan (Dynamic Range Compression)")
        btn_night.connect("clicked", lambda *_: self._set_audio_filter("nightmode"))
        eq_row.append(btn_night)

        btn_rst = Gtk.Button(label="Reset")
        btn_rst.add_css_class("iina-seg-btn")
        btn_rst.connect("clicked", lambda *_: self._set_audio_filter("reset"))
        eq_row.append(btn_rst)
        box.append(eq_row)

        return box

    def _build_sub_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        lbl_track = Gtk.Label(label="Primary Subtitle (Bawah):")
        lbl_track.set_xalign(0)
        lbl_track.add_css_class("iina-sec-title")
        box.append(lbl_track)

        self.insp_sub_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_sub_track_box)

        # Secondary Subtitle (Dual Subtitle feature ala IINA)
        lbl_sec_track = Gtk.Label(label="Secondary Subtitle (Atas):")
        lbl_sec_track.set_xalign(0)
        lbl_sec_track.add_css_class("iina-sec-title")
        lbl_sec_track.set_margin_top(8)
        box.append(lbl_sec_track)

        self.insp_sec_sub_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_sec_sub_track_box)

        # External Subtitle Buttons
        lbl_ext = Gtk.Label(label="External Subtitles:")
        lbl_ext.set_xalign(0)
        lbl_ext.add_css_class("iina-sec-title")
        box.append(lbl_ext)

        ext_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_load = Gtk.Button(label="Load File...")
        btn_load.add_css_class("iina-seg-btn")
        btn_load.connect("clicked", self._open_local_sub_dialog)
        ext_row.append(btn_load)

        btn_online = Gtk.Button(label="Search Online...")
        btn_online.add_css_class("iina-seg-btn")
        btn_online.connect("clicked", self._open_online_sub_dialog)
        ext_row.append(btn_online)
        box.append(ext_row)

        # Subtitle delay (-5s s/d +5s)
        lbl_sub_delay = Gtk.Label(label="Subtitle Delay:")
        lbl_sub_delay.set_xalign(0)
        lbl_sub_delay.add_css_class("iina-sec-title")
        box.append(lbl_sub_delay)

        del_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -5.0, 5.0, 0.1)
        self.insp_sub_delay_scale.set_value(0.0)
        self.insp_sub_delay_scale.set_hexpand(True)
        self.insp_sub_delay_label = Gtk.Label(label="0.0s")
        def on_sdelay_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.sub_delay = val
            except Exception:
                pass
            self.insp_sub_delay_label.set_text(f"{val:+.1f}s")
        self.insp_sub_delay_scale.connect("value-changed", on_sdelay_changed)
        del_row.append(self.insp_sub_delay_scale)
        del_row.append(self.insp_sub_delay_label)
        box.append(del_row)

        # Scale / Font Size (0.5 s/d 2.0)
        lbl_scale = Gtk.Label(label="Scale (Ukuran Font):")
        lbl_scale.set_xalign(0)
        lbl_scale.add_css_class("iina-sec-title")
        box.append(lbl_scale)

        scale_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.5, 0.05)
        self.insp_sub_scale.set_value(1.0)
        self.insp_sub_scale.set_hexpand(True)
        self.insp_sub_scale_label = Gtk.Label(label="1.0x")
        def on_sub_scale_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.sub_scale = val
            except Exception:
                pass
            self.insp_sub_scale_label.set_text(f"{val:.2f}x")
        self.insp_sub_scale.connect("value-changed", on_sub_scale_changed)
        scale_row.append(self.insp_sub_scale)
        scale_row.append(self.insp_sub_scale_label)
        box.append(scale_row)

        # Position (0 s/d 100)
        lbl_pos = Gtk.Label(label="Position (Posisi):")
        lbl_pos.set_xalign(0)
        lbl_pos.add_css_class("iina-sec-title")
        box.append(lbl_pos)

        pos_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_pos = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.insp_sub_pos.set_value(100)
        self.insp_sub_pos.set_hexpand(True)
        def on_sub_pos_changed(s):
            try:
                self.player.sub_pos = int(s.get_value())
            except Exception:
                pass
        self.insp_sub_pos.connect("value-changed", on_sub_pos_changed)
        pos_row.append(self.insp_sub_pos)
        box.append(pos_row)

        # Subtitle Color & Styling (ala IINA)
        lbl_style = Gtk.Label(label="Subtitle Style & Color:")
        lbl_style.set_xalign(0)
        lbl_style.add_css_class("iina-sec-title")
        box.append(lbl_style)

        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for col_name, col_code in [("Putih", "#FFFFFF"), ("Kuning", "#FFFF00"), ("Cyan", "#00FFFF"), ("Hijau", "#00FF00")]:
            btn = Gtk.Button(label=col_name)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, c=col_code, n=col_name: self._set_sub_color(c, n))
            color_row.append(btn)
        box.append(color_row)

        # Background Box Toggle (High Contrast untuk teks)
        self.sub_box_chk = Gtk.CheckButton(label="Tampilkan Kotak Latar Belakang (High Contrast)")
        self.sub_box_chk.set_margin_top(4)
        def on_sub_box_toggled(chk):
            try:
                if chk.get_active():
                    self.player.sub_back_color = "#80000000"  # Semi-transparent black box
                    self.show_toast("Subtitle Background Box: Aktif")
                else:
                    self.player.sub_back_color = "#00000000"  # Transparent
                    self.show_toast("Subtitle Background Box: Nonaktif")
            except Exception:
                pass
        self.sub_box_chk.connect("toggled", on_sub_box_toggled)
        box.append(self.sub_box_chk)

        return box

    def _setup_drag_and_drop(self):
        target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        target.connect("drop", self.on_drop)
        self.add_controller(target)

    def _connect_signals(self):
        # Motion controller untuk mendeteksi pergerakan kursor dan auto-hide OSD
        video_motion = Gtk.EventControllerMotion()
        video_motion.connect("motion", self._on_video_motion)
        self.video_overlay.add_controller(video_motion)

        # Gunakan gesture drag untuk mendeteksi saat slider mulai ditarik dan dilepas
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", lambda *_: self._set_dragging(True))
        drag.connect("drag-end", self._on_drag_end)
        self.seekbar.add_controller(drag)

        # Signal value-changed langsung merespon saat slider ditarik/digeser
        self.seekbar.connect("value-changed", self._on_seekbar_value_changed)

        # Hover motion & thumbnail preview pada seekbar
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_seekbar_motion)
        motion.connect("leave", self._on_seekbar_leave)
        self.seekbar.add_controller(motion)

