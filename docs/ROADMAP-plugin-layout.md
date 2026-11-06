# INAA Plugin & Layout Roadmap

Status: Phase 1 implemented (dockable Gtk.Paned panes, layout prefs)
Owner: INAA maintainers
Last updated: 2026-11-06
Scope: plugin platform v2 (capabilities, isolation, contributions) and
layout/theming (docks, OSC, palettes, presets)

Related: `flatpak/README.md`, `tests/test_plugin_loader_security.py`,
`tests/test_plugin_sandbox_v4.py`, `player_window/theme.py`,
`player_window/ui_builder.py`, `plugin_loader.py`

---

## 1. Where we are today

### 1.1 Plugin system

| Area | Current implementation |
| --- | --- |
| Runtime | Python, executed **in-process** by `exec()` |
| Loader | `plugin_loader.py` (186 lines) |
| Manifest | `Info.json` with `name`, `identifier`, `entry`, `permissions`, `enabled` |
| Security | Static AST allowlist: no imports, no dunder access, attribute whitelist, restricted builtins |
| API | 4 calls: `show_toast`, `current_path`, `play_pause`, `seek_relative` |
| Hooks | `on_load(api)`, `on_file_open(path)` |
| Lifecycle | Loaded once at startup; change requires editing `config.json` + restart |
| Discovery | `~/.config/inaa/plugins/`, enabled via `enabled_plugins` in `config.json` |
| Permissions | `show-osd`, `network-request`, `file-system`; the latter two cause the plugin to be **skipped** (there is no sandbox to run them in) |
| Management UI | Preferences → Plugins only has "Open plugin folder" |
| Example | `plugins/example-toast` |
| Tests | AST/sandbox escape regressions, lifecycle, dangerous-permission skip |

Known gaps:

1. Permissions are declarative only — `show-osd` is not enforced per call; any
   loaded plugin can call every API method.
2. No events beyond `on_file_open`: no playback/track/seek/playlist/tick events.
3. No UI contributions: no menu items, sidebar panels, overlays, dialogs, or
   subtitle providers.
4. No install flow, versioning, compatibility check, enable/disable UI, or
   reload. The example plugin's `on_file_open` is only reachable through
   `_trigger_plugin_hook`.
5. In-process `exec` can never be a real security boundary; the AST allowlist
   has been escaped before (see `test_plugin_sandbox_v4.py`).
6. No plugin storage/settings API, no HTTP broker, no resource limits.

### 1.2 Layout and theming

| Area | Current implementation |
| --- | --- |
| Root layout | Flat `Gtk.Box`: playlist sidebar (left, fixed 240 px) → video `Gtk.Overlay` → inspector (right, fixed 320 px) |
| Docking | Sidebar/inspector are shown/hidden only; no resize, no edge switching |
| OSD | Floating bottom-center, fixed size (440 px), auto-hide timer from config |
| Header bar | `Gtk.HeaderBar` always present; `auto_hide_chrome` hides it only after pointer idle, and there is no explicit mode/position |
| Theme | One hardcoded dark CSS blob in `player_window/theme.py`, applied globally |
| Palettes | None (dark glass only) |
| Accent color | Hardcoded `#007aff` |
| System theme | Not detected (no light mode, no portal color-scheme) |
| Presets | None |
| CSS health | Uses unsupported GTK properties (`overflow`, `z-index`), producing runtime `Theme parser error` warnings |
| Persistence | Flat keys in `config.json` (`auto_hide_chrome`, `osd_hide_ms`, `keep_above_mini`, ...) |
| Validation | `config_sanitize.py` covers existing keys only |

Constraints to respect:

- GTK4 CSS has no `z-index`, no real backdrop blur, and no arbitrary
  `overflow`. Glassmorphism is simulated with alpha + shadows.
- Wayland CSD limits how much the header bar can be hidden without losing drag
  and window controls.
- Plugins must not inject GTK widgets directly if we want process isolation
  later; UI must be declarative and rendered by the host.
- The Flatpak sandbox does not allow nested `bwrap`; isolation cannot rely on
  user namespaces alone.

---

## 2. Target state

### 2.1 Plugin platform v2

Guiding decisions:

- **Stay on Python.** It matches the app, the tests, and the existing plugin
  examples. No JS/WebKit runtime.
- **Split API facade from transport.** Plugins keep talking to an `api` object.
  Phase 3 implements it in-process with enforced capabilities; Phase 4 swaps the
  facade to a subprocess RPC client without changing plugin code.
