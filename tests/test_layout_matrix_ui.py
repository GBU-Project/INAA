"""Matriks QA Phase 2.5: palet x mode OSC x mode header, diterapkan langsung.

Butuh xvfb-run + GTK4 + python-mpv. Setiap kombinasi diterapkan lewat objek yang
sama seperti saat pengguna mengubah Preferences, lalu keadaan widget diperiksa.
stderr seluruh proses juga dipastikan bebas "Theme parser error".
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
import itertools
import json
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

app = Gtk.Application(application_id="com.example.inaa.matrix")


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    rows = []

    palettes = [("iina-glass", "dark"), ("graphite", "dark"), ("light", "light")]
    for (palette, mode), osc_mode, header_mode in itertools.product(
        palettes, ("floating", "docked", "off"), ("full", "auto-hide", "hidden")
    ):
        layout = win._config["layout"]
        layout["osc"]["mode"] = osc_mode
        layout["headerbar"] = header_mode
        layout["theme"]["mode"] = mode
        layout["theme"]["palette"] = palette
        win.osc.apply()
        win.header_ctrl.apply()
        win.theme_manager.apply()
        win._reveal_chrome()  # seperti kursor bergerak: OSC floating muncul kembali

        state = win.osc.state
        parent = win.osd_box.get_parent()
        if parent is win.video_overlay:
            where = "overlay"
        elif parent is win.osc_slot_top:
            where = "top"
        elif parent is win.osc_slot_bottom:
            where = "bottom"
        else:
            where = "none"

        if header_mode == "hidden":
            titlebar = "dragbar"
        elif win.get_titlebar() is win.header:
            titlebar = "header"
        else:
            titlebar = "other"

        rows.append({
            "palette": palette,
            "osc": osc_mode,
            "header": header_mode,
            "osc_state": state["mode"],
            "where": where,
            "osd_visible": win.osd_box.get_visible(),
            "header_mode": win.header_ctrl.mode(),
            "titlebar": titlebar,
            "theme": win.theme_manager._signature[0],
        })

    print("RESULT " + json.dumps(rows))
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


def test_palette_osc_header_matrix_stays_consistent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "INAA_LAYOUT_V2": "1"})

    log_path = tmp_path / "out.txt"
    with open(log_path, "w") as log:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", SCRIPT],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=120,
        )
    output = log_path.read_text(errors="replace")
    assert proc.returncode == 0, output[-3000:]
    assert "Theme parser error" not in output
    line = next((ln for ln in output.splitlines() if ln.startswith("RESULT ")), None)
    assert line, output[-3000:]
    rows = json.loads(line[len("RESULT "):])

    assert len(rows) == 3 * 3 * 3
    for row in rows:
        assert row["osc_state"] == row["osc"]
        assert row["header_mode"] == row["header"]
        assert row["theme"] == row["palette"]
        if row["osc"] == "off":
            assert row["osd_visible"] is False
        elif row["osc"] == "floating":
            assert row["where"] == "overlay" and row["osd_visible"] is True
        else:
            assert row["where"] in ("top", "bottom")
        expected_titlebar = "dragbar" if row["header"] == "hidden" else "header"
        assert row["titlebar"] == expected_titlebar
