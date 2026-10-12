"""Preamp otomatis equalizer: boost tidak boleh membuat suara pecah; semuanya satu graf lavfi."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio_filters as af  # noqa: E402


def test_no_boost_no_preamp():
    assert af.preamp_db([0.0] * 10) == 0.0
    assert af.preamp_db([-6.0, -3.0] + [0.0] * 8) == 0.0
    assert "volume=" not in af.compose_af_string([-6.0] + [0.0] * 9)


def test_preamp_equals_highest_positive_gain():
    assert af.preamp_db([3.0, 6.5, -4.0] + [0.0] * 7) == -6.5
    assert af.preamp_db([99.0] + [0.0] * 9) == -12.0  # gain dijepit dulu


@pytest.mark.parametrize("bad", [None, [], "x", [None] * 10, ["x"] * 10])
def test_preamp_survives_garbage(bad):
    assert af.preamp_db(bad if bad is not None else []) <= 0.0


def test_volume_filter_comes_first_and_is_inside_one_graph():
    out = af.compose_af_string(af.EQ_PRESETS["rock"], "nightmode")
    assert out.startswith("lavfi=[volume=volume=-5.0dB,equalizer=")
    assert out.count("lavfi=[") == 1 and out.endswith("loudnorm=I=-16:TP=-1.5:LRA=11]")


def test_every_preset_and_effect_is_a_single_graph():
    for name, gains in af.EQ_PRESETS.items():
        for effect in af.SPECIAL_AUDIO_EFFECTS:
            out = af.compose_af_string(gains, effect)
            assert out == "" or (out.startswith("lavfi=[") and out.endswith("]") and out.count("lavfi=[") == 1), (name, effect, out)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg tidak ada")
@pytest.mark.parametrize("preset", ["bass_boost", "rock", "party", "electronic"])
def test_boosted_noise_does_not_clip_with_preamp(preset):
    chain = af.compose_af_string(af.EQ_PRESETS[preset])[len("lavfi=["):-1]
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "anoisesrc=d=3:c=white:a=0.7:seed=7",
         "-af", f"{chain},volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60)
    line = [l for l in r.stderr.splitlines() if "max_volume" in l][0]
    peak = float(line.split("max_volume:")[1].split("dB")[0])
    assert peak < -0.3, f"{preset}: puncak {peak} dB (pecah)"
