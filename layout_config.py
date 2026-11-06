"""Model layout INAA yang murni (tanpa GTK) dan bisa dites tanpa display.

Dipakai oleh `config_sanitize.py` (validasi config.json) dan nanti oleh
`player_window/layout.py` (kontroller GTK, Phase 1). Semua nilai di sini
harus aman dipakai walau config.json diedit manual atau rusak.

Skema `layout` (lihat docs/ROADMAP-plugin-layout.md):

    layout:
      version: 1
      preset: classic
      playlist:  {edge, visible, width}
      inspector: {edge, visible, width}
      osc:       {mode, position, size, always_visible}
      headerbar: auto-hide
      theme:     {mode, palette, accent}
      reduce_motion: false
      lock_aspect: false
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

LAYOUT_VERSION = 1
CONFIG_VERSION = 2

EDGES = ("left", "right", "hidden")
OSC_MODES = ("floating", "docked", "off")
OSC_POSITIONS = ("top", "bottom")
OSC_SIZES = ("compact", "regular", "large")
HEADERBAR_MODES = ("full", "auto-hide", "hidden")
THEME_MODES = ("system", "dark", "light")
PALETTES = ("iina-glass", "graphite", "light")
ACCENTS = ("blue", "purple", "pink", "orange", "green", "graphite")
PRESET_NAMES = ("classic", "compact", "cinema", "music", "custom")

MIN_PANE_WIDTH = 160
MAX_PANE_WIDTH = 600

_TRUE = {"1", "true", "yes", "on"}


@dataclass
class LayoutState:
    """Nilai layout yang sudah tervalidasi. Urutan field = urutan di file."""

    version: int = LAYOUT_VERSION
    preset: str = "classic"
    playlist_edge: str = "left"
    playlist_visible: bool = True
    playlist_width: int = 260
    inspector_edge: str = "right"
    inspector_visible: bool = False
    inspector_width: int = 320
    osc_mode: str = "floating"
    osc_position: str = "bottom"
    osc_size: str = "regular"
    osc_always_visible: bool = False
    headerbar: str = "auto-hide"
    theme_mode: str = "dark"
    theme_palette: str = "iina-glass"
    theme_accent: str = "blue"
    reduce_motion: bool = False
    lock_aspect: bool = False

    # -- serialisasi -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "preset": self.preset,
            "playlist": {
                "edge": self.playlist_edge,
                "visible": self.playlist_visible,
                "width": self.playlist_width,
            },
            "inspector": {
                "edge": self.inspector_edge,
                "visible": self.inspector_visible,
                "width": self.inspector_width,
            },
            "osc": {
                "mode": self.osc_mode,
                "position": self.osc_position,
                "size": self.osc_size,
                "always_visible": self.osc_always_visible,
            },
            "headerbar": self.headerbar,
            "theme": {
                "mode": self.theme_mode,
                "palette": self.theme_palette,
                "accent": self.theme_accent,
            },
            "reduce_motion": self.reduce_motion,
            "lock_aspect": self.lock_aspect,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "LayoutState":
        clean = sanitize_layout(raw)
        return cls(
            preset=clean["preset"],
            playlist_edge=clean["playlist"]["edge"],
            playlist_visible=clean["playlist"]["visible"],
            playlist_width=clean["playlist"]["width"],
            inspector_edge=clean["inspector"]["edge"],
            inspector_visible=clean["inspector"]["visible"],
            inspector_width=clean["inspector"]["width"],
            osc_mode=clean["osc"]["mode"],
            osc_position=clean["osc"]["position"],
            osc_size=clean["osc"]["size"],
            osc_always_visible=clean["osc"]["always_visible"],
            headerbar=clean["headerbar"],
            theme_mode=clean["theme"]["mode"],
            theme_palette=clean["theme"]["palette"],
            theme_accent=clean["theme"]["accent"],
            reduce_motion=clean["reduce_motion"],
            lock_aspect=clean["lock_aspect"],
        )


def default_layout() -> dict:
    """Layout default dalam bentuk dict siap dimasukkan ke config.json."""
    return LayoutState().to_dict()


# Preset hanya menimpa nilai yang relevan; nama preset disimpan terpisah.
_PRESETS: dict[str, dict] = {
    "classic": {},
    "compact": {
        "playlist": {"edge": "left", "visible": True, "width": 220},
        "inspector": {"edge": "right", "visible": False, "width": 280},
        "osc": {"mode": "docked", "position": "bottom", "size": "compact"},
        "headerbar": "auto-hide",
    },
    "cinema": {
        "playlist": {"edge": "left", "visible": False, "width": 220},
        "inspector": {"edge": "right", "visible": False, "width": 320},
        "osc": {"mode": "floating", "position": "bottom", "size": "compact"},
        "headerbar": "hidden",
    },
    "music": {
        "playlist": {"edge": "right", "visible": True, "width": 300},
        "inspector": {"edge": "left", "visible": False, "width": 320},
        "osc": {"mode": "docked", "position": "bottom", "size": "regular"},
        "headerbar": "auto-hide",
    },
}


def _merge(base: dict, override: Mapping[str, Any]) -> dict:
    """Merge satu level; nilai nested dict digabung, bukan diganti total."""
    out = {}
    for key, value in base.items():
        if isinstance(value, dict):
            extra = override.get(key)
            out[key] = _merge(value, extra if isinstance(extra, Mapping) else {})
        else:
            out[key] = override.get(key, value)
    return out


def preset_layout(name: str) -> dict:
    """Kembalikan dict layout untuk preset. Nama tak dikenal -> classic."""
    key = name if name in _PRESETS else "classic"
    merged = _merge(default_layout(), _PRESETS[key])
    merged["preset"] = key if name != "custom" else "custom"
    return merged


# ---------------------------------------------------------------------------
# Validasi
# ---------------------------------------------------------------------------
def _bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    return default


def _width(value, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_PANE_WIDTH, min(MAX_PANE_WIDTH, number))


def _enum(value, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _section(raw: Mapping[str, Any] | None, key: str) -> Mapping[str, Any]:
    value = raw.get(key) if isinstance(raw, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def sanitize_layout(raw: Mapping[str, Any] | None) -> dict:
    """Kembalikan dict layout lengkap; key asing dibuang, nilai buruk di-default."""
    base = default_layout()
    if not isinstance(raw, Mapping):
        return base

    out = base
    out["preset"] = _enum(raw.get("preset"), PRESET_NAMES, base["preset"])

    playlist = _section(raw, "playlist")
    out["playlist"]["edge"] = _enum(playlist.get("edge"), EDGES, base["playlist"]["edge"])
    out["playlist"]["visible"] = _bool(playlist.get("visible"), base["playlist"]["visible"])
    out["playlist"]["width"] = _width(playlist.get("width"), base["playlist"]["width"])

    inspector = _section(raw, "inspector")
    out["inspector"]["edge"] = _enum(inspector.get("edge"), EDGES, base["inspector"]["edge"])
    out["inspector"]["visible"] = _bool(inspector.get("visible"), base["inspector"]["visible"])
    out["inspector"]["width"] = _width(inspector.get("width"), base["inspector"]["width"])

    osc = _section(raw, "osc")
    out["osc"]["mode"] = _enum(osc.get("mode"), OSC_MODES, base["osc"]["mode"])
    out["osc"]["position"] = _enum(osc.get("position"), OSC_POSITIONS, base["osc"]["position"])
    out["osc"]["size"] = _enum(osc.get("size"), OSC_SIZES, base["osc"]["size"])
    out["osc"]["always_visible"] = _bool(
        osc.get("always_visible"), base["osc"]["always_visible"]
    )

    out["headerbar"] = _enum(raw.get("headerbar"), HEADERBAR_MODES, base["headerbar"])

    theme = _section(raw, "theme")
    out["theme"]["mode"] = _enum(theme.get("mode"), THEME_MODES, base["theme"]["mode"])
    out["theme"]["palette"] = _enum(theme.get("palette"), PALETTES, base["theme"]["palette"])
    out["theme"]["accent"] = _enum(theme.get("accent"), ACCENTS, base["theme"]["accent"])

    out["reduce_motion"] = _bool(raw.get("reduce_motion"), base["reduce_motion"])
    out["lock_aspect"] = _bool(raw.get("lock_aspect"), base["lock_aspect"])
    return out


def layout_from_config(config: Mapping[str, Any] | None) -> dict:
    """Ambil `layout` dari config lengkap (bukan hanya section layout)."""
    if not isinstance(config, Mapping):
        return default_layout()
    return sanitize_layout(config.get("layout"))


DOCK_NAMES = ("playlist", "inspector")
DEFAULT_EDGES = {"playlist": "left", "inspector": "right"}


def dock_sides(layout: Mapping[str, Any] | None) -> tuple[list[str], list[str]]:
    """Kembalikan `(kiri, kanan)`: nama dock yang benar-benar tampil.

    Urutan kiri = dari luar ke dalam, kanan = dari dalam ke luar. Dipakai
    controller GTK untuk menyusun ulang rantai `Gtk.Paned`.
    """
    clean = sanitize_layout(layout)
    left: list[str] = []
    right: list[str] = []
    for name in DOCK_NAMES:
        section = clean[name]
        if not section["visible"] or section["edge"] == "hidden":
            continue
        if section["edge"] == "left":
            left.append(name)
        else:
            right.insert(0, name)
    return left, right


# ---------------------------------------------------------------------------
# Migrasi config
# ---------------------------------------------------------------------------
def migrate_layout_config(data: dict) -> dict:
    """Tambahkan `layout` + `config_version`; idempoten.

    Config v1 tidak punya section layout. Satu-satunya preferensi lama yang
    setara adalah `auto_hide_chrome`; petakan ke mode headerbar supaya
    pengguna tidak kehilangan setelannya.
    """
    if not isinstance(data, dict):
        return data

    layout = data.get("layout")
    if not isinstance(layout, dict):
        layout = {}

    version = data.get("config_version")
    if not isinstance(version, int) or version < CONFIG_VERSION:
        if "headerbar" not in layout:
            layout["headerbar"] = "auto-hide" if data.get("auto_hide_chrome", True) else "full"
        data["layout"] = layout
        data["config_version"] = CONFIG_VERSION
    else:
        data["layout"] = layout
    return data


def layout_v2_enabled(config: Mapping[str, Any] | None, env: Mapping[str, str] | None = None) -> bool:
    """Feature flag Phase 0/1. Env `INAA_LAYOUT_V2=1` menang atas config."""
    env = os.environ if env is None else env
    if str(env.get("INAA_LAYOUT_V2", "")).strip().lower() in _TRUE:
        return True
    if not isinstance(config, Mapping):
        return False
    return config.get("ui_layout_v2") is True


__all__ = [
    "LAYOUT_VERSION", "CONFIG_VERSION", "EDGES", "OSC_MODES", "OSC_POSITIONS",
    "OSC_SIZES", "HEADERBAR_MODES", "THEME_MODES", "PALETTES", "ACCENTS",
    "PRESET_NAMES", "MIN_PANE_WIDTH", "MAX_PANE_WIDTH",
    "LayoutState", "default_layout", "preset_layout", "sanitize_layout",
    "layout_from_config", "migrate_layout_config", "layout_v2_enabled",
    "DOCK_NAMES", "DEFAULT_EDGES", "dock_sides",
]
