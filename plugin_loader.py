import ast
import json
from pathlib import Path

ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
DANGEROUS_PERMISSIONS = {"network-request", "file-system"}
KNOWN_PERMISSIONS = DANGEROUS_PERMISSIONS | {"show-osd"}
_DUNDER_PREFIX = "__"
_FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "dir", "type", "classmethod", "staticmethod", "property",
    "memoryview", "bytearray", "object", "super", "help",
    "__import__", "__loader__", "__spec__", "__builtins__",
}
_PLUGIN_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "enumerate": enumerate,
    "zip": zip,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "print": print,
}


# Daftar PUTIH atribut. Daftar nama terlarang saja tidak cukup: atribut seperti `gi_frame`, `f_back`,
# `f_builtins`, `tb_frame`, `cr_frame` tidak berawalan "__" tetapi tetap bisa dipakai untuk
# keluar dari sandbox (generator.gi_frame.f_back.f_back.f_builtins -> builtins asli).
# `format`/`format_map` sengaja tidak diizinkan: mini-language "{0.__class__}" tidak terlihat di AST.
_API_ATTRIBUTES = {"show_toast", "current_path", "play_pause", "seek_relative"}
_SAFE_TYPE_METHODS = {
    name
    for tp in (str, list, dict, set, tuple, int, float, bool)
    for name in dir(tp)
    if not name.startswith("_")
} - {"format", "format_map"}
ALLOWED_ATTRIBUTES = frozenset(_API_ATTRIBUTES | _SAFE_TYPE_METHODS)


class RestrictedPluginAPI:
    def __init__(self, window):
        def show_toast(message, duration_ms=2500):
            window.show_toast(str(message), duration_ms)

        def current_path():
            return window._current_path

        def play_pause():
            window.on_playpause_clicked(None)

        def seek_relative(seconds):
            try:
                window.player.seek(float(seconds), reference="relative")
            except Exception:
                pass

        self.show_toast = show_toast
        self.current_path = current_path
        self.play_pause = play_pause
        self.seek_relative = seek_relative


class _PluginHooks:
    def __init__(self, namespace):
        self._ns = namespace

    def __getattr__(self, name):
        fn = self._ns.get(name)
        if callable(fn):
            return fn
        raise AttributeError(name)


def _safe_identifier(value):
    if not value or not isinstance(value, str):
        return ""
    if not (1 <= len(value) <= 80):
        return ""
    if not all(ch in ID_CHARS for ch in value):
        return ""
    return value


def _assert_safe_plugin_ast(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("plugin tidak boleh mengimpor modul")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"nama terlarang: {node.id}")
        if isinstance(node, ast.Name) and node.id.startswith(_DUNDER_PREFIX):
            raise ValueError("nama dunder tidak diizinkan")
        if isinstance(node, ast.Attribute) and node.attr.startswith(_DUNDER_PREFIX):
            raise ValueError("akses atribut dunder tidak diizinkan")
        if isinstance(node, ast.Attribute) and node.attr not in ALLOWED_ATTRIBUTES:
            raise ValueError(f"atribut tidak diizinkan: {node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_NAMES:
                raise ValueError(f"pemanggilan terlarang: {node.func.id}")


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
            source = info["entry"].read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(info["entry"]))
            _assert_safe_plugin_ast(tree)
            namespace = {"__builtins__": _PLUGIN_BUILTINS}
            exec(compile(tree, str(info["entry"]), "exec"), namespace, namespace)
            if "on_load" in namespace and callable(namespace["on_load"]):
                namespace["on_load"](api)
            loaded.append(_PluginHooks(namespace))
        except Exception as exc:
            print(f"[plugin] failed to load {info['identifier']}: {exc}")
    return loaded
