import os
import urllib.parse

ALLOWED_URI_SCHEMES = {"http", "https"}


def _has_unsafe_chars(value):
    return any(ch in value for ch in ("\x00", "\n", "\r", "\t"))


def normalize_media_uri(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return ""
    if _has_unsafe_chars(path_or_url):
        return ""
    value = path_or_url.strip()
    if value.startswith("file://"):
        parsed = urllib.parse.urlparse(value)
        host = (parsed.netloc or "").lower()
        if host not in ("", "localhost"):
            return ""
        return urllib.parse.unquote(parsed.path)
    return value


def is_local_media_file(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return False
    if _has_unsafe_chars(path_or_url):
        return False
    value = path_or_url.strip()
    if not value or "://" in value:
        return False
    try:
        if not os.path.isfile(value):
            return False
        real = os.path.realpath(value)
        return os.path.isfile(real)
    except OSError:
        return False


def is_http_media_uri(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return False
    if _has_unsafe_chars(path_or_url):
        return False
    value = path_or_url.strip()
    if not value or "://" not in value:
        return False
    parsed = urllib.parse.urlparse(value)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_URI_SCHEMES:
        return False
    if parsed.username or parsed.password:
        return False
    host = parsed.hostname or ""
    return bool(host)


def is_allowed_media_uri(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return False
    if _has_unsafe_chars(path_or_url):
        return False
    value = path_or_url.strip()
    if not value:
        return False
    if value.startswith("file://"):
        local = normalize_media_uri(value)
        return is_local_media_file(local)
    if "://" in value:
        return is_http_media_uri(value)
    return is_local_media_file(value)
