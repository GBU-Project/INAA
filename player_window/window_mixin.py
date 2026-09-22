"""Toasts, screenshots, mini-player detach/attach, context menu, open-file/open-url dialogs, plugin hooks."""
from .common import *  # noqa: F401,F403


class WindowMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def show_toast(self, message, duration_ms=2500):
        if hasattr(self, "toast_label"):
            self.toast_label.set_text(message)
            self.toast_label.set_visible(True)
            if self._toast_timeout_id:
                GLib.source_remove(self._toast_timeout_id)
                self._toast_timeout_id = None
            def hide_toast():
                self.toast_label.set_visible(False)
                self._toast_timeout_id = None
                return False
            self._toast_timeout_id = GLib.timeout_add(duration_ms, hide_toast)

    def take_screenshot(self):
        if not self._current_path:
            self.show_toast("Tidak ada media yang diputar")
            return

        out_file = None
        try:
            # Simpan ke ~/Pictures/INAA atau ~/Pictures
            pics_dir = Path.home() / "Pictures" / "INAA"
            pics_dir.mkdir(parents=True, exist_ok=True)
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(self._current_path))[0]
            clean_name = "".join(c for c in base_name if c.isalnum() or c in ("-", "_")).strip() or "screenshot"
            out_file = str(pics_dir / f"{clean_name}_{ts}.png")

            # Perintah screenshot video libmpv
            self.player.command("screenshot-to-file", out_file, "video")
            self.show_toast(f"📷 Cuplikan disimpan ke:\nPictures/INAA/{os.path.basename(out_file)}")
        except Exception:
            try:
                if out_file is None:
                    # Belum sempat menyiapkan nama file (mis. gagal membuat
                    # folder Pictures/INAA) — tidak ada apa pun untuk
                    # dijadikan fallback, langsung lempar ke handler luar.
                    raise
                # Fallback format biasa
                self.player.screenshot(out_file)
                self.show_toast(f"📷 Cuplikan disimpan ke Pictures/INAA/{os.path.basename(out_file)}")
            except Exception as e2:
                self.show_toast(f"Gagal mengambil cuplikan: {e2}")

    def detach_video_window(self):
        """"Pisahkan" video jadi window kecil mengambang.

        CATATAN PENTING (kenapa implementasinya seperti ini):
        Versi awal fitur ini memindahkan `self.gl_area` (GLArea yang sama,
        dengan render context mpv yang sedang aktif) ke sebuah `Gtk.Window`
        baru. Itu SELALU memicu unrealize+realize pada GLArea (karena GTK
        mewajibkan itu saat widget pindah top-level window), yang otomatis
        membebaskan lalu membuat ulang MpvRenderContext.

        Setelah diuji, ternyata `vo=libmpv` milik mpv TIDAK BISA bertahan
        begitu render context-nya dibebaskan sementara ada media yang lagi
        dimuat — mpv langsung menganggap video output gagal fatal dan
        meng-unload file yang sedang diputar (walau sudah di-pause dulu
        sebelum reparenting; sudah diuji juga tetap gagal). Alias: video
        yang sedang diputar akan mati setiap kali GLArea direparenting ke
        window lain, terlepas dari cara reparenting-nya.

        Karena itu, "detach" di sini TIDAK membuat window baru sama sekali.
        Sebagai gantinya dipakai mekanisme yang sama dengan Mini Player
        (yang sudah terbukti aman karena tidak pernah menyentuh parent
        dari gl_area): jendela utama yang sama diperkecil & chrome
        disembunyikan, memberi efek "mengambang" tanpa pernah membongkar
        render context.
        """
        if not self._current_path:
            self.show_toast("Tidak ada video untuk dipisahkan")
            return
        if not self._is_mini:
            self.mini_btn.set_active(True)  # akan memicu on_mini_toggled
        self.show_toast("Mode mengambang aktif (video tetap di window yang sama)")

    def attach_video_window(self):
        if self._is_mini:
            self.mini_btn.set_active(False)
            self.show_toast("Kembali ke tampilan penuh")

    def _on_video_right_click(self, gesture, n_press, x, y):
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self.video_context_popover.set_pointing_to(rect)
        self._rebuild_video_context_menu()
        self.video_context_popover.popup()

    def _rebuild_video_context_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Mini Player toggle
        if self._is_mini:
            mini_label = "Kembali ke Ukuran Normal (Esc)"
            mini_icon = "view-restore-symbolic"
        else:
            mini_label = "Mode Mini Player"
            mini_icon = "view-restore-symbolic"

        btn_mini = Gtk.Button(label=mini_label)
        btn_mini.set_icon_name(mini_icon)
        def toggle_mini_action(_):
            self.video_context_popover.popdown()
            self.mini_btn.set_active(not self._is_mini)
        btn_mini.connect("clicked", toggle_mini_action)
        box.append(btn_mini)

        # Inspector Panel toggle
        if not self._is_mini:
            insp_label = "Sembunyikan Inspector (i)" if self.inspector_panel.get_visible() else "Inspector Pengaturan (i)"
            btn_insp = Gtk.Button(label=insp_label)
            btn_insp.set_icon_name("preferences-other-symbolic")
            def toggle_insp_action(_):
                self.video_context_popover.popdown()
                self.inspector_btn.set_active(not self.inspector_btn.get_active())
            btn_insp.connect("clicked", toggle_insp_action)
            box.append(btn_insp)

        # Layar Penuh
        if not self._is_mini:
            fs_label = "Keluar Layar Penuh (f / Esc)" if self.is_fullscreen() else "Layar Penuh (f)"
            btn_fs = Gtk.Button(label=fs_label)
            btn_fs.set_icon_name("view-fullscreen-symbolic")
            def toggle_fs_action(_):
                self.video_context_popover.popdown()
                self.on_fullscreen_clicked(None)
            btn_fs.connect("clicked", toggle_fs_action)
            box.append(btn_fs)

        # Putar / Jeda
        is_playing = not self.player.pause
        play_label = "Jeda (Spasi)" if is_playing else "Putar (Spasi)"
        play_icon = "media-playback-pause-symbolic" if is_playing else "media-playback-start-symbolic"
        btn_play = Gtk.Button(label=play_label)
        btn_play.set_icon_name(play_icon)
        def toggle_play_action(_):
            self.video_context_popover.popdown()
            self.on_playpause_clicked(None)
        btn_play.connect("clicked", toggle_play_action)
        box.append(btn_play)

        # Bisu / Suara
        is_muted = self.player.mute
        mute_label = "Aktifkan Suara (m)" if is_muted else "Bisu (m)"
        mute_icon = "audio-volume-muted-symbolic" if is_muted else "audio-volume-high-symbolic"
        btn_mute = Gtk.Button(label=mute_label)
        btn_mute.set_icon_name(mute_icon)
        def toggle_mute_action(_):
            self.video_context_popover.popdown()
            self.on_mute_clicked(None)
        btn_mute.connect("clicked", toggle_mute_action)
        box.append(btn_mute)

        # Cuplikan Layar (Screenshot)
        btn_shot = Gtk.Button(label="Ambil Cuplikan Gambar (s)")
        btn_shot.set_icon_name("camera-photo-symbolic")
        def shot_action(_):
            self.video_context_popover.popdown()
            self.take_screenshot()
        btn_shot.connect("clicked", shot_action)
        box.append(btn_shot)

        # Pisahkan Window Video (Detach Picture-in-Picture)
        if not self._is_mini:
            btn_detach = Gtk.Button(label="Pisahkan Window Video (Detach)")
            btn_detach.set_icon_name("window-new-symbolic")
            def detach_action(_):
                self.video_context_popover.popdown()
                self.detach_video_window()
            btn_detach.connect("clicked", detach_action)
            box.append(btn_detach)

        self.video_context_popover.set_child(box)

    def on_open_url_clicked(self, button):
        dialog = Gtk.Dialog(
            title="Buka dari URL",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Buka", Gtk.ResponseType.OK,
        )
        dialog.set_default_size(420, -1)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label="Tempel link video (YouTube, Vimeo, dll.):")
        label.set_xalign(0)
        content.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text("https://www.youtube.com/watch?v=...")
        entry.set_activates_default(True)
        content.append(entry)

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect("response", self._on_open_url_response, entry)
        dialog.show()
        entry.grab_focus()

    def _on_open_url_response(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK:
            url = entry.get_text().strip()
            if url:
                if not is_allowed_media_uri(url):
                    self.show_toast("URL tidak diizinkan (hanya http/https)")
                else:
                    self.add_to_playlist(url)
                    self.open_file(url)
        dialog.destroy()

    def on_open_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Pilih video atau musik",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Buka", Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_open_dialog_response)
        dialog.show()

    def _on_open_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            files = dialog.get_files()
            paths = [files.get_item(i).get_path() for i in range(files.get_n_items())]
            for p in paths:
                self.add_to_playlist(p)
            if paths:
                self.open_file(paths[0])
        dialog.destroy()

    def _load_plugins(self):
        enabled = self._config.get("enabled_plugins") or []
        self._plugins = load_plugins(self, PLUGINS_DIR, enabled)

    def _trigger_plugin_hook(self, hook_name, *args, **kwargs):
        for plugin in self._plugins:
            fn = getattr(plugin, hook_name, None)
            if callable(fn):
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass

