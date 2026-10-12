"""Pemilihan perangkat output audio: logika murni (tanpa GTK).

mpv menerima nama perangkat APA SAJA tanpa error (lalu suara hilang), jadi INAA hanya
mengizinkan nama yang benar-benar dilaporkan mpv lewat `audio-device-list`.
"""
from __future__ import annotations

AUTO = "auto"
AUTO_LABEL = "Otomatis (default sistem)"
MAX_NAME = 200
MAX_DESC = 120


def is_valid_name(name) -> bool:
    return (
        isinstance(name, str)
        and 0 < len(name) <= MAX_NAME
        and not any(ch in name for ch in ("\x00", "\n", "\r", "\t"))
    )


def parse_device_list(raw):
    """Daftar [(name, label)] yang bersih; 'auto' selalu pertama. Tahan data rusak."""
    devices = [(AUTO, AUTO_LABEL)]
    seen = {AUTO}
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not is_valid_name(name) or name in seen:
                continue
            seen.add(name)
            desc = item.get("description")
            desc = " ".join(desc.split())[:MAX_DESC] if isinstance(desc, str) else ""
            devices.append((name, desc or name))
    return devices


def choose_device(saved, devices) -> str:
    """Perangkat tersimpan bila masih tersedia, jika tidak 'auto' (mis. USB dicabut)."""
    names = {n for n, _ in devices}
    return saved if is_valid_name(saved) and saved in names else AUTO
