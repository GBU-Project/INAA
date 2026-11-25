"""Generator stylesheet tema INAA (murni, tanpa GTK/libmpv).

`build_css(palette, accent)` mengisi `_TEMPLATE` dengan role dari `palette.py`.
Penanda `@nama@` diganti nilai palet/aksen; warna transparan putih/hitam ditulis
`rgba(@fg@, 0.14)` supaya palet terang cukup mengganti `fg`.

Dengan `iina-glass` + `blue` hasilnya identik dengan CSS lama
(`tests/fixtures/iina_css_v1.css`).
"""
from __future__ import annotations

import re

from palette import REQUIRED_ROLES, accent_tokens, get_palette

_TEMPLATE = """
/* INAA macOS Glassmorphism Theme */
.iina-osd-panel {
    background-color: @osd_bg@;
    border-radius: 16px;
    border: 1px solid rgba(@fg@, 0.14);
    box-shadow: 0 10px 30px rgba(@shadow@, 0.55);
    padding: 10px 16px 12px 16px;
    margin-bottom: 24px;
    opacity: 1;
    transition: opacity 220ms ease-in-out;
}

.iina-osd-panel.hidden {
    opacity: 0;
}

.iina-osd-panel button {
    border-radius: 8px;
    min-height: 28px;
    min-width: 28px;
    padding: 4px 6px;
    background-color: transparent;
    border: none;
    color: @osd_text@;
}

.iina-osd-panel button:hover {
    background-color: rgba(@fg@, 0.15);
}

.iina-time-label {
    font-size: 11px;
    font-weight: 600;
    color: @osd_text_2@;
    font-feature-settings: "tnum";
}

.iina-inspector {
    background-color: @inspector_bg@;
    border-left: 1px solid rgba(@fg@, 0.12);
    box-shadow: -4px 0 20px rgba(@shadow@, 0.35);
}

.iina-dock-paned > separator {
    background-color: rgba(@fg@, 0.10);
    min-width: 1px;
}

.iina-sec-title {
    font-weight: bold;
    font-size: 12px;
    color: @muted_2@;
    margin-top: 10px;
    margin-bottom: 2px;
}

.iina-seg-btn {
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
}

.iina-seg-btn.iina-seg-active {
    background: @accent@;
    color: @accent_text@;
    border-color: @accent@;
}

/* ========================================================
   IINA 1.5.0 macOS Preferences / Settings Styling
   ======================================================== */
.iina-prefs-window {
    background-color: @prefs_bg@;
    color: @text@;
}

.iina-prefs-sidebar {
    background-color: @prefs_sidebar_bg@;
    border-right: 1px solid rgba(@fg@, 0.08);
    min-width: 190px;
    padding: 8px 6px;
}

.iina-prefs-sidebar searchbar,
.iina-prefs-sidebar entry {
    background-color: rgba(@fg@, 0.08);
    border: 1px solid rgba(@fg@, 0.08);
    border-radius: 8px;
    color: @text@;
    font-size: 12px;
    padding: 4px 8px;
}

.iina-prefs-sidebar entry:focus {
    border-color: @accent@;
}

.iina-prefs-cat-row {
    border-radius: 8px;
    padding: 6px 10px;
    margin: 2px 0;
    font-size: 13px;
    font-weight: 500;
    color: @text_2@;
    transition: background-color 140ms ease;
}

.iina-prefs-cat-row:hover {
    background-color: rgba(@fg@, 0.08);
    color: @text_strong@;
}

.iina-prefs-cat-row:selected {
    background: @accent@;
    color: @accent_text@;
    font-weight: 600;
}

.iina-prefs-cat-row:selected image {
    color: @accent_text@;
}

.iina-prefs-content {
    background-color: @prefs_content_bg@;
    padding: 16px 24px;
}

.iina-prefs-header-title {
    font-size: 20px;
    font-weight: 700;
    color: @text_strong@;
    margin-bottom: 8px;
}

.iina-prefs-section-header {
    font-size: 12px;
    font-weight: 600;
    color: @muted@;
    margin-top: 14px;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Card Container (Apple HIG Grouped Card) */
.iina-pref-card {
    background-color: @card_bg@;
    border: 1px solid rgba(@fg@, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.iina-pref-card-row {
    padding: 6px 0;
    border-bottom: 1px solid rgba(@fg@, 0.05);
}

.iina-pref-card-row:last-child {
    border-bottom: none;
}

.iina-pref-option-box {
    background-color: rgba(@fg@, 0.04);
    border: 1.5px solid rgba(@fg@, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    margin-top: 5px;
    transition: all 140ms ease;
}

.iina-pref-option-box:hover {
    background-color: rgba(@fg@, 0.08);
    border-color: rgba(@fg@, 0.18);
}

.iina-pref-option-box.active {
    border-color: @accent@;
    background-color: @accent_tint@;
}

.iina-pref-check {
    color: @accent@;
    font-size: 16px;
    margin-left: 8px;
}

/* Welcome Screen (IINA Style) */
.iina-welcome-screen {
    background-color: @welcome_bg@;
}

.iina-welcome-card {
    background-color: @welcome_card_bg@;
    border: 1px solid rgba(@fg@, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    transition: all 180ms ease-in-out;
}

.iina-welcome-card:hover {
    background-color: @welcome_card_hover_bg@;
    border-color: rgba(@fg@, 0.22);
}

.iina-action-btn {
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 18px;
    border: 1px solid rgba(@fg@, 0.12);
    background-color: @action_bg@;
    color: @text@;
}

.iina-action-btn:hover {
    background-color: @action_hover_bg@;
    border-color: rgba(@fg@, 0.25);
}

.iina-action-btn.primary {
    background: linear-gradient(135deg, @accent@, @accent_dark@);
    border-color: @accent_light@;
    color: @accent_text@;
}

.iina-action-btn.primary:hover {
    background: linear-gradient(135deg, @accent_hover1@, @accent_hover2@);
}

.iina-recent-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(@fg@, 0.05);
}

.iina-recent-row:hover {
    background-color: rgba(@fg@, 0.08);
}

.iina-recent-title {
    font-size: 13px;
    font-weight: 500;
    color: @text_3@;
}

.iina-recent-sub {
    font-size: 11px;
    color: @muted@;
}

.iina-history-dialog {
    background-color: @dialog_bg@;
    color: @text@;
}

/* ListBox mengecat latar sendiri (putih di tema terang) padahal teks kita terang:
   buat transparan agar latar kartu/dialog yang gelap yang terlihat. */
.iina-history-dialog list,
.iina-history-dialog row,
.iina-welcome-card list,
.iina-welcome-card row {
    background-color: transparent;
    color: inherit;
}

.iina-history-dialog .dim-label,
.iina-welcome-card .dim-label {
    color: @dim@;
    opacity: 1;
}

.iina-history-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(@fg@, 0.08);
    transition: background-color 150ms ease;
}

.iina-history-row:hover {
    background-color: rgba(@fg@, 0.09);
}

.iina-eq-band-box {
    padding: 2px 4px;
}

.iina-eq-val-lbl {
    font-size: 10px;
    color: @muted_3@;
    font-feature-settings: "tnum";
}

.iina-eq-hz-lbl {
    font-size: 10px;
    font-weight: 600;
    color: @text_4@;
}

.iina-toast {
    background-color: @toast_bg@;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 8px 18px;
    color: @toast_text@;
    font-size: 13px;
    font-weight: 600;
    box-shadow: 0 8px 24px rgba(@shadow@, 0.5);
    margin-top: 24px;
}

.iina-thumb-grid-item {
    border-radius: 4px;
    transition: transform 120ms ease-out;
}

.iina-thumb-grid-item:hover {
    transform: scale(1.08);
}

.iina-thumb-time-label {
    background-color: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
}

.iina-shader-active {
    color: @ok@;
    font-weight: 600;
}
"""

