"""Pembersih config.json: nilai rusak/diubah manual tidak boleh membuat aplikasi crash saat start.

Murni (tanpa GTK) agar bisa dites. Mengubah dict di tempat dan mengembalikannya.
"""
from __future__ import annotations

import math

from audio_devices import AUTO as _AUTO_DEVICE, is_valid_name as _valid_device
from audio_filters import EQ_PRESETS, SPECIAL_AUDIO_EFFECTS, clamp_gain

MAX_RECENT = 300
MAX_TEXT = 4096
MAX_CUSTOM_PRESETS = 50


def _num(value, default, low=0.0, high=1e9):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(low, min(high, number))


def _gains(value):
    items = value if isinstance(value, (list, tuple)) else []
    out = []
    for i in range(10):
        try:
            number = float(items[i])
        except (IndexError, TypeError, ValueError):
            number = 0.0
        out.append(clamp_gain(number if math.isfinite(number) else 0.0))
    return out


def _recent(entries):
    if not isinstance(entries, list):
        return []
    out, seen = [], set()
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip() or len(path) > MAX_TEXT or "\x00" in path or path in seen:
            continue
        seen.add(path)
        item = dict(raw)
        item["path"] = path
        title = raw.get("title")
        item["title"] = title[:300] if isinstance(title, str) else ""
        item["position"] = round(_num(raw.get("position"), 0.0), 1)
        item["duration"] = round(_num(raw.get("duration"), 0.0), 1)
        last = raw.get("last_played", "")
        item["last_played"] = last if isinstance(last, str) else ""
        out.append(item)
        if len(out) >= MAX_RECENT:
            break
    return out


def sanitize_config(data):
    if not isinstance(data, dict):
        return {}
    data["recent_files"] = _recent(data.get("recent_files"))
    data["audio_eq_gains"] = _gains(data.get("audio_eq_gains"))

    presets = data.get("audio_custom_presets")
    clean = {}
    if isinstance(presets, dict):
        reserved = {n.casefold() for n in EQ_PRESETS} | {"custom"}
        for name, gains in presets.items():
            if (isinstance(name, str) and name.strip() and len(name) <= 40
                    and name.casefold() not in reserved and len(clean) < MAX_CUSTOM_PRESETS):
                clean[name] = _gains(gains)
    data["audio_custom_presets"] = clean

    device = data.get("audio_device")
    data["audio_device"] = device if _valid_device(device) else _AUTO_DEVICE

    effect = data.get("audio_special_effect")
    data["audio_special_effect"] = effect if effect in SPECIAL_AUDIO_EFFECTS else "none"
    preset = data.get("audio_eq_preset")
    data["audio_eq_preset"] = preset if isinstance(preset, str) and len(preset) <= 40 else "custom"

    for key in ("enabled_plugins", "custom_shaders"):
        value = data.get(key)
        data[key] = (
            [v for v in value if isinstance(v, str) and v.strip() and len(v) <= MAX_TEXT and "\x00" not in v]
            if isinstance(value, list) else []
        )
    if not isinstance(data.get("shortcuts"), dict):
        data["shortcuts"] = {}
    data["volume"] = _num(data.get("volume"), 100, 0, 100)
    data["width"] = int(_num(data.get("width"), 1000, 200, 10000))
    data["height"] = int(_num(data.get("height"), 620, 150, 10000))
    return data
