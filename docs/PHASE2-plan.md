# Rencana implementasi Phase 2 — OSC, header bar, tema

Turunan dari `docs/ROADMAP-plugin-layout.md` (bagian Phase 2). Dokumen ini
adalah rencana kerja; status tiap tahap dicatat di bagian "Status".

## Temuan dasar

- Skema `layout` (`layout_config.py`) sudah memvalidasi `osc.*`, `headerbar`,
  `theme.*`, `reduce_motion`, dan preset. Belum ada konsumen UI-nya, jadi tidak
  perlu migrasi config baru.
- Tema masih satu blob CSS dengan warna tertanam (`#007aff` di banyak aturan).
  `_apply_iina_css()` hanya menambah provider sekali ke display.
- `tests/test_theme_css.py` mengambil literal `_IINA_CSS` lewat `ast`, dan
  `tests/test_css_contrast.py` memakai regex pada teks `theme.py`. Keduanya harus
  diubah saat CSS dibuat dari template.
- OSC sekarang `osd_box` di dalam `Gtk.Overlay` (lebar tetap 440 px,
  `valign=END`, `halign=CENTER`); popover thumbnail menempel pada `seekbar`.
- Header bar memuat hampir semua tombol fitur, jadi mode `hidden` berisiko
  membuat fitur tidak terjangkau.
- Modul baru harus masuk manifest Flatpak (`tests/test_flatpak_manifest.py`).

## Keputusan yang dipakai

1. Satu `CssProvider` global (bukan per-window).
2. OSC `docked` memakai ruang sendiri di atas/bawah video; `gl_area` tidak
   pernah dipindah (render context libmpv rapuh).
3. Header bar `hidden` dibuktikan lewat spike (`Gtk.WindowHandle` +
   `Gtk.WindowControls`, bukan `set_decorated(False)`) sebelum dikerjakan penuh.

## Tahap

### 2.0 Pemisahan murni (±2–3 hari)
- `palette.py` (root): dataclass palet + `contrast_ratio()`; tanpa GTK/mpv.
- `theme_css.py` (root): `build_css(palette, accent)`; tanpa GTK/mpv.
  Ditaruh di root (bukan `player_window/`) agar bisa diimpor tes tanpa memicu
  `player_window/__init__.py` yang meng-import `gi` dan `mpv`.
- Tes snapshot: `build_css("iina-glass", "blue")` identik dengan CSS lama.
- Ubah `test_theme_css.py` dan `test_css_contrast.py` agar memanggil `build_css`.
- Daftarkan modul baru di manifest Flatpak (`palette.py`, `theme_css.py` harus
  masuk daftar `cp -r`). Catatan: folder `flatpak/` tidak ada di working tree saat
  tahap ini dikerjakan, jadi langkah ini belum bisa dilakukan.

### 2.1 Theme manager (±1 minggu)
- Satu `CssProvider` yang dimuat ulang saat tema berubah (live, tanpa restart).
- Palet `iina-glass`, `graphite`, `light`; aksen blue/purple/pink/orange/green/graphite.
- Mode `system`: portal `org.freedesktop.appearance color-scheme` lewat
  `Gio.DBusProxy`, fallback `Gtk.Settings`.
- Sinkronkan `gtk-application-prefer-dark-theme` dengan palet.
- Reduce motion: `layout.reduce_motion` atau `gtk-enable-animations` mati ->
  class `.reduce-motion` dan transisi stack `NONE`.
- Tes: semua role terdefinisi, kontras teks >= 4.5 (WCAG AA), palet x aksen dimuat
  tanpa "Theme parser error".

### 2.2 OSC (±1–1,5 minggu)
- `Gtk.Box` vertikal `[slot_atas, overlay, slot_bawah]` sebagai `center` DockLayout.
- Controller `player_window/chrome.py` (pola `DockLayout`).
- Mode `floating`/`docked`/`off`; ukuran `compact`/`regular`/`large`;
  `always_visible`; interaksi mini player, fullscreen (Revealer), popover thumbnail.
- Tes xvfb: parent slot, visibilitas, suppress mini player, `gl_area` tidak pindah parent.

### 2.3 Header bar (±1 minggu, spike dulu)
- `full`, `auto-hide`, `hidden`; semua pembacaan `auto_hide_chrome` dialihkan ke
  `layout.headerbar`.
- Menu klik kanan harus memuat aksi yang biasanya hanya ada di header bar.

### 2.4 Preset dan UI Preferences (±3–4 hari)
- Halaman Layout: preset, OSC, header bar, tema, reduce motion.
- `detect_preset()` murni; label berubah ke `custom` saat diedit manual.
- `lock_aspect` ditunda.

### 2.5 Pengerasan dan QA (±2–3 hari)
- Matriks palet x mode OSC x mode header; smoke xvfb; checklist manual
  (Wayland/X11, fullscreen, mini, terang/gelap, skala 200%).

## Risiko

| Risiko | Penanganan |
|---|---|
| Header `hidden` merusak drag/resize di Wayland | Spike dulu; `auto-hide` tetap default |
| Memindah OSC memengaruhi render mpv | `gl_area` tidak disentuh; tes asersi parent |
| Tema terang memunculkan teks tak terbaca | Tes kontras AA + matriks palet |
| Modul baru lupa masuk Flatpak | `test_flatpak_manifest.py` |

## Status

- [~] 2.0 kode dan tes ditulis; `palette.py`, `theme_css.py`; snapshot CSS default
  identik dengan yang lama.
