"""
Extra coverage for plugin_loader.py, on top of tests/test_plugin_loader.py.

Kept separate so the original suite stays untouched. This file focuses on
two things the original suite doesn't cover yet:

  1. Sandbox-escape regression tests for the specific bypass techniques
     tried during the manual security audit (generator-frame f_builtins
     introspection, str.format() attribute traversal). If either of these
     ever starts passing "payload not blocked", the sandbox has regressed
     and needs immediate attention — that's the whole point of encoding
     them as tests instead of just a one-off manual check.
  2. Error-path resilience: malformed Info.json, missing entry file,
     absolute entry path, plugin with a syntax error — load_plugins()
     must skip these silently, never raise, and never crash the app
     at startup because one plugin on disk is broken.
"""
import ast
import json

import pytest

from plugin_loader import _assert_safe_plugin_ast, _read_info, load_plugins


def _write_plugin(plugin_dir, info=None, entry_name="main.py", entry_source="def on_load(api):\n    pass\n"):
    plugin_dir.mkdir(parents=True, exist_ok=True)
    default_info = {
        "identifier": plugin_dir.name,
        "name": plugin_dir.name,
        "entry": entry_name,
        "permissions": [],
        "enabled": False,
    }
    if info:
        default_info.update(info)
    (plugin_dir / "Info.json").write_text(json.dumps(default_info), encoding="utf-8")
    if entry_source is not None:
        (plugin_dir / entry_name).write_text(entry_source, encoding="utf-8")
    return plugin_dir


class _FakeWindow:
    def __init__(self):
        self._current_path = "/tmp/fake.mp4"
        self.toasts = []

    def show_toast(self, message, duration_ms=2500):
        self.toasts.append(message)

    def on_playpause_clicked(self, _btn):
        pass

    class player:
        @staticmethod
        def seek(seconds, reference="relative"):
            pass


class TestReadInfoErrorPaths:
    def test_malformed_json_returns_none(self, tmp_path):
        d = tmp_path / "demo"
        d.mkdir()
        (d / "Info.json").write_text("{not valid json", encoding="utf-8")
        assert _read_info(d) is None

    def test_missing_info_json_returns_none(self, tmp_path):
        d = tmp_path / "demo"
        d.mkdir()
        assert _read_info(d) is None

    def test_missing_entry_file_returns_none(self, tmp_path):
        d = tmp_path / "demo"
        d.mkdir()
        (d / "Info.json").write_text(
            json.dumps({"identifier": "demo", "entry": "main.py"}), encoding="utf-8"
        )
        assert _read_info(d) is None  # main.py deliberately not written

    def test_absolute_entry_path_rejected(self, tmp_path):
        d = tmp_path / "demo"
        d.mkdir()
        (d / "Info.json").write_text(
            json.dumps({"identifier": "demo", "entry": "/etc/passwd"}), encoding="utf-8"
        )
        assert _read_info(d) is None

    def test_entry_not_py_extension_returns_none(self, tmp_path):
        d = _write_plugin(tmp_path / "demo", info={"entry": "main.txt"}, entry_name="main.txt")
        assert _read_info(d) is None


class TestLoadPluginsErrorPathsDoNotCrash:
    def test_syntax_error_in_plugin_is_skipped_not_raised(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(plugins_dir / "broken", entry_source="def on_load(api:\n    pass\n")
        window = _FakeWindow()
        loaded = load_plugins(window, plugins_dir, enabled_ids=["broken"])
        assert loaded == []

    def test_plugin_dir_created_if_missing(self, tmp_path):
        plugins_dir = tmp_path / "does" / "not" / "exist_yet"
        window = _FakeWindow()
        loaded = load_plugins(window, plugins_dir, enabled_ids=[])
        assert loaded == []
        assert plugins_dir.is_dir()

    def test_import_os_inside_plugin_fails_to_load_silently(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "evil",
            entry_source="import os\n\ndef on_load(api):\n    os.system('touch /tmp/pwned')\n",
        )
        window = _FakeWindow()
        loaded = load_plugins(window, plugins_dir, enabled_ids=["evil"])
        assert loaded == []


class TestSandboxEscapeRegressions:
    """Each of these encodes a bypass technique that was manually tried
    against the sandbox during a security audit. All must stay blocked."""

    def test_ast_level_dunder_bases_chain_blocked(self):
        tree = ast.parse("x = ().__class__.__bases__[0].__subclasses__()")
        with pytest.raises(ValueError):
            _assert_safe_plugin_ast(tree)

    def test_ast_level_globals_via_function_dunder_blocked(self):
        tree = ast.parse("def f(): pass\nx = f.__globals__['__builtins__']")
        with pytest.raises(ValueError):
            _assert_safe_plugin_ast(tree)

    def test_str_format_attribute_traversal_does_not_yield_a_live_object(self, tmp_path):
        # str.format()'s {0.attr.attr2} mini-language is not blocked at the
        # AST level (it's just a string literal + a .format() call), so this
        # confirms empirically that it's a dead end: format() always
        # stringifies the resolved attribute, it never hands back a live,
        # callable Python object to the plugin. (Deliberately avoids
        # type()/isinstance() here since those aren't in the plugin's
        # restricted builtins either — the test itself has to play by the
        # sandbox's rules.)
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "fmt_escape",
            entry_source=(
                "def on_load(api):\n"
                "    sub_method = '{0.__class__.__base__.__subclasses__}'.format(api)\n"
                "    try:\n"
                "        sub_method()\n"
                "        result = 'callable-ESCAPE'\n"
                "    except:\n"
                "        result = 'not-callable'\n"
                "    api.show_toast(result)\n"
            ),
        )
        window = _FakeWindow()
        loaded = load_plugins(window, plugins_dir, enabled_ids=["fmt_escape"])
        assert len(loaded) == 1
        assert window.toasts == ["not-callable"]

    def test_generator_frame_introspection_does_not_leak_real_builtins(self, tmp_path):
        # gi_frame / f_builtins are not dunder-prefixed so the AST check
        # doesn't block them, but the restricted __builtins__ namespace
        # passed to exec() propagates through nested frames correctly, so
        # this must still only see the small safe subset, never 'eval'.
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "frame_escape",
            entry_source=(
                "def on_load(api):\n"
                "    def gen():\n"
                "        yield 1\n"
                "    g = gen()\n"
                "    fb = g.gi_frame.f_builtins\n"
                "    api.show_toast(str('eval' in fb))\n"
            ),
        )
        window = _FakeWindow()
        loaded = load_plugins(window, plugins_dir, enabled_ids=["frame_escape"])
        assert len(loaded) == 1
        assert window.toasts == ["False"]
