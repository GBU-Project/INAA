"""Teks terang di kartu/dialog gelap tidak boleh berada di atas ListBox yang dicat putih oleh tema terang."""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "player_window" / "common.py").read_text()


def _rule(selector_fragment):
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", SRC):
        if selector_fragment in m.group(1):
            return m.group(1), m.group(2)
    raise AssertionError(f"aturan CSS untuk {selector_fragment!r} tidak ditemukan")


def test_history_and_welcome_lists_are_transparent():
    selectors, body = _rule(".iina-history-dialog list")
    for needed in (".iina-history-dialog list", ".iina-history-dialog row", ".iina-welcome-card list", ".iina-welcome-card row"):
        assert needed in selectors
    assert "background-color: transparent" in body


def test_history_dialog_window_gets_the_dark_class():
    mix = (Path(__file__).resolve().parent.parent / "player_window" / "window_mixin.py").read_text()
    assert 'dialog.add_css_class("iina-history-dialog")' in mix


def test_dim_text_stays_readable_on_dark_cards():
    _, body = _rule(".iina-history-dialog .dim-label")
    assert "#a1a1a6" in body
