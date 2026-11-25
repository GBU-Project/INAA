"""Deteksi dan penerapan preset layout (Phase 2.4), murni tanpa GTK."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from layout_config import (  # noqa: E402
    REAL_PRESETS,
    apply_preset,
    default_layout,
    detect_preset,
    sanitize_layout,
)


def test_default_layout_is_classic():
    assert detect_preset(default_layout()) == "classic"


@pytest.mark.parametrize("name", REAL_PRESETS)
def test_apply_then_detect_round_trips(name):
    lay = apply_preset(default_layout(), name)
    assert lay["preset"] == name
    assert detect_preset(lay) == name


def test_all_presets_are_distinguishable():
    seen = {detect_preset(apply_preset(default_layout(), n)) for n in REAL_PRESETS}
    assert seen == set(REAL_PRESETS)


@pytest.mark.parametrize(
    "edit",
    [
        lambda l: l["osc"].update(size="large"),
        lambda l: l["osc"].update(mode="off"),
        lambda l: l["osc"].update(position="top"),
        lambda l: l.update(headerbar="full"),
        lambda l: l["playlist"].update(edge="right"),
        lambda l: l["inspector"].update(visible=True),
    ],
)
def test_manual_edit_becomes_custom(edit):
    lay = apply_preset(default_layout(), "compact")
    edit(lay)
    assert detect_preset(lay) == "custom"


@pytest.mark.parametrize(
    "edit",
    [
        lambda l: l["playlist"].update(width=333),
        lambda l: l["theme"].update(accent="green", mode="light"),
        lambda l: l.update(reduce_motion=True),
        lambda l: l["osc"].update(always_visible=True),
    ],
)
def test_width_theme_and_motion_do_not_change_preset(edit):
    lay = apply_preset(default_layout(), "cinema")
    edit(lay)
    assert detect_preset(lay) == "cinema"


def test_apply_preset_keeps_theme_and_motion():
    lay = default_layout()
    lay["theme"].update(mode="light", palette="light", accent="pink")
    lay["reduce_motion"] = True
    out = apply_preset(lay, "music")
    assert out["theme"] == {"mode": "light", "palette": "light", "accent": "pink"}
    assert out["reduce_motion"] is True
    assert out["osc"]["mode"] == "docked" and out["playlist"]["edge"] == "right"


@pytest.mark.parametrize("name", ["custom", "aneh", "", None])
def test_non_real_preset_changes_only_label(name):
    lay = apply_preset(default_layout(), "compact")
    out = apply_preset(lay, name)
    assert out["osc"] == lay["osc"] and out["headerbar"] == lay["headerbar"]
    assert out["preset"] == "compact"  # label mengikuti isi layout yang sebenarnya


@pytest.mark.parametrize("raw", [None, "rusak", 5, {"osc": "x"}])
def test_broken_input_is_safe(raw):
    assert detect_preset(raw) == "classic"
    assert apply_preset(raw, "cinema")["preset"] == "cinema"
    assert sanitize_layout(apply_preset(raw, "cinema")) == apply_preset(raw, "cinema")
