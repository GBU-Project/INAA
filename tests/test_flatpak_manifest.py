"""Manifest Flatpak harus konsisten dengan kode: semua modul yang diimpor ikut disalin, sumber dipin, izin sempit."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "flatpak" / "io.github.inaa.json").read_text())


def _app_module():
    return next(m for m in MANIFEST["modules"] if m["name"] == "inaa")


def _copied():
    cmd = next(c for c in _app_module()["build-commands"] if c.startswith("cp -r "))
    return {Path(x).name for x in cmd.split()[2:-1]}


def _imported_local_modules():
    local = {p.stem for p in ROOT.glob("*.py")}
    needed = set()
    files = list(ROOT.glob("*.py")) + list((ROOT / "player_window").glob("*.py"))
    for f in files:
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.Import):
                needed |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                needed.add(node.module.split(".")[0])
    return {n for n in needed if n in local}


def test_every_imported_module_is_copied_into_the_flatpak():
    copied = _copied()
    missing = sorted(m for m in _imported_local_modules() if f"{m}.py" not in copied)
    assert not missing, f"modul diimpor tapi tidak disalin ke Flatpak: {missing}"
    assert "player_window" in copied and "plugins" in copied and "main.py" in copied


def test_copied_files_exist():
    for name in _copied():
        assert (ROOT / name).exists(), name


def test_no_broad_device_access():
    args = MANIFEST["finish-args"]
    assert "--device=all" not in args and "--device=dri" in args
    assert not any(a.startswith("--filesystem=host") or a == "--filesystem=home" for a in args)


def test_git_sources_are_pinned_to_a_commit():
    for module in MANIFEST["modules"]:
        for src in module.get("sources", []):
            if src.get("type") == "git":
                has_commit = bool(re.fullmatch(r"[0-9a-f]{40}", src.get("commit", "")))
                has_tag = bool(src.get("tag"))
                assert has_commit or has_tag, f"{module['name']} tidak dipin ke commit atau tag"


def test_ffmpeg_can_write_jpeg_thumbnails():
    ffmpeg = next(m for m in MANIFEST["modules"] if m["name"] == "ffmpeg")
    opts = ffmpeg["config-opts"]
    # thumbnail ditulis sebagai .jpg lewat -f image2 (input_mixin.py); --disable-muxers/encoders mematikan keduanya
    assert "--enable-encoder=mjpeg" in opts and "--enable-muxer=image2" in opts
    assert "--disable-programs" not in opts