- **Capabilities, not booleans.** A plugin declares fine-grained scopes; the
  host enforces each call and can show a consent prompt.
- **Declarative UI only.** Plugins describe widgets/overlays as data; the host
  renders them with INAA theming and accessibility.
- **Fail closed.** Unknown capability, malformed manifest, timeout, or crash
  disables the plugin with a visible reason.

Capability model:

| Capability | Grants |
| --- | --- |
| `ui.toast` | Transient toasts |
| `ui.osd` | OSD overlays (text, image from plugin dir) |
| `ui.menu` | Add items to app/video/playlist context menus |
| `ui.sidebar` | Declarative sidebar panel |
| `ui.dialog` | Host-rendered message/confirm dialogs |
| `playback.read` | Position, duration, speed, volume, tracks |
| `playback.control` | Play/pause/seek/speed/volume/next/prev |
| `playlist.read` / `playlist.write` | Read/modify playlist |
| `subtitles.read` | Track and cue metadata |
| `subtitles.provider` | Register an online subtitle provider |
| `mpv.props.read` / `mpv.props.write` | Allowlisted mpv properties only |
| `files.read` | Read files under granted roots (media folder, plugin dir) |
| `files.write` | Write only inside the plugin data dir |
| `storage` | Per-plugin key/value settings |
| `network` | HTTP through a host broker (timeouts, size limits) |
| `shell` | **Not offered.** Out of scope; use `network` + brokered APIs |

Manifest v2 (backward compatible reader):

```json
{
  "identifier": "io.github.inaa.example-stats",
  "name": "Playback Stats",
  "version": "1.0.0",
  "api_version": 2,
  "min_inaa_version": "0.3.0",
  "entry": "main.py",
  "capabilities": ["ui.toast", "ui.sidebar", "playback.read"],
  "contributes": {
    "menus": [{ "menu": "video-context", "label": "Playback stats…", "action": "show_stats" }],
    "sidebar": [{ "id": "stats", "title": "Stats", "action": "render_stats" }]
  },
  "settings": [{ "key": "compact", "type": "bool", "default": false }]
}
```

Plugin-facing API shape (stable across Phase 3/4):

```python
def on_load(api):
    api.on("file_open", on_file_open)
    api.on("playback_started", on_started)
    api.ui.add_sidebar_panel("stats", render_stats)
    api.storage.set("runs", api.storage.get("runs", 0) + 1)

def render_stats(api):
    return {
        "type": "box", "orientation": "vertical",
        "children": [
            {"type": "label", "text": api.playback.title()},
            {"type": "button", "label": "Reset", "action": "reset"},
        ],
    }

def on_action(api, action):
    if action == "reset":
        api.storage.clear()
```

Events (initial set):

`file_open`, `file_closed`, `playback_started`, `playback_paused`,
`playback_ended`, `seek`, `speed_changed`, `volume_changed`, `track_changed`,
`playlist_changed`, `shutdown`, plus a throttled `tick` (max 1/s, opt-in).

Management UX:

- Preferences → Plugins: list with version, capabilities, status, enable/disable,
  "Install from folder/zip", "Reload", "Uninstall", "View data folder".
- First enable shows a capability consent sheet; risky scopes are highlighted.
- Errors surface as toast + log entry with plugin id, never a silent skip.
- A `plugin.json` index format for an eventual registry, but **no in-app store
  in this roadmap** (Phase 6+).

Security model:

- One subprocess per plugin, started with a minimal environment, `cwd` set to the
  plugin dir, `RLIMIT_AS`/`CPU`/`NOFILE`, and a startup/response timeout.
- Host is the only side with filesystem/network/mpv access. Plugin requests are
  validated against its capability set and path/URL allowlists.
- No `shell`, no raw sockets, no `exec` of user code outside the worker.
- Signed manifests are designed for but not required initially; phase 5 adds
  Ed25519 signatures + trust-on-first-use.
- Keep the AST allowlist for legacy v1 plugins, clearly labeled "legacy,
  in-process".

### 2.2 Layout and theming

Layout model (`layout_config.py`, pure; GTK controller `player_window/layout.py` in Phase 1):

