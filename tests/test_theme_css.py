"""Smoke test CSS tema: harus bisa dimuat GTK tanpa warning parser.

GTK4 tidak mengenal `overflow`/`z-index`; properti itu dulu memunculkan
`Theme parser error` di stderr. Stylesheet kini dibuat oleh
`theme_css.build_css()` (modul murni, tanpa libmpv), lalu dimuat ke
Gtk.CssProvider sambil memeriksa output stderr untuk setiap kombinasi
palet x aksen.
"""
import itertools
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import palette as pal  # noqa: E402
import theme_css  # noqa: E402


def _css_bytes(palette="iina-glass", accent="blue") -> bytes:
    return theme_css.build_css_bytes(palette, accent)


def test_css_has_no_unsupported_gtk_properties():
    for palette, accent in itertools.product(pal.PALETTE_NAMES, pal.ACCENT_NAMES):
        css = _css_bytes(palette, accent).decode("utf-8")
        offenders = re.findall(r"^\s*(overflow|z-index)\s*:", css, re.MULTILINE)
        assert not offenders, f"properti CSS tidak didukung GTK4 ({palette}/{accent}): {set(offenders)}"


def test_thumbnail_clipping_is_done_in_widget_code():
    src = (ROOT / "player_window" / "input_mixin.py").read_text(encoding="utf-8")
    assert "picture.set_overflow(Gtk.Overflow.HIDDEN)" in src


def test_theme_module_uses_the_generator():
    src = (ROOT / "player_window" / "theme.py").read_text(encoding="utf-8")
    assert "build_css_bytes" in src


def _provider():
    gi = pytest.importorskip("gi")
    try:
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as exc:  # pragma: no cover - env tanpa GTK4
        pytest.skip(f"GTK4 tidak tersedia: {exc}")
    try:
        return Gtk.CssProvider()
    except Exception as exc:  # pragma: no cover - env GTK tanpa display
        pytest.skip(f"Gtk.CssProvider tidak bisa dibuat: {exc}")


def _load(provider, css: bytes):
    from gi.repository import GLib

    try:
        provider.load_from_bytes(GLib.Bytes.new(css))
    except AttributeError:  # GTK < 4.12
        provider.load_from_data(css)


def test_stylesheet_loads_without_parser_warnings(capfd):
    provider = _provider()
    _load(provider, _css_bytes())
    err = capfd.readouterr().err
    assert "Theme parser error" not in err, f"warning CSS dari GTK:\n{err}"


@pytest.mark.parametrize("palette,accent", list(itertools.product(pal.PALETTE_NAMES, pal.ACCENT_NAMES)))
def test_every_palette_and_accent_loads_without_parser_warnings(capfd, palette, accent):
    provider = _provider()
    _load(provider, _css_bytes(palette, accent))
    err = capfd.readouterr().err
    assert "Theme parser error" not in err, f"warning CSS dari GTK ({palette}/{accent}):\n{err}"


@pytest.mark.parametrize("palette,accent", list(itertools.product(pal.PALETTE_NAMES, pal.ACCENT_NAMES)))
def test_reduce_motion_stylesheet_loads_without_parser_warnings(capfd, palette, accent):
    provider = _provider()
    _load(provider, theme_css.build_css_bytes(palette, accent, reduce_motion=True))
    err = capfd.readouterr().err
    assert "Theme parser error" not in err, f"warning CSS reduce-motion ({palette}/{accent}):\n{err}"


def test_warning_is_detected_for_unsupported_property(capfd):
    """Kontrol negatif: memastikan tes di atas tidak selalu lolos diam-diam."""
    provider = _provider()
    _load(provider, b"* { overflow: hidden; }")
    err = capfd.readouterr().err
    assert "Theme parser error" in err, "GTK tidak melaporkan properti CSS yang tidak dikenal"
