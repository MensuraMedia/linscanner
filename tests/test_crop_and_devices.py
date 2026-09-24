"""Crop maths, the Devices page sections, and keeping printers out of the scanner list"""

from dataclasses import dataclass, field

from modules import manager_device_info as info
from modules.manager_connection import ConnectionEngine
from utils.util_imaging import crop_box


# -- crop ----------------------------------------------------------------------------------------
def test_crop_box_from_fractions():
    assert crop_box((1000, 800), 0.1, 0.25, 0.6, 0.75) == (100, 200, 600, 600)


def test_crop_box_clamps_to_the_page():
    assert crop_box((100, 100), -0.5, -0.5, 1.5, 1.5) == (0, 0, 100, 100)


def test_crop_box_refuses_a_sliver():
    assert crop_box((1000, 800), 0.5, 0.5, 0.501, 0.9) is None
    assert crop_box((1000, 800), 0.5, 0.5, 0.9, 0.5005) is None


# -- Devices page ---------------------------------------------------------------------------------
@dataclass
class FakeUsb:
    usb_id: str = "04a9:18a4"
    manufacturer: str = "Canon"
    product: str = "TR150 series"
    vendor_db: str = ""
    port_path: str = "3-4"
    bus: int = 3
    dev: int = 80
    speed_mbps: int = 480
    accessible: bool = False
    libsane_matched: bool = False
    interfaces: list = field(default_factory=lambda: [(0x07, 0x01, 0x02, ""), (0xFF, 0xFF, 0xFF, "")])
    kinds: list = field(default_factory=lambda: ["vendor-protocol"])


@dataclass
class FakeDevice:
    vendor: str = "Epson"
    model: str = "ES-400II"
    usb: FakeUsb = None
    methods: list = field(default_factory=list)
    attempts: list = field(default_factory=list)
    hint: str = ""
    kind: str = "usb"


class FakeCaps:
    sources = ["Flatbed", "ADF Duplex"]
    modes = ["Color", "Gray"]
    resolutions = [75, 150, 300, 600]
    max_width_mm = 215.9
    max_height_mm = 297.0
    options = {}


def test_sections_put_capabilities_after_identity():
    titles = [t for t, _rows in info.sections(FakeDevice(usb=FakeUsb()), FakeCaps())]
    assert titles[0] == "Identity" and titles[1] == "Capabilities"
    assert titles[2] == "Connection" and titles[3].startswith("Connection methods")


def test_sections_without_capabilities():
    titles = [t for t, _rows in info.sections(FakeDevice(usb=FakeUsb()), None)]
    assert "Capabilities" not in titles and titles[0] == "Identity"


def test_a_printer_is_not_listed_as_a_scanner(monkeypatch):
    """A printer speaks IPP-USB like scanner MFPs do, but offers no scanner service"""
    monkeypatch.setattr("modules.manager_connection._escl_scanner_on_usb", lambda: False)
    assert ConnectionEngine._printer_without_scanner(FakeUsb())


def test_an_mfp_is_kept(monkeypatch):
    """The same shape of device, but something on ipp-usb really scans"""
    monkeypatch.setattr("modules.manager_connection._escl_scanner_on_usb", lambda: True)
    assert not ConnectionEngine._printer_without_scanner(FakeUsb())


def test_a_known_scanner_is_kept(monkeypatch):
    monkeypatch.setattr("modules.manager_connection._escl_scanner_on_usb", lambda: False)
    scanner = FakeUsb(kinds=["sane-hwdb", "vendor-protocol"], libsane_matched=True)
    assert not ConnectionEngine._printer_without_scanner(scanner)
    no_printer_interface = FakeUsb(interfaces=[(0xFF, 0xFF, 0xFF, "")])
    assert not ConnectionEngine._printer_without_scanner(no_printer_interface)
