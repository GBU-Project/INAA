"""Smoke app untuk mpv_user dengan mpv sungguhan. Argumen: <folder-video> <nama-video>. Mencetak `RESULT {json}`."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

video = str(Path(sys.argv[1]) / sys.argv[2])
home = Path.home()
R = {}
app = Gtk.Application(application_id="com.example.inaa.smoke.userconf")


def safe(label, fn):
    try:
        R[label] = fn()
    except Exception as exc:
        R.setdefault("errors", []).append(f"{label}: {exc!r}")


def on_activate(app):
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    GLib.timeout_add(300, lambda: (win.open_file(video), False)[1])

    def collect_1():
        p = win.player
        safe("deband", lambda: p["deband"])
        safe("sub_font_size", lambda: p["sub-font-size"])
        safe("osc", lambda: p["osc"])
        safe("ipc_server", lambda: p["input-ipc-server"])
        safe("ytdl", lambda: p["ytdl"])
        safe("pos_1", lambda: p.time_pos)
        rep = win._mpv_user_report
        R["applied"] = [k for k, _ in rep.applied]
        R["rejected"] = [src for src, _ in rep.rejected]
        R["scripts_loaded"] = [Path(x).name for x in rep.scripts]
        R["good_marker"] = (home / "good_ran.txt").exists()
        R["evil_marker"] = (home / "evil_ran.txt").exists()
        return False

    def collect_2():
        safe("pos_2", lambda: win.player.time_pos)
        R["path_2"] = win.player.path
        app.quit()
        return False

    def watchdog():
        R.setdefault("errors", []).append("watchdog")
        app.quit()
        return False

    GLib.timeout_add(3500, collect_1)
    GLib.timeout_add(4800, collect_2)
    GLib.timeout_add(30000, watchdog)


app.connect("activate", on_activate)
app.run([])
print("RESULT " + json.dumps(R, default=str), flush=True)
