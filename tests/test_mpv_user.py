"""Tes unit mpv_user: parser mpv.conf, daftar putih opsi, shader, script, dan sifat 'opt-in'."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mpv_user  # noqa: E402


class FakePlayer:
    """Mencatat semua yang disentuh; bisa dipaksa gagal untuk opsi tertentu."""

    def __init__(self, fail_keys=()):
        self.set_calls = {}
        self.commands = []
        self.fail_keys = set(fail_keys)

    def __setitem__(self, key, value):
        if key in self.fail_keys:
            raise RuntimeError("mpv menolak")
        self.set_calls[key] = value

    def command(self, *args):
        self.commands.append(args)


# ------------------------------------------------------------------- parse_conf

def test_parse_conf_basics():
    text = "\n".join(
        [
            "# komentar",
            "",
            "deband",
            "no-interpolation",
            'sub-font="Noto Sans"',
            "Sub_Font_Size = 45",
            "color=#FF0000   ",   # '#' di dalam nilai bukan komentar
        ]
    )
    got = {(k, v) for _, k, v in mpv_user.parse_conf(text)}
    assert ("deband", "yes") in got
    assert ("interpolation", "no") in got
    assert ("sub-font", "Noto Sans") in got
    assert ("sub-font-size", "45") in got
    assert ("color", "#FF0000") in got


def test_parse_conf_ignores_profile_sections_but_returns_to_default():
    text = "deband\n[cinema]\nscale=ewa_lanczos\n[default]\ninterpolation\n"
    keys = [k for _, k, _ in mpv_user.parse_conf(text)]
    assert keys == ["deband", "interpolation"]


# ------------------------------------------------------------------- apply_conf

def _conf(tmp_path, body):
    p = tmp_path / "mpv.conf"
    p.write_text(body)
    return p


def test_safe_options_are_applied(tmp_path):
    p = _conf(tmp_path, "deband=yes\nsub-font-size=50\nhwdec=vaapi\nno-interpolation\naudio-delay=0.2\n")
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_conf(player, p, rep)
    assert player.set_calls == {"deband": "yes", "sub-font-size": "50", "hwdec": "vaapi", "interpolation": "no", "audio-delay": "0.2"}
    assert not rep.rejected


@pytest.mark.parametrize(
    "line",
    [
        "vo=gpu", "ao=pulse", "osc=yes", "input-ipc-server=/tmp/mpv.sock", "input-conf=/tmp/x",
        "script=/tmp/evil.lua", "scripts=/tmp/evil.lua", "scripts-append=/tmp/evil.lua",
        "load-scripts=yes", "ytdl-raw-options=exec=whoami", "ytdl-format=best", "include=/tmp/other.conf",
        "profile=big", "vf=lavfi=[movie=/etc/passwd]", "af=lavfi=[amovie=/etc/passwd]",
        "lavfi-complex=[x]", "log-file=/tmp/log", "screenshot-directory=/etc", "sub-file=/etc/passwd",
        "external-file=/etc/passwd", "glsl-shaders=/tmp/x.glsl", "watch-later-directory=/tmp",
        "use-filedir-conf=yes", "unknown-option=1",
    ],
)
def test_dangerous_or_forced_options_are_never_applied(tmp_path, line):
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_conf(player, _conf(tmp_path, line + "\n"), rep)
    assert player.set_calls == {}, f"{line} seharusnya tidak diterapkan"
    assert len(rep.rejected) == 1


def test_forced_options_cannot_be_set_even_via_dash_underscore_or_case(tmp_path):
    body = "VO=gpu\nInput_IPC_Server=/tmp/s\nOSC=yes\n"
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_conf(player, _conf(tmp_path, body), rep)
    assert player.set_calls == {}
    assert len(rep.rejected) == 3


def test_one_failing_option_does_not_block_the_rest(tmp_path):
    p = _conf(tmp_path, "deband=yes\nsub-font-size=50\n")
    player, rep = FakePlayer(fail_keys={"deband"}), mpv_user.Report()
    mpv_user.apply_conf(player, p, rep)
    assert player.set_calls == {"sub-font-size": "50"}
    assert len(rep.rejected) == 1 and "gagal diterapkan" in rep.rejected[0][1]


def test_missing_oversized_and_long_values(tmp_path):
    rep = mpv_user.Report()
    mpv_user.apply_conf(FakePlayer(), tmp_path / "nope.conf", rep)
    assert "tidak ditemukan" in rep.rejected[0][1]

    big = _conf(tmp_path, "# " + "x" * (mpv_user.MAX_CONF_BYTES + 10))
    rep = mpv_user.Report()
    player = FakePlayer()
    mpv_user.apply_conf(player, big, rep)
    assert player.set_calls == {} and "terlalu besar" in rep.rejected[0][1]

    rep, player = mpv_user.Report(), FakePlayer()
    mpv_user.apply_conf(player, _conf(tmp_path, "sub-font=" + "a" * 600 + "\n"), rep)
    assert player.set_calls == {} and len(rep.rejected) == 1


# --------------------------------------------------------------------- shaders

def test_shaders_relative_inside_folder_and_absolute(tmp_path):
    sdir = tmp_path / "shaders"
    sdir.mkdir()
    (sdir / "a.glsl").write_text("//!HOOK LUMA")
    outside = tmp_path / "b.hook"
    outside.write_text("//!HOOK LUMA")
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_shaders(player, ["a.glsl", str(outside)], sdir, rep)
    appended = [c[3] for c in player.commands if c[:3] == ("change-list", "glsl-shaders", "append")]
    assert appended == [str((sdir / "a.glsl").resolve()), str(outside.resolve())]
    assert player.commands[0] == ("change-list", "glsl-shaders", "clr", "")
    assert not rep.rejected


@pytest.mark.parametrize("entry", ["../escape.glsl", "../../etc/passwd", "a.txt", "missing.glsl", "", None, 5])
def test_bad_shaders_rejected(tmp_path, entry):
    sdir = tmp_path / "shaders"
    sdir.mkdir()
    (tmp_path / "escape.glsl").write_text("x")
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_shaders(player, [entry], sdir, rep)
    assert player.commands == []
    assert len(rep.rejected) == 1


def test_shader_symlink_escape_is_rejected(tmp_path):
    sdir = tmp_path / "shaders"
    sdir.mkdir()
    outside = tmp_path / "secret.glsl"
    outside.write_text("x")
    (sdir / "link.glsl").symlink_to(outside)
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_shaders(player, ["link.glsl"], sdir, rep)
    assert player.commands == [] and len(rep.rejected) == 1


# --------------------------------------------------------------------- scripts

def test_scripts_only_explicit_absolute_existing(tmp_path):
    good = tmp_path / "ok.lua"
    good.write_text("-- hi")
    js = tmp_path / "ok.js"
    js.write_text("// hi")
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_scripts(player, [str(good), str(js), str(good)], rep)  # duplikat diabaikan
    assert [c for c in player.commands] == [("load-script", str(good.resolve())), ("load-script", str(js.resolve()))]


@pytest.mark.parametrize("entry", ["relative.lua", "~nonexistent/x.lua", "/tmp/definitely-missing-xyz.lua", "", None])
def test_bad_scripts_rejected(entry):
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_scripts(player, [entry], rep)
    assert player.commands == [] and len(rep.rejected) == 1


def test_script_wrong_extension_rejected(tmp_path):
    sh = tmp_path / "run.sh"
    sh.write_text("echo hi")
    player, rep = FakePlayer(), mpv_user.Report()
    mpv_user.apply_scripts(player, [str(sh)], rep)
    assert player.commands == [] and "ekstensi" in rep.rejected[0][1]


# ------------------------------------------------------------- opt-in & robust

def test_everything_is_off_by_default():
    player = FakePlayer()
    rep = mpv_user.apply_user_settings(player, {}, Path("/nonexistent"))
    assert player.set_calls == {} and player.commands == []
    assert rep.applied == [] and rep.rejected == []


@pytest.mark.parametrize("config", [
    {"mpv_conf": ""}, {"mpv_conf": None}, {"mpv_conf": 5}, {"mpv_shaders": "a.glsl"},
    {"mpv_shaders": None}, {"mpv_scripts": "x.lua"}, {"mpv_scripts": {"a": 1}},
])
def test_malformed_config_values_are_ignored_without_crashing(config):
    player = FakePlayer()
    rep = mpv_user.apply_user_settings(player, config, Path("/nonexistent"))
    assert player.set_calls == {} and player.commands == []


def test_master_entry_applies_all_three_and_summarises(tmp_path):
    sdir = tmp_path / "shaders"
    sdir.mkdir()
    (sdir / "s.glsl").write_text("x")
    script = tmp_path / "s.lua"
    script.write_text("x")
    conf = tmp_path / "mpv.conf"
    conf.write_text("deband=yes\nosc=yes\n")
    cfg = {"mpv_conf": str(conf), "mpv_shaders": ["s.glsl"], "mpv_scripts": [str(script)]}
    player = FakePlayer()
    rep = mpv_user.apply_user_settings(player, cfg, sdir)
    assert player.set_calls == {"deband": "yes"}
    assert len(rep.shaders) == 1 and len(rep.scripts) == 1 and len(rep.rejected) == 1
    assert "1 opsi" in rep.summary() and "1 diabaikan" in rep.summary()


def test_unexpected_exception_is_contained(tmp_path):
    script = tmp_path / "s.lua"
    script.write_text("x")

    # command() yang melempar Exception biasa harus tercatat, bukan crash
    class Fails(FakePlayer):
        def command(self, *a):
            raise RuntimeError("tidak ada dukungan lua")

    rep = mpv_user.apply_user_settings(Fails(), {"mpv_scripts": [str(script)]}, tmp_path)
    assert rep.scripts == [] and "gagal dimuat" in rep.rejected[0][1]


def test_use_mpv_conf_flag_reads_default_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".config" / "mpv").mkdir(parents=True)
    (home / ".config" / "mpv" / "mpv.conf").write_text("deband=yes\nscript=/tmp/evil.lua\nytdl=yes\n")
    monkeypatch.setenv("HOME", str(home))
    player = FakePlayer()
    rep = mpv_user.apply_user_settings(player, {"use_mpv_conf": True}, tmp_path)
    assert player.set_calls == {"deband": "yes"} and len(rep.rejected) == 2
    off = FakePlayer()
    mpv_user.apply_user_settings(off, {"use_mpv_conf": False}, tmp_path)
    assert off.set_calls == {}


def test_gl_area_never_lets_mpv_read_its_own_config():
    src = (Path(__file__).resolve().parent.parent / "player_window" / "gl_area.py").read_text()
    assert '"config": False' in src and "bool(use_mpv_conf)" not in src
