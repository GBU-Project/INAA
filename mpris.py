"""
MPRIS2 integration for INAA.

MPRIS (Media Player Remote Interfacing Specification) is the standard
D-Bus interface Linux desktops use to let media players show up in:
- GNOME Shell / KDE Plasma "now playing" widgets and lock screen controls
- Multimedia keyboard keys (Play/Pause/Next/Previous) — the desktop
  environment's media-key handler looks for the currently active MPRIS
  player on the session bus and calls its methods; we don't need to grab
  keyboard shortcuts ourselves for this to work.
- Tools like `playerctl`, Waybar/GNOME top bar media widgets, etc.

Spec reference: https://specifications.freedesktop.org/mpris-spec/latest/

This module intentionally fails soft: if the D-Bus session bus isn't
available (e.g. some minimal/headless environments), INAA still runs
fine without MPRIS — publish() just returns False and logs a note.
"""
import hashlib
import os

from media_uri import is_local_media_file, normalize_media_uri

try:
    from pydbus import SessionBus
    from gi.repository import GLib
    _PYDBUS_AVAILABLE = True
except Exception:
    _PYDBUS_AVAILABLE = False


_MPRIS_XML = """
<node>
  <interface name='org.mpris.MediaPlayer2'>
    <method name='Raise'/>
    <method name='Quit'/>
    <property name='CanQuit' type='b' access='read'/>
    <property name='CanRaise' type='b' access='read'/>
    <property name='HasTrackList' type='b' access='read'/>
    <property name='Identity' type='s' access='read'/>
    <property name='DesktopEntry' type='s' access='read'/>
    <property name='SupportedUriSchemes' type='as' access='read'/>
    <property name='SupportedMimeTypes' type='as' access='read'/>
  </interface>
  <interface name='org.mpris.MediaPlayer2.Player'>
    <method name='Next'/>
    <method name='Previous'/>
    <method name='Pause'/>
    <method name='PlayPause'/>
    <method name='Stop'/>
    <method name='Play'/>
    <method name='Seek'>
      <arg direction='in' type='x' name='Offset'/>
    </method>
    <method name='SetPosition'>
      <arg direction='in' type='o' name='TrackId'/>
      <arg direction='in' type='x' name='Position'/>
    </method>
    <method name='OpenUri'>
      <arg direction='in' type='s' name='Uri'/>
    </method>
    <property name='PlaybackStatus' type='s' access='read'/>
    <property name='LoopStatus' type='s' access='readwrite'/>
    <property name='Rate' type='d' access='readwrite'/>
    <property name='Shuffle' type='b' access='readwrite'/>
    <property name='Metadata' type='a{sv}' access='read'/>
    <property name='Volume' type='d' access='readwrite'/>
    <property name='Position' type='x' access='read'/>
    <property name='MinimumRate' type='d' access='read'/>
    <property name='MaximumRate' type='d' access='read'/>
    <property name='CanGoNext' type='b' access='read'/>
    <property name='CanGoPrevious' type='b' access='read'/>
    <property name='CanPlay' type='b' access='read'/>
    <property name='CanPause' type='b' access='read'/>
    <property name='CanSeek' type='b' access='read'/>
    <property name='CanControl' type='b' access='read'/>
  </interface>
</node>
"""


