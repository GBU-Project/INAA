"""Smoke GUI v5: perangkat audio, preamp EQ di mpv, tampilan riwayat. Mencetak `RESULT {json}`."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib  # noqa: E402

video = sys.argv[1]
R = {}
app = Gtk.Application(application_id="com.example.inaa.smoke.v5")


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
    win = PlayerWindow(application=app)
    win.present()
    # config awal berisi perangkat yang tidak ada -> start harus jatuh ke 'auto' tanpa menimpa config
    R["start_device"] = win.player["audio-device"]
    R["start_cfg"] = win._config.get("audio_device")

    def devices():
        R["names"] = list(win._audio_device_names)
        R["dropdown_items"] = win._audio_device_model.get_n_items()
        R["bogus_ok"] = win._set_audio_device("tidak/ada/perangkat")
        R["after_bogus"] = win.player["audio-device"]
        other = [n for n in win._audio_device_names if n != "auto"][0]
        win.audio_device_dropdown.set_selected(win._audio_device_names.index(other))
        R["picked"] = other
        R["after_pick"] = win.player["audio-device"]
        R["cfg_after_pick"] = win._config.get("audio_device")

    def history():
        win.open_history_dialog(None)
        dlg = [t for t in Gtk.Window.list_toplevels() if t is not win and t.get_title() == "Riwayat Pemutaran"][0]
        R["dialog_css"] = dlg.has_css_class("iina-history-dialog")

    def eq():
        win._set_audio_eq_preset("rock")
        R["af"] = [x.get("name") for x in win.player["af"]]
        R["af_str"] = win.player["af"][0].get("params", {}) if win.player["af"] else None

    def fin():
        print("RESULT " + json.dumps(R, default=str), flush=True)
        app.quit()

    GLib.timeout_add(300, lambda: (win.open_file(video), False)[1])
    step(2500, devices)
    step(3200, history)
    step(3800, eq)
    step(4800, fin)
    GLib.timeout_add(25000, lambda: (R.setdefault("errors", []).append("watchdog"), app.quit(), False)[2])


app.connect("activate", on_activate)
app.run([])
