"""Konfigurasi pytest bersama.

Banyak tes GUI menjalankan subproses dengan HOME sementara. Python lalu kehilangan
site-packages pengguna (`~/.local/lib/pythonX.Y/site-packages`), tempat `python-mpv`
sering terpasang, sehingga `import mpv` gagal di subproses. Menetapkan
PYTHONUSERBASE ke lokasi asli membuat subproses tetap menemukan paket itu.
"""
import os
import site

os.environ.setdefault("PYTHONUSERBASE", site.getuserbase())
# Crash native (segfault/abort) di subproses GUI mencetak stack Python-nya ke stderr.
os.environ.setdefault("PYTHONFAULTHANDLER", "1")
# Tes GUI dijalankan lewat xvfb-run, tetapi bila sesi pengembang Wayland (WAYLAND_DISPLAY ada)
# GTK memilih Wayland dan membuka jendela sungguhan di desktop, bukan di Xvfb. Itu membuat tes
# tidak hermetik dan memunculkan segfault acak di callback Wayland GTK. Paksa X11 (Xvfb).
os.environ["GDK_BACKEND"] = "x11"
