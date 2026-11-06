"""Tes integrasi controller dock GTK (butuh xvfb-run + GTK4 + python-mpv).

Logika urutan murni diuji di test_layout_config.py; tes ini memastikan
Gtk.Paned benar-benar dibangun ulang saat sisi dock berubah dan widget
disembunyikan/ditampilkan sesuai state.
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
app = Gtk.Application(application_id="com.example.inaa.layoutui")


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    dock = win.dock_layout

    result["enabled"] = bool(dock._enabled)
    result["initial_sides"] = [list(part) for part in dock._signature]
    result["initial_visible"] = [win.sidebar.get_visible(), win.inspector_panel.get_visible()]

    dock.set_dock_visible("inspector", True)
    result["inspector_on"] = [list(part) for part in dock._signature]

    dock.set_edge("playlist", "right")
    result["both_right"] = [list(part) for part in dock._signature]

    dock.set_edge("inspector", "hidden")
    result["inspector_hidden"] = [list(part) for part in dock._signature]
    result["inspector_visible_after_hidden"] = win.inspector_panel.get_visible()

    dock.set_suppressed(True)
    result["suppressed"] = [win.sidebar.get_visible(), win.inspector_panel.get_visible()]
    dock.set_suppressed(False)
    result["restored"] = [win.sidebar.get_visible(), win.inspector_panel.get_visible()]

    dock.set_width("playlist", 333)
    result["width"] = win._config["layout"]["playlist"]["width"]

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
    return subprocess.run(
        [sys.executable, "-c", probe], capture_output=True
    ).returncode == 0


pytestmark = [
    pytest.mark.skipif(shutil.which("xvfb-run") is None, reason="xvfb-run tidak ada"),
    pytest.mark.skipif(
        not _can_import_gui(),
        reason="PyGObject/GTK4/python-mpv tidak tersedia untuk interpreter ini",
    ),
]


def test_dock_layout_rebuilds_and_persists_edges(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "INAA_LAYOUT_V2": "1"})

    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, "-c", SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None
    )
    assert line, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(line[len("RESULT "):])

    assert result["enabled"] is True
    assert result["initial_sides"] == [["playlist"], []]
    assert result["initial_visible"] == [True, False]
    assert result["inspector_on"] == [["playlist"], ["inspector"]]
    assert result["both_right"] == [[], ["inspector", "playlist"]]
    assert result["inspector_hidden"] == [[], ["playlist"]]
    assert result["inspector_visible_after_hidden"] is False
    assert result["suppressed"] == [False, False]
    assert result["restored"] == [True, False]
    assert result["width"] == 333


LEGACY_SCRIPT = r"""
import json
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

result = {}
app = Gtk.Application(application_id="com.example.inaa.layoutlegacy")


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    dock = win.dock_layout
    result["enabled"] = bool(dock._enabled)
    result["initial_sides"] = [list(part) for part in dock._signature]
    result["initial_visible"] = [win.sidebar.get_visible(), win.inspector_panel.get_visible()]

    win.playlist_toggle.set_active(True)
    result["toggle_sides"] = [list(part) for part in dock._signature]
    result["sidebar_parented"] = win.sidebar.get_parent() is not None
    result["sidebar_visible"] = win.sidebar.get_visible()

    win.playlist_toggle.set_active(False)
    result["off_parented"] = win.sidebar.get_parent() is not None
    result["off_visible"] = win.sidebar.get_visible()
    result["root"] = type(dock.root).__name__

    print("RESULT " + json.dumps(result))
    app.quit()


app.connect("activate", on_activate)
app.run([])
"""


def test_legacy_mode_toggle_actually_attaches_the_pane(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.pop("INAA_LAYOUT_V2", None)
    env.update({"HOME": str(home)})

    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, "-c", LEGACY_SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None
    )
    assert line, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(line[len("RESULT "):])

    assert result["enabled"] is False
    assert result["initial_sides"] == [[], []]
    assert result["initial_visible"] == [False, False]
    assert result["toggle_sides"] == [["playlist"], []]
    assert result["sidebar_parented"] is True
    assert result["sidebar_visible"] is True
    assert result["off_parented"] is False
    assert result["off_visible"] is False
