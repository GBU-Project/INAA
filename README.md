# INAA (GTK4 / Wayland-native edition)

Pemutar media modern dan elegan untuk Linux yang terinspirasi oleh [IINA](https://github.com/iina/iina) (macOS), dibangun menggunakan **GTK4 + libmpv Render API (OpenGL)**.

INAA merender video langsung ke widget `Gtk.GLArea` via OpenGL Framebuffer Object (FBO), berjalan secara **Wayland-native** (juga kompatibel penuh di X11) tanpa bergantung pada XWayland.

---

## Fitur Utama

- **Halaman Sambutan (Welcome Screen ala macOS IINA)**:
  Tampilan awal *dark glassmorphism* saat belum ada media yang dibuka. Dilengkapi tombol aksi cepat (*Buka File*, *Buka URL/Stream*, seret & lepas berkas), serta daftar *Terakhir Diputar* yang dapat diklik langsung untuk melanjutkan tontonan.
- **Floating OSD & Kontrol Melayang**:
  Panel kontrol melayang berdesain *frosted glass* yang otomatis tersembunyi (*auto-hide*) saat video berjalan dan muncul kembali saat mouse digerakkan.
- **Sidebar Inspector Pengaturan Lengkap (`i`)**:
  Panel kanan dengan 3 tab:
  - **Video**: Aspect ratio, rotasi video, deinterlace, filter kecerahan, kontras, saturasi, dan gamma real-time.
  - **Audio**: Pemilihan trek audio, sinkronisasi delay audio (-5s s/d +5s), serta preset equalizer (Bass Boost, Vocal Boost, Flat).
  - **Subtitle**: Pemilihan trek subtitle, pemuat subtitle lokal, pencari subtitle online, pengaturan delay, ukuran font (skala), dan posisi vertikal subtitle.
- **Dukungan Subtitle Komprehensif**:
  - **Auto-load Subtitle Lokal**: Otomatis mendeteksi dan memuat subtitle dari folder yang sama (`sub-auto=fuzzy`).
  - **Pencarian Subtitle Online**: Integrasi pencarian dan pengunduhan subtitle langsung dari OpenSubtitles.
  - **Drag & Drop**: Seret berkas subtitle (.srt, .ass, .vtt) langsung ke jendela video untuk langsung diterapkan.
- **Resume Playback Otomatis**:
  Mengingat detik posisi tontonan terakhir per file dan langsung melanjutkan pemutaran disertai notifikasi toast status.
- **Playlist Cerdas & Auto-Advance**:
  Daftar putar dengan sidebar geser, auto-advance ke trek berikutnya saat lagu/video selesai, dan pemutaran berkelanjutan tanpa henti.
- **Music Mode (Tampilan Musik Khusus)**:
  Beralih otomatis ke antarmuka musik khusus saat memutar file audio, menampilkan visual cover art, judul lagu, dan artis.
- **Picture-in-Picture & Mode Mengambang (`d`)**:
  Mode **Mini Player** yang ringkas dan selalu terlihat — jendela yang sama mengecil dan menyembunyikan chrome, memberi efek video "mengambang". Bisa dipicu lewat tombol Mini Player, shortcut `d`, atau menyeret video ke luar.

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
- **Sistem Plugin Ekstensi**:
  Dukungan script Python kustom yang diletakkan di `~/.config/inaa/plugins/`.

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
| `Esc` | Keluar dari Fullscreen atau keluar dari mode Mini Player |
| *Klik Kiri Video* | Putar / Jeda |
| *Klik Ganda Video* | Layar Penuh (atau restore dari Mini Player) |
| *Klik Kanan Video* | Menampilkan Context Menu lengkap |
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

1. **Pastikan script launcher berada di PATH**:
   ```bash
   chmod +x inaa
   mkdir -p ~/.local/bin
   cp inaa ~/.local/bin/inaa
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
├── player_window.py   # Window utama: OSD, GLArea, Inspector, playlist, shortcut
├── mpris.py           # Integrasi MPRIS2 Linux (D-Bus session bus)
├── inaa               # Bash launcher script untuk ~/.local/bin
├── inaa.desktop       # Desktop entry untuk application launcher & menu context
├── inaa.png           # Ikon aplikasi INAA
├── requirements.txt   # Dependensi pustaka Python (python-mpv, PyGObject, pydbus)
└── README.md          # Dokumentasi teknis & panduan pengguna
```

---

## Konfigurasi & Penyimpanan

Pengaturan pengguna tersimpan otomatis di:
- **Konfigurasi & Riwayat**: `~/.config/inaa/config.json` (volume, ukuran jendela, daftar putar terakhir, posisi timestamp tontonan).
- **Direktori Plugin**: `~/.config/inaa/plugins/` (tempat meletakkan skrip ekstensi Python kustom).
- **Tangkapan Layar**: `~/Pictures/INAA/` (cuplikan frame PNG beresolusi penuh).
