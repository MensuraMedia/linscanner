"""SANE output parsing against output captured from real devices"""

from backends.parser_sane import (
    capabilities_from_options,
    model_key,
    parse_device_list,
    parse_options,
    parse_progress,
    redact,
)
from conftest import fixture_text


def test_epson_es400ii_capabilities():
    caps = capabilities_from_options(parse_options(fixture_text("epsonds-es400ii-A.txt")))
    assert caps.sources == ["ADF Front", "ADF Duplex"]
    assert caps.modes == ["Lineart", "Gray", "Color"]
    assert caps.resolutions == [50, 75, 100, 150, 200, 240, 300, 360, 400, 600]
    assert (caps.max_width_mm, caps.max_height_mm) == (215.9, 393.7)
    assert caps.default_source == "ADF Front"


def test_boolean_and_empty_options_parse():
    opts = parse_options(fixture_text("epsonds-es400ii-A.txt"))
    assert opts["adf-skew"]["values"] == ["yes", "no"]
    assert opts["eject"]["values"] == []


def test_range_resolution_uses_standard_steps():
    caps = capabilities_from_options(parse_options(fixture_text("test-backend-A.txt")))
    assert caps.resolutions == [75, 100, 150, 200, 300, 400, 600, 1200]  # "1..1200dpi (in steps of 1)"
    assert "Automatic Document Feeder" in caps.sources


def test_device_list_and_serial_redaction():
    devices = parse_device_list(fixture_text("list-f.txt"))
    assert [d.backend for d in devices] == ["epsonds", "epsonscan2", "test", "airscan"]
    epson2 = devices[1]
    assert "0123456789ABCDEF01" not in epson2.model  # serial hidden from the UI
    assert model_key(devices[0]) == model_key(epson2) == "es400ii"
    assert "0123456789ABCDEF01" not in redact(epson2.id)


def test_progress():
    assert parse_progress("Progress: 3.1%\rProgress: 88.0%\r") == 88.0
    assert parse_progress("scanimage: rounded value") is None


def test_groups_flags_and_features():
    from backends.parser_sane import device_features

    opts = parse_options(fixture_text("epsonds-es400ii-A.txt"))
    assert opts["source"]["group"] == "standard"
    assert opts["load"]["flags"] == ["inactive"]
    assert opts["load"]["default"] == ""  # flag not swallowed into the value
    feats = device_features(opts)
    assert "Skew correction" in feats and "Auto-crop" in feats and "Load sheet (inactive)" in feats
    sensors = parse_options("  Sensors:\n    --scan[=(yes|no)] [no] [hardware]\n")
    assert sensors["scan"] == {
        "values": ["yes", "no"],
        "default": "no",
        "unit": "",
        "group": "sensors",
        "flags": ["hardware"],
    }
