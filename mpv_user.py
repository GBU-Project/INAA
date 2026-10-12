"""Pengaturan mpv milik pengguna (mpv.conf, shader, script) — semuanya opt-in dan dibatasi.

Kenapa tidak membiarkan mpv membaca ~/.config/mpv sendiri (config=yes)?
  * Setiap opsi mpv bisa diubah saat runtime, termasuk `vo`, `osc`, `input-*`, `ytdl-*`, `script`.
    Kalau mpv.conf dibaca mentah, file itu bisa menimpa pengaturan yang INAA butuhkan agar
    render lewat libmpv, atau memuat script/IPC tanpa sepengetahuan pengguna.
  * Jadi INAA mem-parse mpv.conf sendiri dan hanya menerapkan opsi di SAFE_OPTIONS (daftar putih).
    Opsi lain dilaporkan sebagai "diabaikan", tidak pernah diterapkan.

Kunci config.json (semua nonaktif secara default):
  "use_mpv_conf": true                                   # baca ~/.config/mpv/mpv.conf (hanya opsi aman)
  "mpv_conf":    "/path/lain/mpv.conf"                   # opsional: path mpv.conf alternatif
  "mpv_scripts": ["/home/aku/.config/mpv/scripts/x.lua"]  # wajib path absolut .lua/.js
Shader dikelola lewat "custom_shaders" (UI Inspector) dan dimuat via apply_shaders().

PERINGATAN: script mpv (Lua/JS) berjalan dengan akses penuh ke akunmu (bisa menjalankan perintah),
sama seperti plugin INAA. Hanya muat script dari sumber yang kamu percaya.
Modul ini tidak bergantung pada GTK sehingga bisa dites langsung.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MPV_CONF = "~/.config/mpv/mpv.conf"
MAX_CONF_BYTES = 256 * 1024
MAX_VALUE_CHARS = 512
SHADER_SUFFIXES = {".glsl", ".hook", ".frag"}
SCRIPT_SUFFIXES = {".lua", ".js"}

# Hanya opsi tampilan/pemutaran yang aman. SENGAJA tidak ada: vo, ao, osc, input-*, ytdl*,
# script/scripts/load-scripts, include, profile, vf/af/lavfi-complex (graf lavfi bisa membuka
# file/URL), *-directory, log-file, external-file*, sub-file*, glsl-shaders (pakai mpv_shaders).
SAFE_OPTIONS = frozenset(
    {
        # video / render
        "hwdec", "hwdec-codecs", "scale", "cscale", "dscale", "tscale", "scale-antiring",
        "cscale-antiring", "dscale-antiring", "dither", "dither-depth", "temporal-dither",
        "deband", "deband-iterations", "deband-threshold", "deband-range", "deband-grain",
        "interpolation", "video-sync", "framedrop", "correct-downscaling", "linear-downscaling",
        "sigmoid-upscaling", "tone-mapping", "tone-mapping-param", "tone-mapping-mode",
        "hdr-compute-peak", "gamut-mapping-mode", "inverse-tone-mapping", "target-trc",
        "target-prim", "target-peak", "blend-subtitles", "vd-lavc-threads",
        "vd-lavc-skiploopfilter",
        # audio
        "audio-channels", "audio-normalize-downmix", "audio-pitch-correction", "replaygain",
        "replaygain-preamp", "replaygain-clip", "volume-max", "alang", "audio-delay",
        # subtitle
        "slang", "sub-font", "sub-font-size", "sub-color", "sub-border-color", "sub-border-size",
        "sub-back-color", "sub-shadow-color", "sub-shadow-offset", "sub-pos", "sub-scale",
        "sub-bold", "sub-italic", "sub-margin-y", "sub-margin-x", "sub-ass-override",
        "sub-ass-style-overrides", "sub-delay", "sub-codepage", "sub-fix-timing", "sub-use-margins",
        # cache / jaringan / seek
        "cache", "cache-secs", "demuxer-max-bytes", "demuxer-max-back-bytes",
        "demuxer-readahead-secs", "network-timeout", "user-agent", "hr-seek", "hr-seek-framedrop",
    }
)


@dataclass
class Report:
    applied: list = field(default_factory=list)     # [(opsi, nilai)]
    rejected: list = field(default_factory=list)    # [(sumber, alasan)]
    shaders: list = field(default_factory=list)     # path shader yang dipasang
    scripts: list = field(default_factory=list)     # path script yang dimuat

    @property
    def has_problems(self):
        return bool(self.rejected)

    def summary(self):
        parts = []
        if self.applied:
            parts.append(f"{len(self.applied)} opsi")
        if self.shaders:
            parts.append(f"{len(self.shaders)} shader")
        if self.scripts:
            parts.append(f"{len(self.scripts)} script")
        text = "mpv: " + (", ".join(parts) if parts else "tidak ada yang diterapkan")
        if self.rejected:
            text += f" ({len(self.rejected)} diabaikan)"
        return text


# ------------------------------------------------------------------ mpv.conf

def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_conf(text: str):
    """Mem-parse isi mpv.conf. Mengembalikan [(nomor_baris, opsi, nilai)] hanya untuk bagian global/[default].

    Aturan mpv yang didukung: komentar hanya jika '#' di awal baris, `opsi` tanpa nilai = yes,
    `no-opsi` = no, nilai boleh diapit kutip, `_` setara `-`. Bagian [profil] diabaikan.
    """
    entries = []
    section = "default"
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower() or "default"
            continue
        if section != "default":
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key, value = key.strip(), _strip_quotes(value.strip())
        else:
            key, value = line, "yes"
        key = key.lower().replace("_", "-")
        if key.startswith("no-") and "=" not in line:
            key, value = key[3:], "no"
        entries.append((number, key, value))
    return entries


def apply_conf(player, conf_path, report: Report):
    path = Path(os.path.expanduser(str(conf_path)))
    try:
        if not path.is_file():
            report.rejected.append((str(path), "mpv.conf tidak ditemukan"))
            return
        if path.stat().st_size > MAX_CONF_BYTES:
            report.rejected.append((str(path), f"mpv.conf terlalu besar (> {MAX_CONF_BYTES // 1024} KB)"))
            return
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        report.rejected.append((str(path), f"tidak bisa dibaca: {exc}"))
        return

    for number, key, value in parse_conf(text):
        source = f"{path.name}:{number} {key}"
        if key not in SAFE_OPTIONS:
            report.rejected.append((source, "opsi tidak ada di daftar yang diizinkan"))
            continue
        if len(value) > MAX_VALUE_CHARS or "\x00" in value:
            report.rejected.append((source, "nilai tidak valid"))
            continue
        try:
            player[key] = value
            report.applied.append((key, value))
        except Exception as exc:
            report.rejected.append((source, f"gagal diterapkan: {exc}"))


# ------------------------------------------------------------------- shaders

def resolve_shader(entry, shaders_dir: Path):
    """Mengembalikan Path shader yang valid, atau (None, alasan)."""
    if not isinstance(entry, str) or not entry.strip():
        return None, "entri kosong/bukan teks"
    raw = os.path.expanduser(entry.strip())
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        base = shaders_dir.resolve()
        resolved = (base / candidate).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            return None, "path relatif keluar dari folder shaders"
    if resolved.suffix.lower() not in SHADER_SUFFIXES:
        return None, f"ekstensi harus salah satu dari {sorted(SHADER_SUFFIXES)}"
    if not resolved.is_file():
        return None, "file tidak ditemukan"
    return resolved, None


def apply_shaders(player, entries, shaders_dir: Path, report: Report):
    good = []
    for entry in entries:
        path, reason = resolve_shader(entry, shaders_dir)
        if path is None:
            report.rejected.append((f"shader {entry!r}", reason))
        elif str(path) not in good:
            good.append(str(path))
    if not good:
        return
    try:
        player.command("change-list", "glsl-shaders", "clr", "")
        for path in good:
            player.command("change-list", "glsl-shaders", "append", path)
        report.shaders.extend(good)
    except Exception as exc:
        report.rejected.append(("shaders", f"gagal dipasang: {exc}"))


# ------------------------------------------------------------------- scripts

def resolve_script(entry):
    if not isinstance(entry, str) or not entry.strip():
        return None, "entri kosong/bukan teks"
    candidate = Path(os.path.expanduser(entry.strip()))
    if not candidate.is_absolute():
        return None, "wajib path absolut (script tidak dicari otomatis)"
    resolved = candidate.resolve()
    if resolved.suffix.lower() not in SCRIPT_SUFFIXES:
        return None, f"ekstensi harus salah satu dari {sorted(SCRIPT_SUFFIXES)}"
    if not resolved.is_file():
        return None, "file tidak ditemukan"
    return resolved, None


def apply_scripts(player, entries, report: Report):
    seen = set()
    for entry in entries:
        path, reason = resolve_script(entry)
        if path is None:
            report.rejected.append((f"script {entry!r}", reason))
            continue
        if str(path) in seen:
            continue
        seen.add(str(path))
        try:
            player.command("load-script", str(path))
            report.scripts.append(str(path))
        except Exception as exc:
            report.rejected.append((f"script {path.name}", f"gagal dimuat: {exc}"))


# ---------------------------------------------------------------- entry point

def _as_list(value):
    return value if isinstance(value, list) else []


def apply_user_settings(player, config: dict, shaders_dir: Path) -> Report:
    """Terapkan mpv.conf/shader/script sesuai config.json. Tidak pernah melempar exception."""
    report = Report()
    try:
        conf = config.get("mpv_conf")
        if isinstance(conf, str) and conf.strip():
            apply_conf(player, conf, report)
        elif config.get("use_mpv_conf") is True:
            apply_conf(player, DEFAULT_MPV_CONF, report)
        scripts = _as_list(config.get("mpv_scripts"))
        if scripts:
            apply_scripts(player, scripts, report)
    except Exception as exc:  # jaring pengaman terakhir: pengaturan pengguna tidak boleh membuat app crash
        report.rejected.append(("mpv_user", f"kesalahan tak terduga: {exc}"))
    return report