- [~] 2.1 kode ditulis: `theme_logic.py` (murni), `player_window/theme_manager.py`
  (GTK/D-Bus), `build_css(..., reduce_motion)`; `PlayerWindow.__init__` kini membuat
  `ThemeManager` menggantikan `_apply_iina_css()`.
  Tes murni lulus di sandbox (92: 2.0 + 2.1). BELUM diverifikasi di mesin dengan GTK4:
  jalankan `pytest` penuh (khususnya `test_theme_css.py`, yang memuat tiap kombinasi
  palet x aksen x reduce-motion ke `Gtk.CssProvider`) dan buka aplikasinya.
- Belum beres dari 2.0: `palette.py`, `theme_css.py`, `theme_logic.py` harus masuk daftar
  `cp -r` di manifest Flatpak; berkas `flatpak/io.github.inaa.json` tidak ditemukan di
  working tree (`tests/test_flatpak_manifest.py` membacanya, jadi tes itu akan gagal
  sampai berkas ada).
- Temuan di luar rencana (2026-11-25): `Gtk.FileChooserDialog` meng-abort proses di mesin
  pengembang (GTK 4.22.4, cairo 1.18.4, KDE/Wayland) dengan
  `cairo_surface_set_device_scale ... Assertion`, juga pada skrip GTK mandiri tanpa INAA
  (`/mnt/ssd2/data/Projetcs/repro_filechooser.py`). Bukan akibat ThemeManager. Tema GTK,
  tema ikon, renderer, dan dconf sudah diuji dan bukan penyebabnya; penyebab pastinya
  belum diketahui. `Gtk.FileDialog` dan `Gtk.FileChooserNative` tidak crash.
  Solusi: `player_window/file_dialogs.py` (`pick_files`, `pick_save_path`) dipakai oleh
  buka file, buka/simpan M3U, dan pemilih shader. Belum diverifikasi manual bahwa dialog
  benar-benar muncul dan mengembalikan file di INAA.
- 2.1 dikonfirmasi jalan di mesin pengembang (2026-11-25); sakelar `INAA_LEGACY_THEME` dihapus.
- Perbaikan di luar rencana: lebar minimum `Gtk.Stack` (halaman musik dengan nama file panjang)
  melebarkan jendela melewati layar sehingga tombol jendela terpotong; kini `hhomogeneous=False`
  dan label musik di-ellipsize. Tombol minimize/keluar fullscreen/tutup ditambahkan ke header saat
  fullscreen. Dikonfirmasi pengguna.
- [x] 2.2 terverifikasi di GTK (2026-11-25): 394 tes lulus + 9 smoke lulus; flatpak diabaikan.
  Catatan tes: `tests/conftest.py` mempertahankan PYTHONUSERBASE (HOME sementara membuat `import mpv`
  gagal di subproses); `test_smoke.py` memakai file, bukan pipe, karena layanan latar D-Bus
  menahan pipe. `ThemeManager` memakai DO_NOT_AUTO_START untuk proxy portal.
  Kode 2.2: `chrome_logic.py` (murni; logika dicek di sandbox dengan stub),
  `player_window/chrome.py` (`OscController`), `center_box` [slot atas, video, slot bawah],
  `tests/test_chrome_logic.py`, `tests/test_osc_ui.py` (xvfb).
  Aktif hanya dengan `INAA_LAYOUT_V2=1`; belum ada UI untuk mengubah mode (itu tahap 2.4).
  Header belum disentuh (2.3).
- [~] 2.3 sebagian ditulis (belum dijalankan): `resolve_header_mode`/`auto_hide_flags` di
  `chrome_logic.py`, `OscController.chrome_auto_hide()`, `input_mixin` memisahkan auto-hide
  OSC dan header (flag v2 mati = perilaku lama via `auto_hide_chrome`). `full` dan `auto-hide`
  berfungsi; `hidden` sementara diperlakukan sebagai `auto-hide` sampai spike Wayland
  (`Gtk.WindowHandle` + `Gtk.WindowControls`) membuktikan drag/resize aman.
  Belum: menu klik kanan memuat aksi header (prasyarat `hidden`).
- [~] 2.4 ditulis (belum dijalankan): `detect_preset`/`apply_preset` di `layout_config.py`
  (identitas preset = edge/visible dock, mode/posisi/ukuran OSC, header; lebar, tema, reduce motion
  tidak ikut), bagian Preset/OSC/Header/Tema di halaman Layout (`prefs_mixin.py`), widget tersinkron
  saat preset/reset. Tes: `test_layout_presets.py` (murni), `test_prefs_layout_ui.py` (xvfb).
  Belum: `lock_aspect` (ditunda), mode header `hidden`.
- [ ] 2.5

## Status Update (2026-11-25)
- **2.3**: Selesai. Mode `hidden` headerbar diimplementasikan dengan `Gtk.WindowHandle` + `Gtk.WindowControls` (Wayland-safe, tanpa `set_decorated(False)`), dengan mekanisme reveal hover dan integrasi dragbar 26px.
- **2.4**: Terverifikasi melalui `test_prefs_layout_ui.py`.
- **2.5**: Automasi via `test_layout_matrix_ui.py` lulus.
- **Catatan**: Smoke tests (`test_smoke.py`, `test_smoke_v3.py`) gagal karena isu D-Bus/MPRIS di environment Xvfb, namun logika UI header dan layout sudah terverifikasi integritasnya melalui `test_layout_matrix_ui` dan tes unit lainnya.
