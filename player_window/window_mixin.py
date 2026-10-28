"""Toasts, screenshots, mini-player detach/attach, context menu, open-file/open-url dialogs, plugin hooks."""
import os
from pathlib import Path

from gi.repository import Gdk, GLib, Gtk, Pango

from fmt import display_name as _display_name, format_time as _format_time
from media_uri import is_allowed_media_uri
from plugin_loader import load_plugins

from .common import PLUGINS_DIR
from .media_types import AUDIO_EXTENSIONS


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
        self.show_toast("Mini player aktif (selalu di atas)")

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

        btn_loop = Gtk.Button(label={"off": "Ulangi: Mati", "all": "Ulangi: Semua", "one": "Ulangi: Satu"}.get(self._loop_mode, "Ulangi"))
        btn_loop.set_icon_name("media-playlist-repeat-symbolic")
        def loop_action(_):
            self.video_context_popover.popdown()
            self.cycle_loop_mode()
        btn_loop.connect("clicked", loop_action)
        box.append(btn_loop)

        btn_shuffle = Gtk.Button(label="Acak: Aktif" if self._shuffle else "Acak: Mati")
        btn_shuffle.set_icon_name("media-playlist-shuffle-symbolic")
        def shuffle_action(_):
            self.video_context_popover.popdown()
            self._set_shuffle(not self._shuffle, from_ui=True)
        btn_shuffle.connect("clicked", shuffle_action)
        box.append(btn_shuffle)

        btn_hist = Gtk.Button(label="Riwayat Pemutaran (Ctrl+H)")
        btn_hist.set_icon_name("document-open-recent-symbolic")
        def hist_action(_):
            self.video_context_popover.popdown()
            self.open_history_dialog()
        btn_hist.connect("clicked", hist_action)
        box.append(btn_hist)

        btn_prefs = Gtk.Button(label="Pengaturan (Ctrl+P)")
        btn_prefs.set_icon_name("preferences-system-symbolic")
        def prefs_action(_):
            self.video_context_popover.popdown()
            self.open_preferences()
        btn_prefs.connect("clicked", prefs_action)
        box.append(btn_prefs)

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

    def open_history_dialog(self, _button=None):
        """Membuka jendela Riwayat Pemutaran dengan pencarian (ala IINA Playback History)."""
        dialog = Gtk.Dialog(
            title="Riwayat Pemutaran",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons("Tutup", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(620, 520)

        content = dialog.get_content_area()
        dialog.add_css_class("iina-history-dialog")  # seluruh jendela, bukan hanya area isi
        content.add_css_class("iina-history-dialog")
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_spacing(10)

        # Header bar search & clear
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text("Cari riwayat (nama file, judul, path)...")
        search_entry.set_hexpand(True)
        top_bar.append(search_entry)

        btn_clear = Gtk.Button(label="Bersihkan Riwayat")
        btn_clear.add_css_class("destructive-action")

        confirm_popover = Gtk.Popover()
        confirm_popover.set_parent(btn_clear)
        confirm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        confirm_box.set_margin_start(10)
        confirm_box.set_margin_end(10)
        confirm_box.set_margin_top(8)
        confirm_box.set_margin_bottom(8)
        lbl_confirm = Gtk.Label(label="Hapus semua riwayat pemutaran?")
        lbl_confirm.add_css_class("iina-sec-title")
        confirm_box.append(lbl_confirm)

        btn_confirm_clear = Gtk.Button(label="Ya, Hapus Semua")
        btn_confirm_clear.add_css_class("destructive-action")
        def on_confirm_clear_clicked(_b):
            confirm_popover.popdown()
            self._clear_recent_files()
            populate_history(search_entry.get_text())
            self.show_toast("Riwayat pemutaran dibersihkan")
        btn_confirm_clear.connect("clicked", on_confirm_clear_clicked)
        confirm_box.append(btn_confirm_clear)
        confirm_popover.set_child(confirm_box)

        btn_clear.connect("clicked", lambda *_: confirm_popover.popup())
        top_bar.append(btn_clear)
        content.append(top_bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(listbox)
        content.append(scroll)

        def populate_history(query=""):
            child = listbox.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                listbox.remove(child)
                child = nxt

            recents = self._config.get("recent_files", [])
            query_lower = query.strip().lower()

            filtered = []
            for item in recents:
                p = item.get("path", "")
                t = item.get("title", "")
                if not query_lower or query_lower in p.lower() or query_lower in t.lower():
                    filtered.append(item)

            if not filtered:
                empty_lbl = Gtk.Label(label="Tidak ada riwayat pemutaran yang cocok" if query_lower else "Belum ada riwayat pemutaran")
                empty_lbl.add_css_class("dim-label")
                empty_lbl.set_valign(Gtk.Align.CENTER)
                empty_lbl.set_vexpand(True)
                listbox.append(empty_lbl)
                return

            for item in filtered:
                path = item.get("path")
                if not path:
                    continue

                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.add_css_class("iina-history-row")

                icon_name = "audio-x-generic-symbolic" if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS else "video-x-generic-symbolic"
                img = Gtk.Image.new_from_icon_name(icon_name)
                img.set_pixel_size(24)
                img.set_valign(Gtk.Align.CENTER)
                row.append(img)

                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                info_box.set_hexpand(True)

                title_txt = item.get("title") or _display_name(path)
                t_lbl = Gtk.Label(label=title_txt)
                t_lbl.set_halign(Gtk.Align.START)
                t_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                t_lbl.add_css_class("iina-recent-title")
                info_box.append(t_lbl)

                pos = item.get("position", 0)
                dur = item.get("duration", 0)
                last_played = item.get("last_played", "")

                details = []
                if dur > 0 and pos > 0:
                    pct = int((pos / dur) * 100)
                    details.append(f"Posisi: {_format_time(pos)} / {_format_time(dur)} ({pct}%)")
                elif dur > 0:
                    details.append(f"Durasi: {_format_time(dur)}")

                if last_played:
                    details.append(f"Terakhir: {last_played}")

                sub_txt = " • ".join(details) if details else path
                s_lbl = Gtk.Label(label=sub_txt)
                s_lbl.set_halign(Gtk.Align.START)
                s_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                s_lbl.add_css_class("iina-recent-sub")
                info_box.append(s_lbl)

                # Path kecil
                p_lbl = Gtk.Label(label=path)
                p_lbl.set_halign(Gtk.Align.START)
                p_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                p_lbl.add_css_class("dim-label")
                info_box.append(p_lbl)

                row.append(info_box)

                play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
                play_btn.set_tooltip_text("Putar dan lanjutkan")
                play_btn.set_valign(Gtk.Align.CENTER)
                missing = "://" not in path and not os.path.exists(path)
                opened = [False]  # cegah open_file ganda (tombol + klik baris)

                def on_play_clicked(_b, p=path, resume_pos=pos, dur=dur, gone=missing):
                    if opened[0]:
                        return
                    if gone:
                        self.show_toast("File tidak ditemukan")
                        return
                    opened[0] = True
                    dialog.destroy()
                    # Hampir selesai ditonton -> mulai dari awal, bukan dari ujung.
                    ext = os.path.splitext(p)[1].lower()
                    if ext in AUDIO_EXTENSIONS or (resume_pos and dur and resume_pos >= dur - 5):
                        resume_pos = 0
                    self.open_file(p, resume_pos=resume_pos or None)

                if missing:
                    play_btn.set_sensitive(False)
                    play_btn.set_tooltip_text("File tidak ditemukan")
                    row.set_opacity(0.55)
                    s_lbl.set_text("File tidak ditemukan • " + sub_txt)
                else:
                    play_btn.connect("clicked", on_play_clicked)
                    # Klik pada baris (bukan tombol) juga memutar; tombol sendiri
                    # sudah menangani kliknya, jadi gesture hanya di area info.
                    gesture = Gtk.GestureClick()
                    gesture.connect("released", lambda _g, _n, _x, _y: on_play_clicked(None))
                    info_box.add_controller(gesture)
                row.append(play_btn)

                listbox.append(row)

        search_entry.connect("search-changed", lambda e: populate_history(e.get_text()))
        populate_history()
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()