```json
{
  "layout": {
    "version": 1,
    "preset": "classic",
    "playlist": { "edge": "left", "visible": true, "width": 260 },
    "inspector": { "edge": "right", "visible": false, "width": 320 },
    "osc": { "mode": "floating", "position": "bottom", "size": "regular", "always_visible": false },
    "headerbar": "auto-hide",
    "theme": { "mode": "dark", "palette": "iina-glass", "accent": "blue" },
    "reduce_motion": false,
    "lock_aspect": false
  }
}
```

Behavior:

- Playlist and inspector each become a `Gtk.Paned` pane; widths persist and are
  clamped (160–600 px). Edges are `left`/`right`/`hidden`; if both target the
  same edge they stack in a single pane with a separator.
- OSC modes: `floating` (today), `docked` (single bar at the chosen edge),
  `off`. Position: `top`/`bottom`. Size: `compact`/`regular`/`large`.
  `always_visible` keeps it on screen during playback.
- Header bar modes: `full`, `auto-hide` (still shows on pointer to top edge),
  `hidden` (custom drag area + window controls; Wayland-safe).
- Presets: `classic`, `compact`, `cinema` (hidden chrome, minimal OSD),
  `music` (playlist right, large art). A preset only seeds values; user edits
  create a `custom` profile.
- Live apply: toggling a layout option updates widgets immediately, no restart.

Theming (refactor `theme.py` into a theme manager):

- CSS is generated from a palette dict instead of a fixed blob:
  background, surface, text, muted, border, accent, danger, shadow alpha.
- Palettes: `iina-glass` (current), `graphite`, `light`, `system`.
  `system` follows the XDG portal `org.freedesktop.appearance color-scheme`,
  falling back to `Gtk.Settings:gtk-application-prefer-dark-theme`.
- Accent choices: blue (default), purple, pink, orange, green, graphite.
- Fix invalid CSS (`overflow`, `z-index`) and the resulting parser warnings;
  use widget-level `set_overflow()`/clip containers where needed.
- Honor `gtk-enable-animations` / reduced motion: disable OSD fades and
  thumbnail zoom transitions.
- Scope providers per top-level window where possible so the preferences window
  and player can differ during a live theme switch.

Preferences structure:

- New **Layout** page in `prefs_mixin.py` mirroring IINA 1.5:
  dock edges, pane visibility/width, OSC mode/position/size, header bar mode,
  preset picker, reset to defaults.
- **Appearance** section (inside Layout or its own page): palette, accent,
  light/dark/system, reduced motion.

---

## 3. Phased plan

Estimates are for one developer, part-time assumptions noted. Each phase ships
behind a config flag where behavior changes are visible.

### Phase 0 — Foundations (S, ~1 week) — DONE

- Added `config_version` and nested `layout` defaults to `common.py`.
- Extended `config_sanitize.py` with strict enum/clamp validation for layout keys.
- Added `layout_config.py` with a `LayoutState` dataclass, `sanitize_layout`,
  presets, migration and `layout_v2_enabled` (pure, no GTK), plus
  `tests/test_layout_config.py`.
- Added the feature flag: `"ui_layout_v2": false` (config or `INAA_LAYOUT_V2=1`).
- Fixed `theme.py` invalid CSS (`overflow`, `z-index`; thumbnail clipping moved
  to `Gtk.Overflow.HIDDEN` in `input_mixin.py`) and added
  `tests/test_theme_css.py`, which loads the stylesheet through `Gtk.CssProvider`
  and asserts there are no parser warnings.

Exit criteria: layout config round-trips, invalid values are clamped, no CSS
parser warnings, existing tests green (apart from 4 pre-existing smoke failures
caused by the test harness isolating `HOME` from the user-installed `python-mpv`).

### Phase 1 — Dockable panes (M, ~2 weeks) — DONE

- Replaced the fixed sidebar/inspector children with a `Gtk.Paned` chain built
  by `player_window/layout.py` (`DockLayout`).
- Implemented edge switching (left/right/hidden) and persistent widths, stored
  in `layout.playlist` / `layout.inspector` and applied on startup.
- Kept the existing toggle buttons, `i` shortcut, context menu, mini player and
  window-fit logic working; the controller syncs button state with the config.
- Added a Layout prefs page (enable v2, dock visibility/edge/width, reset).
- Built on the Phase 0 migration (`auto_hide_chrome` → `layout.headerbar`);
  window `width`/`height` stay top-level (window geometry, not layout).
- When `ui_layout_v2` is off, behaviour stays legacy: playlist on the left,
  inspector on the right, both hidden until toggled, widths not persisted.

