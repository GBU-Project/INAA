"""Helper parsing dan ekspor playlist M3U / M3U8 untuk INAA."""
import os
from pathlib import Path
from media_uri import is_allowed_media_uri, normalize_media_uri


def parse_m3u(file_path):
    """Membaca berkas .m3u / .m3u8 dan mengembalikan daftar URI atau path valid.
    
    Mendukung entri path relatif terhadap lokasi file .m3u itu sendiri,
    path absolut, serta URI http/https. Baris komentar (#) dilewati,
    kecuali metadata jika diperlukan di masa depan.
    """
    entries = []
    base_dir = Path(file_path).parent

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Cek jika path lokal relatif
                if not line.startswith("http://") and not line.startswith("https://") and not line.startswith("file://"):
                    candidate = (base_dir / line).resolve()
                    if candidate.exists():
                        line = str(candidate)

                norm = normalize_media_uri(line)
                if is_allowed_media_uri(norm):
                    entries.append(norm)
    except Exception:
        pass

    return entries


def export_m3u(file_path, items):
    """Menyimpan daftar path / URI ke dalam format Extended M3U (#EXTM3U)."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for item in items:
                # Tulis nama tampilan sebagai informasi EXTINF
                title = os.path.basename(item) if not item.startswith("http") else item
                f.write(f"#EXTINF:-1,{title}\n")
                f.write(f"{item}\n")
        return True
    except Exception:
        return False
