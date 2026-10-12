"""audio_devices.py: hanya perangkat yang dilaporkan mpv yang boleh dipilih."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio_devices as ad  # noqa: E402
from config_sanitize import sanitize_config  # noqa: E402

RAW = [
    {"name": "auto", "description": "Autoselect device"},
    {"name": "pulse/alsa_output.pci-0000", "description": "  Speaker \n  Built-in  "},
    {"name": "alsa", "description": "Default (alsa)"},
]


def test_auto_is_always_first_and_not_duplicated():
    devs = ad.parse_device_list(RAW)
    assert devs[0] == (ad.AUTO, ad.AUTO_LABEL)
    assert [n for n, _ in devs].count("auto") == 1
    assert [n for n, _ in devs] == ["auto", "pulse/alsa_output.pci-0000", "alsa"]


def test_descriptions_are_normalised_and_capped():
    devs = dict(ad.parse_device_list(RAW + [{"name": "x", "description": "d" * 999}]))
    assert devs["pulse/alsa_output.pci-0000"] == "Speaker Built-in"
    assert len(devs["x"]) == ad.MAX_DESC


@pytest.mark.parametrize("bad", [None, "x", 5, {}, [None, 1, "s", {}], [{"name": 5}, {"name": ""}, {"name": "a\nb"}, {"name": "a" * 300}, {"name": "a\x00"}]])
def test_garbage_yields_only_auto(bad):
    assert ad.parse_device_list(bad) == [(ad.AUTO, ad.AUTO_LABEL)]


def test_description_missing_falls_back_to_name():
    assert ad.parse_device_list([{"name": "alsa"}])[1] == ("alsa", "alsa")


def test_choose_device():
    devs = ad.parse_device_list(RAW)
    assert ad.choose_device("alsa", devs) == "alsa"
    assert ad.choose_device("usb-dicabut", devs) == "auto"          # hilang -> auto
    for bad in (None, 5, "", "a\nb", ["alsa"]):
        assert ad.choose_device(bad, devs) == "auto"


def test_config_sanitize_keeps_valid_and_resets_invalid():
    assert sanitize_config({"audio_device": "alsa"})["audio_device"] == "alsa"
    for bad in (None, 5, "", "a\nb", "x" * 300, ["alsa"]):
        assert sanitize_config({"audio_device": bad})["audio_device"] == "auto"
