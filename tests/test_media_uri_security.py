"""
Extra coverage for media_uri.py, on top of tests/test_media_uri.py.

Kept as a separate file (rather than merged into test_media_uri.py) so the
original suite stays untouched and this file's purpose is self-contained:
adversarial/edge cases from the manual security audit that the original
suite doesn't cover yet (symlinks, relative paths, scheme case, ports,
directories-as-files).
"""
import pytest

from media_uri import (
    is_allowed_media_uri,
    is_http_media_uri,
    is_local_media_file,
)


class TestLocalFileEdgeCases:
    def test_directory_is_not_a_file(self, tmp_path):
        assert is_local_media_file(str(tmp_path)) is False

    def test_symlink_to_real_file_is_true(self, tmp_path):
        real = tmp_path / "real.mp4"
        real.write_bytes(b"data")
        link = tmp_path / "link.mp4"
        link.symlink_to(real)
        assert is_local_media_file(str(link)) is True

    def test_broken_symlink_is_false(self, tmp_path):
        link = tmp_path / "broken.mp4"
        link.symlink_to(tmp_path / "missing.mp4")
        assert is_local_media_file(str(link)) is False


class TestHttpUriEdgeCases:
    def test_scheme_is_case_insensitive(self):
        assert is_http_media_uri("HTTPS://example.com/video.mp4") is True

    def test_url_with_port_and_query_ok(self):
        assert is_http_media_uri("https://example.com:8443/v.mp4?token=abc") is True

    @pytest.mark.parametrize("scheme", ["javascript", "data", "gopher"])
    def test_uncommon_schemes_rejected(self, scheme):
        assert is_http_media_uri(f"{scheme}://example.com/x") is False


class TestAllowedUriEdgeCases:
    def test_relative_path_to_existing_file_allowed(self, tmp_path, monkeypatch):
        f = tmp_path / "video.mp4"
        f.write_bytes(b"x")
        monkeypatch.chdir(tmp_path)
        assert is_allowed_media_uri("video.mp4") is True

    def test_javascript_pseudo_scheme_rejected(self):
        assert is_allowed_media_uri("javascript:alert(1)") is False
