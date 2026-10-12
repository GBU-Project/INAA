"""GUI + mpv sungguhan: pilih perangkat audio hanya dari daftar mpv, fallback ke auto, kelas CSS riwayat, EQ satu graf."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent / "_smoke_v5_app.py"


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
    cfg.mkdir(parents=True)
    video = media / "movie.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=20:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-c:v", "libx264", "-g", "10",
         "-c:a", "aac", "-shortest", str(video)], check=True)
    (cfg / "config.json").write_text(json.dumps({"audio_device": "usb/sudah-dicabut"}))
    env = dict(os.environ, HOME=str(home), LIBGL_ALWAYS_SOFTWARE="1", GTK_A11Y="none")
    proc = subprocess.run(["xvfb-run", "-a", sys.executable, str(APP), str(video)],
                          env=env, capture_output=True, text=True, timeout=70)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")]
    assert lines, f"tidak ada RESULT.\nstdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}"
    data = json.loads(lines[-1][len("RESULT "):])
    data["_cfg_file"] = str(cfg / "config.json")
    return data


def test_no_errors(run):
    assert not run.get("errors"), run.get("errors")


def test_missing_saved_device_falls_back_to_auto_without_overwriting_config(run):
    assert run["start_device"] == "auto"
    assert run["start_cfg"] == "usb/sudah-dicabut"


def test_dropdown_lists_mpv_devices_and_auto_first(run):
    assert run["names"][0] == "auto" and len(run["names"]) >= 2
    assert run["dropdown_items"] == len(run["names"])


def test_bogus_device_is_rejected_and_real_one_is_applied(run):
    assert run["bogus_ok"] is False and run["after_bogus"] == "auto"
    assert run["after_pick"] == run["picked"] and run["cfg_after_pick"] == run["picked"]
    saved = json.loads(Path(run["_cfg_file"]).read_text())
    assert saved["audio_device"] == run["picked"]


def test_history_dialog_window_carries_dark_style_class(run):
    assert run["dialog_css"] is True


def test_equalizer_is_one_lavfi_graph_in_real_mpv(run):
    assert run["af"] == ["lavfi"]
