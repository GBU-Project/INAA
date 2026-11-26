"""Smoke app untuk mpv_user dengan mpv sungguhan. Argumen: <folder-video> <nama-video>. Mencetak `RESULT {json}`."""
import json
import os
import sys
import time
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

    T0 = time.time()

    def collect_1():
        p = win.player
        # Tunggu pemutaran benar-benar mulai (di Xvfb/render software lebih lambat dari GPU asli).
        if p.time_pos is None and time.time() - T0 < 15:
            return True
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
        T1[0] = time.time()
        GLib.timeout_add(1300, collect_2)
        return False

    T1 = [None]

    def collect_2():
        pos_1, pos_2 = R.get("pos_1"), win.player.time_pos
        # Tunggu sampai posisi benar-benar maju (maks 10 detik sejak collect_1).
        if (pos_1 is None or pos_2 is None or pos_2 <= pos_1) and time.time() - T1[0] < 10:
            return True
        safe("pos_2", lambda: win.player.time_pos)
        R["path_2"] = win.player.path
        app.quit()
        return False

    def watchdog():
        R.setdefault("errors", []).append("watchdog")
        app.quit()
        return False

    GLib.timeout_add(3500, collect_1)
    GLib.timeout_add(40000, watchdog)


app.connect("activate", on_activate)
app.run([])
print("RESULT " + json.dumps(R, default=str), flush=True)
