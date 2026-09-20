import os
import urllib.parse

ALLOWED_URI_SCHEMES = {"http", "https"}


def normalize_media_uri(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return ""
    value = path_or_url.strip()
    if value.startswith("file://"):
        parsed = urllib.parse.urlparse(value)
        return urllib.parse.unquote(parsed.path)
    return value


def is_allowed_media_uri(path_or_url):
    if not path_or_url or not isinstance(path_or_url, str):
        return False
    value = path_or_url.strip()
    if not value:
        return False
    if value.startswith("file://"):
        local = normalize_media_uri(value)
        return os.path.isfile(local)
    if "://" in value:
        parsed = urllib.parse.urlparse(value)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ALLOWED_URI_SCHEMES:
            return False
        return bool(parsed.netloc)
    return os.path.isfile(value)
