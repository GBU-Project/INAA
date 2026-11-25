"""Tema CSS IINA dan pemasangannya ke Gtk.StyleContext.

Stylesheet dibuat oleh `theme_css.build_css()` (modul murni di root proyek) dari
palet di `palette.py`. Default (iina-glass + blue) identik dengan CSS lama;
lihat `tests/test_theme_palettes.py`.
"""
from theme_css import build_css_bytes

from .common import Gdk, Gtk

# Default iina-glass + blue. Nama dipertahankan untuk kompatibilitas.
_IINA_CSS = build_css_bytes()


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
