import json
import shutil
import tempfile
import unittest
from pathlib import Path

from plugin_loader import (
    RestrictedPluginAPI,
    _assert_safe_plugin_ast,
    _read_info,
    _safe_identifier,
    load_plugins,
)


class MockPlayer:
    def __init__(self, window):
        self.window = window

    def seek(self, seconds, reference="relative"):
        self.window.seek_args.append((seconds, reference))


class MockWindow:
    def __init__(self):
        self._current_path = "/home/user/video.mp4"
        self.toasts = []
        self.play_pause_called = False
        self.seek_args = []
        self.player = MockPlayer(self)

    def show_toast(self, msg, duration_ms):
        self.toasts.append((msg, duration_ms))

    def on_playpause_clicked(self, widget):
        self.play_pause_called = True


class TestPluginLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="inaa_test_plugins_")
        self.plugins_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_identifier(self):
        self.assertEqual(_safe_identifier("valid-plugin_1.0"), "valid-plugin_1.0")
        self.assertEqual(_safe_identifier(""), "")
        self.assertEqual(_safe_identifier(None), "")
        self.assertEqual(_safe_identifier("invalid/slash"), "")
        self.assertEqual(_safe_identifier("invalid space"), "")
        self.assertEqual(_safe_identifier("a" * 81), "")

    def test_assert_safe_plugin_ast_forbidden_imports(self):
        import ast
        tree_import = ast.parse("import os")
        with self.assertRaises(ValueError):
            _assert_safe_plugin_ast(tree_import)

        tree_from = ast.parse("from os import path")
        with self.assertRaises(ValueError):
            _assert_safe_plugin_ast(tree_from)

    def test_assert_safe_plugin_ast_forbidden_names_and_dunders(self):
        import ast
        forbidden_snippets = [
            "eval('1+1')",
            "open('file.txt')",
            "__import__('sys')",
            "x = __builtins__",
            "obj.__class__",
        ]
        for snippet in forbidden_snippets:
            tree = ast.parse(snippet)
            with self.assertRaises(ValueError):
                _assert_safe_plugin_ast(tree)

    def test_read_info_valid(self):
        plugin_dir = self.plugins_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("print('hello')", encoding="utf-8")
        info = {
            "identifier": "my_plugin",
            "name": "My Plugin",
            "entry": "main.py",
            "permissions": ["show-osd"],
            "enabled": True,
        }
        (plugin_dir / "Info.json").write_text(json.dumps(info), encoding="utf-8")

        result = _read_info(plugin_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result["identifier"], "my_plugin")
        self.assertEqual(result["name"], "My Plugin")
        self.assertIn("show-osd", result["permissions"])
        self.assertTrue(result["enabled_default"])

    def test_read_info_path_traversal(self):
        plugin_dir = self.plugins_path / "bad_plugin"
        plugin_dir.mkdir()
        info = {
            "identifier": "bad_plugin",
            "name": "Bad Plugin",
            "entry": "../other.py",
        }
        (plugin_dir / "Info.json").write_text(json.dumps(info), encoding="utf-8")
        self.assertIsNone(_read_info(plugin_dir))

    def test_load_plugins_lifecycle(self):
        plugin_dir = self.plugins_path / "hello_plugin"
        plugin_dir.mkdir()
        entry_content = (
            "def on_load(api):\n"
            "    api.show_toast('Plugin loaded', 1000)\n"
            "    api.play_pause()\n"
            "    api.seek_relative(10)\n"
            "\n"
            "def custom_action():\n"
            "    return 'ok'\n"
        )
        (plugin_dir / "main.py").write_text(entry_content, encoding="utf-8")
        info = {
            "identifier": "hello_plugin",
            "name": "Hello Plugin",
            "entry": "main.py",
            "permissions": ["show-osd"],
        }
        (plugin_dir / "Info.json").write_text(json.dumps(info), encoding="utf-8")

        window = MockWindow()
        loaded = load_plugins(window, self.plugins_path, ["hello_plugin"])

        self.assertEqual(len(loaded), 1)
        self.assertEqual(window.toasts, [("Plugin loaded", 1000)])
        self.assertTrue(window.play_pause_called)
        self.assertEqual(window.seek_args, [(10.0, "relative")])
        self.assertEqual(loaded[0].custom_action(), "ok")

    def test_load_plugins_skip_dangerous_permissions(self):
        plugin_dir = self.plugins_path / "dangerous_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("print('bad')", encoding="utf-8")
        info = {
            "identifier": "dangerous_plugin",
            "entry": "main.py",
            "permissions": ["file-system"],
        }
        (plugin_dir / "Info.json").write_text(json.dumps(info), encoding="utf-8")

        window = MockWindow()
        loaded = load_plugins(window, self.plugins_path, ["dangerous_plugin"])
        self.assertEqual(len(loaded), 0)


if __name__ == "__main__":
    unittest.main()
