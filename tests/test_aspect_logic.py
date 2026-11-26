"""Kunci rasio jendela (lock_aspect), logika murni."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import aspect_logic as al  # noqa: E402
from layout_config import apply_preset, default_layout, sanitize_layout  # noqa: E402


def test_already_matching_returns_none():
    # area video 1000x563 (16:9) + header 48
    assert al.aspect_target(1000, 611, 1920, 1080, chrome_h=48) is None


def test_within_tolerance_returns_none():
    assert al.aspect_target(1000, 615, 1920, 1080, chrome_h=48) is None


def test_default_keeps_width_and_adjusts_height():
    assert al.aspect_target(1000, 700, 1920, 1080, chrome_h=48) == (1000, 610)


def test_user_changed_height_keeps_height_and_adjusts_width():
    # tinggi berubah 600 -> 700, lebar tetap: tinggi yang dipertahankan
    target = al.aspect_target(1000, 700, 1920, 1080, chrome_h=48, prev_size=(1000, 600))
    assert target == (1159, 700)


def test_user_changed_width_keeps_width():
    target = al.aspect_target(1000, 700, 1920, 1080, chrome_h=48, prev_size=(800, 700))
    assert target == (1000, 610)


def test_dock_width_excluded_from_video_area():
    # dock 260 px: area video 1000 -> tinggi 563 + 48
    assert al.aspect_target(1260, 611, 1920, 1080, chrome_h=48, extra_w=260) is None
    assert al.aspect_target(1260, 800, 1920, 1080, chrome_h=48, extra_w=260) == (1260, 610)


def test_portrait_video():
    # 9:16, area lebar 600 -> tinggi 1067 + 48
    assert al.aspect_target(600, 700, 1080, 1920, chrome_h=48) == (600, 1115)


def test_minimum_height_clamped():
    target = al.aspect_target(500, 900, 2000, 500, chrome_h=0)
    assert target == (500, al.MIN_HEIGHT)


def test_invalid_inputs_return_none():
    assert al.aspect_target(1000, 700, 0, 1080) is None
    assert al.aspect_target(1000, 700, 1920, 0) is None
    assert al.aspect_target(0, 700, 1920, 1080) is None
    assert al.aspect_target(100, 700, 1920, 1080, extra_w=200) is None
    assert al.aspect_target(1000, 40, 1920, 1080, chrome_h=48) is None


def test_applying_result_is_stable():
    first = al.aspect_target(1234, 777, 1280, 720, chrome_h=48, extra_w=100)
    assert first is not None
    assert al.aspect_target(*first, 1280, 720, chrome_h=48, extra_w=100) is None


def test_lock_aspect_survives_presets_and_sanitize():
    layout = default_layout()
    layout["lock_aspect"] = True
    assert apply_preset(layout, "cinema")["lock_aspect"] is True
    assert sanitize_layout({"lock_aspect": True})["lock_aspect"] is True
    assert sanitize_layout({"lock_aspect": "ya"})["lock_aspect"] is False
