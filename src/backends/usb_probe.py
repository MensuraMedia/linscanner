"""
USB Probe
Driver-independent USB facts for scanner detection, read straight from sysfs
and the udev database (no subprocesses, no root):
identity, speed, interface classes, device-node access and SANE's udev match.
See docs/research/device-capabilities.md §5.
"""

import glob
import os
from dataclasses import dataclass, field

SYS_USB = "/sys/bus/usb/devices"
UDEV_DATA = "/run/udev/data"

# Vendor IDs of scanner makers (a vendor-specific USB interface from one of
# these is very likely a scanner)
SCANNER_VENDORS = {
    "04b8": "Epson",
    "04a9": "Canon",
    "03f0": "HP",
    "04f9": "Brother",
    "04c5": "Fujitsu",
    "05ca": "Ricoh",
    "0638": "Avision",
    "1083": "Canon (DR)",
    "040a": "Kodak",
    "07b3": "Plustek",
    "04da": "Panasonic",
    "04e8": "Samsung",
    "0924": "Xerox",
    "043d": "Lexmark",
    "0482": "Kyocera",
    "232b": "Pantum",
    "04a7": "Visioneer",
}


@dataclass
class UsbDevice:
    """One USB device and what its interfaces suggest"""

    bus: int
    dev: int
    vid: str
    pid: str
    manufacturer: str
    product: str
    speed_mbps: int
    port_path: str  # e.g. "3-5"
    interfaces: list = field(default_factory=list)  # [(class, subclass, protocol, driver)]
    node: str = ""  # /dev/bus/usb/BBB/DDD
    accessible: bool = False  # current user can open the node read/write
    libsane_matched: bool = False  # SANE's udev hwdb knows this scanner
    vendor_db: str = ""  # usb.ids vendor name from udev

    @property
    def usb_id(self):
        """VID:PID string"""
        return f"{self.vid}:{self.pid}"

    @property
    def libusb_name(self):
        """How SANE names this device: libusb:BBB:DDD"""
        return f"libusb:{self.bus:03d}:{self.dev:03d}"

    def has_class(self, cls, sub=None, proto=None):
        """True if any interface matches the class (and optional subclass/protocol)"""
        return any(
            c == cls and (sub is None or s == sub) and (proto is None or p == proto)
            for c, s, p, _ in self.interfaces
        )

    @property
    def kinds(self):
        """Why this device may be a scanner (empty list = probably not one)"""
        found = []
        if self.has_class(0x07, 0x01, 0x04):
            found.append("ipp-usb")  # IPP-over-USB: driverless eSCL through ipp-usb
        if self.has_class(0x06):
            found.append("still-image")  # PTP camera / some portable scanners
        if self.libsane_matched:
            found.append("sane-hwdb")  # listed in SANE's hardware database
        if self.has_class(0xFF) and self.vid in SCANNER_VENDORS:
            found.append("vendor-protocol")  # vendor-specific interface from a scanner maker
        return found


def _read(path, default=""):
    try:
        with open(path, errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def _udev_properties(sys_path):
    """E: properties from the udev database for a device (empty if unavailable)"""
    major_minor = _read(os.path.join(sys_path, "dev"))
    props = {}
    if major_minor:
        for line in _read(os.path.join(UDEV_DATA, f"c{major_minor}")).splitlines():
            if line.startswith("E:") and "=" in line:
                key, value = line[2:].split("=", 1)
                props[key] = value
    return props


def probe(sys_root=SYS_USB):
    """All USB devices (not hubs' interfaces) with scanner-relevant facts"""
    devices = []
    for path in sorted(glob.glob(os.path.join(sys_root, "*"))):
        base = os.path.basename(path)
        if ":" in base or not os.path.exists(os.path.join(path, "idVendor")):
            continue
        interfaces = []
        for iface in sorted(glob.glob(os.path.join(path, f"{base}:*"))):
            try:
                cls = int(_read(f"{iface}/bInterfaceClass", "0"), 16)
                sub = int(_read(f"{iface}/bInterfaceSubClass", "0"), 16)
                proto = int(_read(f"{iface}/bInterfaceProtocol", "0"), 16)
            except ValueError:
                continue
            drv = (
                os.path.basename(os.path.realpath(f"{iface}/driver"))
                if os.path.exists(f"{iface}/driver")
                else ""
            )
            interfaces.append((cls, sub, proto, drv))
        try:
            bus, dev = int(_read(f"{path}/busnum", "0")), int(_read(f"{path}/devnum", "0"))
            speed = int(float(_read(f"{path}/speed", "0") or 0))
        except ValueError:
            continue
        node = f"/dev/bus/usb/{bus:03d}/{dev:03d}"
        props = _udev_properties(path)
        devices.append(
            UsbDevice(
                bus=bus,
                dev=dev,
                vid=_read(f"{path}/idVendor"),
                pid=_read(f"{path}/idProduct"),
                manufacturer=_read(f"{path}/manufacturer"),
                product=_read(f"{path}/product"),
                speed_mbps=speed,
                port_path=base,
                interfaces=interfaces,
                node=node,
                accessible=os.access(node, os.R_OK | os.W_OK),
                libsane_matched=props.get("libsane_matched") == "yes",
                vendor_db=props.get("ID_VENDOR_FROM_DATABASE", ""),
            )
        )
    return devices


def likely_scanners(devices):
    """USB devices that are probably scanners (or scanner-capable MFPs)"""
    return [d for d in devices if d.kinds and d.vid != "1d6b"]  # 1d6b = Linux root hubs


def speed_label(mbps):
    """Human USB speed name"""
    return {1: "USB 1.0 low speed", 12: "USB 1.1 full speed", 480: "USB 2.0", 5000: "USB 3.x (5 Gbps)"}.get(
        mbps, f"USB 3.x ({mbps / 1000:g} Gbps)" if mbps > 5000 else f"{mbps} Mbps"
    )
