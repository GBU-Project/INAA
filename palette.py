"""Palet warna dan aksen tema INAA (murni, tanpa GTK/libmpv).

Dipakai oleh `theme_css.build_css()` untuk membuat stylesheet. Nilai palet
`iina-glass` + aksen `blue` sengaja identik dengan CSS lama (lihat
`tests/fixtures/iina_css_v1.css`), jadi tampilan default tidak berubah.

Nama palet/aksen harus sama dengan `layout_config.PALETTES` / `ACCENTS`
(dijaga oleh `tests/test_theme_palettes.py`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

PALETTE_NAMES = ("iina-glass", "graphite", "light")
ACCENT_NAMES = ("blue", "purple", "pink", "orange", "green", "graphite")

# Role yang wajib ada di setiap palet (dipakai template CSS).
REQUIRED_ROLES = (
    "fg", "shadow",
    "osd_bg", "osd_text", "osd_text_2",
    "inspector_bg",
    "muted", "muted_2", "muted_3", "dim",
    "text", "text_2", "text_3", "text_4", "text_strong",
    "prefs_bg", "prefs_sidebar_bg", "prefs_content_bg", "card_bg",
    "welcome_bg", "welcome_card_bg", "welcome_card_hover_bg",
    "action_bg", "action_hover_bg",
    "dialog_bg",
    "toast_bg", "toast_text",
    "ok",
)

# Role yang diturunkan dari aksen.
ACCENT_ROLES = (
    "accent", "accent_dark", "accent_light",
    "accent_hover1", "accent_hover2", "accent_tint", "accent_text",
)


@dataclass(frozen=True)
class Palette:
    name: str
    is_dark: bool
    tokens: Mapping[str, str]


_GLASS = {
    "fg": "255, 255, 255",
    "shadow": "0, 0, 0",
    "osd_bg": "rgba(26, 26, 28, 0.82)",
    "osd_text": "#f0f0f0",
    "osd_text_2": "#e0e0e0",
    "inspector_bg": "rgba(28, 28, 30, 0.96)",
    "muted": "#8e8e93",
    "muted_2": "#a0a0a5",
    "muted_3": "#98989d",
    "dim": "#a1a1a6",
    "text": "#f5f5f7",
    "text_2": "#e2e2e7",
    "text_3": "#f0f0f2",
    "text_4": "#d1d1d6",
    "text_strong": "#ffffff",
    "prefs_bg": "#1e1e20",
    "prefs_sidebar_bg": "rgba(30, 30, 32, 0.98)",
    "prefs_content_bg": "#161618",
    "card_bg": "rgba(40, 40, 44, 0.7)",
    "welcome_bg": "#121214",
    "welcome_card_bg": "rgba(36, 36, 40, 0.65)",
    "welcome_card_hover_bg": "rgba(50, 50, 56, 0.85)",
    "action_bg": "rgba(45, 45, 50, 0.8)",
    "action_hover_bg": "rgba(70, 70, 78, 0.95)",
    "dialog_bg": "#1c1c1e",
    "toast_bg": "rgba(20, 20, 22, 0.88)",
    "toast_text": "#f5f5f7",
    "ok": "#4ade80",
}

# Graphite: gelap netral, permukaan sedikit lebih terang dari iina-glass.
_GRAPHITE = {
    **_GLASS,
    "osd_bg": "rgba(44, 44, 46, 0.85)",
    "inspector_bg": "rgba(44, 44, 46, 0.97)",
    "prefs_bg": "#2c2c2e",
    "prefs_sidebar_bg": "rgba(40, 40, 42, 0.98)",
    "prefs_content_bg": "#1c1c1e",
    "card_bg": "rgba(58, 58, 60, 0.7)",
    "welcome_bg": "#1c1c1e",
    "welcome_card_bg": "rgba(58, 58, 60, 0.65)",
    "welcome_card_hover_bg": "rgba(72, 72, 74, 0.85)",
    "action_bg": "rgba(58, 58, 60, 0.8)",
    "action_hover_bg": "rgba(84, 84, 88, 0.95)",
    "dialog_bg": "#2c2c2e",
    "toast_bg": "rgba(28, 28, 30, 0.9)",
    # permukaan lebih terang -> teks redup perlu dinaikkan agar tetap >= 4.5:1
    "muted": "#a1a1a6",
    "muted_3": "#a8a8ad",
}

# Terang: teks gelap di atas permukaan terang; garis tipis memakai hitam.
_LIGHT = {
    "fg": "0, 0, 0",
    "shadow": "0, 0, 0",
    "osd_bg": "rgba(250, 250, 252, 0.88)",
    "osd_text": "#1d1d1f",
    "osd_text_2": "#3a3a3c",
    "inspector_bg": "rgba(246, 246, 248, 0.97)",
    "muted": "#6e6e73",
    "muted_2": "#6e6e73",
    "muted_3": "#6e6e73",
    "dim": "#6e6e73",
    "text": "#1d1d1f",
    "text_2": "#3a3a3c",
    "text_3": "#1d1d1f",
    "text_4": "#3a3a3c",
    "text_strong": "#000000",
    "prefs_bg": "#f5f5f7",
    "prefs_sidebar_bg": "rgba(238, 238, 242, 0.98)",
    "prefs_content_bg": "#ffffff",
    "card_bg": "rgba(245, 245, 247, 0.9)",
    "welcome_bg": "#f2f2f4",
    "welcome_card_bg": "rgba(255, 255, 255, 0.8)",
    "welcome_card_hover_bg": "rgba(255, 255, 255, 1)",
    "action_bg": "rgba(255, 255, 255, 0.9)",
    "action_hover_bg": "rgba(240, 240, 244, 1)",
    "dialog_bg": "#f5f5f7",
    "toast_bg": "rgba(40, 40, 44, 0.92)",
    "toast_text": "#f5f5f7",
    "ok": "#1a7f37",
}

_PALETTES = {
    "iina-glass": Palette("iina-glass", True, _GLASS),
    "graphite": Palette("graphite", True, _GRAPHITE),
    "light": Palette("light", False, _LIGHT),
}


def get_palette(name: str) -> Palette:
    """Palet menurut nama; nama tak dikenal -> iina-glass."""
    return _PALETTES.get(name, _PALETTES["iina-glass"])


# ---------------------------------------------------------------------------
# Warna & kontras
# ---------------------------------------------------------------------------
_HEX = re.compile(r"^#([0-9a-fA-F]{6})$")
_RGBA = re.compile(
    r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([0-9.]+)\s*)?\)$"
)


def parse_color(value: str) -> tuple[int, int, int, float]:
    """`#rrggbb` atau `rgb[a](r, g, b[, a])` -> (r, g, b, alpha)."""
    text = value.strip()
    m = _HEX.match(text)
    if m:
        raw = m.group(1)
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 1.0
    m = _RGBA.match(text)
    if m:
        alpha = float(m.group(4)) if m.group(4) is not None else 1.0
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), alpha
    raise ValueError(f"format warna tidak dikenal: {value!r}")


def blend(fg: str, bg: str) -> tuple[int, int, int]:
    """Gabungkan `fg` (boleh transparan) di atas `bg` (dianggap opak)."""
    fr, fgc, fb, alpha = parse_color(fg)
    br, bgc, bb, _ = parse_color(bg)
    return (
        round(fr * alpha + br * (1 - alpha)),
        round(fgc * alpha + bgc * (1 - alpha)),
        round(fb * alpha + bb * (1 - alpha)),
    )


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(a: str, b: str, backdrop: str = "#000000") -> float:
    """Rasio kontras WCAG 2.x antara dua warna CSS.

    Warna transparan digabung di atas `backdrop` (b di atas backdrop, lalu a
    di atas hasilnya), jadi hasil realistis untuk panel kaca di atas video.
    """
    bg_rgb = blend(b, backdrop)
    bg_hex = "#%02x%02x%02x" % bg_rgb
    fg_rgb = blend(a, bg_hex)
    l1, l2 = luminance(fg_rgb), luminance(bg_rgb)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# Aksen
# ---------------------------------------------------------------------------
_ACCENT_BASE = {
    "blue": "#007aff",
    "purple": "#af52de",
    "pink": "#ff2d55",
    "orange": "#ff9500",
    "green": "#34c759",
    "graphite": "#636366",
}

# Nilai biru identik dengan CSS lama.
_BLUE_TOKENS = {
    "accent": "#007aff",
    "accent_dark": "#0056b3",
    "accent_light": "#3395ff",
    "accent_hover1": "#1a88ff",
    "accent_hover2": "#0066cc",
    "accent_tint": "rgba(0, 122, 255, 0.22)",
    "accent_text": "#ffffff",
}


def _mix(base: tuple[int, int, int], other: tuple[int, int, int], amount: float) -> str:
    out = tuple(round(b * (1 - amount) + o * amount) for b, o in zip(base, other))
    return "#%02x%02x%02x" % out


def accent_tokens(name: str) -> dict[str, str]:
    """Role aksen untuk template CSS; nama tak dikenal -> blue."""
    if name not in _ACCENT_BASE or name == "blue":
        return dict(_BLUE_TOKENS)
    base_hex = _ACCENT_BASE[name]
    r, g, b, _ = parse_color(base_hex)
    base = (r, g, b)
    black, white = (0, 0, 0), (255, 255, 255)
    white_ok = contrast_ratio("#ffffff", base_hex) >= 3.0
    return {
        "accent": base_hex,
        "accent_dark": _mix(base, black, 0.30),
        "accent_light": _mix(base, white, 0.20),
        "accent_hover1": _mix(base, white, 0.10),
        "accent_hover2": _mix(base, black, 0.15),
        "accent_tint": f"rgba({r}, {g}, {b}, 0.22)",
        "accent_text": "#ffffff" if white_ok else "#000000",
    }


__all__ = [
    "PALETTE_NAMES", "ACCENT_NAMES", "REQUIRED_ROLES", "ACCENT_ROLES",
    "Palette", "get_palette", "accent_tokens",
    "parse_color", "blend", "luminance", "contrast_ratio",
]
