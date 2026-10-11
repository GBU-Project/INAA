"""Smoke test end-to-end: pemutaran nyata, subtitle auto-load, MPRIS, screenshot, detach, resume.

Butuh: Python dengan PyGObject+GTK4, python-mpv/libmpv, ffmpeg, xvfb-run.
Kalau salah satu tidak ada, tes di-skip (bukan gagal). MPRIS dites kalau `dbus-run-session` ada.
Jalankan dengan Python yang cocok dengan PyGObject sistem, mis. `python3 -m pytest tests`.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__file__).resolve().parent / "_smoke_app.py"


def _can_import_gui():
    probe = (
        "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; import mpv"
    )
    return subprocess.run([sys.executable, "-c", probe], capture_output=True).returncode == 0


pytestmark = [
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg tidak ada"),
    pytest.mark.skipif(shutil.which("xvfb-run") is None, reason="xvfb-run tidak ada"),
    pytest.mark.skipif(not _can_import_gui(), reason="PyGObject/GTK4/python-mpv tidak tersedia untuk interpreter ini"),
]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    media = tmp_path_factory.mktemp("media")
    home = tmp_path_factory.mktemp("home")

    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=25:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=25", "-c:v", "libx264", "-g", "10",
         "-c:a", "aac", "-shortest", str(media / "movie.mp4")],
        check=True,
    )
    (media / "movie.srt").write_text("1\n00:00:01,000 --> 00:00:03,000\nuji subtitle\n")

    env = dict(os.environ, HOME=str(home), LIBGL_ALWAYS_SOFTWARE="1", GTK_A11Y="none")
    cmd = ["xvfb-run", "-a", sys.executable, str(APP), str(media), "movie.mp4"]
    if shutil.which("dbus-run-session"):
        cmd = ["dbus-run-session", "--"] + cmd

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=70)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")]
    assert lines, f"aplikasi smoke tidak menghasilkan RESULT.\nstdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}"
    data = json.loads(lines[-1][len("RESULT "):])
    data["_home"] = str(home)
    data["_video"] = str(media / "movie.mp4")
    return data


def test_no_step_raised(result):
    assert not result.get("errors"), result.get("errors")


def test_playback_advances(result):
    assert result["pos_after_open"] is not None and result["pos_after_open"] > 0.3


def test_local_subtitle_autoloaded(result):
    assert result["external_sub"] is True


def test_speed_label_is_not_doubled(result):
    # Regresi bug "1.00xx" di UI sungguhan, bukan hanya di helper.
    assert result["label_1x"] == "1x"
    assert result["label_1_5x"] == "1.5x"


def test_mpris_controls(result):
    if not result["mpris_published"]:
        pytest.skip("D-Bus session bus tidak tersedia di lingkungan ini")
    assert result["mpris_identity"] == "INAA"
    assert result["mpris_status_after_pause"] == "Paused"
    assert result["mpris_status_after_play"] == "Playing"


def test_screenshot_written(result):
    assert result["pictures"], "tidak ada PNG di ~/Pictures/INAA"


def test_detach_keeps_playback_alive(result):
    # Regresi: dulu reparenting GLArea mematikan mpv (path/pos jadi None) atau segfault.
    assert result["pos_before_detach"] is not None
    assert result["pos_after_detach"] is not None
    assert result["pos_after_attach"] is not None
    assert result["pos_after_attach"] >= result["pos_before_detach"]
    assert result["path_after_attach"] == result["_video"]


def test_invalid_media_is_rejected_without_killing_playback(result):
    assert result["path_unchanged_after_bad_open"] is True


def test_resume_position_saved(result):
    saved = result["recent_saved"]
    assert saved, "file tidak tercatat di recent_files"
    assert saved[0]["position"] >= 5
