"""Modul equalizer audio dan filter audio INAA yang aman (allowlist).

Semua kalkulasi filter audio (10-band equalizer, preset audio) diisolasi
dalam modul ini dengan sintaks filter mpv yang divalidasi ketat agar tidak
membuka celah injeksi graf libavfilter (lavfi) atau jalur file sewenang-wenang.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# 10 Band standar ISO / IINA (Hz)
EQ_BANDS: Tuple[float, ...] = (
    31.25,
    62.5,
    125.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    4000.0,
    8000.0,
    16000.0,
)

EQ_BAND_LABELS: Tuple[str, ...] = (
    "31Hz",
    "62Hz",
    "125Hz",
    "250Hz",
    "500Hz",
    "1kHz",
    "2kHz",
    "4kHz",
    "8kHz",
    "16kHz",
)

# Preset equalizer 10-band (gain dalam dB, rentang -12 dB s/d +12 dB)
EQ_PRESETS: Dict[str, Tuple[float, ...]] = {
    "flat": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "bass_boost": (6.0, 5.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    "vocal_boost": (-2.0, -1.0, 0.0, 2.0, 4.0, 4.0, 3.0, 1.0, 0.0, -1.0),
    "electronic": (5.0, 4.0, 2.0, 0.0, -2.0, 2.0, 1.0, 3.0, 4.0, 5.0),
    "rock": (5.0, 3.5, 2.0, -1.0, -2.0, 0.0, 2.5, 3.5, 4.0, 4.5),
    "pop": (-1.5, 1.5, 3.0, 3.5, 2.0, -1.0, -1.5, -1.5, 1.0, 2.0),
    "classical": (4.5, 3.5, 2.5, 1.5, -1.0, -1.0, 0.0, 2.0, 3.0, 3.5),
    "party": (5.0, 4.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.5, 5.0),
    "acoustic": (3.5, 2.5, 1.5, 1.0, 1.5, 1.5, 2.5, 3.0, 2.5, 2.0),
}

# Allowlist preset efek audio khusus
SPECIAL_AUDIO_EFFECTS = {
    "none": "",
    "nightmode": "lavfi=[loudnorm=I=-16:TP=-1.5:LRA=11]",
    "karaoke": "lavfi=[stereotools=mlev=0.01:slev=1.5]",
    "clarity": "equalizer=f=3000:width_type=q:w=1.2:g=4,equalizer=f=12000:width_type=q:w=1:g=3",
}


def clamp_gain(gain: float) -> float:
    """Batasi nilai gain antara -12.0 dB dan +12.0 dB."""
    try:
        val = float(gain)
    except (ValueError, TypeError):
        return 0.0
    return max(-12.0, min(12.0, round(val, 1)))


def build_equalizer_filter(gains: List[float] | Tuple[float, ...]) -> str:
    """Membangun string filter libavfilter equalizer aman dari 10 band gain."""
    if not gains:
        return ""
    filters = []
    for i, freq in enumerate(EQ_BANDS):
        g = clamp_gain(gains[i]) if i < len(gains) else 0.0
        if abs(g) >= 0.1:
            freq_str = f"{freq:g}"
            filters.append(f"equalizer=f={freq_str}:width_type=o:w=1:g={g:.1f}")
    return ",".join(filters)


def compose_af_string(eq_gains: List[float] | Tuple[float, ...], special_effect: str = "none") -> str:
    """Menggabungkan filter equalizer dan efek khusus yang divalidasi."""
    parts = []
    eq_str = build_equalizer_filter(eq_gains)
    if eq_str:
        parts.append(eq_str)

    if special_effect in SPECIAL_AUDIO_EFFECTS and SPECIAL_AUDIO_EFFECTS[special_effect]:
        parts.append(SPECIAL_AUDIO_EFFECTS[special_effect])

    return ",".join(parts)
