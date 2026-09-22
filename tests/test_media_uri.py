import os
import tempfile
import unittest

from media_uri import (
    is_allowed_media_uri,
    is_http_media_uri,
    is_local_media_file,
    normalize_media_uri,
)


class TestMediaUri(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"video dummy data")
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_unsafe_characters(self):
        unsafe_inputs = [
            "video\x00.mp4",
            "video\n.mp4",
            "video\r.mp4",
            "video\t.mp4",
            "http://example.com/test\n.mp4",
        ]
        for inp in unsafe_inputs:
            self.assertEqual(normalize_media_uri(inp), "")
            self.assertFalse(is_local_media_file(inp))
            self.assertFalse(is_http_media_uri(inp))
            self.assertFalse(is_allowed_media_uri(inp))

    def test_normalize_media_uri(self):
        self.assertEqual(normalize_media_uri(""), "")
        self.assertEqual(normalize_media_uri(None), "")
        self.assertEqual(normalize_media_uri(123), "")
        self.assertEqual(normalize_media_uri("  /path/to/movie.mkv  "), "/path/to/movie.mkv")
        self.assertEqual(normalize_media_uri("file:///home/user/test%20space.mp4"), "/home/user/test space.mp4")
        self.assertEqual(normalize_media_uri("file://localhost/home/user/video.mp4"), "/home/user/video.mp4")
        # Remote file:// host should be rejected
        self.assertEqual(normalize_media_uri("file://remotehost/home/user/video.mp4"), "")
        self.assertEqual(normalize_media_uri("https://example.com/stream.m3u8"), "https://example.com/stream.m3u8")

    def test_is_local_media_file(self):
        self.assertTrue(is_local_media_file(self.temp_file.name))
        self.assertFalse(is_local_media_file("/non/existent/path/for/sure/video.mp4"))
        self.assertFalse(is_local_media_file(""))
        self.assertFalse(is_local_media_file("https://example.com/video.mp4"))
        self.assertFalse(is_local_media_file("file:///path/to/video.mp4"))

    def test_is_http_media_uri(self):
        self.assertTrue(is_http_media_uri("http://example.com/stream.mp4"))
        self.assertTrue(is_http_media_uri("https://example.com/stream.mp4"))
        self.assertFalse(is_http_media_uri("ftp://example.com/stream.mp4"))
        self.assertFalse(is_http_media_uri("file:///path/to/video.mp4"))
        self.assertFalse(is_http_media_uri("https://user:pass@example.com/stream.mp4"))
        self.assertFalse(is_http_media_uri("https://"))
        self.assertFalse(is_http_media_uri("/local/path/video.mp4"))

    def test_is_allowed_media_uri(self):
        self.assertTrue(is_allowed_media_uri(self.temp_file.name))
        self.assertTrue(is_allowed_media_uri(f"file://{self.temp_file.name}"))
        self.assertTrue(is_allowed_media_uri("https://example.com/video.mp4"))
        self.assertFalse(is_allowed_media_uri("ftp://example.com/video.mp4"))
        self.assertFalse(is_allowed_media_uri("file:///non/existent/video.mp4"))
        self.assertFalse(is_allowed_media_uri("/non/existent/video.mp4"))


if __name__ == "__main__":
    unittest.main()
