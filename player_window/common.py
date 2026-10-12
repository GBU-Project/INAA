"""
PlayerWindow (INAA, GTK4 edition): main window that renders mpv video through
the libmpv render API (OpenGL) inside a Gtk.GLArea.

Why this instead of the old `wid` embedding trick:
The previous GTK3 version embedded mpv's video output using an X11 window ID
(`self.player.wid = xid`). That only works under Xorg or XWayland — it does
NOT work on native Wayland compositor sessions.

This version draws frames itself via OpenGL inside a Gtk.GLArea, using mpv's
render API (the same approach mpv's own `--vo=gpu` uses internally, and the
same one apps like Celluloid use). It works natively under both Wayland and
X11 because it never asks mpv to create or embed its own window — it just
asks mpv to render into whatever GL context Gtk.GLArea gives us.

get_proc_address is implemented via libepoxy (the GL function loader GTK
itself is built on). libepoxy automatically resolves functions through EGL
on Wayland or GLX on X11, so we don't need to special-case either backend.
"""
import ctypes
import ctypes.util
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from keybindings import (
    DEFAULT_SHORTCUTS,
    SHORTCUT_LABELS,
    combo_from_event,
    invert_shortcuts,
    merge_shortcuts,
)
from media_uri import (
    is_allowed_media_uri,
    is_http_media_uri,
    is_local_media_file,
    normalize_media_uri,
)
from opensubtitles import download_subtitle, search_subtitles
from fmt import format_speed
from config_sanitize import sanitize_config
from m3u_parser import export_m3u, parse_m3u
from plugin_loader import load_plugins
from playlist_nav import auto_advance_index, cycle_loop_mode, loop_status_mpris, next_playlist_index

# mpv internal parser & shader compiler requires LC_NUMERIC="C"
try:
    _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
    _libc.setlocale(1, b"C")  # 1 = LC_NUMERIC on Linux
except Exception:
    pass
import tempfile
import threading
import urllib
import urllib.parse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GObject, GdkPixbuf, Pango


import mpv

from mpris import MprisPlayer



SEEK_STEP_SECONDS = 5
VOLUME_STEP = 5
SPEED_PRESETS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v",
    ".ts", ".m2ts", ".vob", ".ogv", ".3gp"
}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx", ".lrc"}