Files: `ui_builder.py`, `playlist_mixin.py`, `player_window/layout.py`,
`prefs_mixin.py`, `layout_config.py`, `filters_mixin.py`, `playback_mixin.py`.

Tests: `tests/test_layout_ui.py` (xvfb + GTK) covers edge changes, visibility,
suppression (mini player) and width persistence; `tests/test_layout_config.py`
covers the pure dock ordering.

Exit criteria: panes are resizable and survive restart; switching edges does
not lose playlist/inspector state; no regressions in mini-player or fullscreen.

### Phase 2 — OSC, header bar, themes (M–L, ~3 weeks)

- OSC modes/positions/sizes and `always_visible`; reposition via container
  layout, not CSS hacks.
- Header bar modes with a Wayland-safe hidden mode.
- Theme manager with palettes, accents, light/dark/system, reduced motion.
- Live theme switching; theme the preferences window consistently.
- Presets (`classic`, `compact`, `cinema`, `music`).
- Accessibility pass: focus rings, contrast check for all palettes, larger hit
  targets in `large` OSC.

Exit criteria: all palette × mode combinations render without warnings; theme
switch requires no restart; contrast validated (WCAG AA) for text on OSD.

### Phase 3 — Plugin API v2, in-process with capabilities (L, ~3–4 weeks)

- `plugin_manifest.py`: parse/validate v2 manifests, version compatibility,
  unknown capabilities rejected.
- `plugin_api.py`: capability-enforcing facade over the current window; keep the
  four existing methods as v1 aliases.
- Event bus: emit the event set from the mixins (`playback`, `playlist`,
  `subtitles`, `window`); guarantee ordering and exception isolation.
- Declarative UI: menu contributions, sidebar panel, overlays, dialogs.
- `storage` API scoped to `~/.config/inaa/plugin-data/<id>/`.
- Plugins prefs page: list, enable/disable, install from folder/zip, reload,
  uninstall, capability consent.
- Compatibility shim for v1 plugins; deprecation warning in logs.
- Example plugins: stats sidebar, context-menu action, subtitle provider stub.

Files: `plugin_loader.py` (orchestrator), new `plugin_manifest.py`,
`plugin_api.py`, `plugin_ui.py`, `player_window/__init__.py`,
`window_mixin.py`, `prefs_mixin.py`, tests.

Exit criteria: a v2 plugin can add a menu item and a sidebar panel, receive
playback events, persist settings, and be disabled/reloaded from the UI. All
existing security tests still pass; v1 example still loads.

### Phase 4 — Process isolation (L, ~4–6 weeks)

- `plugin_host.py`: worker entry point; loads one plugin, exposes the API over
  newline-delimited JSON-RPC on stdin/stdout.
- `plugin_rpc.py`: host-side client with request ids, per-call timeouts,
  crash/restart policy (max 3 restarts/min, then disable).
- Resource limits (`RLIMIT_*`), scrubbed env, plugin-dir `cwd`.
- Brokers: files (granted roots), network (host allowlist + size/time limits,
  reusing `opensubtitles.py` patterns), mpv properties (existing allowlist).
- Migrate the Phase 3 facade to RPC; plugin code unchanged.
- Security tests: capability bypass attempts, malformed RPC, huge payloads,
  path traversal, timeout, worker crash, zombie cleanup.
- Flatpak smoke test: plugin with `ui.toast` + `playback.read` works inside the
  sandbox; `network` works through the broker.

Exit criteria: no plugin code runs in the main process; a hanging plugin cannot
freeze the UI; capability violations return a structured error and are logged.

### Phase 5 — Ecosystem polish (M, ongoing)

- Manifest signing (Ed25519) + trust-on-first-use prompt.
- `inaa-plugin` CLI: create/sign/validate/package a plugin.
- Developer docs + type stubs for the `api` object.
- Registry index format and an external catalog (no in-app store yet).
- Deprecate/remove v1 in-process execution after a release cycle.

### Phase 6+ — Out of scope for this roadmap

- In-app marketplace purchases/ratings.
- JavaScript/WebKit plugin runtime.
- Arbitrary GTK widget injection.
- Multi-process per-window player instances (IINA `global` API parity).

---

## 4. Config schema and migrations

Add to `config.json`:

```json
{
  "config_version": 2,
  "ui_layout_v2": true,
  "plugin_api": 2,
  "layout": { "...": "see section 2.2" },
  "plugin_settings": { "io.github.inaa.example-stats": { "compact": false } }
}
```

