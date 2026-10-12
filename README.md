# INAA (GTK4 / Wayland-native edition)

Pemutar media modern dan elegan untuk Linux yang terinspirasi oleh [IINA](https://github.com/iina/iina) (macOS), dibangun menggunakan **GTK4 + libmpv Render API (OpenGL)**.

INAA merender video langsung ke widget `Gtk.GLArea` via OpenGL Framebuffer Object (FBO), berjalan secara **Wayland-native** (juga kompatibel penuh di X11) tanpa bergantung pada XWayland.

---

## Fitur Utama

- **Halaman Sambutan (Welcome Screen ala macOS IINA)**:
  Tampilan awal *dark glassmorphism* saat belum ada media yang dibuka. Dilengkapi tombol aksi cepat (*Buka File*, *Buka URL/Stream*, seret & lepas berkas), serta daftar *Terakhir Diputar* yang dapat diklik langsung untuk melanjutkan tontonan.
- **Floating OSD, Auto-hide Header & Kontrol Melayang**:
  Panel kontrol *frosted glass* dan headerbar otomatis tersembunyi saat video berjalan, lalu muncul kembali saat mouse digerakkan (dapat diatur di Pengaturan).
- **Sidebar Inspector Pengaturan Lengkap (`i`)**:
  Panel kanan dengan 3 tab:
  - **Video**: Hardware Acceleration switcher (Auto, VA-API, NVDEC, Off), aspect ratio, **Video Crop / Black Bar Removal** (16:9, 4:3, 2.35:1, 21:9), rotasi video, deinterlace, filter kecerahan, kontras, saturasi, dan gamma real-time.
  - **Audio**: Pemilihan trek audio, sinkronisasi delay audio (-5s s/d +5s), serta preset equalizer (Bass Boost, Vocal Boost, Night Mode/Dynamic Range Compression, Flat).
  - **Subtitle**: Dukungan Dual Subtitle (Primary Subtitle bawah & Secondary Subtitle atas ala IINA), pemuat subtitle lokal, pencari subtitle online, pengaturan delay, ukuran font (skala), posisi vertikal, **Pilihan Warna Subtitle** (Putih, Kuning, Cyan, Hijau), dan **Kotak Latar Belakang Kontras Tinggi (Background Box)**.
- **Dukungan Subtitle Komprehensif & Dual Subtitles**:
  - **Dual Subtitles (Subtitle Ganda)**: Menampilkan 2 subtitle sekaligus di layar (cocok untuk pembelajaran bahasa).
  - **Custom Subtitle Styling**: Pengaturan warna teks dan background box semi-transparan untuk keterbacaan maksimal di layar terang.
  - **Auto-load Subtitle Lokal**: Otomatis mendeteksi dan memuat subtitle dari folder yang sama (`sub-auto=fuzzy`).
  - **Pencarian Subtitle Online**: Integrasi pencarian dan pengunduhan subtitle langsung dari OpenSubtitles.
  - **Drag & Drop**: Seret berkas subtitle (.srt, .ass, .vtt) langsung ke jendela video untuk langsung diterapkan.
- **Gestur Mouse & Trackpad (IINA Gestures)**:
  - **Scroll Vertikal**: Mengatur volume suara secara halus dengan toast umpan balik visual instan.
  - **Scroll Horizontal**: Scrubbing dan seeking video maju/mundur dengan akurat.
- **Playback History & Resume Otomatis (`Ctrl+H`)**:
  - Jendela Riwayat Pemutaran khusus ala IINA dengan kotak pencarian instan (nama file, judul, path) dan konfirmasi proteksi saat menghapus riwayat.
  - Menyimpan path file, waktu terakhir diputar, durasi, dan posisi resume (hingga 100 berkas).
  - Klik pada riwayat untuk langsung melanjutkan pemutaran disertai notifikasi toast status.
- **Audio Equalizer 10-Band & Filter Audio Aman**:
  - Equalizer 10 band standar ISO (31Hz hingga 16kHz) dengan rentang gain -12 dB hingga +12 dB di tab Inspector Audio (`i`).
  - Berbagai preset equalizer instan: *Flat, Bass Boost, Vocal Boost, Rock, Pop, Classic, Electro, Acoustic, Party*.
  - **Dukungan Custom Preset**: Simpan kombinasi frekuensi favorit dengan nama kustom langsung dari panel Inspector.
  - Efek audio khusus terisolasi: *Night Mode* (Dynamic Range Compression), *Karaoke* (Center Vocal Reducer), dan *Clarity Boost*.
  - Delay audio dan delay subtitle (-5s s/d +5s) dengan sinkronisasi presisi.
  - Seluruh parameter filter audio dibangun lewat allowlist divalidasi ketat (`audio_filters.py`), bukan membuka celah opsi `af` mentah dari `mpv.conf`.
- **Playlist Cerdas & Smart Next Episode (Auto-Advance)**:
  - **Smart Folder Discovery**: Saat memutar salah satu file di folder, INAA secara otomatis mendeteksi episode/file media lainnya di direktori yang sama dan menyusunnya rapi ke dalam playlist.
  - Daftar putar dengan sidebar geser, **ulang semua / ulang satu / acak**, auto-advance ke trek berikutnya, dan pemutaran berkelanjutan.
- **Music Mode (Tampilan Musik Khusus)**:
  Beralih otomatis ke antarmuka musik khusus saat memutar file audio, menampilkan visual cover art, judul lagu, dan artis.
- **Picture-in-Picture & Mode Mengambang (`d`)**:
  Mode **Mini Player** yang ringkas, selalu di atas, dan selalu terlihat — jendela yang sama mengecil dan menyembunyikan chrome. Bisa dipicu lewat tombol Mini Player, shortcut `d`, atau menyeret video ke luar.

  > **Catatan teknis**: versi awal fitur "Detach" mencoba memindahkan video ke `Gtk.Window` terpisah yang sungguhan. Setelah diuji, ternyata `vo=libmpv` (render API mpv yang dipakai INAA) tidak bisa bertahan begitu render context-nya dibongkar untuk reparenting — mpv langsung meng-unload media yang sedang diputar, bahkan sempat menyebabkan crash total (segfault) sebelum diperbaiki. Karena itu "Detach" sekarang memakai mekanisme Mini Player yang sama (window yang sama diperkecil, bukan window baru sungguhan) — terbukti aman lewat pengujian playback berkelanjutan tanpa jeda.
- **Cuplikan Layar / Screenshot (`s`)**:
  Ambil tangkapan frame video beresolusi penuh langsung ke `~/Pictures/INAA/` menggunakan tombol OSD kamera atau shortcut `s`.
- **Integrasi MPRIS2 Linux**:
  Terhubung ke D-Bus session bus (`org.mpris.MediaPlayer2.inaa`). Otomatis terintegrasi dengan now-playing widget GNOME Shell / KDE Plasma, lock screen controls, tombol media keyboard (Play/Pause/Next/Prev), dan CLI `playerctl`. Diuji nyata lewat panggilan D-Bus eksternal (simulasi tombol media keyboard): Play/Pause/Seek semua terverifikasi bekerja.
- **Streaming & URL Langsung**:
  Mendukung link YouTube, Vimeo, Twitch, atau direct HTTP/HLS stream via `yt-dlp`.
- **A-B Loop & Kecepatan Fleksibel**:
  Fitur pengulangan cuplikan bagian tertentu (Titik A ⟲ Titik B) dan kecepatan playback 0.25x hingga 4.0x.
- **Visual Thumbnail Seekbar**:
  Hover timestamp dan thumbnail preview visual instan saat mengarahkan kursor di sepanjang seek bar.
- **Dukungan mpv.conf & Custom GLSL Shaders (Opt-In)**:
  - **Custom Shaders**: Peningkatan kualitas gambar dengan shader GLSL / mpv hooks (.hook, .glsl seperti Anime4K, FSRCNNX, CAS) yang dapat ditambahkan dan dikelola langsung dari tab Video Inspector.
  - **mpv.conf Opt-in (aman)**: INAA membaca `~/.config/mpv/mpv.conf` sendiri dan hanya menerapkan opsi tampilan/audio/subtitle/cache dari daftar yang diizinkan (`mpv_user.py`). Opsi seperti `script`, `input-ipc-server`, `ytdl*`, `vo`, `osc`, `include`, `vf/af` diabaikan dan dilaporkan di log. mpv sengaja tidak diizinkan membaca `mpv.conf` sendiri karena file itu bisa menimpa pengaturan keamanan INAA.
  - **Script mpv (opt-in)**: isi `"mpv_scripts": ["/path/absolut/x.lua"]` di `~/.config/inaa/config.json`. Script Lua/JS berjalan dengan akses penuh ke akunmu; muat hanya yang kamu percaya.
- **Playlist M3U / M3U8 Lengkap**:
  - Dukungan impor dan ekspor daftar putar format `.m3u` dan Extended M3U (`#EXTM3U`).
  - Toolbar aksi cepat di sidebar (Buka Playlist, Simpan Playlist, Kosongkan) serta dukungan drag-and-drop file playlist langsung ke jendela.
- **Pengaturan (`Ctrl+P`) & Editor Pintasan (`Ctrl+,`)**:
  - Jendela Preferences: auto-hide chrome, sesuaikan jendela ke rasio video, resume playback, mini player always-on-top, delay OSD, mode ulang/acak, dan pintasan.
- **Sistem Plugin Ekstensi (ala IINA)**:
  Plugin berupa folder dengan `Info.json` + entry Python di `~/.config/inaa/plugins/`. Tidak dijalankan otomatis — harus diaktifkan lewat `enabled_plugins` di `config.json`. Plugin hanya menerima API terbatas (toast, path, play/pause, seek) dan diperiksa lewat AST dengan **daftar putih** atribut (tanpa `import`/`eval`/`open`, tanpa atribut introspeksi seperti `gi_frame`/`f_builtins`).

  > **Penting — ini pagar, bukan penjara.** Plugin tetap kode Python yang dijalankan di dalam proses INAA. Sandbox AST pernah berhasil ditembus lewat `generator.gi_frame.f_back.f_back.f_builtins` (kini ditutup dan diuji, lihat `tests/test_plugin_sandbox_v4.py`), dan teknik serupa bisa saja ditemukan lagi. Perlakukan mengaktifkan plugin sama seperti menjalankan programnya: **pasang hanya plugin dari sumber yang kamu percaya.** Isolasi yang sebenarnya membutuhkan proses terpisah dengan izin terbatas (belum ada).

---

## Keyboard Shortcuts

| Tombol Shortcut | Fungsi |
| :--- | :--- |
| `Spasi` | Putar / Jeda (Play / Pause) |
| `←` / `→` | Mundur / Maju 5 detik |
| `↑` / `↓` | Naikkan / Turunkan volume suara |
| `m` | Bisu / Suara (Mute Toggle) |
| `f` | Masuk / Keluar Layar Penuh (Fullscreen) |
| `i` | Buka / Tutup Panel Inspector Pengaturan |
| `s` | Ambil Cuplikan Gambar (Screenshot) |
| `d` | Aktifkan / keluar Mode Mengambang (Mini Player) |
| `[` / `]` | Kurangi / Tambah kecepatan putar (-0.25x / +0.25x) |
| `\` atau `Backspace` | Reset kecepatan pemutaran ke normal (1.0x) |
| `l` | Langkah A-B Loop (Set Titik A → Set Titik B → Hapus Loop) |
| `Page Up` / `Page Down` | Bab / Chapter Sebelumnya / Berikutnya |
| `Ctrl+P` | Buka jendela Pengaturan |
| `Ctrl+,` | Sunting pintasan keyboard |
| `Esc` | Keluar dari Fullscreen atau keluar dari mode Mini Player |
| *Klik Kiri Video* | Putar / Jeda |
| *Klik Ganda Video* | Layar Penuh (atau restore dari Mini Player) |
| *Klik Kanan Video* | Menampilkan Context Menu lengkap |
| *Scroll Vertikal Video* | Naikkan / Turunkan volume suara |
| *Scroll Horizontal Video* | Scrubbing / Seeking video maju atau mundur |
| *Seret Mouse Keluar* | Aktifkan Mode Mengambang (Mini Player) |

---

## Instalasi Dependensi

### Ubuntu / Debian (Wayland & X11)
```bash
sudo apt update
sudo apt install -y \
    python3-gi \
    gir1.2-gtk-4.0 \
    gir1.2-gdkpixbuf-2.0 \
    gir1.2-pango-1.0 \
    libmpv-dev \
    mpv \
    ffmpeg \
    yt-dlp

pip3 install -r requirements.txt --break-system-packages
```

### Fedora
```bash
sudo dnf install python3-gobject gtk4 mpv-libs-devel mpv ffmpeg yt-dlp
pip3 install -r requirements.txt
```

### Arch Linux
```bash
sudo pacman -S python-gobject gtk4 mpv ffmpeg yt-dlp
pip3 install -r requirements.txt
```

---

## Menjalankan Aplikasi & Pemasangan Launcher

### Menjalankan Langsung via Terminal
```bash
python3 main.py                     # Membuka halaman sambutan INAA
python3 main.py /path/ke/video.mp4  # Langsung memutar berkas video/musik
```

### Menyiapkan Launcher Sistem (`inaa` & Desktop Icon)
Agar INAA dapat dipanggil dari mana saja cukup dengan mengetik `inaa` di terminal atau lewat menu aplikasi sistem:

1. **Pasang launcher ke PATH** (symlink agar skrip menemukan `main.py`):
   ```bash
   chmod +x inaa
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/inaa" ~/.local/bin/inaa
   ```

2. **Pasang Desktop Entry & Icon**:
   ```bash
   mkdir -p ~/.local/share/applications ~/.local/share/icons/hicolor/256x256/apps
   cp inaa.png ~/.local/share/icons/hicolor/256x256/apps/io.github.inaa.png
   cp inaa.desktop ~/.local/share/applications/inaa.desktop
   update-desktop-database ~/.local/share/applications/
   ```

Sekarang Anda dapat membuka INAA langsung dari Application Menu desktop atau memilih INAA sebagai aplikasi pemutar default (*"Open With INAA"*).

---

## Struktur Proyek

```
INAA/
├── main.py            # Entry point GtkApplication (GTK4) & asosiasi berkas
├── player_window/     # Modul modular window utama (GLArea, OSD, mixins)
│   ├── __init__.py    # Class PlayerWindow (komposisi mixin)
│   ├── gl_area.py     # OpenGL rendering context & libmpv integration
│   ├── ui_builder.py  # Konstruksi widget UI, OSD overlay, dan menu
│   ├── playback_mixin.py # Kontrol playback, chapter, A-B loop, speed
│   ├── playlist_mixin.py # Playlist & riwayat berkas terakhir
│   ├── subtitles_mixin.py # Trek subtitle & integrasi OpenSubtitles
│   ├── filters_mixin.py  # Video equalizer, crop, & audio filter
│   ├── input_mixin.py    # Gesture, scroll seek, & keyboard shortcuts
│   ├── window_mixin.py   # Mini player, PiP, toast, & screenshot
│   ├── prefs_mixin.py    # Jendela Pengaturan (Ctrl+P)
│   └── common.py         # Config, shared helper, styling & GL proc loader
├── playlist_nav.py    # Logika next/loop/shuffle playlist
├── mpris.py           # Integrasi MPRIS2 Linux (D-Bus session bus)
├── media_uri.py       # Validasi URI file/http/https
├── plugin_loader.py   # Loader plugin Info.json (opt-in, API terbatas)
├── opensubtitles.py   # Pencarian/unduh subtitle dengan host & size limit
├── inaa               # Bash launcher script untuk ~/.local/bin
├── inaa.desktop       # Desktop entry untuk application launcher & menu context
├── inaa.png           # Ikon aplikasi INAA
├── logging_setup.py   # Rotating log file (~/.config/inaa/logs/) + crash handling
├── keybindings.py     # Skema shortcut default (dipakai oleh input_mixin.py)
├── tests/             # Unit test (pytest/unittest) untuk media_uri.py & plugin_loader.py
├── flatpak/           # Manifest Flatpak (io.github.inaa.json) + panduan build
├── LICENSE            # MIT
├── requirements.txt   # Dependensi pustaka Python (python-mpv, PyGObject, pydbus)
├── requirements-dev.txt # Dependensi tambahan untuk menjalankan test (pytest)
└── README.md          # Dokumentasi teknis & panduan pengguna
```

---

## Instalasi via Flatpak

Selain instalasi manual (lihat "Instalasi Dependensi" di atas), tersedia manifest
Flatpak di `flatpak/io.github.inaa.json` yang membangun INAA beserta libmpv dari
source (jadi tidak bergantung pada versi libmpv/ffmpeg yang terpasang di sistem).
Lihat `flatpak/README.md` untuk cara build, apa yang sudah diverifikasi, dan apa
yang masih perlu dicek sebelum build produksi/submit ke Flathub.

---

## Menjalankan Test

Modul yang tidak butuh GTK4/libmpv (`media_uri.py`, validasi URI/path; `plugin_loader.py`,
sandbox plugin berbasis AST) punya unit test yang bisa dijalankan di mesin mana pun,
termasuk tanpa GTK4 terpasang:

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/test_media_uri.py` dan `tests/test_plugin_loader.py` berisi test dasar (gaya
`unittest`). `tests/test_media_uri_security.py` dan `tests/test_plugin_loader_security.py`
menambah cakupan kasus tepi dari audit keamanan — termasuk regression test untuk teknik
bypass sandbox yang pernah dicoba (introspeksi frame generator, `str.format()` attribute
traversal, path traversal pada `entry` di `Info.json`). Kalau salah satu regression test
itu mulai lolos ("payload not blocked"), itu tandanya sandbox mengalami regresi dan perlu
segera dicek.

---

## Konfigurasi & Penyimpanan

Pengaturan pengguna tersimpan otomatis di:
- **Konfigurasi & Riwayat**: `~/.config/inaa/config.json` (volume, ukuran jendela, riwayat, loop/shuffle, auto-hide, `enabled_plugins`).
- **Direktori Plugin**: `~/.config/inaa/plugins/<id>/` berisi `Info.json` dan berkas entry. Contoh:

```json
{
  "enabled_plugins": ["io.github.inaa.example-toast"],
  "opensubtitles_api_key": ""
}
```

- **Tangkapan Layar**: `~/Pictures/INAA/` (cuplikan frame PNG beresolusi penuh).

URI yang diterima pemutar hanya berkas lokal, `file://`, `http://`, dan `https://`. `yt-dlp` hanya diaktifkan saat membuka URL http(s) dari UI. MPRIS `OpenUri` hanya menerima berkas lokal (bukan URL). Konfigurasi disimpan dengan izin `0600`. Subtitle unduhan memakai berkas sementara unik, bukan nama tetap di `/tmp`.

## Ketahanan config & perbaikan terbaru
- `config_sanitize.py` membersihkan `config.json` saat dimuat (riwayat, gain equalizer, preset kustom, shader, dll.), jadi file yang rusak atau diubah manual tidak lagi membuat aplikasi crash saat start.
- Mode loop di Preferensi kini menandai pilihan yang aktif; riwayat tidak lagi membuka file dua kali dan file yang hilang tidak bisa diklik.
- Shader hanya satu jalur (`custom_shaders`) dan divalidasi (ekstensi, folder); `mpv_shaders` sudah dihapus.
- Mengaktifkan `mpv.conf` langsung berlaku (opsi aman saja); mematikannya butuh restart.
- Nama preset kustom tidak boleh sama dengan preset bawaan.

## Perbaikan hasil audit
- **Flatpak**: seluruh modul yang diimpor kini disalin ke paket (sebelumnya 6 modul hilang sehingga aplikasi gagal start), ffmpeg/mpv dipin ke commit, ffmpeg bisa menulis thumbnail JPEG (`mjpeg` + muxer `image2`), dan akses perangkat dipersempit ke `--device=dri`. `tests/test_flatpak_manifest.py` menjaga konsistensi ini.
- **Playlist M3U**: dibatasi 5 MB / 5000 entri / 4096 karakter per baris agar playlist raksasa tidak membekukan jendela.
- **Subtitle online**: setiap redirect juga harus ke host OpenSubtitles yang diizinkan.

## Audio: peredam volume, perangkat output
- **Preamp otomatis equalizer**: bila ada band yang dinaikkan, volume diturunkan sebesar gain tertinggi di awal rantai filter agar tidak pecah (clipping). Pada derau uji, preset `rock` dan `party` yang tadinya menyentuh 0,0 dB kini turun ke sekitar -1,1 dB. Ini heuristik: kalau band bertetangga sama-sama dinaikkan, respons gabungannya bisa sedikit lebih tinggi. Equalizer dan efek khusus selalu digabung menjadi satu graf `lavfi`.
- **Perangkat output audio** (Inspector > Audio): pilih perangkat dari daftar yang dilaporkan mpv; tombol muat ulang untuk perangkat yang baru dicolok. mpv menerima nama perangkat apa saja tanpa error (lalu suara hilang), jadi INAA hanya mengizinkan nama dari daftar itu. Jika perangkat tersimpan sudah tidak ada, INAA memakai `auto` tanpa menghapus pilihanmu.
- **Tampilan riwayat di tema terang**: daftar di dialog riwayat dan kartu "Terakhir Diputar" kini transparan di atas latar gelap, sehingga judul terbaca. File yang hilang juga ditandai dan tidak bisa diklik di halaman awal.

