"""Real scans through SANE's virtual 'test' scanner (no hardware needed)"""

import threading

import pytest
from PIL import Image

from backends.backend_base import ScanError, ScanRequest
from backends.backend_sane import SaneBackend
from conftest import requires_sane

pytestmark = requires_sane


@pytest.fixture
def backend():
    b = SaneBackend(only_backends=["test"])
    yield b
    b.close()


def test_lists_virtual_scanner(backend):
    assert "test:0" in [d.id for d in backend.list_devices()]


@pytest.mark.parametrize("mode,resolution,expect_mode", [("Color", 150, "RGB"), ("Gray", 75, "L")])
def test_flatbed_single_page(backend, tmp_path, mode, resolution, expect_mode):
    req = ScanRequest("test:0", str(tmp_path), "Flatbed", mode, resolution, 100, 50, multi_page=False)
    pages = backend.scan(req)
    assert len(pages) == 1
    img = Image.open(pages[0])
    assert img.mode == expect_mode
    # 100 x 50 mm at the requested resolution (+/- 1 px rounding)
    assert abs(img.width - round(100 / 25.4 * resolution)) <= 1


def test_feeder_scans_until_empty_with_progress(backend, tmp_path):
    progress, seen = [], []
    req = ScanRequest(
        "test:0", str(tmp_path), "Automatic Document Feeder", "Gray", 75, 50, 50, multi_page=True
    )
    pages = backend.scan(req, on_page=seen.append, on_progress=progress.append)
    assert len(pages) == 10 == len(seen)  # the virtual feeder holds 10 pages
    assert progress and max(progress) == 100


def test_cancel_keeps_pages_so_far(backend, tmp_path):
    cancel = threading.Event()
    seen = []

    def on_page(p):
        seen.append(p)
        if len(seen) == 2:
            cancel.set()

    req = ScanRequest(
        "test:0", str(tmp_path), "Automatic Document Feeder", "Gray", 75, 50, 50, multi_page=True
    )
    pages = backend.scan(req, on_page=on_page, cancel_event=cancel)
    assert 2 <= len(pages) < 10


def test_unknown_device_raises(backend, tmp_path):
    with pytest.raises(ScanError):
        backend.get_capabilities("test:99")


def test_test_scanner_uses_color_pattern(backend, tmp_path):
    from PIL import ImageStat

    req = ScanRequest("test:0", str(tmp_path), "Flatbed", "Color", 75, 60, 60, multi_page=False)
    assert "--test-picture" in backend.build_command(req)
    img = Image.open(backend.scan(req)[0])
    assert max(ImageStat.Stat(img).mean) > 20  # not the default solid black


def test_one_sheet_mode_on_feeder_scans_single_page(backend, tmp_path):
    req = ScanRequest("test:0", str(tmp_path), "Automatic Document Feeder", "Gray", 75, 50, 50, max_pages=1)
    assert "--batch-count=1" in backend.build_command(req)
    assert len(backend.scan(req)) == 1  # the virtual feeder holds 10; only one taken


def test_sane_calls_are_serialised(backend):
    """Concurrent option reads never overlap: a scanner is single-user"""
    import time
    from unittest import mock

    from backends import backend_sane

    active, overlap = [0], [False]
    real_run = backend_sane.subprocess.run

    def tracking_run(*args, **kwargs):
        active[0] += 1
        overlap[0] |= active[0] > 1
        time.sleep(0.05)
        try:
            return real_run(*args, **kwargs)
        finally:
            active[0] -= 1

    with mock.patch.object(backend_sane.subprocess, "run", tracking_run):
        threads = [threading.Thread(target=backend.get_capabilities, args=("test:0",)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert not overlap[0]
