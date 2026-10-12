"""Smoke GUI untuk perbaikan v3. Args: <video>. Mencetak `RESULT {json}`."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

video = sys.argv[1]
R = {}
app = Gtk.Application(application_id="com.example.inaa.smoke.v3")


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def step(ms, fn):
    def run():
        try:
            fn()
        except Exception as exc:
            R.setdefault("errors", []).append(f"{fn.__name__}: {exc!r}")
        return False
    GLib.timeout_add(ms, run)


def on_activate(app):
    from player_window import PlayerWindow
    win = PlayerWindow(application=app)  # config sengaja berisi nilai rusak: tidak boleh crash
    win.present()
    R["constructed"] = True
    calls = []
    real_open = win.open_file
    win.open_file = lambda *a, **k: calls.append((a, k))

    def loop_buttons():
        win._prefs_audio_page()
        win._set_loop_mode("one")
        R["loop_active"] = [m for m, b in win._prefs_loop_buttons.items() if b.has_css_class("iina-seg-active")]
        win._set_loop_mode("off")
        R["loop_active_after"] = [m for m, b in win._prefs_loop_buttons.items() if b.has_css_class("iina-seg-active")]

    def history():
        win.open_history_dialog(None)
        dlg = [t for t in Gtk.Window.list_toplevels() if t is not win and t.get_title() == "Riwayat Pemutaran"][0]
        btns = [w for w in walk(dlg) if isinstance(w, Gtk.Button) and w.get_tooltip_text() in ("Putar dan lanjutkan", "File tidak ditemukan")]
        R["history_buttons"] = [(b.get_tooltip_text(), b.get_sensitive()) for b in btns]
        playable = [b for b in btns if b.get_sensitive()][0]
        playable.emit("clicked")
        playable.emit("clicked")
        R["open_calls"] = len(calls)

    def shaders():
        R["glsl"] = [Path(x).name for x in win.player["glsl-shaders"]]

    def conf():
        R["deband_before"] = win.player["deband"]
        win._on_use_mpv_conf_changed(True)
        R["deband_after"] = win.player["deband"]
        R["osc"] = win.player["osc"]
        R["ipc"] = win.player["input-ipc-server"]

    def presets():
        R["save_flat"] = win._save_custom_eq_preset("Flat")
        R["save_rock"] = win._save_custom_eq_preset("rock")
        R["save_ok"] = win._save_custom_eq_preset("Punyaku")
        R["custom_names"] = sorted(win._config.get("audio_custom_presets", {}))

    def af_mixed():
        win._set_audio_eq_preset("bass_boost")
        win._set_audio_special_effect("nightmode")
        R["af"] = [x.get("name") for x in win.player["af"]]

    def fin():
        print("RESULT " + json.dumps(R, default=str), flush=True)
        app.quit()

    step(500, loop_buttons)
    step(1200, history)
    step(1800, shaders)
    step(2200, conf)
    step(2600, presets)
    step(3000, lambda: win.open_file.__call__ and None)
    GLib.timeout_add(3200, lambda: (setattr(win, "open_file", real_open), win.open_file(video), False)[1])
    step(6500, af_mixed)
    step(7500, fin)
    GLib.timeout_add(25000, lambda: (R.setdefault("errors", []).append("watchdog"), app.quit(), False)[2])


app.connect("activate", on_activate)
app.run([])
