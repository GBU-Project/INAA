"""Logika tema murni (Phase 2.1): resolusi palet, portal color-scheme, reduce motion."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import palette as pal  # noqa: E402
import theme_css  # noqa: E402
import theme_logic as tl  # noqa: E402


# -- resolve_palette_name ----------------------------------------------------
@pytest.mark.parametrize(
    "theme,system,expected",
    [
        # mode light: selalu light, apa pun palet/OS
        ({"mode": "light", "palette": "iina-glass"}, True, "light"),
        ({"mode": "light", "palette": "graphite"}, None, "light"),
        # mode dark: palet gelap pilihan dipakai; palet terang diganti iina-glass
        ({"mode": "dark", "palette": "graphite"}, False, "graphite"),
        ({"mode": "dark", "palette": "iina-glass"}, False, "iina-glass"),
        ({"mode": "dark", "palette": "light"}, True, "iina-glass"),
        # mode system: ikuti OS
        ({"mode": "system", "palette": "graphite"}, True, "graphite"),
        ({"mode": "system", "palette": "graphite"}, False, "light"),
        ({"mode": "system", "palette": "iina-glass"}, None, "iina-glass"),
        ({"mode": "system", "palette": "light"}, True, "iina-glass"),
        # nilai rusak/asing -> perilaku aman
        ({"mode": "aneh", "palette": "graphite"}, True, "graphite"),
        ({"mode": "dark", "palette": "tidak-ada"}, None, "iina-glass"),
        ({}, None, "iina-glass"),
        (None, False, "light"),
        ("rusak", True, "iina-glass"),
    ],
)
def test_resolve_palette_name(theme, system, expected):
    assert tl.resolve_palette_name(theme, system) == expected


def test_resolved_palette_always_exists():
    for mode in ("system", "dark", "light", "x"):
        for chosen in (*pal.PALETTE_NAMES, "x"):
            for system in (True, False, None):
                name = tl.resolve_palette_name({"mode": mode, "palette": chosen}, system)
                assert name in pal.PALETTE_NAMES


def test_dark_modes_never_return_a_light_palette():
    for chosen in (*pal.PALETTE_NAMES, "x"):
        name = tl.resolve_palette_name({"mode": "dark", "palette": chosen}, False)
        assert pal.get_palette(name).is_dark


def test_resolve_accent():
    assert tl.resolve_accent({"accent": "green"}) == "green"
    assert tl.resolve_accent({"accent": "neon"}) == "blue"
    assert tl.resolve_accent(None) == "blue"


# -- portal ------------------------------------------------------------------
class _FakeVariant:
    """Meniru GLib.Variant: unpack() memberi nilai (mungkin berlapis)."""

    def __init__(self, inner):
        self._inner = inner

    def unpack(self):
        return self._inner


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, None), (1, True), (2, False), (3, None), (-1, None),
        (True, None), (False, None), ("1", None), (None, None), (1.0, None),
        ((1,), True), ((2,), False), (((1,),), True), ((1, 2), None), ((), None),
        (_FakeVariant(1), True),
        (_FakeVariant((2,)), False),
        (_FakeVariant(_FakeVariant(1)), True),
        (_FakeVariant("gelap"), None),
    ],
)
def test_parse_portal_color_scheme(value, expected):
    assert tl.parse_portal_color_scheme(value) is expected


def test_parse_portal_survives_broken_variant():
    class Broken:
        def unpack(self):
            raise RuntimeError("rusak")

    assert tl.parse_portal_color_scheme(Broken()) is None


def test_parse_portal_terminates_on_self_referential_variant():
    class Loop:
        def unpack(self):
            return self

    assert tl.parse_portal_color_scheme(Loop()) is None


# -- reduce motion -----------------------------------------------------------
@pytest.mark.parametrize(
    "cfg,gtk,expected",
    [(False, True, False), (False, None, False), (True, True, True),
     (True, None, True), (False, False, True), (True, False, True)],
)
def test_should_reduce_motion(cfg, gtk, expected):
    assert tl.should_reduce_motion(cfg, gtk) is expected


def test_css_default_has_no_reduce_motion_block_and_flag_adds_one():
    base = theme_css.build_css("iina-glass", "blue")
    reduced = theme_css.build_css("iina-glass", "blue", reduce_motion=True)
    assert "reduce motion" not in base
    assert reduced.startswith(base)
    assert "transition: none" in reduced[len(base):]
    assert reduced.count("{") == reduced.count("}")
