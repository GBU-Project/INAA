"""Smoke test CSS tema: harus bisa dimuat GTK tanpa warning parser.

GTK4 tidak mengenal `overflow`/`z-index`; properti itu dulu memunculkan
`Theme parser error` di stderr. Tes ini mengekstrak literal `_IINA_CSS` dari
theme.py (tanpa mengimpor paket player_window yang butuh libmpv) lalu
memuatnya ke Gtk.CssProvider sambil memeriksa output stderr.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "player_window" / "theme.py"


def _css_bytes() -> bytes:
    tree = ast.parse(THEME.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_IINA_CSS":
                    return ast.literal_eval(node.value)
    raise AssertionError("_IINA_CSS tidak ditemukan di theme.py")


def test_css_has_no_unsupported_gtk_properties():
    css = _css_bytes().decode("utf-8")
    offenders = re.findall(r"^\s*(overflow|z-index)\s*:", css, re.MULTILINE)
    assert not offenders, f"properti CSS tidak didukung GTK4: {set(offenders)}"


def test_thumbnail_clipping_is_done_in_widget_code():
    src = (ROOT / "player_window" / "input_mixin.py").read_text(encoding="utf-8")
    assert "picture.set_overflow(Gtk.Overflow.HIDDEN)" in src


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


def test_warning_is_detected_for_unsupported_property(capfd):
    """Kontrol negatif: memastikan tes di atas tidak selalu lolos diam-diam."""
    provider = _provider()
    _load(provider, b"* { overflow: hidden; }")
    err = capfd.readouterr().err
    assert "Theme parser error" in err, "GTK tidak melaporkan properti CSS yang tidak dikenal"
