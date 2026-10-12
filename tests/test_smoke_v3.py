"""Smoke GUI + mpv sungguhan untuk perbaikan v3 (loop aktif, riwayat, shader, mpv.conf langsung, preset, af gabungan)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent / "_smoke_v3_app.py"


def _can_import_gui():
    probe = "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; import mpv"
    return subprocess.run([sys.executable, "-c", probe], capture_output=True).returncode == 0


pytestmark = [
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg tidak ada"),
    pytest.mark.skipif(shutil.which("xvfb-run") is None, reason="xvfb-run tidak ada"),
    pytest.mark.skipif(not _can_import_gui(), reason="PyGObject/GTK4/python-mpv tidak tersedia"),
]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    media = tmp_path_factory.mktemp("media")
    home = tmp_path_factory.mktemp("home")
    cfg = home / ".config" / "inaa"
    (cfg / "shaders").mkdir(parents=True)
    (home / ".config" / "mpv").mkdir(parents=True)
    video = media / "movie.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=20:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-c:v", "libx264", "-g", "10",
         "-c:a", "aac", "-shortest", str(video)], check=True)
    good = cfg / "shaders" / "ok.glsl"
    good.write_text("//!HOOK LUMA\n//!BIND HOOKED\nvec4 hook() { return HOOKED_texOff(0); }\n")
    (home / ".config" / "mpv" / "mpv.conf").write_text("deband=yes\nosc=yes\ninput-ipc-server=%s\n" % (home / "ipc.sock"))
    (cfg / "config.json").write_text(json.dumps({
        "recent_files": [
            {"path": str(video), "title": "Ada", "position": 5, "duration": 20, "last_played": "2026-10-12 09:00"},
            {"path": str(media / "hilang.mp4"), "title": "Hilang", "position": 5, "duration": 20},
            {"path": 123}, "rusak", None,
        ],
        "audio_eq_gains": ["x", None, 99],
        "custom_shaders": [str(good), "/etc/passwd", "../x.glsl", 5],
        "audio_custom_presets": {"flat": [9] * 10},
        "use_mpv_conf": False,
    }))
    env = dict(os.environ, HOME=str(home), LIBGL_ALWAYS_SOFTWARE="1", GTK_A11Y="none")
    proc = subprocess.run(["xvfb-run", "-a", sys.executable, str(APP), str(video)],
                          env=env, capture_output=True, text=True, timeout=70)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")]
    assert lines, f"tidak ada RESULT.\nstdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}"
    data = json.loads(lines[-1][len("RESULT "):])
    data["_home"] = str(home)
    return data


def test_corrupt_config_does_not_crash_and_app_runs(run):
    assert run["constructed"] is True
    assert not run.get("errors"), run.get("errors")


def test_loop_mode_active_button_is_marked(run):
    assert run["loop_active"] == ["one"] and run["loop_active_after"] == ["off"]


def test_history_opens_once_and_missing_file_is_not_clickable(run):
    assert run["open_calls"] == 1
    assert ("Putar dan lanjutkan", True) in [tuple(x) for x in run["history_buttons"]]
    assert ("File tidak ditemukan", False) in [tuple(x) for x in run["history_buttons"]]


def test_only_valid_shader_reaches_mpv(run):
    assert run["glsl"] == ["ok.glsl"]


def test_use_mpv_conf_applies_immediately_but_stays_safe(run):
    assert run["deband_before"] is False and run["deband_after"] is True
    assert run["osc"] is False and run["ipc"] in ("", None)
    assert not (Path(run["_home"]) / "ipc.sock").exists()


def test_custom_preset_cannot_shadow_builtin(run):
    assert run["save_flat"] is False and run["save_rock"] is False and run["save_ok"] is True
    assert run["custom_names"] == ["Punyaku"]


def test_combined_equalizer_and_loudnorm_is_accepted_by_real_mpv(run):
    assert run["af"] == ["lavfi"]  # satu graf lavfi: equalizer + loudnorm
