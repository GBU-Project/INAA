"""Dijalankan oleh test_smoke.py di proses terpisah (HOME sudah diisolasi ke folder sementara).

Argumen: <folder-video> <nama-video> ; mencetak satu baris `RESULT {json}` di akhir.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

video_dir = Path(sys.argv[1])
video = str(video_dir / sys.argv[2])
missing = str(video_dir / "tidak_ada_file_ini.mp4")

R = {}
app = Gtk.Application(application_id="com.example.inaa.smoke")


def step(delay_ms, fn):
    def run():
        try:
            fn()
        except Exception as exc:  # satu langkah gagal jangan menghentikan sisanya
            R.setdefault("errors", []).append(f"{fn.__name__}: {exc!r}")
        return False

    GLib.timeout_add(delay_ms, run)


def on_activate(app):
    from player_window import PlayerWindow

    win = PlayerWindow(application=app)
    win.present()
    R["mpris_published"] = bool(win.mpris.is_published)

    def open_video():
        state["t_open"] = time.time()
        win.open_file(video)

    def poll_playing():
        # Tunggu pemutaran mulai dan subtitle eksternal termuat (maks 15 detik): di Xvfb/render
        # software lebih lambat dari GPU asli, jadi waktu tetap 2 detik terlalu pendek.
        if "t_open" not in state:
            return True  # file belum dibuka
        try:
            pos = win.player.time_pos
            subs = [t for t in win.player.track_list if t.get("type") == "sub"]
            ext = any(t.get("external") for t in subs)
            # pos harus sudah maju melewati ambang yang diuji (> 0.3 di test_smoke), bukan sekadar
            # tidak None: pemutaran yang baru mulai selalu menunjukkan 0.1-0.2 detik.
            if (pos is None or pos <= 0.6 or not ext) and time.time() - state["t_open"] < 15:
                return True
            R["pos_after_open"] = pos
            R["external_sub"] = ext
        except Exception as exc:
            R.setdefault("errors", []).append(f"poll_playing: {exc!r}")
        return False

    def check_speed_label():
        win._set_speed(1.0)
        R["label_1x"] = win.playback_opts_btn.get_label()
        win._set_speed(1.5)
        R["label_1_5x"] = win.playback_opts_btn.get_label()
        win._set_speed(1.0)

    MPRIS_CLIENT = """
import json, time
from pydbus import SessionBus
proxy = SessionBus().get("org.mpris.MediaPlayer2.inaa", "/org/mpris/MediaPlayer2")
out = {"identity": proxy.Identity}
proxy.Pause(); time.sleep(0.4); out["after_pause"] = proxy.PlaybackStatus
proxy.Play(); time.sleep(0.4); out["after_play"] = proxy.PlaybackStatus
print(json.dumps(out))
"""
    state = {}

    def mpris_start():
        # Klien HARUS di proses lain: layanan MPRIS hidup di main loop proses ini,
        # jadi memanggilnya dari sini akan deadlock.
        if win.mpris.is_published:
            state["t0"] = time.time()
            state["proc"] = subprocess.Popen(
                [sys.executable, "-c", MPRIS_CLIENT], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

    def mpris_collect():
        proc = state.get("proc")
        if proc is None:
            return
        # Jangan memblokir main loop (communicate) saat klien belum selesai: klien butuh
        # main loop ini untuk dijawab, jadi menunggu secara blok = deadlock bila klien lambat
        # (mesin sibuk). Tunggu sambil membiarkan loop berjalan.
        if proc.poll() is None:
            if time.time() - state["t0"] < 25:
                GLib.timeout_add(200, lambda: (step_run(mpris_collect), False)[1])
                return
            proc.kill()
        out, err = proc.communicate(timeout=10)
        data = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        R["mpris_identity"] = data.get("identity")
        R["mpris_status_after_pause"] = data.get("after_pause")
        R["mpris_status_after_play"] = data.get("after_play")
        if proc.returncode != 0:
            R.setdefault("errors", []).append(f"mpris client rc={proc.returncode}: {err[-300:]}")

    def step_run(fn):
        try:
            fn()
        except Exception as exc:
            R.setdefault("errors", []).append(f"{fn.__name__}: {exc!r}")

    def screenshot():
        win.take_screenshot()

    def detach():
        R["pos_before_detach"] = win.player.time_pos
        win.detach_video_window()

    def check_after_detach():
        R["pos_after_detach"] = win.player.time_pos
        win.attach_video_window()

    def check_after_attach():
        R["pos_after_attach"] = win.player.time_pos
        R["path_after_attach"] = win.player.path

    def hostile_open():
        before = win.player.path
        win.open_file(missing)
        R["path_unchanged_after_bad_open"] = win.player.path == before

    def save_resume():
        win.player.seek(8.0, reference="absolute", precision="exact")

    def save_resume2():
        R["pos_before_save"] = win.player.time_pos
        win._update_current_recent_position()
        win._save_config_throttled(force=True)
        recents = win._config.get("recent_files", [])
        R["recent_saved"] = [r for r in recents if r.get("path") == video]

    def finish():
        proc = state.get("proc")
        if proc is not None and proc.poll() is None and "mpris_identity" not in R:
            GLib.timeout_add(300, lambda: (finish(), False)[1])  # tunggu klien MPRIS selesai
            return
        app.quit()

    step(500, open_video)
    GLib.timeout_add(500, poll_playing)
    step(2200, check_speed_label)
    step(2500, mpris_start)
    step(4500, mpris_collect)
    step(4800, screenshot)
    step(5400, detach)
    step(6100, check_after_detach)
    step(6800, check_after_attach)
    step(7000, hostile_open)
    step(7600, save_resume)
    step(8400, save_resume2)
    step(8800, finish)

    def watchdog():
        R.setdefault("errors", []).append("watchdog: dihentikan paksa")
        app.quit()
        return False

    GLib.timeout_add(40000, watchdog)


app.connect("activate", on_activate)
app.run([])

R["pictures"] = sorted(p.name for p in (Path.home() / "Pictures" / "INAA").glob("*.png")) if (Path.home() / "Pictures" / "INAA").exists() else []
print("RESULT " + json.dumps(R, default=str), flush=True)
