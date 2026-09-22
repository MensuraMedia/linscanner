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
        """Display name: vendor, model and the SANE driver in brackets"""
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
    max_pages: int = 0  # >0 caps the pages per job (1 = one side, 2 = one duplex sheet)
    separate: bool = False  # Single Page: every sheet becomes its own document
    sheet_pages: int = 1  # pages per sheet (2 for Front & Back)
    auto_detect: bool = False  # crop each page to the paper afterwards (Auto-Detect, receipts, cards)
    nominal_mm: tuple = ()  # size used by Auto-Detect when the paper's edges can't be seen
    extra_args: list = field(default_factory=list)  # driver options, e.g. ["--adf-crp=yes"]


# Error codes. USER_ACTION codes mean the user must fix something (retrying
# another connection method would fail or double-feed); the others let the
# connection engine fall through to the next method.
USER_ACTION_CODES = {"no_docs", "jammed", "cover_open"}
FALLTHROUGH_CODES = {"busy", "io", "timeout", "access", "unsupported", "missing", "no_device", "error"}

# scanimage exits with the SANE status number (sane-backends frontend/scanimage.c)
SANE_EXIT_CODES = {
    3: "busy",  # SANE_STATUS_DEVICE_BUSY
    4: "unsupported",  # SANE_STATUS_INVAL
    6: "jammed",  # SANE_STATUS_JAMMED
    7: "no_docs",  # SANE_STATUS_NO_DOCS
    8: "cover_open",  # SANE_STATUS_COVER_OPEN
    9: "io",  # SANE_STATUS_IO_ERROR
    10: "io",  # SANE_STATUS_NO_MEM
    11: "access",  # SANE_STATUS_ACCESS_DENIED
    1: "unsupported",  # SANE_STATUS_UNSUPPORTED
}


class ScanError(Exception):
    """Raised when listing, probing or scanning fails (message is user-facing)"""

    def __init__(self, message, code="error"):
        """message: shown to the user; code: see USER_ACTION_CODES / FALLTHROUGH_CODES"""
        super().__init__(message)
        self.code = code

    @property
    def needs_user(self):
        """True if the user must act (feeder empty, jam, cover open)"""
        return self.code in USER_ACTION_CODES


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