Rules:

- Unknown keys inside `layout` are dropped; enums fall back to defaults.
- Widths clamped 160–600; `osc.size` ∈ {compact, regular, large}.
- `plugin_settings` is namespaced by plugin id and value size-capped (4 KiB per
  plugin) so a plugin cannot bloat `config.json`.
- Migration is one-way and idempotent: v1 keys map to `layout.*`, then
  `config_version` is bumped. Keep reading v1 keys for one release.

---

## 5. Test strategy

Unit (no display):

- `tests/test_layout_config.py`: defaults, clamps, enums, migration.
- `tests/test_plugin_manifest.py`: v1/v2 parsing, unknown capability rejection,
  version gates, path traversal in `entry`.
- `tests/test_plugin_capabilities.py`: every API call without its capability
  fails with `permission_denied`; with it succeeds.
- `tests/test_plugin_rpc.py`: framing, timeouts, crash/restart, oversized
  payloads, malformed JSON.
- `tests/test_theme_palettes.py`: every palette defines all required roles;
  generated CSS loads in a `Gtk.CssProvider` (xvfb/offscreen).

Integration:

- Extend `tests/test_plugin_sandbox_v4.py` and
  `tests/test_plugin_loader_security.py` with v2 equivalents; keep the v1 suite
  until v1 is removed.
- Smoke tests under `xvfb-run` for: dock edge switching, OSC position/size,
  theme switch, plugin sidebar render, menu action dispatch.
- Flatpak job: build, then run a headless plugin-host test plus a real
  `ui.toast`/`playback.read` smoke.

Manual checklist per release: Wayland and X11, fullscreen/mini-player, light and
dark, reduced motion, 200% scale, RTL (future).

---

## 6. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| GTK4 CSS/CSD limitations (no blur/z-index, hidden header bar on Wayland) | Visual regressions | Generate CSS from a small role set; prototype hidden-titlebar early in Phase 2; keep `auto-hide` as the safe default |
| Process isolation complexity in Flatpak | Slipped Phase 4 | Land a working in-process capability facade first; treat isolation as a transport swap; no bwrap dependency |
| Plugin ecosystem is empty at launch | Low adoption | Ship 3 first-party examples, templates, and docs before announcing |
| Widget-tree churn breaks mixins | Bugs in playlist/inspector | Layout controller owns panes; mixins keep operating on existing widget references |
| Performance regression from per-event RPC | UI jank | Batch/throttle `tick`; allow sync calls only for cheap reads; profile before/after |
| Config growth/corruption | Startup failures | `config_sanitize.py` is mandatory for every new key; migration tests |
| Scope creep into marketplace | Roadmap stall | Phase 6 list is explicitly out of scope |

---

## 7. Sequenced milestones

```
P0 foundations ──► P1 dockable panes ──► P2 OSC/themes
                         │                    │
                         └──────┬─────────────┘
                                ▼
                     P3 plugin API v2 (in-process)
                                ▼
                     P4 process isolation
                                ▼
                     P5 signing/tooling/docs
```

P3 depends on P1 only for sidebar placement, not for correctness; it can start
in parallel once the layout state model is stable. P2 and P3 are independent
otherwise.

Definition of done for the whole roadmap:

- Dockable, resizable playlist/inspector with persistent layout and presets.
- Palettes + accent + light/dark/system, no CSS warnings, reduced motion honored.
- Plugins declare capabilities; the host enforces them; v2 plugins can contribute
  menus, sidebars, overlays, events, storage, and subtitle providers.
- V2 plugins run out of process with timeouts and resource limits.
- Tests and docs above are in CI, and the Flatpak build passes with a plugin
  smoke test.

## 8. Open decisions

1. Minimum INAA version for v2 plugins: gate on `api_version` only, or also
   semantic app version? (Recommendation: both, `api_version` primary.)
2. Should sidebar panels support images/icons from the plugin dir, or text and
   symbolic icons only? (Recommendation: images with size cap + MIME sniffing.)
3. Plugin data location: `~/.config/inaa/plugin-data/<id>` vs
   `~/.local/share/inaa/plugins/<id>`. (Recommendation: XDG data dir for plugin
   state, config dir only for enabled flags.)
4. Theme switching strategy: regenerate one global provider vs per-window
   providers. (Recommendation: per-window providers, one palette source.)
5. Whether legacy v1 in-process plugins get a hard removal date in the next
   cycle.
