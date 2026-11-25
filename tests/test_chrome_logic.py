"""Logika OSC murni (Phase 2.2)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chrome_logic as cl  # noqa: E402
from layout_config import default_layout  # noqa: E402


def _layout(**osc):
    lay = default_layout()
    lay["osc"].update(osc)
    return lay


def test_flag_off_ignores_config_and_uses_legacy_floating():
    st = cl.resolve_osc(_layout(mode="docked", size="large", always_visible=True), enabled=False)
    assert st["mode"] == "floating" and st["slot"] is None
    assert st["size"] == "regular" and st["width"] == 440
    assert st["always_visible"] is False and st["visible"] is True


@pytest.mark.parametrize("pos", ["top", "bottom"])
def test_docked_uses_slot_and_height(pos):
    st = cl.resolve_osc(_layout(mode="docked", position=pos, size="compact"), enabled=True)
    assert st["slot"] == pos and st["docked_height"] == cl.DOCKED_HEIGHTS["compact"]
    assert not cl.osc_auto_hide_allowed(st)


def test_floating_has_no_slot_and_can_auto_hide():
    st = cl.resolve_osc(_layout(mode="floating"), enabled=True)
    assert st["slot"] is None and st["docked_height"] == 0
    assert cl.osc_auto_hide_allowed(st)


def test_always_visible_blocks_auto_hide():
    st = cl.resolve_osc(_layout(mode="floating", always_visible=True), enabled=True)
    assert not cl.osc_auto_hide_allowed(st)


def test_off_is_hidden():
    st = cl.resolve_osc(_layout(mode="off"), enabled=True)
    assert st["visible"] is False and st["slot"] is None


def test_mini_forces_visible_floating_even_when_off_or_docked():
    for mode in ("off", "docked", "floating"):
        st = cl.resolve_osc(_layout(mode=mode), enabled=True, is_mini=True)
        assert st["mode"] == "floating" and st["visible"] and st["slot"] is None
        assert st["always_visible"] and not cl.osc_auto_hide_allowed(st)


def test_fullscreen_turns_docked_into_floating_but_keeps_off():
    st = cl.resolve_osc(_layout(mode="docked"), enabled=True, is_fullscreen=True)
    assert st["mode"] == "floating" and st["slot"] is None
    st = cl.resolve_osc(_layout(mode="off"), enabled=True, is_fullscreen=True)
    assert st["visible"] is False


@pytest.mark.parametrize("raw", [None, "rusak", {"osc": "x"}, {"osc": {"mode": "aneh", "size": 5}}])
def test_broken_layout_falls_back_to_defaults(raw):
    st = cl.resolve_osc(raw, enabled=True)
    assert st["mode"] == "floating" and st["size"] == "regular" and st["visible"]


def test_widths_cover_all_sizes():
    assert set(cl.OSC_WIDTHS) == set(cl.DOCKED_HEIGHTS) == {"compact", "regular", "large"}


# -- header bar & auto-hide (Phase 2.3) ---------------------------------------
@pytest.mark.parametrize(
    "legacy,expected", [(True, "auto-hide"), (False, "full")]
)
def test_header_mode_flag_off_follows_legacy_setting(legacy, expected):
    lay = default_layout()
    lay["headerbar"] = "full" if legacy else "auto-hide"  # diabaikan saat flag mati
    assert cl.resolve_header_mode(lay, enabled=False, legacy_auto_hide=legacy) == expected


@pytest.mark.parametrize(
    "mode,expected",
    [("full", "full"), ("auto-hide", "auto-hide"), ("hidden", "hidden"), ("aneh", "auto-hide")],
)
def test_header_mode_flag_on_uses_layout(mode, expected):
    lay = default_layout()
    lay["headerbar"] = mode
    assert cl.resolve_header_mode(lay, enabled=True, legacy_auto_hide=False) == expected


def _flags(layout, **kw):
    osc = cl.resolve_osc(layout, enabled=kw["enabled"])
    return cl.auto_hide_flags(layout, osc_state=osc, **kw)


def test_flags_flag_off_both_follow_legacy():
    lay = default_layout()
    assert _flags(lay, enabled=False, legacy_auto_hide=True) == (True, True)
    assert _flags(lay, enabled=False, legacy_auto_hide=False) == (False, False)


def test_flags_flag_on_are_independent():
    lay = _layout(mode="docked")
    lay["headerbar"] = "auto-hide"
    assert _flags(lay, enabled=True, legacy_auto_hide=False) == (False, True)
    lay = _layout(mode="floating")
    lay["headerbar"] = "full"
    assert _flags(lay, enabled=True, legacy_auto_hide=False) == (True, False)
    lay = _layout(mode="floating", always_visible=True)
    lay["headerbar"] = "full"
    assert _flags(lay, enabled=True, legacy_auto_hide=True) == (False, False)


def test_hidden_header_is_never_auto_hidden():
    lay = _layout(mode="floating")
    lay["headerbar"] = "hidden"
    assert _flags(lay, enabled=True, legacy_auto_hide=True) == (True, False)
