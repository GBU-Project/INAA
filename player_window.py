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
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from media_uri import is_allowed_media_uri, normalize_media_uri
from opensubtitles import download_subtitle, search_subtitles
from plugin_loader import load_plugins

# Pastikan ~/.local/bin ada di PATH agar mpv selalu menemukan versi yt-dlp terbaru
_local_bin = str(Path.home() / ".local" / "bin")
if _local_bin not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = _local_bin + os.pathsep + os.environ.get("PATH", "")

# mpv internal parser & shader compiler requires LC_NUMERIC="C"
try:
    _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
    _libc.setlocale(1, b"C")  # 1 = LC_NUMERIC on Linux
except Exception:
    pass
import tempfile
import threading
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
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx", ".lrc"}

CONFIG_DIR = Path.home() / ".config" / "inaa"
CONFIG_FILE = CONFIG_DIR / "config.json"
PLUGINS_DIR = CONFIG_DIR / "plugins"

_IINA_CSS = b"""
/* INAA macOS Glassmorphism Theme */
.iina-osd-panel {
    background-color: rgba(26, 26, 28, 0.82);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
    padding: 10px 16px 12px 16px;
    margin-bottom: 24px;
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
    background-color: rgba(28, 28, 30, 0.94);
    border-left: 1px solid rgba(255, 255, 255, 0.12);
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
                return data
    except Exception:
        pass
    return {"volume": 100, "width": 1000, "height": 620, "recent_files": [], "enabled_plugins": []}


def _save_config(data):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
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


class MpvGLArea(Gtk.GLArea):
    """A GTK4 widget that plays video by handing mpv an OpenGL surface."""

    __gsignals__ = {
        "mpv-event": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.set_has_depth_buffer(False)
        self.set_has_stencil_buffer(False)
        self.set_required_version(3, 2)
        self.set_auto_render(False)

        # Allow Desktop GL API if available to ensure full compatibility with libmpv shaders
        if hasattr(self, "set_allowed_apis") and hasattr(Gdk, "GLAPI"):
            try:
                self.set_allowed_apis(Gdk.GLAPI.GL)
            except Exception:
                pass

        self.player = mpv.MPV(
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,       # we draw our own controls
            vo="libmpv",     # render via the libmpv render API, not a native window
            hwdec="auto-safe",
            sub_auto="fuzzy",           # otomatis memuat subtitle dari folder yang sama
            audio_file_auto="fuzzy",     # otomatis memuat audio eksternal jika ada
            ytdl=True,       # enable yt-dlp so URLs (YouTube, etc.) can be played directly
            ytdl_format="bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        )
        self.player.volume = 100
        self._render_ctx = None

        self.connect("realize", self._on_realize)
        self.connect("unrealize", self._on_unrealize)
        self.connect("render", self._on_render)

    def _on_realize(self, area):
        self.make_current()
        self._render_ctx = mpv.MpvRenderContext(
            self.player,
            "opengl",
            opengl_init_params={"get_proc_address": _get_proc_address_wrapper},
        )
        self._render_ctx.update_cb = self._on_mpv_update

    def _on_unrealize(self, area):
        # PENTING: JANGAN terminate() player di sini. `unrealize` juga
        # terpicu saat widget ini dipindah ke top-level window lain (mis.
        # fitur "detach video window") — bukan cuma saat aplikasi ditutup.
        # Kalau mpv di-terminate di sini, saat widget di-realize ulang di
        # window baru kita akan mencoba membuat render context di atas
        # instance mpv yang sudah mati -> segfault. Cukup lepas render
        # context saja; instance mpv tetap hidup dan siap dipakai lagi
        # saat widget di-realize ulang (baik di window yang sama maupun
        # window baru). Mematikan mpv sepenuhnya dilakukan secara terpisah
        # lewat shutdown_player(), dipanggil saat window utama benar-benar
        # ditutup.
        if self._render_ctx:
            self._render_ctx.free()
            self._render_ctx = None

    def shutdown_player(self):
        """Matikan instance mpv sepenuhnya. Panggil ini hanya saat aplikasi
        benar-benar ditutup, bukan saat widget cuma dipindah antar window."""
        if self._render_ctx:
            self._render_ctx.free()
            self._render_ctx = None
        try:
            self.player.terminate()
        except Exception:
            pass

    def _on_mpv_update(self):
        # Called from mpv's internal thread; hop back to the GTK main loop.
        GLib.idle_add(self._request_frame)

    def _request_frame(self):
        if self._render_ctx and self._render_ctx.update():
            self.queue_render()
        return False

    def _on_render(self, area, gl_context):
        if not self._render_ctx:
            return False
        scale = self.get_scale_factor()
        width = self.get_width() * scale
        height = self.get_height() * scale

        # GTK4 GLArea renders into its own internal framebuffer object (FBO).
        # We query the currently bound draw framebuffer so mpv renders into the exact target.
        fbo_val = 0
        if _gl_get_integerv:
            current_fbo = ctypes.c_int(0)
            _gl_get_integerv(GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(current_fbo))
            if current_fbo.value > 0:
                fbo_val = current_fbo.value

        self._render_ctx.render(
            flip_y=True,
            opengl_fbo={"w": width, "h": height, "fbo": fbo_val},
        )
        return True


class PlayerWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._config = _load_config()
        initial_w = self._config.get("width", 1000)
        initial_h = self._config.get("height", 620)
        self.set_default_size(initial_w, initial_h)
        self.set_title("INAA")

        self.playlist = []
        self.playlist_index = -1
        self._current_path = None
        self._seekbar_user_dragging = False
        self._is_mini = False
        self._is_music_mode = False
        self._normal_size = (initial_w, initial_h)

        self._ab_state = 0  # 0: None, 1: A set, 2: A & B set
        self._chapters = []
        self._current_chapter = -1
        self._pending_resume_pos = None
        self._drag_start_pos = None
        self._has_played_media = False
        self._last_config_save = 0.0

        # Cache thumbnail seekbar
        self._thumb_cache = {}
        self._thumb_pending = set()
        self._thumb_temp_dir = tempfile.mkdtemp(prefix="inaa_thumb_")

        # Plugin registry
        self._plugins = []

        # State Floating OSD auto-hide
        self._osd_hide_timeout_id = None

        _apply_iina_css()
        self._build_ui()
        self._connect_signals()
        self._setup_drag_and_drop()

        # Terapkan volume dari konfigurasi tersimpan
        saved_vol = self._config.get("volume", 100)
        self.volume_scale.set_value(saved_vol)
        self.player.volume = saved_vol

        # Muat plugin pengguna (IINA-style: Info.json + explicit enable)
        self._load_plugins()

        # Integrasi MPRIS (media control sistem: GNOME/KDE now-playing,
        # tombol media keyboard, lock screen). Gagal dengan lembut kalau
        # session bus tidak tersedia.
        self.mpris = MprisPlayer(self)
        self.mpris.publish()

        GLib.timeout_add(200, self._poll_mpv_state)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self.header = Gtk.HeaderBar()
        self.set_titlebar(self.header)

        open_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        open_btn.set_tooltip_text("Buka file video/audio")
        open_btn.connect("clicked", self.on_open_clicked)
        self.header.pack_start(open_btn)

        open_url_btn = Gtk.Button.new_from_icon_name("insert-link-symbolic")
        open_url_btn.set_tooltip_text("Buka dari URL (YouTube, dll.)")
        open_url_btn.connect("clicked", self.on_open_url_clicked)
        self.header.pack_start(open_url_btn)

        self.playlist_toggle = Gtk.ToggleButton()
        self.playlist_toggle.set_icon_name("view-list-symbolic")
        self.playlist_toggle.set_tooltip_text("Playlist")
        self.playlist_toggle.connect("toggled", self.on_playlist_toggled)
        self.header.pack_start(self.playlist_toggle)

        # Chapter menu button
        self.chapter_menu_btn = Gtk.MenuButton()
        self.chapter_menu_btn.set_icon_name("media-playlist-consecutive-symbolic")
        self.chapter_menu_btn.set_tooltip_text("Bab / Chapters")
        self.chapter_popover = Gtk.Popover()
        self.chapter_popover.connect("show", lambda *_: self._rebuild_chapter_menu())
        self.chapter_menu_btn.set_popover(self.chapter_popover)
        self.header.pack_start(self.chapter_menu_btn)

        # Video & Audio Filters button
        self.filters_btn = Gtk.MenuButton()
        self.filters_btn.set_icon_name("camera-photo-symbolic")
        self.filters_btn.set_tooltip_text("Filter Video & Equalizer Audio")
        self.filters_popover = Gtk.Popover()
        self.filters_popover.connect("show", lambda *_: self._rebuild_filters_menu())
        self.filters_btn.set_popover(self.filters_popover)
        self.header.pack_start(self.filters_btn)

        # Inspector Panel Button (macOS IINA style)
        self.inspector_btn = Gtk.ToggleButton()
        self.inspector_btn.set_icon_name("preferences-other-symbolic")
        self.inspector_btn.set_tooltip_text("Pengaturan / Inspector (i)")
        self.inspector_btn.connect("toggled", self.on_inspector_toggled)
        self.header.pack_end(self.inspector_btn)

        # Audio / Subtitle popover button
        self.track_menu_btn = Gtk.MenuButton()
        self.track_menu_btn.set_icon_name("preferences-desktop-locale-symbolic")
        self.track_menu_btn.set_tooltip_text("Audio & Subtitle Track / Unduh Subtitle")
        self.track_popover = Gtk.Popover()
        self.track_popover.connect("show", lambda *_: self._rebuild_track_menu())
        self.track_menu_btn.set_popover(self.track_popover)
        self.header.pack_end(self.track_menu_btn)

        # Playback Speed & A-B Loop popover button
        self.playback_opts_btn = Gtk.MenuButton()
        self.playback_opts_btn.set_label("1.0x")
        self.playback_opts_btn.set_tooltip_text("Kecepatan Pemutaran & A-B Loop")
        self.playback_opts_popover = Gtk.Popover()
        self.playback_opts_popover.connect("show", lambda *_: self._rebuild_playback_menu())
        self.playback_opts_btn.set_popover(self.playback_opts_popover)
        self.header.pack_end(self.playback_opts_btn)

        # Music Mode Toggle Button
        self.music_toggle_btn = Gtk.ToggleButton()
        self.music_toggle_btn.set_icon_name("audio-x-generic-symbolic")
        self.music_toggle_btn.set_tooltip_text("Music Mode (Tampilan Musik / Album)")
        self.music_toggle_btn.connect("toggled", self.on_music_mode_toggled)
        self.header.pack_end(self.music_toggle_btn)

        self.mini_btn = Gtk.ToggleButton()
        self.mini_btn.set_icon_name("view-restore-symbolic")
        self.mini_btn.set_tooltip_text("Mini Player")
        self.mini_btn.connect("toggled", self.on_mini_toggled)
        self.header.pack_end(self.mini_btn)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.set_child(root)

        # Playlist sidebar (Kiri)
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar.set_size_request(220, -1)
        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.connect("row-activated", self.on_playlist_row_activated)
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_child(self.sidebar_list)
        sidebar_scroll.set_vexpand(True)
        self.sidebar.append(sidebar_scroll)
        self.sidebar.set_visible(False)
        root.append(self.sidebar)

        # Main video area with Overlay for Floating OSD
        self.video_overlay = Gtk.Overlay()
        self.video_overlay.set_hexpand(True)
        self.video_overlay.set_vexpand(True)
        root.append(self.video_overlay)

        # Stack to switch between Video (MpvGLArea) and Music View
        self.display_stack = Gtk.Stack()
        self.display_stack.set_hexpand(True)
        self.display_stack.set_vexpand(True)
        self.display_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Page 1: Video GLArea
        self.gl_area = MpvGLArea()
        self.gl_area.set_hexpand(True)
        self.gl_area.set_vexpand(True)

        # Left click gesture: single click play/pause, double click toggle fullscreen / restore mini player
        click_gesture = Gtk.GestureClick()
        click_gesture.set_button(1)
        click_gesture.connect("released", self._on_video_left_click)
        self.gl_area.add_controller(click_gesture)

        # Right click gesture: show context menu (Mini Player toggle, Fullscreen, Play/Pause)
        right_click_gesture = Gtk.GestureClick()
        right_click_gesture.set_button(3)
        right_click_gesture.connect("pressed", self._on_video_right_click)
        self.gl_area.add_controller(right_click_gesture)

        # Drag gesture to detach video when dragged outward
        video_drag_gesture = Gtk.GestureDrag()
        video_drag_gesture.set_button(1)
        video_drag_gesture.connect("drag-begin", self._on_video_drag_begin)
        video_drag_gesture.connect("drag-end", self._on_video_drag_end)
        self.gl_area.add_controller(video_drag_gesture)

        # Trackpad / Mouse Scroll Gesture (IINA-style: Vertical = Volume, Horizontal = Seeking)
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.HORIZONTAL
        )
        scroll_controller.connect("scroll", self._on_video_scroll)
        self.gl_area.add_controller(scroll_controller)

        # Video context menu popover
        self.video_context_popover = Gtk.Popover()
        self.video_context_popover.set_parent(self.gl_area)
        self.video_context_popover.set_has_arrow(False)

        self.display_stack.add_named(self.gl_area, "video")

        # Page 2: Music View
        self.music_view = self._build_music_view()
        self.display_stack.add_named(self.music_view, "music")

        # Page 3: Welcome Screen (macOS IINA Style)
        self.welcome_view = self._build_welcome_view()
        self.display_stack.add_named(self.welcome_view, "welcome")
        self.display_stack.set_visible_child_name("welcome")

        self.video_overlay.set_child(self.display_stack)

        # ----------------- FLOATING OSD (macOS IINA Style) -----------------
        self.osd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.osd_box.add_css_class("iina-osd-panel")
        self.osd_box.set_valign(Gtk.Align.END)
        self.osd_box.set_halign(Gtk.Align.CENTER)
        self.osd_box.set_size_request(440, -1)
        self.osd_box.set_visible(False)

        # Seekbar row
        seek_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.time_label = Gtk.Label(label="00:00")
        self.time_label.add_css_class("iina-time-label")
        self.seekbar = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self.seekbar.set_draw_value(False)
        self.seekbar.set_hexpand(True)
        self.duration_label = Gtk.Label(label="00:00")
        self.duration_label.add_css_class("iina-time-label")
        seek_row.append(self.time_label)
        seek_row.append(self.seekbar)
        seek_row.append(self.duration_label)
        self.osd_box.append(seek_row)

        # Popover thumbnail preview saat hover seekbar
        self.thumb_popover = Gtk.Popover()
        self.thumb_popover.set_parent(self.seekbar)
        self.thumb_popover.set_position(Gtk.PositionType.TOP)
        self.thumb_popover.set_autohide(False)
        self.thumb_picture = Gtk.Picture()
        self.thumb_picture.set_size_request(160, 90)
        self.thumb_label = Gtk.Label(label="00:00")
        thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        thumb_box.append(self.thumb_picture)
        thumb_box.append(self.thumb_label)
        self.thumb_popover.set_child(thumb_box)

        # Buttons row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Volume section (kiri)
        vol_btn = Gtk.Button.new_from_icon_name("audio-volume-high-symbolic")
        vol_btn.set_has_frame(False)
        vol_btn.set_tooltip_text("Bisu / Suara (m)")
        vol_btn.connect("clicked", self.on_mute_clicked)
        btn_row.append(vol_btn)
        self.vol_btn = vol_btn

        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_size_request(80, -1)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        btn_row.append(self.volume_scale)

        spacer_left = Gtk.Box()
        spacer_left.set_hexpand(True)
        btn_row.append(spacer_left)

        # Playback control (tengah)
        self.prev_btn = Gtk.Button.new_from_icon_name("media-skip-backward-symbolic")
        self.prev_btn.set_tooltip_text("File Sebelumnya")
        self.prev_btn.connect("clicked", lambda *_: self.play_relative(-1))
        btn_row.append(self.prev_btn)

        self.playpause_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.playpause_btn.set_tooltip_text("Putar / Jeda (Spasi)")
        self.playpause_btn.connect("clicked", self.on_playpause_clicked)
        btn_row.append(self.playpause_btn)

        self.next_btn = Gtk.Button.new_from_icon_name("media-skip-forward-symbolic")
        self.next_btn.set_tooltip_text("File Berikutnya")
        self.next_btn.connect("clicked", lambda *_: self.play_relative(1))
        btn_row.append(self.next_btn)

        spacer_right = Gtk.Box()
        spacer_right.set_hexpand(True)
        btn_row.append(spacer_right)

        # Action section (kanan)
        self.ab_label = Gtk.Label(label="")
        self.ab_label.add_css_class("iina-time-label")
        btn_row.append(self.ab_label)

        # Chapter nav
        self.prev_chapter_btn = Gtk.Button.new_from_icon_name("media-seek-backward-symbolic")
        self.prev_chapter_btn.set_tooltip_text("Bab Sebelumnya (PgUp)")
        self.prev_chapter_btn.connect("clicked", lambda *_: self.navigate_chapter(-1))
        btn_row.append(self.prev_chapter_btn)

        self.next_chapter_btn = Gtk.Button.new_from_icon_name("media-seek-forward-symbolic")
        self.next_chapter_btn.set_tooltip_text("Bab Berikutnya (PgDn)")
        self.next_chapter_btn.connect("clicked", lambda *_: self.navigate_chapter(1))
        btn_row.append(self.next_chapter_btn)

        fullscreen_btn = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic")
        fullscreen_btn.set_tooltip_text("Layar Penuh (f)")
        fullscreen_btn.connect("clicked", self.on_fullscreen_clicked)
        btn_row.append(fullscreen_btn)

        screenshot_btn = Gtk.Button.new_from_icon_name("camera-photo-symbolic")
        screenshot_btn.set_tooltip_text("Ambil Cuplikan Gambar / Screenshot (s)")
        screenshot_btn.connect("clicked", lambda *_: self.take_screenshot())
        btn_row.append(screenshot_btn)

        self.osd_box.append(btn_row)
        self.video_overlay.add_overlay(self.osd_box)

        # Toast notification OSD (Cuplikan layar, bookmark, dll.)
        self.toast_label = Gtk.Label(label="")
        self.toast_label.add_css_class("iina-toast")
        self.toast_label.set_halign(Gtk.Align.CENTER)
        self.toast_label.set_valign(Gtk.Align.START)
        self.toast_label.set_visible(False)
        self.video_overlay.add_overlay(self.toast_label)
        self._toast_timeout_id = None

        # ----------------- INSPECTOR PANEL (Kanan - macOS IINA Style) -----------------
        self.inspector_panel = self._build_inspector_panel()
        self.inspector_panel.set_visible(False)
        root.append(self.inspector_panel)

        # Key controller
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_press)
        self.add_controller(key_controller)

        # Simpan ukuran jendela saat ditutup
        self.connect("close-request", self._on_close_request)

    def _build_music_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        self.music_art = Gtk.Image()
        self.music_art.set_pixel_size(180)
        self.music_art.set_from_icon_name("audio-x-generic-symbolic")
        box.append(self.music_art)

        self.music_title = Gtk.Label(label="Tidak Ada Musik Diputar")
        self.music_title.add_css_class("title-1")
        box.append(self.music_title)

        self.music_artist = Gtk.Label(label="—")
        self.music_artist.add_css_class("dim-label")
        box.append(self.music_artist)

        return box

    def _build_welcome_view(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.add_css_class("iina-welcome-screen")
        root_box.set_hexpand(True)
        root_box.set_vexpand(True)

        # Center container
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_vexpand(True)
        center_box.set_hexpand(True)
        center_box.set_margin_top(32)
        center_box.set_margin_bottom(32)

        # Header branding: App Icon + Name + Subtitle
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header_box.set_halign(Gtk.Align.CENTER)

        app_icon = Gtk.Image.new_from_icon_name("io.github.inaa")
        app_icon.set_pixel_size(72)
        header_box.append(app_icon)

        title_lbl = Gtk.Label(label="INAA")
        title_lbl.add_css_class("title-1")
        title_lbl.set_markup("<span size='xx-large' weight='bold'>INAA</span>")
        header_box.append(title_lbl)

        sub_lbl = Gtk.Label(label="Pemutar media modern & elegan untuk Linux")
        sub_lbl.add_css_class("dim-label")
        header_box.append(sub_lbl)

        center_box.append(header_box)

        # Main content grid: Quick Actions (Left/Top) and Recent Files (Right/Bottom)
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        content_box.set_halign(Gtk.Align.CENTER)

        # --- Quick Actions Column ---
        actions_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        actions_card.add_css_class("iina-welcome-card")
        actions_card.set_size_request(260, -1)
        actions_card.set_valign(Gtk.Align.START)

        actions_title = Gtk.Label(label="Mulai Menonton")
        actions_title.set_halign(Gtk.Align.START)
        actions_title.add_css_class("heading")
        actions_card.append(actions_title)

        # Open File Button
        btn_open = Gtk.Button()
        btn_open.add_css_class("iina-action-btn")
        btn_open.add_css_class("primary")
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon_file = Gtk.Image.new_from_icon_name("document-open-symbolic")
        lbl_file = Gtk.Label(label="Buka File...")
        b_box.append(icon_file)
        b_box.append(lbl_file)
        btn_open.set_child(b_box)
        btn_open.connect("clicked", lambda *_: self.on_open_clicked(None))
        actions_card.append(btn_open)

        # Open URL Button
        btn_url = Gtk.Button()
        btn_url.add_css_class("iina-action-btn")
        u_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon_url = Gtk.Image.new_from_icon_name("insert-link-symbolic")
        lbl_url = Gtk.Label(label="Buka URL / Stream...")
        u_box.append(icon_url)
        u_box.append(lbl_url)
        btn_url.set_child(u_box)
        btn_url.connect("clicked", lambda *_: self.on_open_url_clicked(None))
        actions_card.append(btn_url)

        # Drag hint
        hint_lbl = Gtk.Label(label="atau seret & lepas file ke sini")
        hint_lbl.add_css_class("dim-label")
        hint_lbl.set_margin_top(8)
        actions_card.append(hint_lbl)

        content_box.append(actions_card)

        # --- Recent Files Column ---
        recent_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        recent_card.add_css_class("iina-welcome-card")
        recent_card.set_size_request(340, 260)

        recent_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        recent_title = Gtk.Label(label="Terakhir Diputar")
        recent_title.set_halign(Gtk.Align.START)
        recent_title.set_hexpand(True)
        recent_title.add_css_class("heading")
        recent_header.append(recent_title)

        btn_clear_recent = Gtk.Button()
        btn_clear_recent.set_icon_name("edit-clear-symbolic")
        btn_clear_recent.set_has_frame(False)
        btn_clear_recent.set_tooltip_text("Bersihkan riwayat")
        btn_clear_recent.connect("clicked", lambda *_: self._clear_recent_files())
        recent_header.append(btn_clear_recent)

        recent_card.append(recent_header)

        # Scrolled list of recents
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self.recent_listbox = Gtk.ListBox()
        self.recent_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(self.recent_listbox)
        recent_card.append(scroll)

        content_box.append(recent_card)
        center_box.append(content_box)
        root_box.append(center_box)

        self._populate_recent_files()
        return root_box

    def _populate_recent_files(self):
        # Bersihkan isi listbox terlebih dahulu
        child = self.recent_listbox.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.recent_listbox.remove(child)
            child = nxt

        recents = self._config.get("recent_files", [])
        if not recents:
            empty_lbl = Gtk.Label(label="Belum ada file yang diputar")
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_valign(Gtk.Align.CENTER)
            empty_lbl.set_vexpand(True)
            self.recent_listbox.append(empty_lbl)
            return

        for item in recents:
            path = item.get("path")
            if not path:
                continue

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("iina-recent-row")

            # Icon video/audio
            icon_name = "audio-x-generic-symbolic" if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS else "video-x-generic-symbolic"
            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(20)
            row.append(img)

            # Text info
            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            title_txt = item.get("title") or _display_name(path)
            t_lbl = Gtk.Label(label=title_txt)
            t_lbl.set_halign(Gtk.Align.START)
            t_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            t_lbl.add_css_class("iina-recent-title")
            info_box.append(t_lbl)

            pos = item.get("position", 0)
            dur = item.get("duration", 0)
            if dur > 0 and pos > 0:
                time_str = f"Lanjutkan dari {_format_time(pos)} / {_format_time(dur)}"
            elif dur > 0:
                time_str = f"Durasi: {_format_time(dur)}"
            else:
                time_str = path
            s_lbl = Gtk.Label(label=time_str)
            s_lbl.set_halign(Gtk.Align.START)
            s_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            s_lbl.add_css_class("iina-recent-sub")
            info_box.append(s_lbl)

            row.append(info_box)

            # Play button on right
            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_has_frame(False)
            play_btn.set_valign(Gtk.Align.CENTER)
            row.append(play_btn)

            # Gesture click to open and resume
            gesture = Gtk.GestureClick()
            gesture.connect("released", lambda _g, _n, _x, _y, p=path, resume_pos=pos: self.open_file(p, resume_pos=resume_pos))
            row.add_controller(gesture)

            self.recent_listbox.append(row)

    def _clear_recent_files(self):
        self._config["recent_files"] = []
        _save_config(self._config)
        self._populate_recent_files()

    def _record_recent_file(self, path, pos=0, duration=0):
        if not path:
            return
        recents = self._config.get("recent_files", [])
        # Hapus duplikat path yang sama jika sudah ada
        recents = [r for r in recents if r.get("path") != path]

        title = os.path.basename(path)
        try:
            meta = self.player.metadata or {}
            media_title = meta.get("title") or (self.player.media_title if hasattr(self.player, "media_title") else None)
            if media_title:
                title = media_title
        except Exception:
            pass

        recents.insert(0, {
            "path": path,
            "title": title,
            "position": round(pos, 1) if pos else 0,
            "duration": round(duration, 1) if duration else 0,
        })
        # Batasi riwayat maksimal 10 file
        self._config["recent_files"] = recents[:10]
        self._save_config_throttled(force=True)
        # Update tampilan jika welcome view sedang aktif
        if hasattr(self, "recent_listbox"):
            self._populate_recent_files()

    def _update_current_recent_position(self):
        if not self._current_path:
            return
        try:
            pos = self.player.time_pos or 0
            dur = self.player.duration or 0
            if dur > 0 and pos > 0:
                recents = self._config.get("recent_files", [])
                for item in recents:
                    if item.get("path") == self._current_path:
                        item["position"] = round(pos, 1)
                        item["duration"] = round(dur, 1)
                        break
                self._save_config_throttled()
        except Exception:
            pass

    def _save_config_throttled(self, force=False):
        now = time.monotonic()
        if not force and (now - self._last_config_save) < 8.0:
            return
        self._last_config_save = now
        _save_config(self._config)

    def _build_inspector_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(280, -1)
        panel.add_css_class("iina-inspector")
        panel.set_margin_start(0)

        # Header switcher (VIDEO / AUDIO / SUBTITLE)
        self.insp_stack = Gtk.Stack()
        self.insp_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.insp_stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_margin_top(10)
        switcher.set_margin_bottom(6)
        panel.append(switcher)

        # Tab 1: VIDEO
        tab_video = self._build_video_tab()
        self.insp_stack.add_titled(tab_video, "video", "VIDEO")

        # Tab 2: AUDIO
        tab_audio = self._build_audio_tab()
        self.insp_stack.add_titled(tab_audio, "audio", "AUDIO")

        # Tab 3: SUBTITLE
        tab_sub = self._build_sub_tab()
        self.insp_stack.add_titled(tab_sub, "subtitles", "SUBTITLE")

        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.insp_stack)
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        panel.append(scroll)

        return panel

    def _build_video_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        # Hardware Decoding (hwdec)
        lbl_hw = Gtk.Label(label="Hardware Acceleration:")
        lbl_hw.set_xalign(0)
        lbl_hw.add_css_class("iina-sec-title")
        box.append(lbl_hw)

        hw_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for hw_val, hw_txt in [("auto-safe", "Auto"), ("vaapi", "VA-API"), ("nvdec", "NVDEC"), ("no", "Off")]:
            btn = Gtk.Button(label=hw_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=hw_val: self._set_hwdec(v))
            hw_box.append(btn)
        box.append(hw_box)

        # Aspect Ratio
        lbl_ar = Gtk.Label(label="Aspect Ratio:")
        lbl_ar.set_xalign(0)
        lbl_ar.add_css_class("iina-sec-title")
        box.append(lbl_ar)

        ar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for ar_val, ar_txt in [("no", "Default"), ("4:3", "4:3"), ("16:9", "16:9"), ("16:10", "16:10"), ("2.35:1", "2.35")]:
            btn = Gtk.Button(label=ar_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=ar_val: self._set_aspect_ratio(v))
            ar_box.append(btn)
        box.append(ar_box)

        # Video Crop / Black Bar Removal (ala IINA)
        lbl_crop = Gtk.Label(label="Video Crop (Black Bars):")
        lbl_crop.set_xalign(0)
        lbl_crop.add_css_class("iina-sec-title")
        box.append(lbl_crop)

        crop_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for c_val, c_txt in [("none", "None"), ("16:9", "16:9"), ("4:3", "4:3"), ("2.35:1", "2.35"), ("21:9", "21:9")]:
            btn = Gtk.Button(label=c_txt)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, v=c_val: self._set_crop(v))
            crop_box.append(btn)
        box.append(crop_box)

        # Rotation
        lbl_rot = Gtk.Label(label="Rotation:")
        lbl_rot.set_xalign(0)
        lbl_rot.add_css_class("iina-sec-title")
        box.append(lbl_rot)

        rot_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for rot in [0, 90, 180, 270]:
            btn = Gtk.Button(label=f"{rot}°")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, r=rot: self._set_video_rotate(r))
            rot_box.append(btn)
        box.append(rot_box)

        # Speed
        lbl_spd = Gtk.Label(label="Playback Speed:")
        lbl_spd.set_xalign(0)
        lbl_spd.add_css_class("iina-sec-title")
        box.append(lbl_spd)

        spd_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_spd_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.25, 4.0, 0.25)
        self.insp_spd_scale.set_value(1.0)
        self.insp_spd_scale.set_hexpand(True)
        self.insp_spd_label = Gtk.Label(label="1.0x")
        def on_spd_changed(s):
            val = round(s.get_value(), 2)
            self._set_speed(val)
            self.insp_spd_label.set_text(f"{val:.2f}x".rstrip("0").rstrip(".") + "x")
        self.insp_spd_scale.connect("value-changed", on_spd_changed)
        spd_row.append(self.insp_spd_scale)
        spd_row.append(self.insp_spd_label)
        box.append(spd_row)

        # Deinterlace
        self.deinterlace_chk = Gtk.CheckButton(label="Deinterlace Video")
        self.deinterlace_chk.set_margin_top(6)
        def on_deint_toggled(chk):
            try:
                self.player.deinterlace = chk.get_active()
            except Exception:
                pass
        self.deinterlace_chk.connect("toggled", on_deint_toggled)
        box.append(self.deinterlace_chk)

        # Equalizer Video sliders (Brightness, Contrast, Saturation)
        lbl_adj = Gtk.Label(label="Penyesuaian Video:")
        lbl_adj.set_xalign(0)
        lbl_adj.add_css_class("iina-sec-title")
        box.append(lbl_adj)

        for prop, name in [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation")]:
            adj_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -100, 100, 1)
            sc.set_value(0)
            sc.set_hexpand(True)
            sc_lbl = Gtk.Label(label=f"{name}: 0")
            sc_lbl.set_size_request(95, -1)
            sc_lbl.set_xalign(0)
            sc.connect("value-changed", lambda s, p=prop, l=sc_lbl, n=name: self._on_filter_changed(p, s.get_value(), l, n))
            adj_row.append(sc_lbl)
            adj_row.append(sc)
            box.append(adj_row)

        return box

    def _build_audio_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        lbl_track = Gtk.Label(label="Audio Track:")
        lbl_track.set_xalign(0)
        lbl_track.add_css_class("iina-sec-title")
        box.append(lbl_track)

        self.insp_audio_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_audio_track_box)

        # Audio delay slider (-5s s/d +5s)
        lbl_delay = Gtk.Label(label="Audio Delay:")
        lbl_delay.set_xalign(0)
        lbl_delay.add_css_class("iina-sec-title")
        box.append(lbl_delay)

        del_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_audio_delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -5.0, 5.0, 0.1)
        self.insp_audio_delay_scale.set_value(0.0)
        self.insp_audio_delay_scale.set_hexpand(True)
        self.insp_audio_delay_label = Gtk.Label(label="0.0s")
        def on_adelay_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.audio_delay = val
            except Exception:
                pass
            self.insp_audio_delay_label.set_text(f"{val:+.1f}s")
        self.insp_audio_delay_scale.connect("value-changed", on_adelay_changed)
        del_row.append(self.insp_audio_delay_scale)
        del_row.append(self.insp_audio_delay_label)
        box.append(del_row)

        # Audio Equalizer Presets
        lbl_eq = Gtk.Label(label="Audio Presets:")
        lbl_eq.set_xalign(0)
        lbl_eq.add_css_class("iina-sec-title")
        box.append(lbl_eq)

        eq_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_bb = Gtk.Button(label="Bass Boost")
        btn_bb.add_css_class("iina-seg-btn")
        btn_bb.connect("clicked", lambda *_: self._set_audio_filter("bassboost"))
        eq_row.append(btn_bb)

        btn_voc = Gtk.Button(label="Vocal Boost")
        btn_voc.add_css_class("iina-seg-btn")
        btn_voc.connect("clicked", lambda *_: self._set_audio_filter("vocal"))
        eq_row.append(btn_voc)

        btn_night = Gtk.Button(label="Night Mode")
        btn_night.add_css_class("iina-seg-btn")
        btn_night.set_tooltip_text("Normalisasi volume dialog dan suara ledakan (Dynamic Range Compression)")
        btn_night.connect("clicked", lambda *_: self._set_audio_filter("nightmode"))
        eq_row.append(btn_night)

        btn_rst = Gtk.Button(label="Reset")
        btn_rst.add_css_class("iina-seg-btn")
        btn_rst.connect("clicked", lambda *_: self._set_audio_filter("reset"))
        eq_row.append(btn_rst)
        box.append(eq_row)

        return box

    def _build_sub_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(12)

        lbl_track = Gtk.Label(label="Primary Subtitle (Bawah):")
        lbl_track.set_xalign(0)
        lbl_track.add_css_class("iina-sec-title")
        box.append(lbl_track)

        self.insp_sub_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_sub_track_box)

        # Secondary Subtitle (Dual Subtitle feature ala IINA)
        lbl_sec_track = Gtk.Label(label="Secondary Subtitle (Atas):")
        lbl_sec_track.set_xalign(0)
        lbl_sec_track.add_css_class("iina-sec-title")
        lbl_sec_track.set_margin_top(8)
        box.append(lbl_sec_track)

        self.insp_sec_sub_track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(self.insp_sec_sub_track_box)

        # External Subtitle Buttons
        lbl_ext = Gtk.Label(label="External Subtitles:")
        lbl_ext.set_xalign(0)
        lbl_ext.add_css_class("iina-sec-title")
        box.append(lbl_ext)

        ext_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_load = Gtk.Button(label="Load File...")
        btn_load.add_css_class("iina-seg-btn")
        btn_load.connect("clicked", self._open_local_sub_dialog)
        ext_row.append(btn_load)

        btn_online = Gtk.Button(label="Search Online...")
        btn_online.add_css_class("iina-seg-btn")
        btn_online.connect("clicked", self._open_online_sub_dialog)
        ext_row.append(btn_online)
        box.append(ext_row)

        # Subtitle delay (-5s s/d +5s)
        lbl_sub_delay = Gtk.Label(label="Subtitle Delay:")
        lbl_sub_delay.set_xalign(0)
        lbl_sub_delay.add_css_class("iina-sec-title")
        box.append(lbl_sub_delay)

        del_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -5.0, 5.0, 0.1)
        self.insp_sub_delay_scale.set_value(0.0)
        self.insp_sub_delay_scale.set_hexpand(True)
        self.insp_sub_delay_label = Gtk.Label(label="0.0s")
        def on_sdelay_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.sub_delay = val
            except Exception:
                pass
            self.insp_sub_delay_label.set_text(f"{val:+.1f}s")
        self.insp_sub_delay_scale.connect("value-changed", on_sdelay_changed)
        del_row.append(self.insp_sub_delay_scale)
        del_row.append(self.insp_sub_delay_label)
        box.append(del_row)

        # Scale / Font Size (0.5 s/d 2.0)
        lbl_scale = Gtk.Label(label="Scale (Ukuran Font):")
        lbl_scale.set_xalign(0)
        lbl_scale.add_css_class("iina-sec-title")
        box.append(lbl_scale)

        scale_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 2.5, 0.05)
        self.insp_sub_scale.set_value(1.0)
        self.insp_sub_scale.set_hexpand(True)
        self.insp_sub_scale_label = Gtk.Label(label="1.0x")
        def on_sub_scale_changed(s):
            val = round(s.get_value(), 2)
            try:
                self.player.sub_scale = val
            except Exception:
                pass
            self.insp_sub_scale_label.set_text(f"{val:.2f}x")
        self.insp_sub_scale.connect("value-changed", on_sub_scale_changed)
        scale_row.append(self.insp_sub_scale)
        scale_row.append(self.insp_sub_scale_label)
        box.append(scale_row)

        # Position (0 s/d 100)
        lbl_pos = Gtk.Label(label="Position (Posisi):")
        lbl_pos.set_xalign(0)
        lbl_pos.add_css_class("iina-sec-title")
        box.append(lbl_pos)

        pos_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.insp_sub_pos = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.insp_sub_pos.set_value(100)
        self.insp_sub_pos.set_hexpand(True)
        def on_sub_pos_changed(s):
            try:
                self.player.sub_pos = int(s.get_value())
            except Exception:
                pass
        self.insp_sub_pos.connect("value-changed", on_sub_pos_changed)
        pos_row.append(self.insp_sub_pos)
        box.append(pos_row)

        # Subtitle Color & Styling (ala IINA)
        lbl_style = Gtk.Label(label="Subtitle Style & Color:")
        lbl_style.set_xalign(0)
        lbl_style.add_css_class("iina-sec-title")
        box.append(lbl_style)

        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for col_name, col_code in [("Putih", "#FFFFFF"), ("Kuning", "#FFFF00"), ("Cyan", "#00FFFF"), ("Hijau", "#00FF00")]:
            btn = Gtk.Button(label=col_name)
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, c=col_code, n=col_name: self._set_sub_color(c, n))
            color_row.append(btn)
        box.append(color_row)

        # Background Box Toggle (High Contrast untuk teks)
        self.sub_box_chk = Gtk.CheckButton(label="Tampilkan Kotak Latar Belakang (High Contrast)")
        self.sub_box_chk.set_margin_top(4)
        def on_sub_box_toggled(chk):
            try:
                if chk.get_active():
                    self.player.sub_back_color = "#80000000"  # Semi-transparent black box
                    self.show_toast("Subtitle Background Box: Aktif")
                else:
                    self.player.sub_back_color = "#00000000"  # Transparent
                    self.show_toast("Subtitle Background Box: Nonaktif")
            except Exception:
                pass
        self.sub_box_chk.connect("toggled", on_sub_box_toggled)
        box.append(self.sub_box_chk)

        return box

    def on_inspector_toggled(self, button):
        visible = button.get_active()
        self.inspector_panel.set_visible(visible)
        if visible:
            self._refresh_inspector_tracks()

    def _set_hwdec(self, mode):
        try:
            self.player.hwdec = mode
            mode_lbl = "Auto" if mode == "auto-safe" else mode.upper() if mode != "no" else "Nonaktif"
            self.show_toast(f"⚡ Hardware Acceleration: {mode_lbl}")
        except Exception:
            pass

    def _set_sub_color(self, color_code, name):
        try:
            self.player.sub_color = color_code
            self.show_toast(f"Subtitle Color: {name}")
        except Exception:
            pass

    def _set_aspect_ratio(self, val):
        try:
            self.player.video_aspect_override = val
        except Exception:
            pass

    def _set_crop(self, crop_ratio):
        try:
            if crop_ratio in ("none", "no", None):
                # Hapus filter crop
                current_vf = getattr(self.player, "vf", "") or ""
                # Filter out lavfi crop
                self.player["vf"] = ""
                self.show_toast("Video Crop: Dinonaktifkan")
            else:
                # Terapkan filter crop aspect ratio
                # 16:9 -> 16/9, 21:9 -> 21/9, dll
                parts = crop_ratio.split(":")
                if len(parts) == 2:
                    w_r, h_r = float(parts[0]), float(parts[1])
                    ratio_val = w_r / h_r
                    # Gunakan crop filter FFmpeg: memotong bagian luar agar rasio pas
                    self.player["vf"] = f"crop=w='min(iw,ih*{ratio_val})':h='min(ih,iw/{ratio_val})'"
                    self.show_toast(f"✂ Video Crop: {crop_ratio}")
        except Exception:
            pass

    def _set_video_rotate(self, val):
        try:
            self.player.video_rotate = val
        except Exception:
            pass

    def _refresh_inspector_tracks(self):
        try:
            tracks = self.player.track_list or []
        except Exception:
            tracks = []

        # Audio tracks
        while child := self.insp_audio_track_box.get_first_child():
            self.insp_audio_track_box.remove(child)

        audio_tracks = [t for t in tracks if t.get("type") == "audio"]
        current_aid = getattr(self.player, "aid", None)
        for t in audio_tracks:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Audio #{tid}"
            is_sel = (current_aid == tid) or t.get("selected")
            btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("aid", track_id))
            self.insp_audio_track_box.append(btn)

        # Primary Subtitle tracks
        while child := self.insp_sub_track_box.get_first_child():
            self.insp_sub_track_box.remove(child)

        current_sid = getattr(self.player, "sid", None)
        none_btn = Gtk.Button(label=f"{'✓ ' if current_sid in ('no', False, None) else '   '}<None>")
        none_btn.add_css_class("iina-seg-btn")
        none_btn.connect("clicked", lambda *_: self._set_track("sid", "no"))
        self.insp_sub_track_box.append(none_btn)

        sub_tracks = [t for t in tracks if t.get("type") == "sub"]
        for t in sub_tracks:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Sub #{tid}"
            is_sel = (current_sid == tid) or t.get("selected")
            btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
            btn.add_css_class("iina-seg-btn")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("sid", track_id))
            self.insp_sub_track_box.append(btn)

        # Secondary Subtitle tracks (Dual Subtitle)
        if hasattr(self, "insp_sec_sub_track_box"):
            while child := self.insp_sec_sub_track_box.get_first_child():
                self.insp_sec_sub_track_box.remove(child)

            try:
                current_sec_sid = getattr(self.player, "secondary_sid", "no")
            except Exception:
                current_sec_sid = "no"

            sec_none_btn = Gtk.Button(label=f"{'✓ ' if current_sec_sid in ('no', False, None) else '   '}<None>")
            sec_none_btn.add_css_class("iina-seg-btn")
            sec_none_btn.connect("clicked", lambda *_: self._set_track("secondary_sid", "no"))
            self.insp_sec_sub_track_box.append(sec_none_btn)

            for t in sub_tracks:
                tid = t.get("id")
                name = t.get("title") or t.get("lang") or f"Sub #{tid}"
                is_sel = (current_sec_sid == tid)
                btn = Gtk.Button(label=f"{'✓ ' if is_sel else '   '}{name}")
                btn.add_css_class("iina-seg-btn")
                btn.connect("clicked", lambda b, track_id=tid: self._set_track("secondary_sid", track_id))
                self.insp_sec_sub_track_box.append(btn)

    def _setup_drag_and_drop(self):
        target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        target.connect("drop", self.on_drop)
        self.add_controller(target)

    # --------------------------------------------------------------- player

    @property
    def player(self):
        return self.gl_area.player

    def open_file(self, path, resume_pos=None):
        path = normalize_media_uri(path)
        if not is_allowed_media_uri(path):
            self.show_toast("URI media tidak diizinkan")
            return
        self._current_path = path

        # Jika resume_pos tidak diberikan secara eksplisit, cari riwayat posisi terakhir dari config
        if resume_pos is None:
            recents = self._config.get("recent_files", [])
            for item in recents:
                if item.get("path") == path:
                    saved_p = item.get("position", 0)
                    dur = item.get("duration", 0)
                    if saved_p > 5 and (dur == 0 or saved_p < dur - 5):
                        resume_pos = saved_p
                    break

        self._pending_resume_pos = resume_pos
        if path not in self.playlist:
            self.playlist.append(path)
            # Smart Auto-Load Folder Media (ala IINA: otomatis mengisi daftar putar jika memutar file lokal)
            self._auto_populate_folder_playlist(path)
            self._refresh_sidebar()
        self.playlist_index = self.playlist.index(path)

        # PENTING: pindah ke halaman video/music di display_stack SEBELUM
        # memanggil player.play(). Gtk.Stack tidak me-realize child yang
        # sedang tersembunyi, jadi kalau gl_area (halaman "video") belum
        # terlihat saat play() dipanggil, mpv render context belum ada dan
        # loadfile akan gagal secara senyap ("No render context set").
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS:
            self.set_music_mode(True)
        else:
            if not self.music_toggle_btn.get_active():
                self.set_music_mode(False)
            else:
                self.display_stack.set_visible_child_name("music")

        self.player.play(path)
        self.player.pause = False
        self._has_played_media = False
        self._highlight_current_row()
        self._reset_ab_loop()

        # Bersihkan cache thumbnail untuk file baru
        self._thumb_cache.clear()
        self._thumb_pending.clear()

        # Tampilkan OSD saat media dibuka
        self.osd_box.set_visible(True)

        # Update trek, metadata musik, & chapter setelah media dimuat
        GLib.timeout_add(600, self._on_media_loaded)

        # Panggil hook plugin on_file_open
        self._trigger_plugin_hook("on_file_open", path)


    def _on_media_loaded(self):
        self._rebuild_track_menu()
        self._update_chapters()
        self._update_music_metadata()

        # Terapkan resume position jika ada
        if self._pending_resume_pos is not None and self._pending_resume_pos > 0:
            try:
                dur = self.player.duration or 0
                if dur > 0 and self._pending_resume_pos < dur - 2:
                    self.player.seek(self._pending_resume_pos, reference="absolute")
                    self.show_toast(f"Melanjutkan dari {_format_time(self._pending_resume_pos)}")
            except Exception:
                pass
            self._pending_resume_pos = None

        # Catat ke riwayat file terakhir diputar
        try:
            dur = self.player.duration or 0
            pos = self.player.time_pos or 0
            self._record_recent_file(self._current_path, pos=pos, duration=dur)
        except Exception:
            pass

        try:
            meta = self.player.metadata or {}
            media_title = meta.get("title") or (self.player.media_title if hasattr(self.player, "media_title") else None)
            if not media_title and self._current_path:
                media_title = _display_name(self._current_path)
            if media_title:
                self.set_title(f"{media_title} — INAA")
        except Exception:
            pass
        return False

    def _update_music_metadata(self):
        if not self._current_path:
            return
        try:
            meta = self.player.metadata or {}
            title = meta.get("title") or os.path.basename(self._current_path)
            artist = meta.get("artist") or meta.get("album_artist") or "Artis Tidak Diketahui"
            album = meta.get("album")
            if album:
                artist += f" • {album}"
            self.music_title.set_text(title)
            self.music_artist.set_text(artist)
        except Exception:
            self.music_title.set_text(os.path.basename(self._current_path))
            self.music_artist.set_text("—")

    def on_music_mode_toggled(self, button):
        self.set_music_mode(button.get_active())

    def set_music_mode(self, active):
        self._is_music_mode = active
        self.music_toggle_btn.set_active(active)
        if active:
            self.display_stack.set_visible_child_name("music")
            self._update_music_metadata()
        else:
            self.display_stack.set_visible_child_name("video")

    def _update_chapters(self):
        try:
            chapters = self.player.chapter_list or []
            self._chapters = chapters
            self.seekbar.clear_marks()
            duration = self.player.duration or 0

            if chapters and duration > 0:
                self.chapter_menu_btn.set_visible(True)
                self.prev_chapter_btn.set_sensitive(True)
                self.next_chapter_btn.set_sensitive(True)
                for ch in chapters:
                    time = ch.get("time", 0)
                    scale_pos = (time / duration) * 1000.0
                    self.seekbar.add_mark(scale_pos, Gtk.PositionType.BOTTOM, None)
            else:
                self.prev_chapter_btn.set_sensitive(False)
                self.next_chapter_btn.set_sensitive(False)
        except Exception:
            pass

    def _auto_populate_folder_playlist(self, current_file_path):
        """Mendeteksi berkas media lain di folder yang sama dan menambahkannya
        secara berurutan ke playlist (fitur Smart Next Episode ala IINA)."""
        try:
            if not current_file_path or current_file_path.startswith(("http://", "https://", "rtmp://", "ytdl://")):
                return
            folder = os.path.dirname(current_file_path)
            if not os.path.isdir(folder):
                return

            valid_extensions = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
            entries = []
            for item in sorted(os.listdir(folder)):
                full_p = os.path.join(folder, item)
                if os.path.isfile(full_p):
                    ext = os.path.splitext(item)[1].lower()
                    if ext in valid_extensions:
                        entries.append(full_p)

            # Tambahkan berkas yang belum ada di playlist dengan urutan rapi
            for p in entries:
                if p not in self.playlist:
                    self.playlist.append(p)
        except Exception:
            pass

    def add_to_playlist(self, path):
        path = normalize_media_uri(path)
        if not is_allowed_media_uri(path):
            return
        if path and path not in self.playlist:
            self.playlist.append(path)
            self._refresh_sidebar()

    def play_relative(self, delta):
        if not self.playlist:
            return
        new_index = self.playlist_index + delta
        if 0 <= new_index < len(self.playlist):
            self.open_file(self.playlist[new_index])

    def _refresh_sidebar(self):
        child = self.sidebar_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.sidebar_list.remove(child)
            child = nxt
        for path in self.playlist:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=_display_name(path))
            label.set_xalign(0)
            label.set_margin_start(8)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            row.set_child(label)
            self.sidebar_list.append(row)
        self._highlight_current_row()

    def _highlight_current_row(self):
        row = self.sidebar_list.get_row_at_index(self.playlist_index)
        if row is not None:
            self.sidebar_list.select_row(row)

    # -------------------------------------------------------- menus & popovers

    def _rebuild_filters_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_size_request(240, -1)

        title = Gtk.Label(label="Filter Video Real-time")
        title.set_xalign(0)
        title.add_css_class("heading")
        box.append(title)

        # Sliders: Brightness, Contrast, Saturation, Gamma
        sliders_def = [
            ("Kecerahan (Brightness)", "brightness", -100, 100),
            ("Kontras (Contrast)", "contrast", -100, 100),
            ("Saturasi (Saturation)", "saturation", -100, 100),
            ("Gamma", "gamma", -100, 100),
        ]

        for lbl, prop, min_val, max_val in sliders_def:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            cur_val = getattr(self.player, prop, 0.0) or 0.0
            l = Gtk.Label(label=f"{lbl}: {int(cur_val)}")
            l.set_xalign(0)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_val, max_val, 1)
            scale.set_value(cur_val)
            scale.set_draw_value(False)
            scale.connect("value-changed", lambda sc, p=prop, lb=l, name=lbl: self._on_filter_changed(p, sc.get_value(), lb, name))
            row.append(l)
            row.append(scale)
            box.append(row)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        # Equalizer audio preset
        eq_title = Gtk.Label(label="Audio Equalizer / Efek")
        eq_title.set_xalign(0)
        box.append(eq_title)

        eq_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_bass = Gtk.Button(label="Bass Boost")
        btn_bass.connect("clicked", lambda *_: self._set_audio_filter("bassboost"))
        eq_box.append(btn_bass)

        btn_vocal = Gtk.Button(label="Vocal Boost")
        btn_vocal.connect("clicked", lambda *_: self._set_audio_filter("vocal"))
        eq_box.append(btn_vocal)

        btn_night = Gtk.Button(label="Night Mode")
        btn_night.connect("clicked", lambda *_: self._set_audio_filter("nightmode"))
        eq_box.append(btn_night)
        box.append(eq_box)

        # Reset button
        reset_btn = Gtk.Button(label="Reset Semua Filter")
        reset_btn.connect("clicked", lambda *_: self._reset_filters())
        box.append(reset_btn)

        self.filters_popover.set_child(box)

    def _on_filter_changed(self, prop, val, label, name):
        try:
            setattr(self.player, prop, val)
            label.set_text(f"{name}: {int(val)}")
        except Exception:
            pass

    def _set_audio_filter(self, preset):
        try:
            if preset == "bassboost":
                self.player["af"] = "equalizer=f=64:t=q:w=1:g=8"
                self.show_toast("🎵 Efek Audio: Bass Boost")
            elif preset == "vocal":
                self.player["af"] = "equalizer=f=1000:t=q:w=1:g=6"
                self.show_toast("🎙 Efek Audio: Vocal Boost")
            elif preset == "nightmode":
                self.player["af"] = "lavfi=[loudnorm=I=-16:TP=-1.5:LRA=11]"
                self.show_toast("🌙 Efek Audio: Night Mode (Dynamic Range Normalization)")
            elif preset == "reset":
                self.player["af"] = ""
                self.show_toast("Efek Audio Dinonaktifkan")
        except Exception:
            pass
        self.filters_popover.popdown()

    def _reset_filters(self):
        try:
            self.player.brightness = 0
            self.player.contrast = 0
            self.player.saturation = 0
            self.player.gamma = 0
            self.player["af"] = ""
        except Exception:
            pass
        self._rebuild_filters_menu()

    def _rebuild_playback_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        # Speed title
        speed_label = Gtk.Label(label="Kecepatan Pemutaran")
        speed_label.set_xalign(0)
        box.append(speed_label)

        grid = Gtk.Grid()
        grid.set_column_spacing(4)
        grid.set_row_spacing(4)

        current_speed = round(self.player.speed or 1.0, 2)
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        for i, s in enumerate(speeds):
            btn = Gtk.Button(label=f"{s}x")
            if abs(current_speed - s) < 0.05:
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda b, val=s: self._set_speed(val))
            grid.attach(btn, i % 3, i // 3, 1, 1)
        box.append(grid)

        # A-B Loop Section
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box.append(sep)

        ab_title = Gtk.Label(label="A-B Loop")
        ab_title.set_xalign(0)
        box.append(ab_title)

        ab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_toggle_ab = Gtk.Button(label="Langkah Loop (l)")
        btn_toggle_ab.connect("clicked", lambda *_: self.toggle_ab_loop())
        ab_box.append(btn_toggle_ab)

        btn_clear_ab = Gtk.Button(label="Reset Loop")
        btn_clear_ab.connect("clicked", lambda *_: self._reset_ab_loop())
        ab_box.append(btn_clear_ab)
        box.append(ab_box)

        self.playback_opts_popover.set_child(box)

    def _set_speed(self, speed):
        self.player.speed = speed
        self.playback_opts_btn.set_label(f"{speed:.2f}x".rstrip("0").rstrip(".") + "x")
        self.playback_opts_popover.popdown()

    def change_speed(self, delta):
        current = round(self.player.speed or 1.0, 2)
        new_speed = max(0.25, min(4.0, current + delta))
        self.player.speed = new_speed
        self.playback_opts_btn.set_label(f"{new_speed:.2f}x".rstrip("0").rstrip(".") + "x")

    def toggle_ab_loop(self):
        if self._ab_state == 0:
            pos = self.player.time_pos or 0
            self.player["ab-loop-a"] = pos
            self.player["ab-loop-b"] = "no"
            self._ab_state = 1
            self.ab_label.set_text(f"[Loop: A {_format_time(pos)} → ?]")
        elif self._ab_state == 1:
            pos = self.player.time_pos or 0
            self.player["ab-loop-b"] = pos
            self._ab_state = 2
            a_pos = self.player["ab-loop-a"] or 0
            self.ab_label.set_text(f"[Loop: {_format_time(a_pos)} ⟲ {_format_time(pos)}]")
        else:
            self._reset_ab_loop()
        self.playback_opts_popover.popdown()

    def _reset_ab_loop(self):
        try:
            self.player["ab-loop-a"] = "no"
            self.player["ab-loop-b"] = "no"
        except Exception:
            pass
        self._ab_state = 0
        self.ab_label.set_text("")

    def _rebuild_chapter_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        chapters = self._chapters
        if not chapters:
            label = Gtk.Label(label="Tidak ada data bab pada video ini")
            box.append(label)
        else:
            header_lbl = Gtk.Label(label="Daftar Bab (Chapters)")
            header_lbl.set_xalign(0)
            box.append(header_lbl)
            scroll = Gtk.ScrolledWindow()
            scroll.set_max_content_height(240)
            scroll.set_propagate_natural_height(True)
            list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for idx, ch in enumerate(chapters):
                title = ch.get("title") or f"Bab {idx + 1}"
                time_str = _format_time(ch.get("time", 0))
                btn = Gtk.Button(label=f"{idx + 1}. {title} ({time_str})")
                btn.connect("clicked", lambda b, i=idx: self._seek_chapter(i))
                list_box.append(btn)
            scroll.set_child(list_box)
            box.append(scroll)

        self.chapter_popover.set_child(box)

    def _seek_chapter(self, index):
        try:
            self.player.chapter = index
        except Exception:
            pass
        self.chapter_popover.popdown()

    def navigate_chapter(self, delta):
        try:
            current = self.player.chapter
            if current is not None:
                new_ch = current + delta
                if 0 <= new_ch < len(self._chapters):
                    self.player.chapter = new_ch
        except Exception:
            pass

    def _rebuild_track_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        try:
            tracks = self.player.track_list or []
        except Exception:
            tracks = []

        # Deteksi track yang sedang aktif
        current_aid = getattr(self.player, "aid", None)
        current_sid = getattr(self.player, "sid", None)

        audio_label = Gtk.Label(label="Audio Track")
        audio_label.set_xalign(0)
        box.append(audio_label)
        for t in [t for t in tracks if t.get("type") == "audio"]:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Track {tid}"
            is_sel = t.get("selected") or (current_aid == tid)
            prefix = "✓ " if is_sel else "   "
            btn = Gtk.Button(label=f"{prefix}{name}")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("aid", track_id))
            box.append(btn)

        sub_label = Gtk.Label(label="Subtitle Track")
        sub_label.set_xalign(0)
        sub_label.set_margin_top(8)
        box.append(sub_label)

        # Tombol nonaktifkan subtitle
        is_none_sel = (current_sid in (False, "no", None))
        none_prefix = "✓ " if is_none_sel else "   "
        none_btn = Gtk.Button(label=f"{none_prefix}Nonaktifkan Subtitle")
        none_btn.connect("clicked", lambda b: self._set_track("sid", "no"))
        box.append(none_btn)

        for t in [t for t in tracks if t.get("type") == "sub"]:
            tid = t.get("id")
            name = t.get("title") or t.get("lang") or f"Track {tid}"
            is_sel = t.get("selected") or (current_sid == tid)
            prefix = "✓ " if is_sel else "   "
            btn = Gtk.Button(label=f"{prefix}{name}")
            btn.connect("clicked", lambda b, track_id=tid: self._set_track("sid", track_id))
            box.append(btn)

        # Online subtitle search button
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        box.append(sep)

        online_sub_btn = Gtk.Button(label="Cari Subtitle Online...")
        online_sub_btn.connect("clicked", self._open_online_sub_dialog)
        box.append(online_sub_btn)

        local_sub_btn = Gtk.Button(label="Buka File Subtitle (Lokal)...")
        local_sub_btn.connect("clicked", self._open_local_sub_dialog)
        box.append(local_sub_btn)

        self.track_popover.set_child(box)

    def _set_track(self, kind, value):
        try:
            setattr(self.player, kind, value)
        except Exception:
            pass
        self.track_popover.popdown()
        if hasattr(self, "inspector_panel") and self.inspector_panel.get_visible():
            self._refresh_inspector_tracks()

    def _add_and_select_subtitle(self, sub_path):
        try:
            # Dapatkan daftar id track sub sebelum menambah
            old_sub_ids = {t["id"] for t in (self.player.track_list or []) if t.get("type") == "sub"}
            self.player.sub_add(sub_path)
            # Cari track sub baru yang baru saja ditambahkan dan pilih langsung
            new_tracks = [t for t in (self.player.track_list or []) if t.get("type") == "sub"]
            for t in new_tracks:
                if t.get("id") not in old_sub_ids or t.get("external_filename") == sub_path or t.get("title") == os.path.basename(sub_path):
                    self.player.sid = t["id"]
                    break
            if hasattr(self, "inspector_panel") and self.inspector_panel.get_visible():
                self._refresh_inspector_tracks()
        except Exception:
            pass

    # -------------------------------------------------- online subtitles

    def _open_online_sub_dialog(self, button):
        self.track_popover.popdown()
        dialog = Gtk.Dialog(title="Cari Subtitle Online", transient_for=self, modal=True)
        dialog.set_default_size(420, 360)

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        default_query = os.path.splitext(os.path.basename(self._current_path or ""))[0]
        search_entry = Gtk.Entry()
        search_entry.set_text(default_query)
        search_entry.set_hexpand(True)
        search_btn = Gtk.Button(label="Cari")
        entry_row.append(search_entry)
        entry_row.append(search_btn)
        box.append(entry_row)

        status_lbl = Gtk.Label(label="Ketik judul dan tekan Cari")
        status_lbl.set_xalign(0)
        box.append(status_lbl)

        results_list = Gtk.ListBox()
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(results_list)
        box.append(scroll)

        def do_search(*_):
            query = search_entry.get_text().strip()
            if not query:
                return
            status_lbl.set_text("Mencari subtitle...")
            # Bersihkan hasil lama
            ch = results_list.get_first_child()
            while ch:
                nxt = ch.get_next_sibling()
                results_list.remove(ch)
                ch = nxt

            def fetch():
                try:
                    api_key = (self._config.get("opensubtitles_api_key") or "").strip() or None
                    data = search_subtitles(query, api_key=api_key)
                    GLib.idle_add(lambda: render_results(data))
                except Exception as e:
                    GLib.idle_add(lambda: status_lbl.set_text(f"Pencarian gagal: {e}"))

            threading.Thread(target=fetch, daemon=True).start()

        def render_results(data):
            if not data:
                status_lbl.set_text("Subtitle tidak ditemukan.")
                return
            status_lbl.set_text(f"Ditemukan {len(data)} subtitle:")
            for item in data[:15]:
                sub_name = item.get("name") or "Subtitle"
                lang = item.get("lang") or ""
                file_id = item.get("file_id")
                row = Gtk.ListBoxRow()
                btn = Gtk.Button(label=f"[{lang}] {sub_name}")
                btn.connect("clicked", lambda b, fid=file_id, n=sub_name: download_and_load_sub(fid, n, dialog))
                row.set_child(btn)
                results_list.append(row)

        def download_and_load_sub(file_id, filename, dlg):
            if not file_id:
                status_lbl.set_text("ID file subtitle tidak valid.")
                return
            status_lbl.set_text(f"Mengunduh {filename}...")
            def dl():
                try:
                    api_key = (self._config.get("opensubtitles_api_key") or "").strip() or None
                    out_path = download_subtitle(file_id, filename, api_key=api_key)
                    GLib.idle_add(lambda: apply_sub(out_path, dlg))
                except Exception as e:
                    GLib.idle_add(lambda: status_lbl.set_text(f"Gagal unduh: {e}"))
            threading.Thread(target=dl, daemon=True).start()

        def apply_sub(sub_path, dlg):
            try:
                self._add_and_select_subtitle(sub_path)
                dlg.destroy()
            except Exception:
                pass

        search_btn.connect("clicked", do_search)
        search_entry.connect("activate", do_search)

        content.append(box)
        dialog.show()

    def _open_local_sub_dialog(self, button):
        self.track_popover.popdown()
        dialog = Gtk.FileDialog()
        dialog.set_title("Pilih File Subtitle")

        filter_sub = Gtk.FileFilter()
        filter_sub.set_name("File Subtitle (*.srt, *.vtt, *.ass, ...)")
        for ext in SUBTITLE_EXTENSIONS:
            filter_sub.add_pattern(f"*{ext}")
            filter_sub.add_pattern(f"*{ext.upper()}")

        filter_all = Gtk.FileFilter()
        filter_all.set_name("Semua File")
        filter_all.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_sub)
        filters.append(filter_all)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_sub)

        def on_open_finish(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if gfile:
                    sub_path = gfile.get_path()
                    if sub_path:
                        self._add_and_select_subtitle(sub_path)
            except Exception:
                pass

        dialog.open(self, None, on_open_finish)

    # ---------------------------------------------------- plugin system

    def _load_plugins(self):
        enabled = self._config.get("enabled_plugins") or []
        self._plugins = load_plugins(self, PLUGINS_DIR, enabled)

    def _trigger_plugin_hook(self, hook_name, *args, **kwargs):
        for plugin in self._plugins:
            fn = getattr(plugin, hook_name, None)
            if callable(fn):
                try:
                    fn(*args, **kwargs)
                except Exception:
                    pass

    # ------------------------------------------------------------ handlers

    def on_open_url_clicked(self, button):
        dialog = Gtk.Dialog(
            title="Buka dari URL",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Buka", Gtk.ResponseType.OK,
        )
        dialog.set_default_size(420, -1)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label="Tempel link video (YouTube, Vimeo, dll.):")
        label.set_xalign(0)
        content.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text("https://www.youtube.com/watch?v=...")
        entry.set_activates_default(True)
        content.append(entry)

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect("response", self._on_open_url_response, entry)
        dialog.show()
        entry.grab_focus()

    def _on_open_url_response(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK:
            url = entry.get_text().strip()
            if url:
                if not is_allowed_media_uri(url):
                    self.show_toast("URL tidak diizinkan (hanya http/https)")
                else:
                    self.add_to_playlist(url)
                    self.open_file(url)
        dialog.destroy()

    def on_open_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Pilih video atau musik",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Batal", Gtk.ResponseType.CANCEL,
            "_Buka", Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_open_dialog_response)
        dialog.show()

    def _on_open_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            files = dialog.get_files()
            paths = [files.get_item(i).get_path() for i in range(files.get_n_items())]
            for p in paths:
                self.add_to_playlist(p)
            if paths:
                self.open_file(paths[0])
        dialog.destroy()

    def on_playlist_toggled(self, button):
        self.sidebar.set_visible(button.get_active())

    def on_playlist_row_activated(self, listbox, row):
        index = row.get_index()
        if 0 <= index < len(self.playlist):
            self.open_file(self.playlist[index])

    def on_playpause_clicked(self, button):
        self.player.pause = not self.player.pause
        self._update_playpause_icon()

    def on_volume_changed(self, scale):
        vol = scale.get_value()
        self.player.volume = vol
        self._config["volume"] = vol
        self._save_config_throttled()

    def on_mute_clicked(self, button):
        try:
            self.player.mute = not self.player.mute
            icon = "audio-volume-muted-symbolic" if self.player.mute else "audio-volume-high-symbolic"
            self.vol_btn.set_icon_name(icon)
        except Exception:
            pass

    def on_fullscreen_clicked(self, button):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def on_mini_toggled(self, button):
        self._is_mini = button.get_active()
        if self._is_mini:
            self._normal_size = (self.get_width(), self.get_height())
            self.header.set_visible(False)
            self.set_default_size(360, 220)
        else:
            self.header.set_visible(True)
            self.set_default_size(*self._normal_size)

    def _on_video_left_click(self, gesture, n_press, x, y):
        if n_press == 1:
            self.on_playpause_clicked(None)
        elif n_press == 2:
            if self._is_mini:
                self.mini_btn.set_active(False)
            else:
                self.on_fullscreen_clicked(None)

    def _on_video_drag_begin(self, gesture, start_x, start_y):
        self._drag_start_pos = (start_x, start_y)

    def _on_video_drag_end(self, gesture, offset_x, offset_y):
        # Jika mouse ditarik keluar atau lebih dari 120px, detach window
        dist = (offset_x**2 + offset_y**2)**0.5
        if dist > 120 and not self.is_fullscreen() and not self._is_mini:
            self.detach_video_window()
        self._drag_start_pos = None

    def _on_video_scroll(self, controller, dx, dy):
        """IINA-style trackpad / mouse gesture:
        Scroll vertikal: Naik/turunkan volume
        Scroll horizontal: Seek mundur/maju
        """
        # Tangani scroll vertikal (Volume)
        if abs(dy) >= 0.1:
            step = -dy * 2.0  # Scroll ke atas dy < 0 -> volume bertambah
            cur_vol = self.volume_scale.get_value()
            new_vol = max(0.0, min(100.0, cur_vol + step))
            self.volume_scale.set_value(new_vol)
            self.show_toast(f"🔊 Volume: {int(new_vol)}%", duration_ms=1200)
            return True

        # Tangani scroll horizontal (Seeking)
        if abs(dx) >= 0.1:
            seek_delta = dx * 2.0  # Scroll ke kanan dx > 0 -> maju
            try:
                self.player.seek(seek_delta, reference="relative")
                pos = self.player.time_pos or 0
                dur = self.player.duration or 0
                self.show_toast(f"⏩ {self._format_time(pos)} / {self._format_time(dur)}", duration_ms=1200)
            except Exception:
                pass
            return True

        return False

    def show_toast(self, message, duration_ms=2500):
        if hasattr(self, "toast_label"):
            self.toast_label.set_text(message)
            self.toast_label.set_visible(True)
            if self._toast_timeout_id:
                GLib.source_remove(self._toast_timeout_id)
                self._toast_timeout_id = None
            def hide_toast():
                self.toast_label.set_visible(False)
                self._toast_timeout_id = None
                return False
            self._toast_timeout_id = GLib.timeout_add(duration_ms, hide_toast)

    def take_screenshot(self):
        if not self._current_path:
            self.show_toast("Tidak ada media yang diputar")
            return
        try:
            # Simpan ke ~/Pictures/INAA atau ~/Pictures
            pics_dir = Path.home() / "Pictures" / "INAA"
            pics_dir.mkdir(parents=True, exist_ok=True)
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(self._current_path))[0]
            clean_name = "".join(c for c in base_name if c.isalnum() or c in ("-", "_")).strip() or "screenshot"
            out_file = str(pics_dir / f"{clean_name}_{ts}.png")

            # Perintah screenshot video libmpv
            self.player.command("screenshot-to-file", out_file, "video")
            self.show_toast(f"📷 Cuplikan disimpan ke:\nPictures/INAA/{os.path.basename(out_file)}")
        except Exception as e:
            try:
                # Fallback format biasa
                self.player.screenshot(out_file)
                self.show_toast(f"📷 Cuplikan disimpan ke Pictures/INAA")
            except Exception as e2:
                self.show_toast(f"Gagal mengambil cuplikan: {e2}")

    def detach_video_window(self):
        """"Pisahkan" video jadi window kecil mengambang.

        CATATAN PENTING (kenapa implementasinya seperti ini):
        Versi awal fitur ini memindahkan `self.gl_area` (GLArea yang sama,
        dengan render context mpv yang sedang aktif) ke sebuah `Gtk.Window`
        baru. Itu SELALU memicu unrealize+realize pada GLArea (karena GTK
        mewajibkan itu saat widget pindah top-level window), yang otomatis
        membebaskan lalu membuat ulang MpvRenderContext.

        Setelah diuji, ternyata `vo=libmpv` milik mpv TIDAK BISA bertahan
        begitu render context-nya dibebaskan sementara ada media yang lagi
        dimuat — mpv langsung menganggap video output gagal fatal dan
        meng-unload file yang sedang diputar (walau sudah di-pause dulu
        sebelum reparenting; sudah diuji juga tetap gagal). Alias: video
        yang sedang diputar akan mati setiap kali GLArea direparenting ke
        window lain, terlepas dari cara reparenting-nya.

        Karena itu, "detach" di sini TIDAK membuat window baru sama sekali.
        Sebagai gantinya dipakai mekanisme yang sama dengan Mini Player
        (yang sudah terbukti aman karena tidak pernah menyentuh parent
        dari gl_area): jendela utama yang sama diperkecil & chrome
        disembunyikan, memberi efek "mengambang" tanpa pernah membongkar
        render context.
        """
        if not self._current_path:
            self.show_toast("Tidak ada video untuk dipisahkan")
            return
        if not self._is_mini:
            self.mini_btn.set_active(True)  # akan memicu on_mini_toggled
        self.show_toast("Mode mengambang aktif (video tetap di window yang sama)")

    def attach_video_window(self):
        if self._is_mini:
            self.mini_btn.set_active(False)
            self.show_toast("Kembali ke tampilan penuh")

    def _on_video_right_click(self, gesture, n_press, x, y):
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self.video_context_popover.set_pointing_to(rect)
        self._rebuild_video_context_menu()
        self.video_context_popover.popup()

    def _rebuild_video_context_menu(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Mini Player toggle
        if self._is_mini:
            mini_label = "Kembali ke Ukuran Normal (Esc)"
            mini_icon = "view-restore-symbolic"
        else:
            mini_label = "Mode Mini Player"
            mini_icon = "view-restore-symbolic"

        btn_mini = Gtk.Button(label=mini_label)
        btn_mini.set_icon_name(mini_icon)
        def toggle_mini_action(_):
            self.video_context_popover.popdown()
            self.mini_btn.set_active(not self._is_mini)
        btn_mini.connect("clicked", toggle_mini_action)
        box.append(btn_mini)

        # Inspector Panel toggle
        if not self._is_mini:
            insp_label = "Sembunyikan Inspector (i)" if self.inspector_panel.get_visible() else "Inspector Pengaturan (i)"
            btn_insp = Gtk.Button(label=insp_label)
            btn_insp.set_icon_name("preferences-other-symbolic")
            def toggle_insp_action(_):
                self.video_context_popover.popdown()
                self.inspector_btn.set_active(not self.inspector_btn.get_active())
            btn_insp.connect("clicked", toggle_insp_action)
            box.append(btn_insp)

        # Layar Penuh
        if not self._is_mini:
            fs_label = "Keluar Layar Penuh (f / Esc)" if self.is_fullscreen() else "Layar Penuh (f)"
            btn_fs = Gtk.Button(label=fs_label)
            btn_fs.set_icon_name("view-fullscreen-symbolic")
            def toggle_fs_action(_):
                self.video_context_popover.popdown()
                self.on_fullscreen_clicked(None)
            btn_fs.connect("clicked", toggle_fs_action)
            box.append(btn_fs)

        # Putar / Jeda
        is_playing = not self.player.pause
        play_label = "Jeda (Spasi)" if is_playing else "Putar (Spasi)"
        play_icon = "media-playback-pause-symbolic" if is_playing else "media-playback-start-symbolic"
        btn_play = Gtk.Button(label=play_label)
        btn_play.set_icon_name(play_icon)
        def toggle_play_action(_):
            self.video_context_popover.popdown()
            self.on_playpause_clicked(None)
        btn_play.connect("clicked", toggle_play_action)
        box.append(btn_play)

        # Bisu / Suara
        is_muted = self.player.mute
        mute_label = "Aktifkan Suara (m)" if is_muted else "Bisu (m)"
        mute_icon = "audio-volume-muted-symbolic" if is_muted else "audio-volume-high-symbolic"
        btn_mute = Gtk.Button(label=mute_label)
        btn_mute.set_icon_name(mute_icon)
        def toggle_mute_action(_):
            self.video_context_popover.popdown()
            self.on_mute_clicked(None)
        btn_mute.connect("clicked", toggle_mute_action)
        box.append(btn_mute)

        # Cuplikan Layar (Screenshot)
        btn_shot = Gtk.Button(label="Ambil Cuplikan Gambar (s)")
        btn_shot.set_icon_name("camera-photo-symbolic")
        def shot_action(_):
            self.video_context_popover.popdown()
            self.take_screenshot()
        btn_shot.connect("clicked", shot_action)
        box.append(btn_shot)

        # Pisahkan Window Video (Detach Picture-in-Picture)
        if not self._is_mini:
            btn_detach = Gtk.Button(label="Pisahkan Window Video (Detach)")
            btn_detach.set_icon_name("window-new-symbolic")
            def detach_action(_):
                self.video_context_popover.popdown()
                self.detach_video_window()
            btn_detach.connect("clicked", detach_action)
            box.append(btn_detach)

        self.video_context_popover.set_child(box)

    def on_key_press(self, controller, keyval, keycode, state):
        name = Gdk.keyval_name(keyval)
        if name == "Escape":
            if self._is_mini:
                self.mini_btn.set_active(False)
                return True
            elif self.is_fullscreen():
                self.unfullscreen()
                return True
        elif name == "space":
            self.on_playpause_clicked(None)
            return True
        elif name == "i":  # Inspector toggle
            if not self._is_mini:
                self.inspector_btn.set_active(not self.inspector_btn.get_active())
                return True
        elif name == "Right":
            self.player.seek(SEEK_STEP_SECONDS, reference="relative")
            return True
        elif name == "Left":
            self.player.seek(-SEEK_STEP_SECONDS, reference="relative")
            return True
        elif name == "Up":
            self.volume_scale.set_value(min(100, self.volume_scale.get_value() + VOLUME_STEP))
            return True
        elif name == "Down":
            self.volume_scale.set_value(max(0, self.volume_scale.get_value() - VOLUME_STEP))
            return True
        elif name == "f":
            self.on_fullscreen_clicked(None)
            return True
        elif name == "bracketleft":  # [ kurangi speed
            self.change_speed(-0.25)
            return True
        elif name == "bracketright":  # ] tambah speed
            self.change_speed(0.25)
            return True
        elif name in ("backslash", "BackSpace"):  # reset speed 1.0x
            self._set_speed(1.0)
            return True
        elif name == "l":  # A-B loop toggle
            self.toggle_ab_loop()
            return True
        elif name == "m":  # mute toggle
            self.on_mute_clicked(None)
            return True
        elif name == "s":  # screenshot / capture frame
            self.take_screenshot()
            return True
        elif name == "d":  # detach / separate video window
            self.detach_video_window()
            return True
        elif name == "Page_Up":  # previous chapter
            self.navigate_chapter(-1)
            return True
        elif name == "Page_Down":  # next chapter
            self.navigate_chapter(1)
            return True
        return False

    def on_drop(self, drop_target, gfile, x, y):
        path = gfile.get_path() if gfile else None
        if not path or not os.path.isfile(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext in SUBTITLE_EXTENSIONS:
            self._add_and_select_subtitle(path)
            return True
        self.add_to_playlist(path)
        self.open_file(path)
        return True

    def _connect_signals(self):
        # Motion controller untuk mendeteksi pergerakan kursor dan auto-hide OSD
        video_motion = Gtk.EventControllerMotion()
        video_motion.connect("motion", self._on_video_motion)
        self.video_overlay.add_controller(video_motion)

        # Gunakan gesture drag untuk mendeteksi saat slider mulai ditarik dan dilepas
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", lambda *_: self._set_dragging(True))
        drag.connect("drag-end", self._on_drag_end)
        self.seekbar.add_controller(drag)

        # Signal value-changed langsung merespon saat slider ditarik/digeser
        self.seekbar.connect("value-changed", self._on_seekbar_value_changed)

        # Hover motion & thumbnail preview pada seekbar
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_seekbar_motion)
        motion.connect("leave", self._on_seekbar_leave)
        self.seekbar.add_controller(motion)

    def _on_video_motion(self, controller, x, y):
        # Tampilkan OSD saat kursor bergerak
        if not self.osd_box.get_visible():
            self.osd_box.set_visible(True)

        if self._osd_hide_timeout_id:
            GLib.source_remove(self._osd_hide_timeout_id)
            self._osd_hide_timeout_id = None

        # Sembunyikan OSD jika video sedang play dan tidak sedang drag seekbar setelah 3 detik
        if not self.player.pause and not self._seekbar_user_dragging and not self._is_mini:
            self._osd_hide_timeout_id = GLib.timeout_add(3000, self._hide_osd_callback)

    def _hide_osd_callback(self):
        if not self.player.pause and not self._seekbar_user_dragging and not self._is_mini:
            self.osd_box.set_visible(False)
        self._osd_hide_timeout_id = None
        return False

    def _on_seekbar_motion(self, controller, x, y):
        try:
            duration = self.player.duration or 0
            alloc_width = self.seekbar.get_width()
            if duration > 0 and alloc_width > 0:
                fraction = max(0.0, min(1.0, x / alloc_width))
                hover_time = fraction * duration
                time_str = _format_time(hover_time)
                self.thumb_label.set_text(time_str)

                rect = Gdk.Rectangle()
                rect.x = int(x)
                rect.y = 0
                rect.width = 1
                rect.height = 1
                self.thumb_popover.set_pointing_to(rect)
                self.thumb_popover.popup()

                # Request thumbnail frame jika bukan URL online dan bukan file audio
                if self._current_path and not self._current_path.startswith(("http://", "https://")):
                    ext = os.path.splitext(self._current_path)[1].lower()
                    if ext not in AUDIO_EXTENSIONS:
                        self._request_thumbnail(int(hover_time))
        except Exception:
            pass

    def _on_seekbar_leave(self, controller):
        self.thumb_popover.popdown()

    def _request_thumbnail(self, sec):
        if not self._current_path or not os.path.exists(self._current_path):
            return
        if sec in self._thumb_cache:
            self.thumb_picture.set_filename(self._thumb_cache[sec])
            return
        if sec in self._thumb_pending:
            return

        self._thumb_pending.add(sec)

        def extract():
            out_file = os.path.join(self._thumb_temp_dir, f"thumb_{sec}.jpg")
            try:
                # Ambil snapshot cepat dengan ffmpeg
                cmd = [
                    "ffmpeg", "-ss", str(sec), "-i", self._current_path,
                    "-vframes", "1", "-s", "160x90", "-f", "image2", "-y", out_file
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                if os.path.exists(out_file):
                    self._thumb_cache[sec] = out_file
                    GLib.idle_add(lambda: self._on_thumbnail_ready(sec, out_file))
            except Exception:
                pass
            finally:
                self._thumb_pending.discard(sec)

        threading.Thread(target=extract, daemon=True).start()

    def _on_thumbnail_ready(self, sec, file_path):
        if self.thumb_popover.get_visible():
            self.thumb_picture.set_filename(file_path)

    def _set_dragging(self, value):
        self._seekbar_user_dragging = value

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self._apply_seek()
        self._seekbar_user_dragging = False

    def _on_seekbar_value_changed(self, scale):
        if self._seekbar_user_dragging:
            self._apply_seek()

    def _apply_seek(self):
        fraction = self.seekbar.get_value() / 1000.0
        try:
            duration = self.player.duration or 0
            if duration > 0:
                self.player.seek(fraction * duration, reference="absolute")
        except Exception:
            pass

    def _on_close_request(self, window):
        # Simpan posisi tontonan terakhir
        self._update_current_recent_position()
        # Simpan ukuran jendela ke konfigurasi
        if not self._is_mini and not self.is_fullscreen():
            self._config["width"] = self.get_width()
            self._config["height"] = self.get_height()
            _save_config(self._config)
        try:
            shutil.rmtree(self._thumb_temp_dir, ignore_errors=True)
        except Exception:
            pass
        self.mpris.unpublish()
        self.gl_area.shutdown_player()
        return False

    # --------------------------------------------------------------- poll

    def _update_playpause_icon(self):
        icon_name = "media-playback-pause-symbolic" if not self.player.pause else "media-playback-start-symbolic"
        self.playpause_btn.set_icon_name(icon_name)

    def _poll_mpv_state(self):
        try:
            pos = self.player.time_pos or 0
            duration = self.player.duration or 0
            if not self._seekbar_user_dragging and duration > 0:
                self.seekbar.set_value((pos / duration) * 1000.0)
            self.time_label.set_text(_format_time(pos))
            self.duration_label.set_text(_format_time(duration))
            self._update_playpause_icon()

            # Pastikan tampilan tetap pada video jika memutar stream video
            # (tapi jangan sentuh display_stack kalau video sedang di
            # jendela terpisah/detach — "video" tidak lagi terdaftar di
            # situ, jadi set_visible_child_name akan gagal terus-menerus).
            if not self.player.pause and self._current_path:
                if not self._is_music_mode:
                    if self.display_stack.get_visible_child_name() != "video":
                        self.display_stack.set_visible_child_name("video")
                self.gl_area.queue_render()

                # Simpan posisi periodik ke konfigurasi setiap ~10 detik
                if int(pos) > 0 and int(pos) % 10 == 0:
                    self._update_current_recent_position()

            current_spd = self.player.speed or 1.0
            spd_text = f"{current_spd:.2f}x".rstrip("0").rstrip(".") + "x"
            if self.playback_opts_btn.get_label() != spd_text:
                self.playback_opts_btn.set_label(spd_text)

            # Sinkronkan status ke MPRIS (now-playing GNOME/KDE, media keys, dll)
            self.mpris.notify_state_changed()

            # Deteksi pemutaran aktif untuk logika auto-advance playlist
            if pos > 0.5:
                self._has_played_media = True

            # Auto-advance ke trek berikutnya di playlist saat lagu/video selesai
            if self._has_played_media and self._current_path:
                current_mpv_path = None
                try:
                    current_mpv_path = self.player.path
                except Exception:
                    pass

                # Kondisi selesai: mpv sudah selesai memuat file (path jadi None/idle),
                # atau pos sudah mencapai durasi akhir (selisih < 0.35s)
                is_finished = (current_mpv_path is None) or (duration > 0 and pos >= duration - 0.35)
                if is_finished:
                    self._has_played_media = False
                    # Jika ada trek berikutnya di playlist, putar otomatis
                    if self.playlist and self.playlist_index + 1 < len(self.playlist):
                        next_path = self.playlist[self.playlist_index + 1]
                        GLib.idle_add(lambda: self.open_file(next_path))
        except Exception:
            pass
        return True


def _format_time(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