class MprisPlayer:
    """Publishes an INAA PlayerWindow on the D-Bus session bus as an
    MPRIS2 media player (org.mpris.MediaPlayer2.inaa)."""

    dbus = _MPRIS_XML

    def __init__(self, window):
        self._win = window
        self._bus = None
        self._reg = None
        self._last_status = None
        self._last_track_key = None

    # ------------------------------------------------------------- setup

    def publish(self):
        if not _PYDBUS_AVAILABLE:
            print("[MPRIS] pydbus tidak tersedia, integrasi MPRIS dilewati.")
            return False
        try:
            self._bus = SessionBus()
            self._reg = self._bus.publish(
                "org.mpris.MediaPlayer2.inaa",
                ("/org/mpris/MediaPlayer2", self),
            )
            return True
        except Exception as e:
            # Common on headless/minimal sessions with no session bus.
            print(f"[MPRIS] Tidak bisa publish ke D-Bus session bus: {e}")
            self._bus = None
            self._reg = None
            return False

    def unpublish(self):
        if self._reg is not None:
            try:
                self._reg.unpublish()
            except Exception:
                pass
            self._reg = None

    @property
    def is_published(self):
        return self._reg is not None

    # --------------------------------------------------- MediaPlayer2 root

    def Raise(self):
        self._win.present()

    def Quit(self):
        self._win.close()

    @property
    def CanQuit(self):
        return True

    @property
    def CanRaise(self):
        return True

    @property
    def HasTrackList(self):
        return False

    @property
    def Identity(self):
        return "INAA"

    @property
    def DesktopEntry(self):
        return "inaa"

    @property
    def SupportedUriSchemes(self):
        return ["file"]

    @property
    def SupportedMimeTypes(self):
        return [
            "video/mp4", "video/x-matroska", "video/webm",
            "video/x-msvideo", "video/quicktime",
            "audio/mpeg", "audio/flac", "audio/x-wav", "audio/ogg",
        ]

    # ------------------------------------------------------- Player iface

    def Next(self):
        self._win.play_relative(1)

    def Previous(self):
        self._win.play_relative(-1)

    def Pause(self):
        try:
            if not self._win.player.pause:
                self._win.on_playpause_clicked(None)
        except Exception:
            pass

    def Play(self):
        try:
            if self._win.player.pause:
                self._win.on_playpause_clicked(None)
        except Exception:
            pass

    def PlayPause(self):
        try:
            self._win.on_playpause_clicked(None)
        except Exception:
            pass

    def Stop(self):
        try:
            self._win.player.pause = True
        except Exception:
            pass

    def Seek(self, offset_us):
        try:
            self._win.player.seek(offset_us / 1_000_000, reference="relative", precision="exact")
        except Exception:
            pass

    def SetPosition(self, track_id, position_us):
        try:
            self._win.player.seek(position_us / 1_000_000, reference="absolute", precision="exact")
        except Exception:
            pass

    def OpenUri(self, uri):
        path = normalize_media_uri(uri)
        if not is_local_media_file(path):
            return
        self._win.add_to_playlist(path)
        self._win.open_file(path)

    @property
    def PlaybackStatus(self):
        try:
            if self._win.player.path is None:
                return "Stopped"
            return "Paused" if self._win.player.pause else "Playing"
        except Exception:
            return "Stopped"

    @property
    def LoopStatus(self):
        from playlist_nav import loop_status_mpris
        return loop_status_mpris(getattr(self._win, "_loop_mode", "off"))

    @LoopStatus.setter
    def LoopStatus(self, value):
        mapping = {"None": "off", "Track": "one", "Playlist": "all"}
        mode = mapping.get(value)
        if mode:
            self._win._set_loop_mode(mode)

    @property
    def Rate(self):
        try:
            return float(self._win.player.speed or 1.0)
        except Exception:
            return 1.0

    @Rate.setter
    def Rate(self, value):
        try:
            self._win._set_speed(float(value))
        except Exception:
            pass

    @property
    def Shuffle(self):
        return bool(getattr(self._win, "_shuffle", False))

    @Shuffle.setter
    def Shuffle(self, value):
        self._win._set_shuffle(bool(value))

    @property
    def Metadata(self):
        path = None
        duration = 0
        try:
            path = self._win.player.path
            duration = self._win.player.duration or 0
        except Exception:
            pass

        if not path:
            return {"mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/inaa/NoTrack")}

        title = os.path.basename(path)
        digest = hashlib.sha256(path.encode("utf-8", errors="replace")).hexdigest()[:16]
        track_id = f"/org/mpris/MediaPlayer2/inaa/track/{digest}"

        metadata = {
            "mpris:trackid": GLib.Variant("o", track_id),
            "mpris:length": GLib.Variant("x", int(duration * 1_000_000)),
            "xesam:title": GLib.Variant("s", title),
            "xesam:url": GLib.Variant("s", path if "://" in path else f"file://{path}"),
        }
        return metadata

    @property
    def Volume(self):
        try:
            return (self._win.player.volume or 0) / 100.0
        except Exception:
            return 1.0

    @Volume.setter
    def Volume(self, value):
        try:
            self._win.player.volume = max(0.0, min(100.0, value * 100.0))
        except Exception:
            pass

    @property
    def Position(self):
        try:
            return int((self._win.player.time_pos or 0) * 1_000_000)
        except Exception:
            return 0

    @property
    def MinimumRate(self):
        return 0.25

    @property
    def MaximumRate(self):
        return 4.0

    @property
    def CanGoNext(self):
        return True

    @property
    def CanGoPrevious(self):
        return True

    @property
    def CanPlay(self):
        return True

    @property
    def CanPause(self):
        return True

    @property
    def CanSeek(self):
        return True

    @property
    def CanControl(self):
        return True

    # ------------------------------------------------------- change sync

    def notify_state_changed(self):
        """Call this periodically (or on state-changing actions) so the
        desktop's now-playing widgets and lock screen stay in sync. Only
        emits a D-Bus signal when something actually changed, to avoid
        spamming the session bus."""
        if self._reg is None:
            return
        try:
            status = self.PlaybackStatus
            path = None
            try:
                path = self._win.player.path
            except Exception:
                pass

            changed = {}
            if status != self._last_status:
                changed["PlaybackStatus"] = GLib.Variant("s", status)
                self._last_status = status
            if path != self._last_track_key:
                changed["Metadata"] = GLib.Variant("a{sv}", self.Metadata)
                self._last_track_key = path

            if changed:
                self._emit_properties_changed("org.mpris.MediaPlayer2.Player", changed)
        except Exception as e:
            print(f"[MPRIS] notify_state_changed error: {e}")

    def _emit_properties_changed(self, iface, changed):
        try:
            self._bus.con.emit_signal(
                None,
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (iface, changed, [])),
            )
        except Exception as e:
            print(f"[MPRIS] emit_properties_changed error: {e}")
