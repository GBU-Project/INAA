"""Tema CSS IINA dan pemasangannya ke Gtk.StyleContext.

Blok _IINA_CSS dipindah verbatim dari common.py; isinya tidak berubah.
"""
from .common import Gdk, Gtk

_IINA_CSS = b"""
/* INAA macOS Glassmorphism Theme */
.iina-osd-panel {
    background-color: rgba(26, 26, 28, 0.82);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
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
    color: #f0f0f0;
}

.iina-osd-panel button:hover {
    background-color: rgba(255, 255, 255, 0.15);
}

.iina-time-label {
    font-size: 11px;
    font-weight: 600;
    color: #e0e0e0;
    font-feature-settings: "tnum";
}

.iina-inspector {
    background-color: rgba(28, 28, 30, 0.96);
    border-left: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.35);
    min-width: 320px;
}

.iina-sec-title {
    font-weight: bold;
    font-size: 12px;
    color: #a0a0a5;
    margin-top: 10px;
    margin-bottom: 2px;
}

.iina-seg-btn {
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
}

.iina-seg-btn.iina-seg-active {
    background: #007aff;
    color: #ffffff;
    border-color: #007aff;
}

/* ========================================================
   IINA 1.5.0 macOS Preferences / Settings Styling
   ======================================================== */
.iina-prefs-window {
    background-color: #1e1e20;
    color: #f5f5f7;
}

.iina-prefs-sidebar {
    background-color: rgba(30, 30, 32, 0.98);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    min-width: 190px;
    padding: 8px 6px;
}

.iina-prefs-sidebar searchbar,
.iina-prefs-sidebar entry {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #f5f5f7;
    font-size: 12px;
    padding: 4px 8px;
}

.iina-prefs-sidebar entry:focus {
    border-color: #007aff;
}

.iina-prefs-cat-row {
    border-radius: 8px;
    padding: 6px 10px;
    margin: 2px 0;
    font-size: 13px;
    font-weight: 500;
    color: #e2e2e7;
    transition: background-color 140ms ease;
}

.iina-prefs-cat-row:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

.iina-prefs-cat-row:selected {
    background: #007aff;
    color: #ffffff;
    font-weight: 600;
}

.iina-prefs-cat-row:selected image {
    color: #ffffff;
}

.iina-prefs-content {
    background-color: #161618;
    padding: 16px 24px;
}

.iina-prefs-header-title {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 8px;
}

.iina-prefs-section-header {
    font-size: 12px;
    font-weight: 600;
    color: #8e8e93;
    margin-top: 14px;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Card Container (Apple HIG Grouped Card) */
.iina-pref-card {
    background-color: rgba(40, 40, 44, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.iina-pref-card-row {
    padding: 6px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.iina-pref-card-row:last-child {
    border-bottom: none;
}

.iina-pref-option-box {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1.5px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    margin-top: 5px;
    transition: all 140ms ease;
}

.iina-pref-option-box:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.18);
}

.iina-pref-option-box.active {
    border-color: #007aff;
    background-color: rgba(0, 122, 255, 0.22);
}

.iina-pref-check {
    color: #007aff;
    font-size: 16px;
    margin-left: 8px;
}

/* Welcome Screen (IINA Style) */
.iina-welcome-screen {
    background-color: #121214;
}

.iina-welcome-card {
    background-color: rgba(36, 36, 40, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    transition: all 180ms ease-in-out;
}

.iina-welcome-card:hover {
    background-color: rgba(50, 50, 56, 0.85);
    border-color: rgba(255, 255, 255, 0.22);
}

.iina-action-btn {
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 18px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background-color: rgba(45, 45, 50, 0.8);
    color: #f5f5f7;
}

.iina-action-btn:hover {
    background-color: rgba(70, 70, 78, 0.95);
    border-color: rgba(255, 255, 255, 0.25);
}

.iina-action-btn.primary {
    background: linear-gradient(135deg, #007aff, #0056b3);
    border-color: #3395ff;
    color: #ffffff;
}

.iina-action-btn.primary:hover {
    background: linear-gradient(135deg, #1a88ff, #0066cc);
}

.iina-recent-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.iina-recent-row:hover {
    background-color: rgba(255, 255, 255, 0.08);
}

.iina-recent-title {
    font-size: 13px;
    font-weight: 500;
    color: #f0f0f2;
}

.iina-recent-sub {
    font-size: 11px;
    color: #8e8e93;
}

.iina-history-dialog {
    background-color: #1c1c1e;
    color: #f5f5f7;
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
    color: #a1a1a6;
    opacity: 1;
}

.iina-history-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    transition: background-color 150ms ease;
}

.iina-history-row:hover {
    background-color: rgba(255, 255, 255, 0.09);
}

.iina-eq-band-box {
    padding: 2px 4px;
}

.iina-eq-val-lbl {
    font-size: 10px;
    color: #98989d;
    font-feature-settings: "tnum";
}

.iina-eq-hz-lbl {
    font-size: 10px;
    font-weight: 600;
    color: #d1d1d6;
}

.iina-toast {
    background-color: rgba(20, 20, 22, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 8px 18px;
    color: #f5f5f7;
    font-size: 13px;
    font-weight: 600;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    margin-top: 24px;
}

.iina-thumb-grid-item {
    border-radius: 4px;
    overflow: hidden;
    transition: transform 120ms ease-out;
}

.iina-thumb-grid-item:hover {
    transform: scale(1.08);
    z-index: 1;
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
    color: #4ade80;
    font-weight: 600;
}
"""

def _apply_iina_css():
    try:
        provider = Gtk.CssProvider()
        provider.load_from_data(_IINA_CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
    except Exception:
        pass
