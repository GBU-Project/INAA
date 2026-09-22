DEFAULT_SHORTCUTS = {
    "play_pause": "space",
    "seek_forward": "Right",
    "seek_backward": "Left",
    "volume_up": "Up",
    "volume_down": "Down",
    "fullscreen": "f",
    "inspector": "i",
    "mute": "m",
    "screenshot": "s",
    "mini_player": "d",
    "speed_down": "bracketleft",
    "speed_up": "bracketright",
    "speed_reset": "backslash",
    "ab_loop": "l",
    "chapter_prev": "Page_Up",
    "chapter_next": "Page_Down",
    "open_file": "Ctrl+o",
    "open_url": "Ctrl+l",
    "history": "Ctrl+h",
    "edit_shortcuts": "Ctrl+comma",
}

SHORTCUT_LABELS = {
    "play_pause": "Putar / Jeda",
    "seek_forward": "Maju 5 detik",
    "seek_backward": "Mundur 5 detik",
    "volume_up": "Naikkan volume",
    "volume_down": "Turunkan volume",
    "fullscreen": "Layar penuh",
    "inspector": "Inspector",
    "mute": "Bisu",
    "screenshot": "Cuplikan layar",
    "mini_player": "Mini player",
    "speed_down": "Kurangi kecepatan",
    "speed_up": "Tambah kecepatan",
    "speed_reset": "Reset kecepatan",
    "ab_loop": "A-B loop",
    "chapter_prev": "Bab sebelumnya",
    "chapter_next": "Bab berikutnya",
    "open_file": "Buka file",
    "open_url": "Buka URL",
    "history": "Riwayat pemutaran",
    "edit_shortcuts": "Sunting pintasan",
}

_MODIFIER_KEYS = {
    "Control_L", "Control_R", "Shift_L", "Shift_R",
    "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Super_L", "Super_R",
    "ISO_Level3_Shift", "Caps_Lock", "Num_Lock",
}


def merge_shortcuts(stored):
    merged = dict(DEFAULT_SHORTCUTS)
    if isinstance(stored, dict):
        for action, combo in stored.items():
            if action in DEFAULT_SHORTCUTS and isinstance(combo, str) and combo.strip():
                merged[action] = combo.strip()
    return merged


def combo_from_event(keyval_name, ctrl=False, alt=False, shift=False):
    if not keyval_name or keyval_name in _MODIFIER_KEYS:
        return None
    parts = []
    if ctrl:
        parts.append("Ctrl")
    if alt:
        parts.append("Alt")
    if shift and len(keyval_name) > 1:
        parts.append("Shift")
    parts.append(keyval_name)
    return "+".join(parts)


def invert_shortcuts(shortcuts):
    lookup = {}
    for action, combo in shortcuts.items():
        if combo:
            lookup[combo] = action
    return lookup
