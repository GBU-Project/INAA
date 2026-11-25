"""Konfigurasi pytest bersama.

Banyak tes GUI menjalankan subproses dengan HOME sementara. Python lalu kehilangan
site-packages pengguna (`~/.local/lib/pythonX.Y/site-packages`), tempat `python-mpv`
sering terpasang, sehingga `import mpv` gagal di subproses. Menetapkan
PYTHONUSERBASE ke lokasi asli membuat subproses tetap menemukan paket itu.
"""
import os
import site

os.environ.setdefault("PYTHONUSERBASE", site.getuserbase())
