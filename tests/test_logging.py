"""Logging: file, redaction, fail-safety, scan/feature/page records, diagnostics"""

import logging
import os
import threading
import zipfile

import pytest
from PIL import Image

from conftest import requires_sane
from utils import util_logging
from utils.util_logging import get_logger, setup_logging, write_diagnostics

SERIAL = "0123456789ABCDEF01"  # placeholder in the scanner-serial format


@pytest.fixture
def logfile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    path = setup_logging(debug=True)
    yield path
    setup_logging(debug=False)  # drop handlers pointing at tmp_path
    for h in list(logging.getLogger("linscanner").handlers):
        logging.getLogger("linscanner").removeHandler(h)


def read(path):
    for h in logging.getLogger("linscanner").handlers:
        h.flush()
    return open(path, encoding="utf-8").read()


def test_log_file_created_and_redacted(logfile):
    home = os.path.expanduser("~")
    get_logger("test").info("device epsonscan2:ES-400II:%s at %s/Documents", SERIAL, home)
    text = read(logfile)
    assert os.path.dirname(logfile).endswith(os.path.join("linscanner", "logs"))
    assert "ES-400II:…" in text and SERIAL not in text
    assert "~/Documents" in text and f"{home}/Documents" not in text


def test_unwritable_log_location_never_raises(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocker))  # makedirs will fail
    assert setup_logging() is None
    get_logger("test").error("still fine")  # must not raise


@requires_sane
def test_scan_is_logged(logfile, tmp_path):
    from backends.backend_base import ScanRequest
    from backends.backend_sane import SaneBackend

    backend = SaneBackend(only_backends=["test"])
    try:
        backend.scan(
            ScanRequest(
                "test:0", str(tmp_path / "s"), "Automatic Document Feeder", "Gray", 75, 50, 50, max_pages=2
            )
        )
    finally:
        backend.close()
    text = read(logfile)
    assert "scan start: scanimage -d test:0" in text
    assert "page 1 received" in text and "page 2 received" in text
    assert "scan end: 2 page(s), exit 0" in text


def test_feature_crash_logged_with_traceback(logfile, tmp_path):
    from features import BaseFeature, FeatureRegistry
    from modules.manager_settings import SettingsManager

    class Crashy(BaseFeature):
        id = "crashy"
        default_enabled = True

        def process_page(self, image, page):
            raise ValueError("processor exploded")

    reg = FeatureRegistry(SettingsManager(str(tmp_path / "s.json")), folder=str(tmp_path))  # no modules
    reg.features = [Crashy(reg.settings)]
    assert reg.process_page(Image.new("L", (100, 100), 255), {}) is not None
    text = read(logfile)
    assert (
        "feature crashy: process_page failed" in text and "Traceback" in text and "processor exploded" in text
    )


def test_page_notes_and_drops_logged(logfile, tmp_path):
    from features import FeatureRegistry
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager

    settings = SettingsManager(str(tmp_path / "s.json"))
    manager = ScanManager(settings, backend=object())
    manager.features = FeatureRegistry(settings)
    blank = str(tmp_path / "blank.png")
    Image.new("L", (800, 1000), 252).save(blank)
    assert manager.process_page({"path": blank, "rotation": 0, "dpi": 150, "mode": "Gray"}) is False
    text = read(logfile)
    assert "page blank.png: DROPPED by blank_removal [blank_score=" in text


def test_uncaught_thread_exception_logged(logfile):
    util_logging.install_excepthook()

    def boom():
        raise RuntimeError("worker blew up")

    t = threading.Thread(target=boom, name="worker-x")
    t.start()
    t.join()
    text = read(logfile)
    assert "Uncaught exception in thread worker-x" in text and "worker blew up" in text


def test_diagnostics_zip(logfile, tmp_path):
    get_logger("test").info("scanner serial %s", SERIAL)
    out = write_diagnostics(str(tmp_path / "diag.zip"), {"Scanner": f"id epsonscan2:ES-400II:{SERIAL}"})
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "system-info.txt" in names and any(n.startswith("linscanner-") for n in names)
        blob = "".join(z.read(n).decode() for n in names)
    assert "linscanner" in blob and "scanimage" in blob and SERIAL not in blob
