"""
Connection Engine
Heuristic, multi-method scanner connection (docs/research/connection-methods.md).

1. Discovery asks every backend (SANE, direct eSCL) plus the USB probe what
   it sees, and groups entries that are the same physical scanner.
2. Each physical scanner gets its connection methods ranked:
     A1 open-source SANE driver (USB)      e.g. epsonds, pixma, genesys
     A3 vendor SANE driver                 e.g. epsonscan2, hpaio, brother*
     B2 driverless eSCL over IPP-USB       SANE airscan/escl on 127.0.0.1
     D1 linscanner's own eSCL client       backend_escl (USB or network)
     B1 driverless network eSCL / WSD      SANE airscan/escl
     C1 remote SANE (saned)                SANE net
     T  SANE virtual test scanner
3. A scan tries method 1; on a connection-type failure (busy, I/O, timeout,
   access, unsupported, missing driver) it tries the next, and so on. It
   never falls through when the user must act (feeder empty, jam, cover
   open), since another method on the same device would fail or double-feed.
"""

import re
from dataclasses import dataclass, field

from backends.backend_base import ScanError
from backends.parser_sane import model_key
from backends.usb_probe import likely_scanners, probe

METHOD_ORDER = ["A1", "A3", "B2", "D1", "B1", "C1", "T"]
METHOD_LABELS = {
    "A1": "Open-source SANE driver",
    "A3": "Vendor SANE driver",
    "B2": "Driverless eSCL over USB (ipp-usb)",
    "D1": "linscanner eSCL client",
    "B1": "Driverless network scanning (eSCL/WSD)",
    "C1": "Remote SANE (saned)",
    "T": "SANE virtual test scanner",
}
VENDOR_SANE_BACKENDS = {
    "epsonscan2",
    "hpaio",
    "hp",
    "brother",
    "brother2",
    "brother3",
    "brother4",
    "brother5",
}
VENDOR_SANE_PREFIXES = ("brother", "canon_pixma", "scangearmp")


def method_code(device):
    """Connection method code (A1/A3/B1/B2/C1/D1/T) for a backend device entry"""
    b = device.backend
    if b == "test":
        return "T"
    if b == "escl-direct":
        return "D1"
    if b == "net":
        return "C1"
    if b in ("airscan", "escl"):
        local = "127.0.0.1" in device.id or "localhost" in device.id or "(USB)" in device.model
        return "B2" if local else "B1"
    if b in VENDOR_SANE_BACKENDS or b.startswith(VENDOR_SANE_PREFIXES):
        return "A3"
    return "A1"


@dataclass
class Method:
    """One way to reach a physical scanner"""

    code: str
    backend: object  # ScannerBackend
    device: object  # ScannerDevice

    @property
    def label(self):
        """e.g. 'Open-source SANE driver · epsonds'"""
        return f"{METHOD_LABELS.get(self.code, self.code)} · {self.device.backend}"


@dataclass
class PhysicalDevice:
    """A scanner, with every method that can reach it (best first)"""

    key: str
    vendor: str
    model: str
    methods: list = field(default_factory=list)
    usb: object = None  # UsbDevice when known
    attempts: list = field(default_factory=list)  # [(method label, "ok" or error message)]
    hint: str = ""  # shown when no method works

    @property
    def id(self):
        """Stable id for the UI: the preferred method's device id (or the key)"""
        return self.methods[0].device.id if self.methods else self.key

    @property
    def backend(self):
        """Driver name of the preferred method"""
        return self.methods[0].device.backend if self.methods else "none"

    @property
    def kind(self):
        """Device type text from the preferred method"""
        return self.methods[0].device.kind if self.methods else "detected on USB"

    @property
    def label(self):
        """Display name with the driver in brackets"""
        extra = f" (+{len(self.methods) - 1} more)" if len(self.methods) > 1 else ""
        return f"{self.vendor} {self.model}  ({self.backend}{extra})".strip()


def _usb_for(device, usb_devices):
    """UsbDevice matching a SANE libusb:BBB:DDD device name, if any"""
    m = re.search(r"libusb:(\d{3}):(\d{3})", device.id)
    if m:
        bus, dev = int(m.group(1)), int(m.group(2))
        return next((u for u in usb_devices if u.bus == bus and u.dev == dev), None)
    return None


