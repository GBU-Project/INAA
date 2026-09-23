# Membangun INAA sebagai Flatpak

Manifest ini (`io.github.inaa.json`) belum pernah di-build dengan `flatpak-builder`
sungguhan — lingkungan yang dipakai untuk menyusunnya tidak punya akses untuk
menginstal `flatpak-builder` (masalah jaringan/mirror di sandbox tempat manifest ini
ditulis, bukan masalah pada manifest-nya). Jadi anggap ini **starting point yang
solid**, bukan sesuatu yang sudah terbukti build hijau — kamu perlu build sekali di
mesin Linux sungguhan untuk menangkap typo/kesalahan config-opts yang mungkin lolos
dari review manual.

## Yang sudah diverifikasi (bukan tebakan)

- Modul build libmpv (luajit → ffmpeg → libass → uchardet → libcdio/libdvdnav →
  libmpv) diambil dari [manifest Flatpak resmi Celluloid](https://github.com/celluloid-player/celluloid/blob/master/flatpak/io.github.celluloid_player.Celluloid.json)
  (GPLv3), sebuah aplikasi mpv+GTK Flatpak yang sudah lama live di Flathub — jadi
  urutan & config-opts modul ini sudah terbukti bisa build. Satu perubahan sengaja
  dari punya Celluloid: ffmpeg TIDAK dibangun dengan `--disable-programs`, karena
  `input_mixin.py` INAA memanggil binary `ffmpeg` langsung lewat `subprocess` untuk
  thumbnail preview di seekbar — jadi butuh executable-nya, bukan cuma shared library-nya.
- sha256 dan URL untuk `pydbus` dan `python-mpv` diambil langsung dari PyPI JSON API
  (bukan ditebak), dan dicross-check dengan hash hasil download manual — cocok.
- Dikonfirmasi (lewat manifest Flathub app Python+GTK4 lain, `io.frama.tractor.carburetor`)
  bahwa `org.gnome.Platform` sudah menyediakan PyGObject sendiri, jadi manifest ini
  tidak perlu build PyGObject dari source.

## Yang PERLU kamu cek/isi sebelum build asli

1. **Versi runtime**: dipin ke `org.gnome.Platform` versi `50`. Cek versi stabil
   terbaru saat kamu build (`flatpak remote-info flathub org.gnome.Platform`) dan
   sesuaikan `runtime-version`/`sdk` kalau sudah ada yang lebih baru.
2. **Source aplikasi**: modul `"inaa"` memakai `"type": "dir", "path": ".."` supaya
   gampang dites dari working tree lokal. Untuk build yang bisa direproduksi orang
   lain (atau submit ke Flathub), ganti ke:
   ```json
   { "type": "git", "url": "https://github.com/<kamu>/INAA.git", "tag": "v0.1.0" }
   ```
3. **Versi mpv**: dipin ke tag `v0.38.0`. Naikkan kalau mau versi lebih baru — cukup
   ganti nilai `tag` di modul `libmpv`.

## Build & jalankan secara lokal

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Platform//50 org.gnome.Sdk//50

cd INAA
flatpak-builder --force-clean --user --install build-dir flatpak/io.github.inaa.json
flatpak run io.github.inaa
```

Build pertama akan lama (mengkompilasi ffmpeg + libplacebo-equivalent chain dari
source) — ini wajar, sama seperti Celluloid/mpv Flatpak lain.

## Kalau build gagal

Kemungkinan besar di salah satu titik ini duluan:
- **Checksum mismatch** pada source `type: archive`/`type: file` — server upstream
  kadang mengganti file di URL yang sama (jarang, tapi terjadi); jalankan ulang
  `sha256sum` pada file yang gagal dan bandingkan.
- **`desktop-file-edit` tidak ada** — ini bagian dari `desktop-file-utils`, seharusnya
  ada di `org.gnome.Sdk`; kalau tidak ada, ganti dua baris `desktop-file-edit` di
  `build-commands` modul `"inaa"` dengan `sed -i` langsung ke file `.desktop`.
- **libmpv gagal menemukan salah satu optional dependency** — beberapa `config-opts`
  di modul `libmpv` (mis. `-Dlibarchive=enabled`) butuh library itu sudah ke-build
  duluan di modul sebelumnya; urutan modul di manifest ini sudah disusun sesuai
  urutan dependency Celluloid, tapi kalau kamu menambah/menghapus modul, urutan itu
  gampang rusak.

## Belum termasuk (di luar cakupan manifest ini)

- **Belum submission-ready ke Flathub**: `io.github.inaa.metainfo.xml` masih minim
  (belum ada `<screenshot>` sungguhan, belum lolos review guideline Flathub
  sepenuhnya). Lihat https://docs.flathub.org/docs/for-app-authors/submission/
  untuk checklist lengkapnya.
- **Belum ada CI** yang otomatis build Flatpak ini tiap push (lihat juga catatan
  "no CI" di audit sebelumnya — kalau nanti dibuatkan GitHub Actions, action resmi
  `flatpak/flatpak-github-actions` tinggal dipoint ke manifest ini).
