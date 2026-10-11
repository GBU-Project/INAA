"""Unit tests untuk pemformatan kecepatan (fmt.py) dan regresi label 1.00xx.
Dapat dijalankan langsung dengan pytest atau unittest standard library.
"""
from pathlib import Path
import unittest

from fmt import format_speed


class TestFmtSpeed(unittest.TestCase):
    def test_format_speed_values(self):
        cases = [
            (1.0, "1x"),
            (1.5, "1.5x"),
            (0.25, "0.25x"),
            (2.0, "2x"),
            (0.5, "0.5x"),
            (1.25, "1.25x"),
            (4, "4x"),
        ]
        for val, expected in cases:
            self.assertEqual(format_speed(val), expected)

    def test_format_speed_bad_inputs(self):
        for bad in [None, "abc", ""]:
            self.assertEqual(format_speed(bad), "1x")

    def test_format_speed_never_doubles_the_x(self):
        # Regresi untuk bug label "1.00xx".
        for v in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
            self.assertFalse(format_speed(v).endswith("xx"))

    def test_old_pattern_was_actually_broken(self):
        # Dokumentasi bug: pola lama menghasilkan "1.00xx". Kalau tes ini gagal,
        # berarti perilaku Python berubah dan komentar di fmt.py perlu ditinjau.
        v = 1.0
        old = f"{v:.2f}x".rstrip("0").rstrip(".") + "x"
        self.assertEqual(old, "1.00xx")

    def test_player_window_uses_format_speed_everywhere(self):
        pw_dir = Path(__file__).resolve().parent.parent / "player_window"
        py_files = list(pw_dir.glob("*.py"))
        self.assertTrue(len(py_files) > 0)

        found_format_speed = False
        for py_file in py_files:
            src = py_file.read_text(encoding="utf-8")
            self.assertNotIn('.rstrip("0").rstrip(".") + "x"', src, f"masih ada pemformatan kecepatan manual di {py_file.name}")
            if "format_speed(" in src or "format_speed" in src:
                found_format_speed = True

        self.assertTrue(found_format_speed, "format_speed belum digunakan di modul player_window")


if __name__ == "__main__":
    unittest.main()