_TOKEN = re.compile(r"@([a-z0-9_]+)@")


def template_tokens() -> set[str]:
    """Semua nama token yang dipakai template."""
    return set(_TOKEN.findall(_TEMPLATE))


# Mode gerak-dikurangi: matikan semua transisi (fade OSD, hover kartu, zoom thumbnail).
# Hanya ditambahkan bila diminta, supaya CSS default tetap identik dengan yang lama.
_REDUCE_MOTION_CSS = """
/* reduce motion */
* {
    transition: none;
}
"""


def build_css(palette: str = "iina-glass", accent: str = "blue", reduce_motion: bool = False) -> str:
    """Stylesheet lengkap untuk kombinasi palet, aksen, dan mode gerak-dikurangi."""
    tokens = {**get_palette(palette).tokens, **accent_tokens(accent)}

    def fill(match: re.Match) -> str:
        name = match.group(1)
        if name not in tokens:
            raise KeyError(f"token CSS tidak dikenal: {name}")
        return tokens[name]

    css = _TOKEN.sub(fill, _TEMPLATE)
    if reduce_motion:
        css += _REDUCE_MOTION_CSS
    return css


def build_css_bytes(palette: str = "iina-glass", accent: str = "blue", reduce_motion: bool = False) -> bytes:
    return build_css(palette, accent, reduce_motion).encode("utf-8")


__all__ = ["build_css", "build_css_bytes", "template_tokens", "REQUIRED_ROLES"]
