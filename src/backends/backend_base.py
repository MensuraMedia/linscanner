"""
Scanner Backend Interface
Every scanner backend (SANE today; others can be added) implements this
interface, so the UI never depends on a specific driver technology.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScannerDevice:
    """A scanner as reported by a backend"""

    id: str  # backend device name, e.g. "epsonds:libusb:003:096"
    vendor: str
    model: str
    kind: str  # e.g. "flatbed scanner", "ESC/I-2"
    backend: str  # driver within the backend, e.g. "epsonds"

    @property
    def label(self):
        return f"{self.vendor} {self.model}  ({self.backend})"


@dataclass
class ScannerCapabilities:
    """What a device can do, normalised from its options"""

    sources: list = field(default_factory=list)  # device's own names, e.g. "ADF Duplex"
    modes: list = field(default_factory=list)  # e.g. ["Lineart", "Gray", "Color"]
    resolutions: list = field(default_factory=list)  # ints, ascending
    max_width_mm: float = 0.0
    max_height_mm: float = 0.0
    default_source: str = ""
    options: dict = field(default_factory=dict)  # every parsed option, for power users


@dataclass
class ScanRequest:
    """One scan job, already resolved to device-specific values"""

    device_id: str
    out_dir: str
    source: str = ""
    mode: str = ""
    resolution: int = 0
    width_mm: float = 0.0  # 0 = device default (full area)
    height_mm: float = 0.0
    multi_page: bool = False  # feeder: keep scanning until it is empty


class ScanError(Exception):
    """Raised when listing, probing or scanning fails (message is user-facing)"""


class ScannerBackend(ABC):
    """Interface all scanner backends implement"""

    name = "base"

    @abstractmethod
    def available(self):
        """True if the backend's tools are installed"""

    @abstractmethod
    def list_devices(self):
        """Return [ScannerDevice]; may take several seconds"""

    @abstractmethod
    def get_capabilities(self, device_id):
        """Return ScannerCapabilities for a device"""

    @abstractmethod
    def scan(self, request, on_page=None, on_progress=None, cancel_event=None):
        """Run a scan; return list of image paths.

        on_page(path) is called as each page is written, on_progress(percent)
        for the page in progress; cancel_event (threading.Event) aborts.
        """
