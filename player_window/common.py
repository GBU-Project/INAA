"""
Bootstrap bersama PlayerWindow (INAA, GTK4 edition).

Modul ini HANYA berisi:
- persyaratan versi & impor gi (GTK4, GdkPixbuf, Pango) + libmpv;
- path konfigurasi dan load/save config;
- resolusi alamat proc OpenGL untuk render API libmpv.

Logika domain tinggal di dekat pemakainya:
- shortcut          -> keybindings.py
- navigasi playlist -> playlist_nav.py
- konstanta media   -> player_window/media_types.py
- tema CSS          -> player_window/theme.py
- format waktu/nama -> fmt.py
"""
import ctypes
import ctypes.util
import json
from pathlib import Path

from config_sanitize import sanitize_config

# mpv internal parser & shader compiler requires LC_NUMERIC="C"
try:
    _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
    _libc.setlocale(1, b"C")  # 1 = LC_NUMERIC on Linux
except Exception:
    pass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio, GObject, GdkPixbuf, Pango

import mpv

CONFIG_DIR = Path.home() / ".config" / "inaa"
CONFIG_FILE = CONFIG_DIR / "config.json"
PLUGINS_DIR = CONFIG_DIR / "plugins"
SHADERS_DIR = CONFIG_DIR / "shaders"

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


__all__ = [
    # bootstrap GTK/libmpv
    "Gtk", "Gdk", "GLib", "Gio", "GObject", "GdkPixbuf", "Pango",
    "mpv", "ctypes",
    # config
    "CONFIG_DIR", "CONFIG_FILE", "PLUGINS_DIR", "SHADERS_DIR",
    "_load_config", "_save_config",
    # GL render bootstrap
    "GL_DRAW_FRAMEBUFFER_BINDING",
    "_get_proc_address",
    "_get_proc_address_wrapper",
    "_gl_get_integerv",
]
