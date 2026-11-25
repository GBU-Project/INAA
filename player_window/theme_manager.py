"""ThemeManager: satu Gtk.CssProvider yang dimuat ulang saat tema berubah.

Logika keputusan (palet efektif, parsing portal, reduce motion) ada di
`theme_logic.py` (murni, dites tanpa GTK); stylesheet dibuat `theme_css.build_css`.
Modul ini hanya menyambungkannya ke GTK dan D-Bus:

  - satu provider dipasang sekali ke display, isinya diganti saat tema berubah;
  - mode "system" mengikuti portal freedesktop `org.freedesktop.appearance color-scheme`
    (dibaca sekali dengan timeout, lalu mendengarkan sinyal `SettingChanged`);
  - reduce motion: config `layout.reduce_motion` atau `gtk-enable-animations` mati
    -> CSS tanpa transisi + kelas `reduce-motion` pada window.
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from layout_config import sanitize_layout
from palette import get_palette
from theme_css import build_css_bytes
from theme_logic import (
    parse_portal_color_scheme,
    resolve_accent,
    resolve_palette_name,
    should_reduce_motion,
)

_PORTAL_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_SETTINGS = "org.freedesktop.portal.Settings"
_APPEARANCE_NS = "org.freedesktop.appearance"
_COLOR_SCHEME_KEY = "color-scheme"
# Batas tunggu panggilan D-Bus sinkron saat startup; portal lambat tidak boleh menahan jendela.
_PORTAL_TIMEOUT_MS = 1000


class ThemeManager:
    """Memasang dan memperbarui tema aplikasi dari `config["layout"]`."""

    def __init__(self, config: dict):
        self._config = config
        self._window = None
        self._system_prefers_dark = None  # True/False/None (tidak diketahui)
        self._signature = None

        self._provider = Gtk.CssProvider()
        self._display = Gdk.Display.get_default()
        if self._display is not None:
            Gtk.StyleContext.add_provider_for_display(
                self._display, self._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        self._settings = Gtk.Settings.get_default()
        self._settings_handler = None
        self._orig_prefer_dark = None
        if self._settings is not None:
            try:
                self._orig_prefer_dark = bool(
                    self._settings.get_property("gtk-application-prefer-dark-theme")
                )
            except Exception:
                self._orig_prefer_dark = None
            self._settings_handler = self._settings.connect(
                "notify::gtk-enable-animations", self._on_gtk_animations_changed
            )

        self._portal = None
        self._portal_handler = None
        self._init_portal()

        self.apply()

    # -- config --------------------------------------------------------------
    def _layout(self) -> dict:
        return sanitize_layout(self._config.get("layout"))

    @property
    def reduce_motion(self) -> bool:
        """True bila animasi harus dimatikan (untuk transisi yang diatur dari kode)."""
        gtk_animations = None
        if self._settings is not None:
            try:
                gtk_animations = bool(self._settings.get_property("gtk-enable-animations"))
            except Exception:
                gtk_animations = None
        return should_reduce_motion(self._layout()["reduce_motion"], gtk_animations)

    # -- window --------------------------------------------------------------
    def set_window(self, window) -> None:
        self._window = window
        self._sync_window_class()

    def _sync_window_class(self) -> None:
        if self._window is None:
            return
        if self.reduce_motion:
            self._window.add_css_class("reduce-motion")
        else:
            self._window.remove_css_class("reduce-motion")

    # -- portal --------------------------------------------------------------
    def _init_portal(self) -> None:
        """Baca preferensi OS dan dengarkan perubahannya; semua kegagalan -> None."""
        try:
            self._portal = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                # Jangan mengaktifkan portal bila belum jalan (bisa menunggu lama di sesi
                # D-Bus kosong, mis. CI/tes); portal yang sudah ada tetap dibaca.
                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES | Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                _PORTAL_NAME,
                _PORTAL_PATH,
                _PORTAL_SETTINGS,
                None,
            )
            reply = self._portal.call_sync(
                "Read",
                GLib.Variant("(ss)", (_APPEARANCE_NS, _COLOR_SCHEME_KEY)),
                Gio.DBusCallFlags.NO_AUTO_START,
                _PORTAL_TIMEOUT_MS,
                None,
            )
            self._system_prefers_dark = parse_portal_color_scheme(reply)
            self._portal_handler = self._portal.connect("g-signal", self._on_portal_signal)
        except Exception:
            self._portal = None
            self._portal_handler = None
            self._system_prefers_dark = None

    def _on_portal_signal(self, _proxy, _sender, signal_name, parameters) -> None:
        if signal_name != "SettingChanged":
            return
        try:
            namespace, key, value = parameters.unpack()
        except Exception:
            return
        if namespace == _APPEARANCE_NS and key == _COLOR_SCHEME_KEY:
            self._system_prefers_dark = parse_portal_color_scheme(value)
            self.apply()

    def _on_gtk_animations_changed(self, *_args) -> None:
        self.apply()

    # -- terapkan ------------------------------------------------------------
    def apply(self) -> None:
        """Terapkan tema dari config saat ini; tidak melakukan apa-apa bila tak ada perubahan."""
        layout = self._layout()
        theme = layout["theme"]
        palette_name = resolve_palette_name(theme, self._system_prefers_dark)
        accent = resolve_accent(theme)
        reduce_motion = self.reduce_motion
        is_dark = get_palette(palette_name).is_dark

        signature = (palette_name, accent, reduce_motion)
        if signature != self._signature:
            css = build_css_bytes(palette_name, accent, reduce_motion)
            try:
                self._provider.load_from_bytes(GLib.Bytes.new(css))
            except AttributeError:  # GTK < 4.12
                self._provider.load_from_data(css)
            self._sync_gtk_dark_pref(is_dark)
            self._signature = signature
        self._sync_window_class()

    def _sync_gtk_dark_pref(self, palette_is_dark: bool) -> None:
        """Selaraskan `gtk-application-prefer-dark-theme` hanya bila perlu.

        Palet terang memaksa False (widget bawaan ikut terang). Palet gelap TIDAK memaksa
        True: nilai asli dipulihkan. Memaksa varian gelap membuat GTK memuat ulang tema
        pengguna dan bisa memicu varian tema yang rusak; perilaku lama aplikasi
        (tidak menyentuh properti ini) dipertahankan untuk palet gelap.
        """
        if self._settings is None or self._orig_prefer_dark is None:
            return
        want = self._orig_prefer_dark if palette_is_dark else False
        try:
            current = bool(self._settings.get_property("gtk-application-prefer-dark-theme"))
            if current != want:
                self._settings.set_property("gtk-application-prefer-dark-theme", want)
        except Exception:
            pass

    # -- penutupan -----------------------------------------------------------
    def shutdown(self) -> None:
        if self._portal is not None and self._portal_handler is not None:
            try:
                self._portal.disconnect(self._portal_handler)
            except Exception:
                pass
        self._portal_handler = None
        self._portal = None
        if self._settings is not None and self._settings_handler is not None:
            try:
                self._settings.disconnect(self._settings_handler)
            except Exception:
                pass
        self._settings_handler = None
        if self._display is not None:
            try:
                Gtk.StyleContext.remove_provider_for_display(self._display, self._provider)
            except Exception:
                pass
        self._window = None
        self._signature = None
