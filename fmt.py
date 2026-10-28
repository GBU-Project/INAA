"""Helper pemformatan kecil tanpa dependensi GTK, supaya bisa dites langsung."""
import os
import urllib.parse


def format_time(seconds):
    """Detik -> "MM:SS" atau "HH:MM:SS"."""
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def display_name(path_or_url):
    """Label pendek untuk file lokal / URL (termasuk shortlink youtu.be)."""
    if path_or_url.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(path_or_url)
        label = parsed.netloc
        # Untuk youtu.be shortlink (misal https://youtu.be/C-BnRZ52jHs?si=...)
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/").split("/")[0]
            if video_id:
                return f"youtu.be · {video_id}"
        # Untuk youtube.com watch link
        elif "v=" in (parsed.query or ""):
            for part in parsed.query.split("&"):
                if part.startswith("v="):
                    label += f" · {part[2:]}"
                    break
        return label or path_or_url
    return os.path.basename(path_or_url)


def format_speed(value):
    """Format kecepatan putar untuk label UI: 1.0 -> "1x", 1.5 -> "1.5x", 0.25 -> "0.25x".

    Bug sebelumnya: f"{v:.2f}x".rstrip("0") tidak menghapus nol apa pun karena
    karakter terakhir adalah "x", lalu "x" ditambahkan lagi -> "1.00xx".
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 1.0
    return f"{number:.2f}".rstrip("0").rstrip(".") + "x"
