"""Logika OSC (on-screen controller) yang murni, tanpa GTK (Phase 2.2).

`resolve_osc` menentukan bagaimana OSC ditampilkan dari `config["layout"]["osc"]`,
flag layout v2, dan keadaan jendela (mini player / fullscreen). Kontroller GTK di
`player_window/chrome.py` hanya menerapkan hasilnya.

Aturan:
  - flag v2 mati            -> perilaku lama: floating, bawah, ukuran regular
  - mini player             -> selalu floating dan terlihat (OSC satu-satunya kontrol)
  - fullscreen + docked     -> floating (tidak ada slot saat layar penuh)
  - mode off                -> OSC disembunyikan
  - docked                  -> menempati slot atas/bawah video, tidak auto-hide
"""
from __future__ import annotations

from typing import Any, Mapping

from layout_config import sanitize_layout

OSC_WIDTHS = {"compact": 360, "regular": 440, "large": 560}
DOCKED_HEIGHTS = {"compact": 64, "regular": 96, "large": 124}


def resolve_osc(
    layout: Mapping[str, Any] | None,
    *,
    enabled: bool,
    is_mini: bool = False,
    is_fullscreen: bool = False,
) -> dict:
    """Kembalikan {mode, slot, size, always_visible, visible, width, docked_height}."""
    osc = sanitize_layout(layout if enabled else None)["osc"]
    mode, position, size = osc["mode"], osc["position"], osc["size"]
    always = bool(osc["always_visible"])

    if is_mini:
        mode, size, always = "floating", "regular", True
    elif mode == "docked" and is_fullscreen:
        mode = "floating"

    visible = mode != "off"
    slot = position if mode == "docked" else None
    return {
        "mode": mode,
        "slot": slot,
        "size": size,
        "always_visible": always,
        "visible": visible,
        "width": OSC_WIDTHS[size],
        "docked_height": DOCKED_HEIGHTS[size] if slot else 0,
    }


def osc_auto_hide_allowed(state: Mapping[str, Any]) -> bool:
    """Auto-hide hanya untuk OSC floating yang tidak diset selalu terlihat."""
    return state["mode"] == "floating" and not state["always_visible"]


def resolve_header_mode(
    layout: Mapping[str, Any] | None, *, enabled: bool, legacy_auto_hide: bool = True
) -> str:
    """Mode header efektif: "full", "auto-hide", atau "hidden" (Phase 2.3).

    Flag v2 mati -> ikuti `auto_hide_chrome` lama. `hidden` aman di Wayland karena
    `player_window/header.py` memakai titlebar transparan (Gtk.WindowHandle +
    Gtk.WindowControls), bukan `set_decorated(False)`.
    """
    if not enabled:
        return "auto-hide" if legacy_auto_hide else "full"
    return sanitize_layout(layout)["headerbar"]


def auto_hide_flags(
    layout: Mapping[str, Any] | None,
    *,
    enabled: bool,
    legacy_auto_hide: bool,
    osc_state: Mapping[str, Any],
) -> tuple[bool, bool]:
    """Kembalikan (osd_auto_hide, header_auto_hide).

    Flag mati: OSC dan header sama-sama mengikuti `auto_hide_chrome` lama.
    Flag hidup: OSC mengikuti `layout.osc`, header mengikuti `layout.headerbar`.
    """
    header = resolve_header_mode(layout, enabled=enabled, legacy_auto_hide=legacy_auto_hide) == "auto-hide"
    osd = osc_auto_hide_allowed(osc_state) and (enabled or legacy_auto_hide)
    return osd, header


__all__ = [
    "OSC_WIDTHS", "DOCKED_HEIGHTS", "resolve_osc", "osc_auto_hide_allowed",
    "resolve_header_mode", "auto_hide_flags",
]
