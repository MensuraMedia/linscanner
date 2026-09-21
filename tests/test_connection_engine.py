"""Connection engine: grouping, method order and fallback, with fake backends"""

import pytest

from backends.backend_base import ScanError, ScannerCapabilities, ScannerDevice, ScanRequest
from backends.usb_probe import UsbDevice
from modules import manager_connection
from modules.manager_connection import ConnectionEngine, method_code


def dev(backend, dev_id, model="ES-400II", vendor="Epson"):
    return ScannerDevice(id=dev_id, vendor=vendor, model=model, kind="", backend=backend)


class FakeBackend:
    """Backend returning fixed devices; scan() fails with a chosen error code"""

    def __init__(self, devices, fail_code=None, pages=2):
        self.devices, self.fail_code, self.pages, self.scanned = devices, fail_code, pages, []

    def list_devices(self):
        return self.devices

    def get_capabilities(self, device_id):
        return ScannerCapabilities(sources=["ADF"], modes=["Color"], resolutions=[300])

    def scan(self, request, on_page=None, on_progress=None, cancel_event=None):
        self.scanned.append(request.device_id)
        if self.fail_code:
            raise ScanError(f"failed with {self.fail_code}", self.fail_code)
        return [f"/tmp/{request.device_id}-{i}.png" for i in range(self.pages)]


def build(method, caps):
    return ScanRequest(method.device.id, "/tmp", "ADF", "Color", 300, multi_page=True)


def test_method_codes():
    assert method_code(dev("epsonds", "epsonds:libusb:003:096")) == "A1"
    assert method_code(dev("epsonscan2", "epsonscan2:ES-400II:x")) == "A3"
    assert method_code(dev("hpaio", "hpaio:/usb/x")) == "A3"
    assert method_code(dev("airscan", "airscan:e0:Brother")) == "B1"
    assert method_code(dev("airscan", "airscan:e1:Canon TS (USB)", model="TS (USB)")) == "B2"
    assert method_code(dev("escl-direct", "escl-direct:http://127.0.0.1:60000/eSCL")) == "D1"
    assert method_code(dev("net", "net:host:epsonds:x")) == "C1"
    assert method_code(dev("test", "test:0")) == "T"


def test_grouping_and_order():
    vendor = FakeBackend([dev("epsonscan2", "epsonscan2:ES-400II:x")])
    sane = FakeBackend(
        [
            dev("epsonds", "epsonds:libusb:003:096"),
            dev("test", "test:0", "tester"),
            dev("test", "test:1", "tester"),
        ]
    )
    engine = ConnectionEngine([vendor, sane], use_usb_probe=False)
    devices = engine.discover()
    epson = [d for d in devices if d.model == "ES-400II"]
    assert len(epson) == 1  # two drivers, one physical scanner
    assert [m.code for m in epson[0].methods] == ["A1", "A3"]  # open driver first
    assert epson[0].id == "epsonds:libusb:003:096"
    assert len([d for d in devices if d.model == "tester"]) == 2  # same driver = separate devices


def test_fallback_on_busy_then_success():
    bad = FakeBackend([dev("epsonds", "epsonds:libusb:003:096")], fail_code="busy")
    good = FakeBackend([dev("epsonscan2", "epsonscan2:ES-400II:x")])
    engine = ConnectionEngine([bad, good], use_usb_probe=False)
    phys = engine.discover()[0]
    pages = engine.scan(phys, build)
    assert pages == ["/tmp/epsonscan2:ES-400II:x-0.png", "/tmp/epsonscan2:ES-400II:x-1.png"]
    assert [status for _, status in phys.attempts] == ["failed with busy", "ok"]


def test_no_fallback_when_user_must_act():
    empty = FakeBackend([dev("epsonds", "epsonds:libusb:003:096")], fail_code="no_docs")
    other = FakeBackend([dev("epsonscan2", "epsonscan2:ES-400II:x")])
    engine = ConnectionEngine([empty, other], use_usb_probe=False)
    phys = engine.discover()[0]
    with pytest.raises(ScanError) as err:
        engine.scan(phys, build)
    assert err.value.code == "no_docs"
    assert other.scanned == []  # never tried: would double-feed or fail the same way


def test_all_methods_fail_reports_every_attempt():
    a = FakeBackend([dev("epsonds", "epsonds:libusb:003:096")], fail_code="io")
    b = FakeBackend([dev("epsonscan2", "epsonscan2:ES-400II:x")], fail_code="timeout")
    engine = ConnectionEngine([a, b], use_usb_probe=False)
    phys = engine.discover()[0]
    with pytest.raises(ScanError) as err:
        engine.scan(phys, build)
    assert "tried:" in str(err.value) and err.value.code == "timeout"


def test_usb_scanner_without_driver_gets_a_hint(monkeypatch):
    lonely = UsbDevice(
        bus=1,
        dev=5,
        vid="04f9",
        pid="1234",
        manufacturer="Brother",
        product="DS-640",
        speed_mbps=480,
        port_path="1-2",
        interfaces=[(0xFF, 0xFF, 0xFF, "")],
        accessible=True,
    )
    monkeypatch.setattr(manager_connection, "probe", lambda: [lonely])
    engine = ConnectionEngine([FakeBackend([])])
    devices = engine.discover()
    assert len(devices) == 1 and not devices[0].methods
    assert "vendor" in devices[0].hint.lower()
    with pytest.raises(ScanError):
        engine.scan(devices[0], build)
