"""Regresi audit: rantai generator-frame (gi_frame.f_back.f_back.f_builtins) harus gagal dimuat, bukan menjalankan kode."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plugin_loader  # noqa: E402


class FakeWindow:
    _current_path = None

    def __init__(self):
        self.toasts = []

    def show_toast(self, msg, ms=2500):
        self.toasts.append(msg)

    def on_playpause_clicked(self, *_):
        pass


def _load(tmp_path, body):
    d = tmp_path / "plugins" / "p"
    d.mkdir(parents=True)
    (d / "Info.json").write_text(json.dumps({"identifier": "p", "entry": "main.py", "permissions": ["show-osd"]}))
    (d / "main.py").write_text(body)
    win = FakeWindow()
    return plugin_loader.load_plugins(win, tmp_path / "plugins", ["p"]), win


def _marker_payload(tmp_path, escape_expr):
    marker = tmp_path / "PWNED.txt"
    return marker, (
        "def on_load(api):\n"
        f"    b = {escape_expr}\n"
        f"    b['__import__']('os').system('echo x > {marker}')\n"
    )


@pytest.mark.parametrize("escape", [
    "[g.gi_frame.f_back.f_back.f_builtins for g in [(g for _ in [1])]][0]",
    "(g := (g.gi_frame.f_back.f_back.f_builtins for _ in [1]))",
    "api.show_toast.func_globals",
    "[e.tb_frame for e in [1]]",
    "(c.cr_frame for c in [1])",
    "str.mro()",
    "'{0.__globals__}'.format(api.show_toast)",
    "'{0}'.format_map({})",
    "api.show_toast.__globals__",
])
def test_escape_attempts_do_not_load_and_do_not_execute(tmp_path, escape):
    marker, body = _marker_payload(tmp_path, escape)
    # Harus ditolak oleh pemeriksaan AST itu sendiri (bukan kebetulan gagal saat dijalankan).
    import ast
    with pytest.raises(ValueError):
        plugin_loader._assert_safe_plugin_ast(ast.parse(body))
    loaded, _ = _load(tmp_path, body)
    assert loaded == [] and not marker.exists()


def test_exact_poc_from_audit_is_blocked(tmp_path):
    marker = tmp_path / "PWNED.txt"
    body = (
        "def on_load(api):\n"
        "    g = (g.gi_frame.f_back.f_back.f_builtins for _ in [1])\n"
        "    real_builtins = list(g)[0]\n"
        f"    real_builtins['__import__']('os').system('echo x > {marker}')\n"
    )
    loaded, _ = _load(tmp_path, body)
    assert loaded == [] and not marker.exists()


def test_legitimate_plugin_still_works(tmp_path):
    body = (
        "TITLE = 'Halo'\n"
        "def on_load(api):\n"
        "    names = [n.strip().upper() for n in ' a, b '.split(',')]\n"
        "    d = {}\n"
        "    d.update({'k': names})\n"
        "    api.show_toast(', '.join(d['k']) + f' {len(names)} {TITLE}')\n"
        "    api.seek_relative(0)\n"
        "def on_file_open(path):\n"
        "    pass\n"
    )
    loaded, win = _load(tmp_path, body)
    assert len(loaded) == 1 and win.toasts == ["A, B 2 Halo"]


def test_shipped_example_plugin_still_loads():
    root = Path(__file__).resolve().parent.parent / "plugins"
    win = FakeWindow()
    loaded = plugin_loader.load_plugins(win, root, ["io.github.inaa.example-toast"])
    assert len(loaded) == 1


def test_allowlist_has_no_introspection_names():
    bad = {"gi_frame", "f_back", "f_builtins", "f_globals", "tb_frame", "cr_frame", "ag_frame", "mro", "format", "format_map"}
    assert not (bad & plugin_loader.ALLOWED_ATTRIBUTES)
