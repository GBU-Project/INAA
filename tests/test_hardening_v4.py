"""Regresi hasil audit: batas M3U dan redirect subtitle hanya ke host yang diizinkan."""
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import m3u_parser  # noqa: E402
import opensubtitles  # noqa: E402


def test_m3u_entry_cap(tmp_path):
    f = tmp_path / "big.m3u"
    f.write_text("\n".join(f"https://example.com/{i}.mp4" for i in range(m3u_parser.MAX_M3U_ENTRIES + 500)))
    assert len(m3u_parser.parse_m3u(str(f))) == m3u_parser.MAX_M3U_ENTRIES


def test_m3u_byte_cap_stops_reading(tmp_path):
    f = tmp_path / "huge.m3u"
    line = "# " + "x" * 1000 + "\n"
    f.write_text("https://example.com/first.mp4\n" + line * (m3u_parser.MAX_M3U_BYTES // 1000 + 50) + "https://example.com/last.mp4\n")
    got = m3u_parser.parse_m3u(str(f))
    assert got == ["https://example.com/first.mp4"]


def test_m3u_overlong_line_skipped_and_normal_entries_kept(tmp_path):
    f = tmp_path / "a.m3u"
    f.write_text("https://example.com/" + "a" * 5000 + ".mp4\nhttps://example.com/ok.mp4\n")
    assert m3u_parser.parse_m3u(str(f)) == ["https://example.com/ok.mp4"]


def test_m3u_small_playlist_unchanged(tmp_path):
    media = tmp_path / "v.mp4"
    media.write_text("x")
    f = tmp_path / "a.m3u"
    f.write_text("#EXTM3U\n#EXTINF:-1,v\nv.mp4\nhttps://example.com/x.mp4\nftp://nope/x\n")
    assert m3u_parser.parse_m3u(str(f)) == [str(media.resolve()), "https://example.com/x.mp4"]


def _redirect(handler, newurl):
    req = urllib.request.Request("https://api.opensubtitles.com/x")
    return handler.redirect_request(req, None, 302, "Found", {}, newurl)


def test_redirect_to_other_host_is_refused():
    h = opensubtitles._AllowlistRedirectHandler()
    for bad in ("https://evil.example/x.srt", "http://127.0.0.1/x", "https://opensubtitles.org.evil.com/x", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            _redirect(h, bad)


def test_redirect_within_allowlist_is_followed():
    h = opensubtitles._AllowlistRedirectHandler()
    new = _redirect(h, "https://dl.opensubtitles.org/file.srt")
    assert new is not None and new.full_url == "https://dl.opensubtitles.org/file.srt"


def test_http_get_uses_the_validating_opener():
    src = Path(opensubtitles.__file__).read_text()
    assert "urllib.request.urlopen" not in src and "_OPENER.open" in src
