"""Konstanta domain media yang dipakai lintas mixin.

Dipisah dari common.py agar modul yang hanya butuh angka/ekstensi tidak
ikut mengimpor bootstrap GTK/GL.
"""

SEEK_STEP_SECONDS = 5
VOLUME_STEP = 5

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus", ".wma"}
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v",
    ".ts", ".m2ts", ".vob", ".ogv", ".3gp",
}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx", ".lrc"}
