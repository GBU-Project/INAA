import gzip
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request

MAX_SUB_BYTES = 2 * 1024 * 1024
ALLOWED_SUB_HOSTS = {
    "api.opensubtitles.com",
    "dl.opensubtitles.org",
    "rest.opensubtitles.org",
    "www.opensubtitles.com",
    "www.opensubtitles.org",
}
USER_AGENT = "INAA v1.0"
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name, default="subtitle.srt"):
    base = os.path.basename(str(name or default))
    base = SAFE_NAME_RE.sub("_", base).strip("._") or default
    if len(base) > 80:
        root, ext = os.path.splitext(base)
        base = root[:60] + (ext or ".srt")
    if not os.path.splitext(base)[1]:
        base += ".srt"
    return base


def _host_allowed(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    if host in ALLOWED_SUB_HOSTS:
        return True
    return host.endswith(".opensubtitles.org") or host.endswith(".opensubtitles.com")


def _http_get(url, headers, timeout=8):
    if not _host_allowed(url):
        raise ValueError("host subtitle tidak diizinkan")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        chunks = []
        total = 0
        while True:
            block = resp.read(64 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_SUB_BYTES:
                raise ValueError("unduh subtitle melebihi batas ukuran")
            chunks.append(block)
        return b"".join(chunks), resp.headers


def _maybe_gunzip(payload):
    if len(payload) >= 2 and payload[0] == 0x1F and payload[1] == 0x8B:
        return gzip.decompress(payload)
    return payload


def search_subtitles(query, api_key=None):
    query = (query or "").strip()
    if not query:
        return []
    if api_key:
        url = "https://api.opensubtitles.com/api/v1/subtitles?" + urllib.parse.urlencode(
            {"query": query, "languages": "en,id"}
        )
        headers = {
            "User-Agent": USER_AGENT,
            "Api-Key": api_key,
            "Accept": "application/json",
        }
        raw, _ = _http_get(url, headers, timeout=8)
        data = json.loads(raw.decode("utf-8", errors="replace"))
        results = []
        for item in (data.get("data") or [])[:15]:
            attrs = item.get("attributes") or {}
            files = attrs.get("files") or [{}]
            file_info = files[0] if files else {}
            results.append({
                "name": file_info.get("file_name") or attrs.get("release") or "Subtitle",
                "lang": attrs.get("language") or "",
                "file_id": file_info.get("file_id"),
            })
        return results

    url = "https://rest.opensubtitles.org/search/query-" + urllib.parse.quote(query)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    raw, _ = _http_get(url, headers, timeout=8)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    results = []
    for item in (data or [])[:15]:
        results.append({
            "name": item.get("SubFileName") or item.get("MovieName") or "Subtitle",
            "lang": item.get("LanguageName") or item.get("SubLanguageID") or "",
            "file_id": item.get("IDSubtitleFile") or item.get("SubDownloadLink"),
        })
    return results


def download_subtitle(file_id, filename, api_key=None):
    safe_name = _safe_filename(filename)
    if api_key and str(file_id).isdigit():
        url = "https://api.opensubtitles.com/api/v1/download"
        body = json.dumps({"file_id": int(file_id)}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Api-Key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            info = json.loads(resp.read().decode("utf-8", errors="replace"))
        link = info.get("link")
        if not link:
            raise ValueError("tautan unduhan subtitle kosong")
        payload, _ = _http_get(link, {"User-Agent": USER_AGENT}, timeout=10)
    elif isinstance(file_id, str) and file_id.startswith(("http://", "https://")):
        payload, _ = _http_get(file_id, {"User-Agent": USER_AGENT}, timeout=10)
    else:
        raise ValueError("identifikasi subtitle tidak valid")

    payload = _maybe_gunzip(payload)
    suffix = os.path.splitext(safe_name)[1] or ".srt"
    fd, out_path = tempfile.mkstemp(prefix="inaa_sub_", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            fd = None
    except Exception:
        if fd is not None:
            os.close(fd)
        raise
    return out_path
