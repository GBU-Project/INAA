"""Teks terang di kartu/dialog gelap tidak boleh berada di atas ListBox yang dicat putih oleh tema terang.

Stylesheet dibuat oleh `theme_css.build_css()` (murni), jadi tes ini tidak perlu
mengimpor paket `player_window` (yang butuh libmpv).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import palette as pal  # noqa: E402
import theme_css  # noqa: E402

SRC = theme_css.build_css("iina-glass", "blue")


def _rule(selector_fragment, src=SRC):
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", src):
        if selector_fragment in m.group(1):
            return m.group(1), m.group(2)
    raise AssertionError(f"aturan CSS untuk {selector_fragment!r} tidak ditemukan")


def test_history_and_welcome_lists_are_transparent():
    selectors, body = _rule(".iina-history-dialog list")
    for needed in (".iina-history-dialog list", ".iina-history-dialog row", ".iina-welcome-card list", ".iina-welcome-card row"):
        assert needed in selectors
    assert "background-color: transparent" in body


def test_transparent_list_rule_holds_for_every_palette():
    for name in pal.PALETTE_NAMES:
        css = theme_css.build_css(name, "blue")
        _, body = _rule(".iina-history-dialog list", css)
        assert "background-color: transparent" in body, name


def test_history_dialog_window_gets_the_dark_class():
    mix = (ROOT / "player_window" / "window_mixin.py").read_text()
    assert 'dialog.add_css_class("iina-history-dialog")' in mix


def test_dim_text_stays_readable_on_dark_cards():
    _, body = _rule(".iina-history-dialog .dim-label")
    assert "#a1a1a6" in body
