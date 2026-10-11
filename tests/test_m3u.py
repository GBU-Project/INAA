"""Unit tests untuk parser dan pembuat berkas playlist .m3u / .m3u8."""
import os
import tempfile
import unittest

from m3u_parser import export_m3u, parse_m3u


class TestM3UParser(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = self.temp_dir.name

        # Buat dummy media file
        self.dummy_media = os.path.join(self.dir_path, "sample.mp4")
        with open(self.dummy_media, "w") as f:
            f.write("dummy")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_m3u_with_relative_and_url(self):
        m3u_file = os.path.join(self.dir_path, "test.m3u")
        content = f"""#EXTM3U
#EXTINF:123,Sample Media
sample.mp4
# Komentar yang diabaikan
https://example.com/live.m3u8
nonexistent_file.mp4
"""
        with open(m3u_file, "w", encoding="utf-8") as f:
            f.write(content)

        parsed = parse_m3u(m3u_file)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0], self.dummy_media)
        self.assertEqual(parsed[1], "https://example.com/live.m3u8")

    def test_export_m3u(self):
        out_file = os.path.join(self.dir_path, "exported.m3u")
        items = [self.dummy_media, "https://example.com/video.mp4"]
        ok = export_m3u(out_file, items)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(out_file))

        # Baca kembali untuk verifikasi
        re_parsed = parse_m3u(out_file)
        self.assertEqual(len(re_parsed), 2)
        self.assertEqual(re_parsed[0], self.dummy_media)
        self.assertEqual(re_parsed[1], "https://example.com/video.mp4")


if __name__ == "__main__":
    unittest.main()
