"""Tes skema layout murni (Phase 0): default, clamp, enum, migrasi config."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import layout_config as lc  # noqa: E402
from config_sanitize import sanitize_config  # noqa: E402


def test_default_layout_is_complete_and_stable():
    default = lc.default_layout()
    assert default["version"] == lc.LAYOUT_VERSION
    assert default["preset"] == "classic"
    assert default["playlist"] == {"edge": "left", "visible": True, "width": 260}
    assert default["inspector"] == {"edge": "right", "visible": False, "width": 320}
    assert default["osc"] == {
        "mode": "floating", "position": "bottom", "size": "regular", "always_visible": False,
    }
    assert default["headerbar"] == "auto-hide"
    assert default["theme"] == {"mode": "dark", "palette": "iina-glass", "accent": "blue"}
    assert lc.sanitize_layout(None) == default
    assert lc.sanitize_layout({}) == default
    assert lc.sanitize_layout("rusak") == default


def test_layout_state_round_trips():
    state = lc.LayoutState(playlist_width=410, osc_size="large", headerbar="hidden")
    assert lc.LayoutState.from_dict(state.to_dict()) == state
    assert lc.LayoutState.from_dict(None).to_dict() == lc.default_layout()


@pytest.mark.parametrize("raw,expected", [
    (0, lc.MIN_PANE_WIDTH),
    (159, lc.MIN_PANE_WIDTH),
    (160, 160),
    (600, 600),
    (601, lc.MAX_PANE_WIDTH),
    (9999, lc.MAX_PANE_WIDTH),
    ("x", 260),
    (None, 260),
    (3.9, lc.MIN_PANE_WIDTH),  # int() truncation lalu di-clamp
])
def test_pane_widths_are_clamped(raw, expected):
    out = lc.sanitize_layout({"playlist": {"width": raw}})
    assert out["playlist"]["width"] == expected


def test_inspector_width_clamped_independently():
    out = lc.sanitize_layout({"inspector": {"width": 9999}})
    assert out["inspector"]["width"] == lc.MAX_PANE_WIDTH
    assert out["playlist"]["width"] == 260


@pytest.mark.parametrize("section,key,value", [
    ("playlist", "edge", "diagonal"),
    ("inspector", "edge", ""),
    ("osc", "mode", "popup"),
    ("osc", "position", "center"),
    ("osc", "size", "huge"),
])
def test_unknown_enums_fall_back_to_defaults(section, key, value):
    default = lc.default_layout()[section][key]
    out = lc.sanitize_layout({section: {key: value}})
    assert out[section][key] == default


def test_headerbar_and_theme_enums():
    assert lc.sanitize_layout({"headerbar": "floating"})["headerbar"] == "auto-hide"
    assert lc.sanitize_layout({"headerbar": "hidden"})["headerbar"] == "hidden"
    assert lc.sanitize_layout({"theme": {"mode": "neon"}})["theme"]["mode"] == "dark"
    assert lc.sanitize_layout({"theme": {"palette": "hotdog"}})["theme"]["palette"] == "iina-glass"
    assert lc.sanitize_layout({"theme": {"accent": "cyan"}})["theme"]["accent"] == "blue"


@pytest.mark.parametrize("value", ["yes", 2, -1, [], {}])
def test_bools_reject_non_boolean_values(value):
    out = lc.sanitize_layout({"reduce_motion": value, "osc": {"always_visible": value}})
    assert out["reduce_motion"] is False
    assert out["osc"]["always_visible"] is False


def test_bools_accept_zero_and_one():
    out = lc.sanitize_layout({"reduce_motion": 1, "lock_aspect": 0})
    assert out["reduce_motion"] is True
    assert out["lock_aspect"] is False


def test_partial_sections_keep_other_defaults():
    out = lc.sanitize_layout({
        "preset": "compact",
        "playlist": {"width": 300},
        "osc": {"mode": "docked"},
        "theme": {"accent": "green"},
    })
    assert out["playlist"] == {"edge": "left", "visible": True, "width": 300}
    assert out["osc"]["mode"] == "docked"
    assert out["osc"]["position"] == "bottom" and out["osc"]["size"] == "regular"
    assert out["theme"] == {"mode": "dark", "palette": "iina-glass", "accent": "green"}


def test_unknown_keys_are_dropped():
    out = lc.sanitize_layout({
        "evil": True,
        "playlist": {"bogus": 1, "width": 200},
        "osc": {"popup": "x"},
        "theme": {"gradient": "yes"},
    })
    assert set(out) == {
        "version", "preset", "playlist", "inspector", "osc", "headerbar",
        "theme", "reduce_motion", "lock_aspect",
    }
    assert set(out["playlist"]) == {"edge", "visible", "width"}
    assert set(out["osc"]) == {"mode", "position", "size", "always_visible"}
    assert set(out["theme"]) == {"mode", "palette", "accent"}


@pytest.mark.parametrize("name", lc.PRESET_NAMES)
def test_presets_are_valid_and_sanitize_cleanly(name):
    preset = lc.preset_layout(name)
    assert preset["preset"] == name
    assert lc.sanitize_layout(preset) == preset


def test_unknown_preset_falls_back_to_classic_seed():
    preset = lc.preset_layout("does-not-exist")
    assert preset["preset"] == "classic"
    assert preset["playlist"]["width"] == lc.default_layout()["playlist"]["width"]


def test_compact_preset_changes_osc_and_width():
    preset = lc.preset_layout("compact")
    assert preset["osc"]["mode"] == "docked"
    assert preset["osc"]["size"] == "compact"
    assert preset["playlist"]["width"] == 220


def test_migration_v1_maps_auto_hide_chrome():
    old = {"auto_hide_chrome": False, "volume": 70}
    out = sanitize_config(dict(old))
    assert out["config_version"] == lc.CONFIG_VERSION
    assert out["layout"]["headerbar"] == "full"
    assert out["volume"] == 70

    out_true = sanitize_config({"auto_hide_chrome": True})
    assert out_true["layout"]["headerbar"] == "auto-hide"


def test_migration_keeps_explicit_layout_headerbar():
    out = sanitize_config({
        "config_version": 1,
        "auto_hide_chrome": False,
        "layout": {"headerbar": "hidden"},
    })
    assert out["layout"]["headerbar"] == "hidden"


def test_migration_is_idempotent_and_does_not_remap_after_v2():
    first = sanitize_config({"auto_hide_chrome": False})
    assert first["layout"]["headerbar"] == "full"
    first["auto_hide_chrome"] = True
    second = sanitize_config(first)
    assert second["layout"]["headerbar"] == "full"
    assert second["config_version"] == lc.CONFIG_VERSION


def test_migration_adds_layout_when_missing_but_version_is_2():
    out = sanitize_config({"config_version": 2})
    assert out["layout"] == lc.default_layout()
    assert out["ui_layout_v2"] is False


def test_layout_v2_flag_validation():
    assert sanitize_config({"ui_layout_v2": True})["ui_layout_v2"] is True
    assert sanitize_config({"ui_layout_v2": 1})["ui_layout_v2"] is True
    for bad in ("yes", 2, None, [], {}):
        assert sanitize_config({"ui_layout_v2": bad})["ui_layout_v2"] is False


def test_layout_v2_enabled_env_wins():
    assert lc.layout_v2_enabled({"ui_layout_v2": False}, {}) is False
    assert lc.layout_v2_enabled({"ui_layout_v2": True}, {}) is True
    assert lc.layout_v2_enabled({}, {"INAA_LAYOUT_V2": "1"}) is True
    assert lc.layout_v2_enabled({}, {"INAA_LAYOUT_V2": "on"}) is True
    assert lc.layout_v2_enabled({"ui_layout_v2": True}, {"INAA_LAYOUT_V2": "0"}) is True
    assert lc.layout_v2_enabled(None, {"INAA_LAYOUT_V2": ""}) is False


def test_layout_from_config_reads_nested_section():
    cfg = {"layout": {"osc": {"size": "large"}}}
    out = lc.layout_from_config(cfg)
    assert out["osc"]["size"] == "large"
    assert lc.layout_from_config(None) == lc.default_layout()


def test_dock_sides_defaults():
    assert lc.dock_sides(lc.default_layout()) == (["playlist"], [])


def test_dock_sides_switches_edges():
    layout = lc.sanitize_layout({
        "playlist": {"edge": "right", "visible": True},
        "inspector": {"edge": "left", "visible": True},
    })
    left, right = lc.dock_sides(layout)
    assert left == ["inspector"]
    assert right == ["playlist"]


def test_dock_sides_both_on_same_edge_order():
    left, right = lc.dock_sides({
        "playlist": {"edge": "left", "visible": True},
        "inspector": {"edge": "left", "visible": True},
    })
    assert left == ["playlist", "inspector"] and right == []

    left, right = lc.dock_sides({
        "playlist": {"edge": "right", "visible": True},
        "inspector": {"edge": "right", "visible": True},
    })
    assert left == [] and right == ["inspector", "playlist"]


def test_dock_sides_skips_hidden_and_invisible():
    assert lc.dock_sides({
        "playlist": {"edge": "hidden", "visible": True},
        "inspector": {"edge": "right", "visible": False},
    }) == ([], [])
    assert lc.dock_sides({
        "playlist": {"edge": "left", "visible": False},
        "inspector": {"edge": "right", "visible": True},
    }) == ([], ["inspector"])


def test_dock_sides_accepts_raw_or_invalid_input():
    assert lc.dock_sides(None) == (["playlist"], [])
    assert lc.dock_sides("rusak") == (["playlist"], [])
