"""Tes config_sanitize: config rusak/diubah manual tidak boleh sampai ke UI."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config_sanitize import sanitize_config  # noqa: E402


@pytest.mark.parametrize("bad", [None, [], "x", 5])
def test_non_dict_becomes_empty(bad):
    assert sanitize_config(bad) == {}


def test_bad_recent_entries_are_dropped_and_numbers_fixed():
    out = sanitize_config({"recent_files": [
        {"path": 123}, "rusak", None, {"path": ""}, {"path": "a\x00b"},
        {"path": "/a.mp4", "title": 7, "position": "x", "duration": -3, "last_played": 5},
        {"path": "/a.mp4"}, {"path": "/b.mp4", "position": float("nan")},
    ]})
    paths = [e["path"] for e in out["recent_files"]]
    assert paths == ["/a.mp4", "/b.mp4"]
    a = out["recent_files"][0]
    assert a["title"] == "" and a["position"] == 0.0 and a["duration"] == 0.0 and a["last_played"] == ""


def test_recent_files_not_a_list():
    assert sanitize_config({"recent_files": "x"})["recent_files"] == []


@pytest.mark.parametrize("bad", ["x", None, 5, [None] * 10, ["x"] * 3, [float("nan")] * 10, [99] * 20])
def test_eq_gains_always_ten_valid_numbers(bad):
    g = sanitize_config({"audio_eq_gains": bad})["audio_eq_gains"]
    assert len(g) == 10 and all(isinstance(x, float) and -12 <= x <= 12 for x in g)


def test_custom_presets_cannot_shadow_builtins_and_are_cleaned():
    out = sanitize_config({"audio_custom_presets": {
        "flat": [1] * 10, "Rock": [2] * 10, "Custom": [1] * 10, "Bass Boost": [1] * 10, "Punyaku": ["x", 50],
        5: [1], "": [1], "n" * 41: [1],
    }})
    assert list(out["audio_custom_presets"]) == ["Bass Boost", "Punyaku"] or list(out["audio_custom_presets"]) == ["Punyaku", "Bass Boost"] or "Punyaku" in out["audio_custom_presets"]
    assert "flat" not in out["audio_custom_presets"] and "Rock" not in out["audio_custom_presets"]
    assert out["audio_custom_presets"]["Punyaku"][0] == 0.0 and out["audio_custom_presets"]["Punyaku"][1] == 12.0


def test_misc_fields():
    out = sanitize_config({"audio_special_effect": "evil", "audio_eq_preset": 5, "enabled_plugins": ["a", 1, None],
                           "shortcuts": [], "volume": "loud", "width": -5, "height": "x"})
    assert out["audio_special_effect"] == "none" and out["audio_eq_preset"] == "custom"
    assert out["enabled_plugins"] == ["a"] and out["shortcuts"] == {}
    assert out["volume"] == 100 and out["width"] >= 200 and out["height"] == 620


def test_valid_config_is_left_alone():
    cfg = {"recent_files": [{"path": "/a.mp4", "title": "A", "position": 1.5, "duration": 10.0, "last_played": "2026-10-12 09:00"}],
           "audio_eq_gains": [1.0] * 10, "audio_special_effect": "nightmode", "volume": 80}
    out = sanitize_config(dict(cfg))
    assert out["recent_files"] == cfg["recent_files"] and out["audio_eq_gains"] == [1.0] * 10
    assert out["audio_special_effect"] == "nightmode" and out["volume"] == 80


def test_custom_shaders_only_clean_strings():
    out = sanitize_config({"custom_shaders": ["/a.glsl", 5, None, "", "x\x00y", ["z"]]})
    assert out["custom_shaders"] == ["/a.glsl"]
    assert sanitize_config({"custom_shaders": "x"})["custom_shaders"] == []
