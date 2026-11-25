"""Halaman Layout di Preferences (Phase 2.4): preset, OSC, header, tema. Butuh xvfb-run + GTK4 + mpv."""
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
app = Gtk.Application(application_id="com.example.inaa.prefslayout")


def sel(win, path):
    widget, _kind, ids = win._layout_widgets[path]
    return ids[widget.get_selected()]


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    win.open_preferences()
    cfg = lambda: win._config["layout"]

    result["initial_preset"] = sel(win, ("preset",))

    # Terapkan preset lewat dropdown yang sama dengan UI.
    widget, _k, ids = win._layout_widgets[("preset",)]
    widget.set_selected(ids.index("compact"))
    result["compact_cfg"] = [cfg()["preset"], cfg()["osc"]["mode"], cfg()["osc"]["size"]]
    result["compact_ui"] = [sel(win, ("osc", "mode")), sel(win, ("osc", "size")), sel(win, ("preset",))]
    result["osc_state"] = [win.osc.state["mode"], win.osc.state["slot"]]

    # Ubah satu opsi -> label menjadi custom.
    w, _k, ids = win._layout_widgets[("osc", "size")]
    w.set_selected(ids.index("large"))
    result["after_manual"] = [cfg()["preset"], sel(win, ("preset",))]

    # Tema: ganti aksen -> preset tidak berubah, tema tersimpan.
    w, _k, ids = win._layout_widgets[("theme", "accent")]
    w.set_selected(ids.index("green"))
    result["accent"] = cfg()["theme"]["accent"]

    # Reduce motion lewat switch.
    sw, _k, _i = win._layout_widgets[("reduce_motion",)]
    sw.set_active(True)
    result["reduce_motion"] = [cfg()["reduce_motion"], win.theme_manager.reduce_motion]

    # Header bar: pilihan hidden langsung memasang titlebar transparan.
    w, _k, ids = win._layout_widgets[("headerbar",)]
    w.set_selected(ids.index("hidden"))
    result["hidden_header"] = [
        cfg()["headerbar"], win.header_ctrl.mode(),
        win.get_titlebar() is win.header_ctrl.dragbar, cfg()["preset"],
    ]

    # Reset layout mengembalikan semuanya (preset dan widget).
    win._reset_layout()
    result["reset"] = [cfg()["preset"], sel(win, ("preset",)), sel(win, ("osc", "mode"))]
    result["reset_header"] = [
        cfg()["headerbar"], win.header_ctrl.mode(), win.get_titlebar() is win.header
    ]

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


def test_layout_page_applies_preset_and_stays_in_sync(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "INAA_LAYOUT_V2": "1"})

    log_path = tmp_path / "out.txt"
    with open(log_path, "w") as log:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", SCRIPT],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=90,
        )
    output = log_path.read_text(errors="replace")
    line = next((ln for ln in output.splitlines() if ln.startswith("RESULT ")), None)
    assert line, output[-3000:]
    result = json.loads(line[len("RESULT "):])

    assert result["initial_preset"] == "classic"
    assert result["compact_cfg"] == ["compact", "docked", "compact"]
    assert result["compact_ui"] == ["docked", "compact", "compact"]
    assert result["osc_state"] == ["docked", "bottom"]
    assert result["after_manual"] == ["custom", "custom"]
    assert result["accent"] == "green"
    assert result["reduce_motion"] == [True, True]
    assert result["hidden_header"] == ["hidden", "hidden", True, "custom"]
    assert result["reset"] == ["classic", "classic", "floating"]
    assert result["reset_header"] == ["auto-hide", "auto-hide", True]
