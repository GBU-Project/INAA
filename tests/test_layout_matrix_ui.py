"""Matriks QA Phase 2.5: palet x mode OSC x mode header (+ mini player dan fullscreen).

Satu proses xvfb menjalankan semua kombinasi; tiap kombinasi diperiksa: posisi osd_box,
visibilitas, palet efektif, auto-hide header, perilaku mini player/fullscreen, dan tidak ada
`Theme parser error` / `Gtk-CRITICAL` di stderr.
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

rows = []
app = Gtk.Application(application_id="com.example.inaa.matrix")


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

    combos = itertools.product(
        ("iina-glass", "graphite", "light"),
        ("floating", "docked", "off"),
        ("full", "auto-hide"),
    )
    for palette, mode, header in combos:
        layout = win._config["layout"]
        layout["theme"].update(mode="light" if palette == "light" else "dark", palette=palette)
        layout["osc"].update(mode=mode, position="top" if mode == "docked" else "bottom", size="regular")
        layout["headerbar"] = header
        win._commit_layout(layout)

        row = {"combo": [palette, mode, header], "problems": []}
        slot = "top" if mode == "docked" else None
        expect_where = slot or "overlay"
        if where(win) != expect_where:
            row["problems"].append(f"posisi {where(win)} != {expect_where}")
        if mode == "docked" and not win.osd_box.get_visible():
            row["problems"].append("docked tidak terlihat")
        if mode == "off" and win.osd_box.get_visible():
            row["problems"].append("off masih terlihat")
        if win.theme_manager._signature[0] != palette:
            row["problems"].append(f"palet {win.theme_manager._signature[0]} != {palette}")
        if win.osc.chrome_auto_hide()[1] != (header == "auto-hide"):
            row["problems"].append("flag auto-hide header salah")
        if mode == "docked" and win.osc.chrome_auto_hide()[0]:
            row["problems"].append("OSC docked tidak boleh auto-hide")

        # mini player: OSC selalu floating dan terlihat, lalu kembali seperti semula
        win.osc.set_mini(True)
        if where(win) != "overlay" or not win.osd_box.get_visible():
            row["problems"].append("mini: OSC tidak floating/terlihat")
        win.osc.set_mini(False)
        if where(win) != expect_where:
            row["problems"].append("mini: tidak kembali ke posisi semula")

        # fullscreen: docked menjadi floating, off tetap off, lalu kembali
        win.osc.set_fullscreen(True)
        if mode == "docked" and where(win) != "overlay":
            row["problems"].append("fullscreen: docked harus floating")
        if mode == "off" and win.osd_box.get_visible():
            row["problems"].append("fullscreen: off harus tetap tersembunyi")
        win.osc.set_fullscreen(False)
        if where(win) != expect_where:
            row["problems"].append("fullscreen: tidak kembali ke posisi semula")

        if win.gl_area.get_parent() is not gl_parent:
            row["problems"].append("gl_area berpindah parent")
        rows.append(row)

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


def test_palette_osc_header_matrix(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update({"HOME": str(home), "INAA_LAYOUT_V2": "1"})

    log_path = tmp_path / "out.txt"
    with open(log_path, "w") as log:
        subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", SCRIPT],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, text=True, timeout=120,
        )
    output = log_path.read_text(errors="replace")
    line = next((ln for ln in output.splitlines() if ln.startswith("RESULT ")), None)
    assert line, output[-3000:]
    rows = json.loads(line[len("RESULT "):])

    assert len(rows) == 18  # 3 palet x 3 mode OSC x 2 mode header
    bad = [r for r in rows if r["problems"]]
    assert not bad, json.dumps(bad, indent=1)
    assert "Theme parser error" not in output
    # Bus aksesibilitas (at-spi) memang tidak ada di xvfb: bukan bug aplikasi.
    critical = [
        ln for ln in output.splitlines()
        if "Gtk-CRITICAL" in ln and "accessibility bus" not in ln
    ]
    assert not critical, "\n".join(critical)
