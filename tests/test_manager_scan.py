"""Mapping user choices onto device capabilities"""

from backends.backend_base import ScannerCapabilities, ScannerDevice
from modules.manager_scan import filter_devices, is_feeder, pick_area, pick_mode, pick_resolution


def dev(backend, model="ES-400II"):
    return ScannerDevice(id=f"{backend}:x", vendor="Epson", model=model, kind="", backend=backend)


def test_color_and_bw_modes():
    modes = ["Lineart", "Gray", "Color"]
    assert pick_mode(modes, "color", "grayscale") == "Color"
    assert pick_mode(modes, "bw", "grayscale") == "Gray"
    assert pick_mode(modes, "bw", "pure") == "Lineart"
    assert pick_mode(["Gray", "Color"], "bw", "pure") == "Gray"  # no lineart: fall back
    assert pick_mode(["True Gray", "24bit Color"], "color", "grayscale") == "24bit Color"


def test_quality_snaps_to_supported_resolution():
    es400 = [50, 75, 100, 150, 200, 240, 300, 360, 400, 600]
    assert [pick_resolution(es400, q) for q in ("high", "medium", "low")] == [600, 300, 150]
    assert pick_resolution([100, 200, 400], "medium") == 400  # 300 is a tie -> higher
    assert pick_resolution([75, 200], "high") == 200


def test_paper_clamped_to_device():
    caps = ScannerCapabilities(max_width_mm=200, max_height_mm=200)
    assert pick_area(caps, "letter") == (200, 200)
    assert pick_area(ScannerCapabilities(max_width_mm=215.9, max_height_mm=393.7), "letter") == (215.9, 279.4)
    assert pick_area(caps, "auto") == (0.0, 0.0)


def test_feeder_detection():
    assert is_feeder("ADF Duplex") and is_feeder("Automatic Document Feeder")
    assert not is_feeder("Flatbed")


def test_duplicate_backends_hidden_and_test_scanner_hidden():
    devices = [dev("epsonscan2"), dev("epsonds"), dev("test", "frontend-tester")]
    visible = filter_devices(devices)
    assert [d.backend for d in visible] == ["epsonds"]
    assert len(filter_devices(devices, show_all=True)) == 3
