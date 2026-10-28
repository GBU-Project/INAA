"""Subtitle track selection/styling and local/online subtitle loading."""
import os
import threading

from gi.repository import Gio, GLib, Gtk

from opensubtitles import download_subtitle, search_subtitles

from .media_types import SUBTITLE_EXTENSIONS


class SubtitlesMixin:
    """Mixed into PlayerWindow. See module docstring for scope."""

    def _set_sub_color(self, color_code, name):
        try:
            self.player.sub_color = color_code
            self.show_toast(f"Subtitle Color: {name}")
        except Exception:
            pass

    def _refresh_inspector_tracks(self):
        try:
            tracks = self.player.track_list or []
        except Exception:
            tracks = []

        # Audio tracks
        while child := self.insp_audio_track_box.get_first_child():
            self.insp_audio_track_box.remove(child)

        audio_tracks = [t for t in tracks if t.get("type") == "audio"]
        current_aid = getattr(self.player, "aid", None)
        for t in audio_tracks:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Audio #{tid}"
            is_sel = (current_aid == tid) or t.get("selected")
            btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("aid", track_id))
            self.insp_audio_track_box.append(btn)

        # Primary Subtitle tracks
        while child := self.insp_sub_track_box.get_first_child():
            self.insp_sub_track_box.remove(child)

        current_sid = getattr(self.player, "sid", None)
        none_btn = Gtk.Button(label=f"{'✓ ' if current_sid in ('no', False, None) else '   '}<None>")
        none_btn.add_css_class("iina-seg-btn")
        none_btn.connect("clicked", lambda *_: self._set_track("sid", "no"))
        self.insp_sub_track_box.append(none_btn)

        sub_tracks = [t for t in tracks if t.get("type") == "sub"]
        for t in sub_tracks:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Sub #{tid}"
            is_sel = (current_sid == tid) or t.get("selected")
            btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("sid", track_id))
            self.insp_sub_track_box.append(btn)

        # Secondary Subtitle tracks (Dual Subtitle)
        if hasattr(self, "insp_sec_sub_track_box"):
            while child := self.insp_sec_sub_track_box.get_first_child():
                self.insp_sec_sub_track_box.remove(child)

            try:
                current_sec_sid = getattr(self.player, "secondary_sid", "no")
            except Exception:
                current_sec_sid = "no"

            sec_none_btn = Gtk.Button(label=f"{'✓ ' if current_sec_sid in ('no', False, None) else '   '}<None>")
            sec_none_btn.add_css_class("iina-seg-btn")
            sec_none_btn.connect("clicked", lambda *_: self._set_track("secondary_sid", "no"))
            self.insp_sec_sub_track_box.append(sec_none_btn)

            for t in sub_tracks:
                tid = t.get("id")
                name = t.get("title") or t.get("lang") or f"Sub #{tid}"
                is_sel = (current_sec_sid == tid)
                btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
                btn.add_css_class("iina-seg-btn")
                btn.connect("clicked", lambda b, track_id=tid: self._set_track("secondary_sid", track_id))
                self.insp_sec_sub_track_box.append(btn)

    def _rebuild_track_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        try:
            tracks = self.player.track_list or []
        except Exception:
            tracks = []

        # Deteksi track yang sedang aktif
        current_aid = getattr(self.player, "aid", None)
        current_sid = getattr(self.player, "sid", None)

        audio_label = Gtk.Label(label="Audio Track")
        audio_label.set_xalign(0)
        box.append(audio_label)
        for t in [t for t in tracks if t.get("type") == "audio"]:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Track {tid}"
            is_sel = t.get("selected") or (current_aid == tid)
            prefix = "✓ " if is_sel else "   "
            btn = Gtk.Button(label=f"{prefix}{name}")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("aid", track_id))
            box.append(btn)

        sub_label = Gtk.Label(label="Subtitle Track")
        sub_label.set_xalign(0)
        sub_label.set_margin_top(8)
        box.append(sub_label)

        # Tombol nonaktifkan subtitle
        is_none_sel = (current_sid in (False, "no", None))
        none_prefix = "✓ " if is_none_sel else "   "
        none_btn = Gtk.Button(label=f"{none_prefix}Nonaktifkan Subtitle")
        none_btn.connect("clicked", lambda b: self._set_track("sid", "no"))
        box.append(none_btn)

        for t in [t for t in tracks if t.get("type") == "sub"]:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Track {tid}"
            is_sel = t.get("selected") or (current_sid == tid)
            prefix = "✓ " if is_sel else "   "
            btn = Gtk.Button(label=f"{prefix}{name}")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("sid", track_id))
            box.append(btn)

        # Online subtitle search button
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box.append(sep)

        online_sub_btn = Gtk.Button(label="Cari Subtitle Online...")
        online_sub_btn.connect("clicked", self._open_online_sub_dialog)
        box.append(online_sub_btn)

        local_sub_btn = Gtk.Button(label="Buka File Subtitle (Lokal)...")
        local_sub_btn.connect("clicked", self._open_local_sub_dialog)
        box.append(local_sub_btn)

        self.track_popover.set_child(box)

    def _set_track(self, kind, value):
        try:
            setattr(self.player, kind, value)
        except Exception:
            pass
        self.track_popover.popdown()
        if hasattr(self, "inspector_panel") and self.inspector_panel.get_visible():
            self._refresh_inspector_tracks()

    def _add_and_select_subtitle(self, sub_path):
        try:
            # Dapatkan daftar id track sub sebelum menambah
            old_sub_ids = {t["id"] for t in (self.player.track_list or []) if t.get("type") == "sub"}
            self.player.sub_add(sub_path)
            # Cari track sub baru yang baru saja ditambahkan dan pilih langsung
            new_tracks = [t for t in (self.player.track_list or []) if t.get("type") == "sub"]
            for t in new_tracks:
                if t.get("id") not in old_sub_ids or t.get("external_filename") == sub_path or t.get("title") == os.path.basename(sub_path):
                    self.player.sid = t["id"]
                    break
            if hasattr(self, "inspector_panel") and self.inspector_panel.get_visible():
                self._refresh_inspector_tracks()
        except Exception:
            pass

    def _open_online_sub_dialog(self, button):
        self.track_popover.popdown()
        dialog = Gtk.Dialog(title="Cari Subtitle Online", transient_for=self, modal=True)
        dialog.set_default_size(420, 360)

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        default_query = os.path.splitext(os.path.basename(self._current_path or ""))[0]
        search_entry = Gtk.Entry()
        search_entry.set_text(default_query)
        search_entry.set_hexpand(True)
        search_btn = Gtk.Button(label="Cari")
        entry_row.append(search_entry)
        entry_row.append(search_btn)
        box.append(entry_row)

        status_lbl = Gtk.Label(label="Ketik judul dan tekan Cari")
        status_lbl.set_xalign(0)
        status_lbl.set_wrap(True)
        box.append(status_lbl)

        results_list = Gtk.ListBox()
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(results_list)
        box.append(scroll)

        def do_search(*_):
            query = search_entry.get_text().strip()
            if not query:
                return
            status_lbl.set_text("Mencari subtitle...")
            # Bersihkan hasil lama
            ch = results_list.get_first_child()
            while ch:
                nxt = ch.get_next_sibling()
                results_list.remove(ch)
                ch = nxt

            def fetch():
                try:
                    api_key = (self._config.get("opensubtitles_api_key") or "").strip() or None
                    data = search_subtitles(query, api_key=api_key)
                    GLib.idle_add(lambda: render_results(data))
                except Exception as e:
                    msg = str(e)
                    GLib.idle_add(lambda m=msg: status_lbl.set_text(m))

            threading.Thread(target=fetch, daemon=True).start()

        def render_results(data):
            if not data:
                status_lbl.set_text("Subtitle tidak ditemukan.")
                return
            status_lbl.set_text(f"Ditemukan {len(data)} subtitle:")
            for item in data[:15]:
                sub_name = item.get("name") or "Subtitle"
                lang = item.get("lang") or ""
                file_id = item.get("file_id")
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f"[{lang}] {sub_name}")
                btn.connect("clicked", lambda b, fid=file_id, n=sub_name: download_and_load_sub(fid, n, dialog))
                row.set_child(btn)
                results_list.append(row)

        def download_and_load_sub(file_id, filename, dlg):
            if not file_id:
                status_lbl.set_text("ID file subtitle tidak valid.")
                return
            status_lbl.set_text(f"Mengunduh {filename}...")
            def dl():
                try:
                    api_key = (self._config.get("opensubtitles_api_key") or "").strip() or None
                    out_path = download_subtitle(file_id, filename, api_key=api_key)
                    GLib.idle_add(lambda: apply_sub(out_path, dlg))
                except Exception as e:
                    GLib.idle_add(lambda err=e: status_lbl.set_text(f"Gagal unduh: {err}"))
            threading.Thread(target=dl, daemon=True).start()

        def apply_sub(sub_path, dlg):
            try:
                self._add_and_select_subtitle(sub_path)
                dlg.destroy()
            except Exception:
                pass

        search_btn.connect("clicked", do_search)
        search_entry.connect("activate", do_search)

        content.append(box)
        dialog.show()

    def _open_local_sub_dialog(self, button):
        self.track_popover.popdown()
        dialog = Gtk.FileDialog()
        dialog.set_title("Pilih File Subtitle")

        filter_sub = Gtk.FileFilter()
        filter_sub.set_name("File Subtitle (*.srt, *.vtt, *.ass, ...)")
        for ext in SUBTITLE_EXTENSIONS:
            filter_sub.add_pattern(f"*{ext}")
            filter_sub.add_pattern(f"*{ext.upper()}")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("Semua File")
        filter_all.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_sub)
        filters.append(filter_all)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_sub)

        def on_open_finish(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    sub_path = gfile.get_path()
                    if sub_path:
                        self._add_and_select_subtitle(sub_path)
            except Exception:
                pass

        dialog.open(self, None, on_open_finish)

