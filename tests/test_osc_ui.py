"""Tes integrasi OSC (Phase 2.2): butuh xvfb-run + GTK4 + python-mpv.

Logika keputusan diuji di test_chrome_logic.py; di sini dipastikan osd_box benar-benar
berpindah antara overlay dan slot, dan gl_area TIDAK berpindah parent.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import json
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

result = {}
app = Gtk.Application(application_id="com.example.inaa.oscui")


def where(win):
    parent = win.osd_box.get_parent()
    if parent is win.video_overlay:
        return "overlay"
    if parent is win.osc_slot_top:
        return "top"
    if parent is win.osc_slot_bottom:
        return "bottom"
    return "none"


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    gl_parent = win.gl_area.get_parent()
    result["initial"] = where(win)

    def set_osc(**kw):
        win._config["layout"]["osc"].update(kw)
        win.osc.apply()

    set_osc(mode="docked", position="bottom")
    result["docked_bottom"] = [where(win), win.osc_slot_bottom.get_visible(), win.osc_slot_top.get_visible()]
    set_osc(position="top")
    result["docked_top"] = [where(win), win.osc_slot_top.get_visible(), win.osc_slot_bottom.get_visible()]
    set_osc(mode="off")
    result["off"] = [where(win), win.osd_box.get_visible()]
    win._reveal_chrome()
    result["off_after_reveal"] = win.osd_box.get_visible()
    set_osc(mode="floating")
    result["floating"] = where(win)

    set_osc(mode="docked", position="bottom")
    win.osc.set_mini(True)
    result["mini"] = [where(win), win.osd_box.get_visible()]
    win.osc.set_mini(False)
    result["after_mini"] = where(win)

    result["gl_area_parent_same"] = win.gl_area.get_parent() is gl_parent
    print("RESULT " + json.dumps(result))
    app.quit()


app.connect("activate", on_activate)
app.run([])
"""


def _can_import_gui():
    probe = (
        "import gi; gi.require_version('Gtk','4.0'); "
        "from gi.repository import Gtk; import mpv"
    )
    return subprocess.run([sys.executable, "-c", probe], capture_output=True).returncode == 0


pytestmark = [
    pytest.mark.skipif(shutil.which("xvfb-run") is None, reason="xvfb-run tidak ada"),
    pytest.mark.skipif(not _can_import_gui(), reason="PyGObject/GTK4/python-mpv tidak tersedia"),
]


def test_osc_moves_between_overlay_and_slots(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "INAA_LAYOUT_V2": "1"})

    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, "-c", SCRIPT],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=90,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(line[len("RESULT "):])

    assert result["initial"] == "overlay"
    assert result["docked_bottom"] == ["bottom", True, False]
    assert result["docked_top"] == ["top", True, False]
    assert result["off"][1] is False
    assert result["off_after_reveal"] is False
    assert result["floating"] == "overlay"
    assert result["mini"] == ["overlay", True]
    assert result["after_mini"] == "bottom"
    assert result["gl_area_parent_same"] is True