class ConnectionEngine:
    """Discovers physical scanners and scans with fallback across methods"""

    def __init__(self, backends, use_usb_probe=True):
        """backends: ScannerBackend instances (e.g. SaneBackend(), EsclBackend())"""
        self.backends = backends
        self.use_usb_probe = use_usb_probe
        self.devices = []

    # -- discovery -------------------------------------------------------------
    def discover(self):
        """List physical scanners (grouped), with ranked methods"""
        usb = probe() if self.use_usb_probe else []
        entries = []  # (method, usb_device)
        errors = []
        for backend in self.backends:
            try:
                found = backend.list_devices()
            except ScanError as e:
                errors.append(str(e))
                continue
            for d in found:
                entries.append((Method(method_code(d), backend, d), _usb_for(d, usb)))

        groups = []
        for method, u in entries:
            group = None
            for g in groups:
                same_usb = u is not None and g.usb is not None and (u.bus, u.dev) == (g.usb.bus, g.usb.dev)
                same_model = model_key(method.device) == model_key(g.methods[0].device)
                other_backend = all(m.device.backend != method.device.backend for m in g.methods)
                if same_usb or (same_model and other_backend and method.code != "T"):
                    group = g
                    break
            if group is None:
                group = PhysicalDevice(
                    key=method.device.id, vendor=method.device.vendor, model=method.device.model, usb=u
                )
                groups.append(group)
            group.methods.append(method)
            if group.usb is None and u is not None:
                group.usb = u

        for g in groups:
            g.methods.sort(key=lambda m: METHOD_ORDER.index(m.code) if m.code in METHOD_ORDER else 99)
            if g.usb is None:  # a USB SANE entry merged by model: find its USB facts
                g.usb = next((u for m in g.methods if (u := _usb_for(m.device, usb))), None)

        # USB devices that look like scanners but that no backend claimed
        claimed = {(g.usb.bus, g.usb.dev) for g in groups if g.usb}
        for u in likely_scanners(usb):
            if (u.bus, u.dev) in claimed:
                continue
            hint = self._hint(u)
            if not hint:
                continue
            groups.append(
                PhysicalDevice(
                    key=f"usb:{u.usb_id}:{u.bus}:{u.dev}",
                    vendor=u.manufacturer or u.vendor_db,
                    model=u.product or u.usb_id,
                    usb=u,
                    hint=hint,
                )
            )
        self.devices = groups
        self.discovery_errors = errors
        return groups

    @staticmethod
    def _hint(u):
        """Why a USB scanner-like device has no working method, and what to do"""
        if not u.accessible:
            return "Found on USB, but you don't have permission to use it. Replug it or log out and in."
        if "ipp-usb" in u.kinds:
            return (
                "Supports driverless IPP-over-USB. Start the ipp-usb service "
                "(sudo systemctl start ipp-usb) and check again. If it still isn't listed, "
                "the device may have no scanner (e.g. a printer)."
            )
        if "still-image" in u.kinds:
            return "Camera-type device (PTP). Install gphoto2 to import its images, or import them from its storage."
        if "sane-hwdb" in u.kinds:
            return (
                "SANE knows this scanner but no driver answered. Power-cycle it and check again; "
                "if it persists, the model may need a vendor driver or firmware."
            )
        if "vendor-protocol" in u.kinds:
            return (
                "Scanner maker's device with a vendor protocol and no SANE driver. "
                "Install the vendor's Linux driver or check the SANE supported-devices list."
            )
        return ""

    # -- scanning with fallback ------------------------------------------------
    def scan(self, physical, build_request, on_page=None, on_progress=None, cancel_event=None):
        """Try each method in order until one scans.

        build_request(method, capabilities) -> ScanRequest for that method.
        Raises the error if the user must act, or the last error if all fail."""
        if not physical.methods:
            raise ScanError(physical.hint or "No way to reach this scanner.", "no_device")
        physical.attempts = []
        last = None
        for method in physical.methods:
            if cancel_event and cancel_event.is_set():
                break
            try:
                caps = method.backend.get_capabilities(method.device.id)
                request = build_request(method, caps)
                pages = method.backend.scan(request, on_page, on_progress, cancel_event)
            except ScanError as e:
                physical.attempts.append((method.label, str(e)))
                if e.needs_user:
                    raise
                last = e
                continue
            physical.attempts.append((method.label, "ok"))
            return pages
        if last is None:
            return []
        tried = "; ".join(label for label, _ in physical.attempts)
        raise ScanError(f"{last} (tried: {tried})", last.code)