def _format_time(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

CONFIG_DIR = Path.home() / ".config" / "inaa"
CONFIG_FILE = CONFIG_DIR / "config.json"
PLUGINS_DIR = CONFIG_DIR / "plugins"
SHADERS_DIR = CONFIG_DIR / "shaders"

_IINA_CSS = b"""
/* INAA macOS Glassmorphism Theme */
.iina-osd-panel {
    background-color: rgba(26, 26, 28, 0.82);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
    padding: 10px 16px 12px 16px;
    margin-bottom: 24px;
    opacity: 1;
    transition: opacity 220ms ease-in-out;
}

.iina-osd-panel.hidden {
    opacity: 0;
}

.iina-osd-panel button {
    border-radius: 8px;
    min-height: 28px;
    min-width: 28px;
    padding: 4px 6px;
    background-color: transparent;
    border: none;
    color: #f0f0f0;
}

.iina-osd-panel button:hover {
    background-color: rgba(255, 255, 255, 0.15);
}

.iina-time-label {
    font-size: 11px;
    font-weight: 600;
    color: #e0e0e0;
    font-feature-settings: "tnum";
}

.iina-inspector {
    background-color: rgba(28, 28, 30, 0.96);
    border-left: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.35);
    min-width: 320px;
}

.iina-sec-title {
    font-weight: bold;
    font-size: 12px;
    color: #a0a0a5;
    margin-top: 10px;
    margin-bottom: 2px;
}

.iina-seg-btn {
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
}

.iina-seg-btn.iina-seg-active {
    background: #007aff;
    color: #ffffff;
    border-color: #007aff;
}

/* ========================================================
   IINA 1.5.0 macOS Preferences / Settings Styling
   ======================================================== */
.iina-prefs-window {
    background-color: #1e1e20;
    color: #f5f5f7;
}

.iina-prefs-sidebar {
    background-color: rgba(30, 30, 32, 0.98);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    min-width: 190px;
    padding: 8px 6px;
}

.iina-prefs-sidebar searchbar,
.iina-prefs-sidebar entry {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #f5f5f7;
    font-size: 12px;
    padding: 4px 8px;
}

.iina-prefs-sidebar entry:focus {
    border-color: #007aff;
}

.iina-prefs-cat-row {
    border-radius: 8px;
    padding: 6px 10px;
    margin: 2px 0;
    font-size: 13px;
    font-weight: 500;
    color: #e2e2e7;
    transition: background-color 140ms ease;
}

.iina-prefs-cat-row:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

.iina-prefs-cat-row:selected {
    background: #007aff;
    color: #ffffff;
    font-weight: 600;
}

.iina-prefs-cat-row:selected image {
    color: #ffffff;
}

.iina-prefs-content {
    background-color: #161618;
    padding: 16px 24px;
}

.iina-prefs-header-title {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 8px;
}

.iina-prefs-section-header {
    font-size: 12px;
    font-weight: 600;
    color: #8e8e93;
    margin-top: 14px;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Card Container (Apple HIG Grouped Card) */
.iina-pref-card {
    background-color: rgba(40, 40, 44, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 12px;
}

.iina-pref-card-row {
    padding: 6px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.iina-pref-card-row:last-child {
    border-bottom: none;
}

.iina-pref-option-box {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1.5px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    margin-top: 5px;
    transition: all 140ms ease;
}

.iina-pref-option-box:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.18);
}

.iina-pref-option-box.active {
    border-color: #007aff;
    background-color: rgba(0, 122, 255, 0.22);
}

.iina-pref-check {
    color: #007aff;
    font-size: 16px;
    margin-left: 8px;
}

/* Welcome Screen (IINA Style) */
.iina-welcome-screen {
    background-color: #121214;
}

.iina-welcome-card {
    background-color: rgba(36, 36, 40, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    transition: all 180ms ease-in-out;
}

.iina-welcome-card:hover {
    background-color: rgba(50, 50, 56, 0.85);
    border-color: rgba(255, 255, 255, 0.22);
}

.iina-action-btn {
    border-radius: 10px;
    font-weight: 600;
    padding: 10px 18px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background-color: rgba(45, 45, 50, 0.8);
    color: #f5f5f7;
}

.iina-action-btn:hover {
    background-color: rgba(70, 70, 78, 0.95);
    border-color: rgba(255, 255, 255, 0.25);
}

.iina-action-btn.primary {
    background: linear-gradient(135deg, #007aff, #0056b3);
    border-color: #3395ff;
    color: #ffffff;
}

.iina-action-btn.primary:hover {
    background: linear-gradient(135deg, #1a88ff, #0066cc);
}

.iina-recent-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.iina-recent-row:hover {
    background-color: rgba(255, 255, 255, 0.08);
}

.iina-recent-title {
    font-size: 13px;
    font-weight: 500;
    color: #f0f0f2;
}

.iina-recent-sub {
    font-size: 11px;
    color: #8e8e93;
}

.iina-history-dialog {
    background-color: #1c1c1e;
    color: #f5f5f7;
}

/* ListBox mengecat latar sendiri (putih di tema terang) padahal teks kita terang:
   buat transparan agar latar kartu/dialog yang gelap yang terlihat. */
.iina-history-dialog list,
.iina-history-dialog row,
.iina-welcome-card list,
.iina-welcome-card row {
    background-color: transparent;
    color: inherit;
}

.iina-history-dialog .dim-label,
.iina-welcome-card .dim-label {
    color: #a1a1a6;
    opacity: 1;
}

.iina-history-row {
    background-color: transparent;
    border-radius: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    transition: background-color 150ms ease;
}

.iina-history-row:hover {
    background-color: rgba(255, 255, 255, 0.09);
}

.iina-eq-band-box {
    padding: 2px 4px;
}

.iina-eq-val-lbl {
    font-size: 10px;
    color: #98989d;
    font-feature-settings: "tnum";
}

.iina-eq-hz-lbl {
    font-size: 10px;
    font-weight: 600;
    color: #d1d1d6;
}

.iina-toast {
    background-color: rgba(20, 20, 22, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 8px 18px;
    color: #f5f5f7;
    font-size: 13px;
    font-weight: 600;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    margin-top: 24px;
}

.iina-thumb-grid-item {
    border-radius: 4px;
    overflow: hidden;
    transition: transform 120ms ease-out;
}

.iina-thumb-grid-item:hover {
    transform: scale(1.08);
    z-index: 1;
}

.iina-thumb-time-label {
    background-color: rgba(0, 0, 0, 0.7);
    color: #fff;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
}

.iina-shader-active {
    color: #4ade80;
    font-weight: 600;
}
"""

def _apply_iina_css():
    try:
        provider = Gtk.CssProvider()
        provider.load_from_data(_IINA_CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
    except Exception:
        pass




def _load_config():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                data.setdefault("volume", 100)
                data.setdefault("width", 1000)
                data.setdefault("height", 620)
                data.setdefault("recent_files", [])
                data.setdefault("enabled_plugins", [])
                data.setdefault("shortcuts", {})
                data.setdefault("use_mpv_conf", False)
                data.setdefault("custom_shaders", [])
                data.setdefault("auto_hide_chrome", True)
                data.setdefault("fit_window", True)
                data.setdefault("resume_playback", True)
                data.setdefault("keep_above_mini", True)
                data.setdefault("osd_hide_ms", 3000)
                data.setdefault("loop_mode", "off")
                data.setdefault("shuffle", False)
                data.setdefault("audio_eq_preset", "flat")
                data.setdefault("audio_eq_gains", [0.0] * 10)
                data.setdefault("audio_special_effect", "none")
                data.setdefault("audio_custom_presets", {})
                data.setdefault("audio_device", "auto")
                sanitize_config(data)
                try:
                    CONFIG_DIR.chmod(0o700)
                    CONFIG_FILE.chmod(0o600)
                except OSError:
                    pass
                return data
    except Exception:
        pass
    return {
        "volume": 100,
        "width": 1000,
        "height": 620,
        "recent_files": [],
        "enabled_plugins": [],
        "shortcuts": {},
        "use_mpv_conf": False,
        "custom_shaders": [],
        "auto_hide_chrome": True,
        "fit_window": True,
        "resume_playback": True,
        "keep_above_mini": True,
        "osd_hide_ms": 3000,
        "loop_mode": "off",
        "shuffle": False,
        "audio_eq_preset": "flat",
        "audio_eq_gains": [0.0] * 10,
        "audio_special_effect": "none",
        "audio_custom_presets": {},
        "audio_device": "auto",
    }


def _save_config(data):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            CONFIG_DIR.chmod(0o700)
        except OSError:
            pass
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        try:
            CONFIG_FILE.chmod(0o600)
        except OSError:
            pass
    except Exception:
        pass


# --------------------------------------------------------------------------
# GL proc address resolution & FBO query.
#
# We load libEGL and libGL/libGLX ourselves (rather than hoping their
# symbols are already visible in the global process namespace — GTK often
# dlopen()s them with RTLD_LOCAL, which hides their symbols from
# ctypes.CDLL(None)). Once loaded, eglGetProcAddress / glXGetProcAddress
# resolve the actual GL entry points, working on both Wayland-native (EGL)
# and X11 (EGL or GLX) sessions.
# --------------------------------------------------------------------------
def _load(*names):
    for name in names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    return None


_libegl = _load("libEGL.so.1", "libEGL.so")
_libglx = _load("libGLX.so.0", "libGL.so.1", "libGL.so")
_libgl = _load("libGL.so.1", "libGL.so")


def _resolve(lib, name):
    if lib is None:
        return None
    try:
        func = getattr(lib, name)
        func.restype = ctypes.c_void_p
        func.argtypes = [ctypes.c_char_p]
        return func
    except AttributeError:
        return None


_egl_get_proc_address = _resolve(_libegl, "eglGetProcAddress")
_glx_get_proc_address = _resolve(_libglx, "glXGetProcAddress") or _resolve(_libglx, "glXGetProcAddressARB")

# Function to get currently bound framebuffer (GTK4 GLArea uses an internal FBO)
_gl_get_integerv = None
if _libgl and hasattr(_libgl, "glGetIntegerv"):
    _gl_get_integerv = _libgl.glGetIntegerv
    _gl_get_integerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
GL_DRAW_FRAMEBUFFER_BINDING = 0x8CA6


def _get_proc_address(_ctx, name):
    # Prefer EGL when present (Wayland-native and most modern X11/Mesa
    # setups); fall back to GLX for older X11-only stacks.
    if _egl_get_proc_address is not None:
        addr = _egl_get_proc_address(name)
        if addr:
            return addr
    if _glx_get_proc_address is not None:
        addr = _glx_get_proc_address(name)
        if addr:
            return addr
    return 0


_get_proc_address_wrapper = mpv.MpvGlGetProcAddressFn(_get_proc_address)


def _display_name(path_or_url):
    if path_or_url.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(path_or_url)
        label = parsed.netloc
        # Untuk youtu.be shortlink (misal https://youtu.be/C-BnRZ52jHs?si=...)
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/").split("/")[0]
            if video_id:
                return f"youtu.be · {video_id}"
        # Untuk youtube.com watch link
        elif "v=" in (parsed.query or ""):
            for part in parsed.query.split("&"):
                if part.startswith("v="):
                    label += f" · {part[2:]}"
                    break
        return label or path_or_url
    return os.path.basename(path_or_url)



# Re-export everything defined above (including underscore-prefixed helpers
# and constants) so sibling mixin modules can simply do
# `from .common import *` without maintaining an explicit import list here.
__all__ = [_name for _name in dir() if not _name.startswith("__")]
