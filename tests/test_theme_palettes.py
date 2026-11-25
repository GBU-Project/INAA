"""Palet + generator CSS tema (Phase 2.0): murni, tanpa GTK/libmpv."""
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import layout_config as lc  # noqa: E402
import palette as pal  # noqa: E402
import theme_css  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "iina_css_v1.css"


def test_default_css_is_identical_to_the_legacy_stylesheet():
    expected = FIXTURE.read_text(encoding="utf-8").strip()
    assert theme_css.build_css("iina-glass", "blue").strip() == expected


def test_palette_and_accent_names_match_layout_schema():
    assert pal.PALETTE_NAMES == lc.PALETTES
    assert pal.ACCENT_NAMES == lc.ACCENTS


@pytest.mark.parametrize("name", pal.PALETTE_NAMES)
def test_every_palette_defines_all_required_roles(name):
    palette = pal.get_palette(name)
    assert palette.name == name
    missing = [r for r in pal.REQUIRED_ROLES if r not in palette.tokens]
    assert not missing, missing
    extra = [r for r in palette.tokens if r not in pal.REQUIRED_ROLES]
    assert not extra, extra


@pytest.mark.parametrize("name", pal.ACCENT_NAMES)
def test_every_accent_defines_all_accent_roles(name):
    tokens = pal.accent_tokens(name)
    assert set(tokens) == set(pal.ACCENT_ROLES)


def test_template_only_uses_known_tokens():
    known = set(pal.REQUIRED_ROLES) | set(pal.ACCENT_ROLES)
    assert theme_css.template_tokens() <= known


@pytest.mark.parametrize("palette,accent", list(itertools.product(pal.PALETTE_NAMES, pal.ACCENT_NAMES)))
def test_every_combination_builds_clean_css(palette, accent):
    css = theme_css.build_css(palette, accent)
    assert "@" not in css
    assert css.count("{") == css.count("}")
    for bad in ("overflow:", "z-index:"):
        assert bad not in css


def test_unknown_names_fall_back_to_defaults():
    assert theme_css.build_css("nope", "nope") == theme_css.build_css("iina-glass", "blue")


def test_light_palette_inverts_line_color_and_default_does_not():
    assert "rgba(0, 0, 0, 0.14)" in theme_css.build_css("light", "blue")
    assert "rgba(255, 255, 255, 0.14)" in theme_css.build_css("iina-glass", "blue")


def test_accent_changes_only_accent_roles():
    blue = theme_css.build_css("iina-glass", "blue")
    green = theme_css.build_css("iina-glass", "green")
    assert "#007aff" in blue and "#007aff" not in green
    assert "#34c759" in green


# -- kontras ---------------------------------------------------------------
AA = 4.5
BACKDROPS = ("#000000", "#ffffff")  # video bisa gelap atau terang di belakang panel kaca


@pytest.mark.parametrize("name", pal.PALETTE_NAMES)
def test_osd_text_is_readable_over_any_video(name):
    t = pal.get_palette(name).tokens
    for backdrop in BACKDROPS:
        for role in ("osd_text", "osd_text_2"):
            ratio = pal.contrast_ratio(t[role], t["osd_bg"], backdrop)
            assert ratio >= AA, (name, role, backdrop, round(ratio, 2))


@pytest.mark.parametrize("name", pal.PALETTE_NAMES)
def test_text_roles_are_readable_on_their_surfaces(name):
    t = pal.get_palette(name).tokens
    pairs = [
        ("text", "prefs_bg"), ("text", "prefs_content_bg"), ("text", "dialog_bg"),
        ("text", "action_bg"), ("text_2", "prefs_sidebar_bg"), ("text_3", "welcome_card_bg"),
        ("text_4", "inspector_bg"), ("text_strong", "prefs_content_bg"),
        ("muted", "prefs_content_bg"), ("muted", "welcome_card_bg"), ("muted", "dialog_bg"),
        ("muted_2", "inspector_bg"), ("muted_3", "inspector_bg"), ("dim", "dialog_bg"),
        ("dim", "welcome_card_bg"), ("ok", "inspector_bg"),
        ("toast_text", "toast_bg"),
    ]
    for fg_role, bg_role in pairs:
        # permukaan transparan digabung di atas latar utama palet itu
        base = t["prefs_content_bg"]
        ratio = pal.contrast_ratio(t[fg_role], t[bg_role], base)
        assert ratio >= AA, (name, fg_role, bg_role, round(ratio, 2))


@pytest.mark.parametrize("name", pal.ACCENT_NAMES)
def test_text_on_accent_is_readable(name):
    t = pal.accent_tokens(name)
    ratio = pal.contrast_ratio(t["accent_text"], t["accent"])
    # blue memakai putih seperti IINA/macOS (4.0:1); ambang 3.0 = teks tebal/komponen UI
    assert ratio >= 3.0, (name, round(ratio, 2))


def test_contrast_ratio_known_values():
    assert pal.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert pal.contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_parse_color_formats():
    assert pal.parse_color("#007aff") == (0, 122, 255, 1.0)
    assert pal.parse_color("rgba(26, 26, 28, 0.82)") == (26, 26, 28, 0.82)
    with pytest.raises(ValueError):
        pal.parse_color("merah")
