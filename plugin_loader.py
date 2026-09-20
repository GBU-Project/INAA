import json
from pathlib import Path

ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
DANGEROUS_PERMISSIONS = {"network-request", "file-system"}
KNOWN_PERMISSIONS = DANGEROUS_PERMISSIONS | {"show-osd"}


class RestrictedPluginAPI:
    def __init__(self, window):
        self._window = window

    def show_toast(self, message, duration_ms=2500):
        self._window.show_toast(str(message), duration_ms)

    def current_path(self):
        return self._window._current_path

    def play_pause(self):
        self._window.on_playpause_clicked(None)

    def seek_relative(self, seconds):
        try:
            self._window.player.seek(float(seconds), reference="relative")
        except Exception:
            pass


def _safe_identifier(value):
    if not value or not isinstance(value, str):
        return ""
    if not (1 <= len(value) <= 80):
        return ""
    if not all(ch in ID_CHARS for ch in value):
        return ""
    return value


def _read_info(plugin_dir):
    info_path = plugin_dir / "Info.json"
    if not info_path.is_file():
        return None
    try:
        data = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    identifier = _safe_identifier(data.get("identifier") or plugin_dir.name)
    entry = data.get("entry")
    if not identifier or not isinstance(entry, str) or not entry.endswith(".py"):
        return None
    if Path(entry).is_absolute() or ".." in Path(entry).parts:
        return None
    entry_path = (plugin_dir / entry).resolve()
    try:
        entry_path.relative_to(plugin_dir.resolve())
    except ValueError:
        return None
    if not entry_path.is_file():
        return None
    perms = set()
    raw_perms = data.get("permissions") or []
    if isinstance(raw_perms, list):
        for item in raw_perms:
            if item in KNOWN_PERMISSIONS:
                perms.add(item)
    return {
        "identifier": identifier,
        "name": str(data.get("name") or identifier),
        "entry": entry_path,
        "permissions": perms,
        "enabled_default": bool(data.get("enabled", False)),
    }


def load_plugins(window, plugins_dir, enabled_ids):
    loaded = []
    try:
        plugins_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return loaded

    enabled = set(enabled_ids or [])
    api = RestrictedPluginAPI(window)

    for plugin_dir in sorted(p for p in plugins_dir.iterdir() if p.is_dir()):
        info = _read_info(plugin_dir)
        if not info:
            continue
        if info["identifier"] not in enabled:
            continue
        if info["permissions"] & DANGEROUS_PERMISSIONS:
            print(
                f"[plugin] skip {info['identifier']}: "
                "dangerous permissions require a future sandbox"
            )
            continue
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                f"inaa_plugin_{info['identifier']}",
                str(info["entry"]),
            )
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "on_load"):
                mod.on_load(api)
            loaded.append(mod)
        except Exception as exc:
            print(f"[plugin] failed to load {info['identifier']}: {exc}")
    return loaded
