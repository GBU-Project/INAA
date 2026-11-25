"""Tes integrasi header bar (Phase 2.3): mode full/auto-hide/hidden + menu klik kanan.

Butuh xvfb-run + GTK4 + python-mpv. Keputusan murni diuji di test_chrome_logic.py.
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
app = Gtk.Application(application_id="com.example.inaa.headerui")


def labels(widget, out):
    if isinstance(widget, Gtk.Label):
        out.append(widget.get_text())
    child = widget.get_first_child()
    while child:
        labels(child, out)
        child = child.get_next_sibling()


def on_activate(app):
    sys.path.insert(0, ".")
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    hc = win.header_ctrl

    def set_header(mode):
        win._config["layout"]["headerbar"] = mode
        hc.apply()

    result["default"] = [hc.mode(), win.get_titlebar() is win.header, win.header.get_visible()]

    set_header("full")
    result["full"] = [hc.mode(), win.get_titlebar() is win.header, win.header.get_visible()]

    set_header("hidden")
    result["hidden"] = [
        hc.mode(),
        win.get_titlebar() is hc.dragbar,
        win.header.get_visible(),
        isinstance(hc.dragbar.get_first_child(), Gtk.WindowHandle),
        hc.dragbar.get_last_child().__gtype__.name,
        hc.chrome_height(),
    ]
    win._reveal_chrome()
    result["hidden_after_reveal"] = win.header.get_visible()

    set_header("auto-hide")
    result["back_autohide"] = [hc.mode(), win.get_titlebar() is win.header, win.header.get_visible()]

    win._rebuild_video_context_menu()
    out = []
    labels(win.video_context_popover.get_child(), out)
    result["menu_labels"] = out

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


def test_header_modes_and_context_menu_cover_header_actions(tmp_path):
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

    assert result["default"] == ["auto-hide", True, True]
    assert result["full"] == ["full", True, True]

    mode, is_dragbar, header_visible, has_handle, last_type, height = result["hidden"]
    assert mode == "hidden"
    assert is_dragbar is True and header_visible is False
    assert has_handle is True and last_type == "GtkWindowControls"
    assert height > 0
    # Mode hidden: reveal tidak boleh memunculkan header lagi.
    assert result["hidden_after_reveal"] is False

    assert result["back_autohide"] == ["auto-hide", True, True]

    labels = set(result["menu_labels"])
    # Label playlist mengikuti status dock saat menu dibangun.
    assert {"Tampilkan Playlist", "Sembunyikan Playlist"} & labels
    for expected in (
        "Buka File...",
        "Buka dari URL...",
        "Bab / Chapters",
        "Music Mode",
        "Filter Video & Equalizer",
        "Audio & Subtitle",
        "Kecepatan & A-B Loop",
        "Sunting Pintasan Keyboard (Ctrl+,)",
        "Pengaturan (Ctrl+P)",
    ):
        assert expected in labels, f"{expected!r} tidak ada di menu klik kanan"
