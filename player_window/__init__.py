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

--------------------------------------------------------------------------
Module layout (split from a single 2800+ line file for maintainability):

    player_window/
        common.py           shared imports, constants, config load/save,
                             GL proc-address resolution, small helpers
        gl_area.py           MpvGLArea (the Gtk.GLArea mpv renders into)
        ui_builder.py         UIBuilderMixin      - widget construction
        playlist_mixin.py     PlaylistMixin       - recent files / playlist
        playback_mixin.py     PlaybackMixin       - transport controls
        subtitles_mixin.py    SubtitlesMixin      - subtitle tracks/styling
        filters_mixin.py      FiltersMixin        - video/audio inspector
        input_mixin.py        InputMixin          - mouse/keyboard/gestures
        shortcuts_mixin.py    ShortcutsMixin      - shortcut editor dialog
        window_mixin.py       WindowMixin         - toasts, screenshots,
                                                     mini-player, dialogs

    PlayerWindow itself only keeps __init__ and _on_close_request; every
    other method lives in one of the mixins above and is composed back
    together via multiple inheritance below. External code should keep
    importing `from player_window import PlayerWindow` — the public API
    is unchanged, only the internal organization is.
--------------------------------------------------------------------------
"""
import shutil
import tempfile

from gi.repository import GLib, Gtk

from mpris import MprisPlayer

from .common import _load_config, _save_config
from .gl_area import MpvGLArea
from .ui_builder import UIBuilderMixin
from .playlist_mixin import PlaylistMixin
from .playback_mixin import PlaybackMixin
from .subtitles_mixin import SubtitlesMixin
from .filters_mixin import FiltersMixin
from .input_mixin import InputMixin
from .shortcuts_mixin import ShortcutsMixin
from .window_mixin import WindowMixin
from .prefs_mixin import PrefsMixin
from .audio_device_mixin import AudioDeviceMixin
from .theme import _apply_iina_css

__all__ = ["PlayerWindow", "MpvGLArea"]


class PlayerWindow(
    PrefsMixin,
    AudioDeviceMixin,
    WindowMixin,
    InputMixin,
    ShortcutsMixin,
    FiltersMixin,
    SubtitlesMixin,
    PlaybackMixin,
    PlaylistMixin,
    UIBuilderMixin,
    Gtk.ApplicationWindow,
):
    """Main INAA player window.

    Behaviour is unchanged from the original monolithic implementation;
    only the source layout changed. Each mixin above owns one cohesive
    area of functionality (see the module docstring for the map), and
    this class exists mainly to hold __init__ / window-close handling
    and to declare the composition order.
    """

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
        self._loop_mode = self._config.get("loop_mode", "off")
        if self._loop_mode not in ("off", "all", "one"):
            self._loop_mode = "off"
        self._shuffle = bool(self._config.get("shuffle", False))
        self._updating_shuffle_ui = False
        self._window_fitted_for = None
        self._chrome_visible = True

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

        # Terapkan shader yang tersimpan
        self._apply_saved_shaders()

        # Perangkat output audio tersimpan (hanya jika masih tersedia)
        self._apply_saved_audio_device()

        # mpv.conf (hanya opsi aman, opt-in) dan script eksplisit
        self._apply_user_mpv_settings()

        # Terapkan filter equalizer & audio yang tersimpan
        self._apply_audio_filters()

        # Muat plugin pengguna (IINA-style: Info.json + explicit enable)
        self._load_plugins()

        # Integrasi MPRIS (media control sistem: GNOME/KDE now-playing,
        # tombol media keyboard, lock screen). Gagal dengan lembut kalau
        # session bus tidak tersedia.
        self.mpris = MprisPlayer(self)
        self.mpris.publish()

        GLib.timeout_add(200, self._poll_mpv_state)

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

