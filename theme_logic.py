"""Logika tema murni (tanpa GTK/D-Bus): bisa dites tanpa display.

Dipakai oleh `player_window/theme_manager.py`:
  - `resolve_palette_name`: mode (system/dark/light) + palet pilihan + preferensi OS -> palet efektif.
  - `parse_portal_color_scheme`: nilai portal freedesktop `color-scheme` -> bool | None.
  - `should_reduce_motion`: config + `gtk-enable-animations` -> bool.
"""
from __future__ import annotations

from typing import Any, Mapping

from palette import ACCENT_NAMES, PALETTE_NAMES, get_palette

DEFAULT_PALETTE = "iina-glass"
LIGHT_PALETTE = "light"
DEFAULT_ACCENT = "blue"


def resolve_accent(theme: Mapping[str, Any] | None) -> str:
    accent = theme.get("accent") if isinstance(theme, Mapping) else None
    return accent if accent in ACCENT_NAMES else DEFAULT_ACCENT


def resolve_palette_name(theme: Mapping[str, Any] | None, system_prefers_dark: bool | None) -> str:
    """Palet efektif.

    - mode "light": selalu `light`.
    - mode "dark": palet pilihan bila gelap, selain itu `iina-glass`.
    - mode "system" (dan nilai tak dikenal): ikuti OS; OS terang -> `light`,
      OS gelap atau tidak diketahui (None) -> seperti "dark".
    """
    if not isinstance(theme, Mapping):
        theme = {}
    mode = theme.get("mode")
    chosen = theme.get("palette")
    if chosen not in PALETTE_NAMES:
        chosen = DEFAULT_PALETTE

    if mode == "light":
        return LIGHT_PALETTE
    if mode == "dark":
        want_dark = True
    else:
        want_dark = system_prefers_dark is not False
    if not want_dark:
        return LIGHT_PALETTE
    return chosen if get_palette(chosen).is_dark else DEFAULT_PALETTE


def parse_portal_color_scheme(value: Any) -> bool | None:
    """Nilai `org.freedesktop.appearance color-scheme`: 1=gelap, 2=terang, selain itu None.

    Menerima int, GLib.Variant (berlapis `v`/tuple), atau tuple/list satu elemen.
    """
    for _ in range(8):
        if hasattr(value, "unpack"):
            try:
                value = value.unpack()
            except Exception:
                return None
        elif isinstance(value, (tuple, list)) and len(value) == 1:
            value = value[0]
        else:
            break
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return {1: True, 2: False}.get(value)


def should_reduce_motion(reduce_motion_cfg: bool, gtk_animations_enabled: bool | None) -> bool:
    """True bila diminta di config atau animasi GTK dimatikan sistem."""
    return bool(reduce_motion_cfg) or gtk_animations_enabled is False


__all__ = [
    "DEFAULT_PALETTE", "LIGHT_PALETTE", "DEFAULT_ACCENT",
    "resolve_accent", "resolve_palette_name",
    "parse_portal_color_scheme", "should_reduce_motion",
]
