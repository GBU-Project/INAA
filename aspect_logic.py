"""Kunci rasio jendela (lock_aspect) — logika murni, tanpa GTK.

GTK4 tidak punya API untuk mengunci rasio jendela, jadi rasio dipulihkan SETELAH
pengguna selesai mengubah ukuran: controller membandingkan ukuran jendela dengan
rasio video, lalu memanggil `set_default_size` dengan ukuran yang dihitung di sini.
"""
from __future__ import annotations

MIN_WIDTH = 480
MIN_HEIGHT = 270
TOLERANCE = 0.02  # selisih rasio yang masih dianggap sama (2%)


def aspect_target(
    win_w: int,
    win_h: int,
    video_w: int,
    video_h: int,
    *,
    chrome_h: int = 0,
    extra_w: int = 0,
    prev_size: tuple[int, int] | None = None,
    tolerance: float = TOLERANCE,
) -> tuple[int, int] | None:
    """Ukuran jendela baru agar area video berrasio video, atau None bila sudah pas.

    `chrome_h` = tinggi header/OSC menempel, `extra_w` = lebar dock yang tampil;
    keduanya tidak ikut area video. Dimensi yang lebih banyak diubah pengguna
    (dibanding `prev_size`) dipertahankan, dimensi lain disesuaikan; tanpa
    `prev_size` lebar dipertahankan.
    """
    if min(video_w, video_h, win_w, win_h) <= 0:
        return None
    area_w = win_w - extra_w
    area_h = win_h - chrome_h
    if area_w <= 0 or area_h <= 0:
        return None

    ratio = video_w / video_h
    if abs((area_w / area_h) / ratio - 1.0) <= tolerance:
        return None

    keep_height = False
    if prev_size is not None:
        keep_height = abs(win_h - prev_size[1]) > abs(win_w - prev_size[0])

    if keep_height:
        new_w = max(MIN_WIDTH, round(area_h * ratio) + extra_w)
        new_h = win_h
    else:
        new_w = win_w
        new_h = max(MIN_HEIGHT, round(area_w / ratio) + chrome_h)

    if (new_w, new_h) == (win_w, win_h):
        return None
    return new_w, new_h


__all__ = ["MIN_WIDTH", "MIN_HEIGHT", "TOLERANCE", "aspect_target"]
