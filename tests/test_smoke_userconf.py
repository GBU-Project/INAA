"""Smoke test mpv_user dengan mpv + GTK sungguhan: opsi aman terpasang, opsi berbahaya tidak, script terkendali."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent / "_smoke_userconf_app.py"


def _can_import_gui():
    probe = "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; import mpv"
    return subprocess.run([sys.executable, "-c", probe], capture_output=True).returncode == 0


pytestmark = [
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg tidak ada"),
    pytest.mark.skipif(shutil.which("xvfb-run") is None, reason="xvfb-run tidak ada"),
    pytest.mark.skipif(not _can_import_gui(), reason="PyGObject/GTK4/python-mpv tidak tersedia"),
]

MARKER_LUA = 'local f = io.open(os.getenv("HOME") .. "/{name}", "w"); f:write("ran"); f:close()\n'


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    media = tmp_path_factory.mktemp("media")
    home = tmp_path_factory.mktemp("home")
    cfg_dir = home / ".config" / "inaa"
    cfg_dir.mkdir(parents=True)
    mpv_dir = home / ".config" / "mpv"
    mpv_dir.mkdir(parents=True)
    scripts = home / "scripts"
    scripts.mkdir()

    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=20:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=20", "-c:v", "libx264", "-g", "10",
         "-c:a", "aac", "-shortest", str(media / "movie.mp4")],
        check=True,
    )

    (scripts / "good.lua").write_text(MARKER_LUA.format(name="good_ran.txt"))
    (scripts / "evil.lua").write_text(MARKER_LUA.format(name="evil_ran.txt"))
    (mpv_dir / "mpv.conf").write_text(
        "\n".join(
            [
                "deband=yes",
                "sub-font-size=47",
                "ytdl=yes",
                "osc=yes",                                   # dipaksa INAA: harus tetap no
                f"script={scripts / 'evil.lua'}",            # tidak boleh dimuat lewat mpv.conf
                f"input-ipc-server={home / 'ipc.sock'}",     # tidak boleh membuka socket
                "vo=null",                                   # tidak boleh mengganti renderer
            ]
        )
        + "\n"
    )
    (cfg_dir / "config.json").write_text(
        json.dumps(
            {
                "mpv_conf": str(mpv_dir / "mpv.conf"),
                                "mpv_scripts": [str(scripts / "good.lua"), "relative.lua"],
            }
        )
    )

    env = dict(os.environ, HOME=str(home), LIBGL_ALWAYS_SOFTWARE="1", GTK_A11Y="none")
    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, str(APP), str(media), "movie.mp4"],
        env=env, capture_output=True, text=True, timeout=70,
    )
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")]
    assert lines, f"tidak ada RESULT.\nstdout:\n{proc.stdout[-1200:]}\nstderr:\n{proc.stderr[-1200:]}"
    data = json.loads(lines[-1][len("RESULT "):])
    data["_stderr"] = proc.stderr
    data["_home"] = str(home)
    return data


def test_app_ran_cleanly(run):
    assert not run.get("errors"), run.get("errors")


def test_safe_conf_options_reach_real_mpv(run):
    assert run["deband"] is True
    assert float(run["sub_font_size"]) == 47.0
    assert set(run["applied"]) == {"deband", "sub-font-size"}


def test_forced_options_win_over_conf(run):
    assert run["osc"] is False                       # osc=yes di mpv.conf diabaikan
    assert run["ipc_server"] in ("", None)           # tidak ada socket IPC
    assert not (Path(run["_home"]) / "ipc.sock").exists()
    # playback tetap lewat render API (vo=null dari conf akan membuat video berhenti/tak tampil)
    assert run["pos_2"] is not None and run["pos_2"] > run["pos_1"]


def test_only_explicit_good_script_ran(run):
    assert run["good_marker"] is True
    assert run["evil_marker"] is False               # script=... di mpv.conf tidak dimuat
    assert run["scripts_loaded"] == ["good.lua"]


def test_ytdl_stays_off(run):
    assert run["ytdl"] is False


def test_rejections_are_reported(run):
    joined = " | ".join(run["rejected"])
    for needle in ("osc", "script", "input-ipc-server", "vo", "ytdl", "relative.lua"):
        assert needle in joined, f"{needle!r} tidak dilaporkan"
