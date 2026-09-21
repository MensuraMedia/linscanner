"""
Scan Manager
Turns the user's choices (Color / Black & White, High / Medium / Low, paper)
into a device-specific ScanRequest, and runs backend calls off the GTK thread.
"""

import shutil
import tempfile
import threading

from gi.repository import GLib

from backends.backend_base import ScanError, ScanRequest
from backends.backend_sane import SaneBackend
from backends.parser_sane import model_key
from config.config_scan import (
    COLOR_MODES,
    DUPLEX_SOURCE_HINTS,
    FEEDER_SOURCE_HINTS,
    HIDDEN_BACKENDS_BY_DEFAULT,
    LINEART_MODE_NAMES,
    PAPER_SIZES,
    PREFERRED_BACKENDS,
    QUALITY_PRESETS,
)


def pick_mode(device_modes, color_mode, bw_style):
    """Map "color" / "bw" onto one of the device's own mode names"""
    lowered = {m.lower(): m for m in device_modes}
    wanted = list(COLOR_MODES[color_mode]["sane"])
    if color_mode == "bw" and bw_style == "pure":
        wanted = LINEART_MODE_NAMES + wanted  # prefer lineart, fall back to gray
    for name in wanted:
        if name in lowered:
            return lowered[name]
    for name in wanted:  # partial match, e.g. "True Gray", "24bit Color"
        for low, original in lowered.items():
            if name in low:
                return original
    return device_modes[0] if device_modes else ""


def pick_resolution(resolutions, quality):
    """Nearest supported resolution to the quality preset (ties go higher)"""
    target = QUALITY_PRESETS[quality]["dpi"]
    if not resolutions:
        return target
    return min(resolutions, key=lambda r: (abs(r - target), -r))


def pick_area(caps, paper):
    """Paper size clamped to the device's maximum area; (0, 0) = device default"""
    size = PAPER_SIZES[paper]["mm"]
    if not size:
        return 0.0, 0.0
    w, h = size
    if caps.max_width_mm:
        w = min(w, caps.max_width_mm)
    if caps.max_height_mm:
        h = min(h, caps.max_height_mm)
    return w, h


def is_feeder(source):
    """True if a source name means a document feeder (scan until empty)"""
    return any(hint in source.lower() for hint in FEEDER_SOURCE_HINTS)


def is_duplex(source):
    """True if a source scans both sides of each sheet"""
    return any(hint in source.lower() for hint in DUPLEX_SOURCE_HINTS)


def sheet_limits(source, sheet_mode):
    """(multi_page, max_pages) for a source and sheet mode ("all" / "one")"""
    if not is_feeder(source):
        return False, 1  # flatbed: always one page
    if sheet_mode == "one":
        return False, 2 if is_duplex(source) else 1  # one sheet: front (+ back)
    return True, 0  # feeder, all sheets: until empty


def filter_devices(devices, show_all=False):
    """Hide SANE's test scanner and duplicate backends for the same model"""
    if show_all:
        return devices
    visible = [d for d in devices if d.backend not in HIDDEN_BACKENDS_BY_DEFAULT]

    def rank(d):
        return PREFERRED_BACKENDS.index(d.backend) if d.backend in PREFERRED_BACKENDS else 99

    best = {}
    for d in sorted(visible, key=rank):
        best.setdefault(model_key(d), d)
    return [d for d in visible if best[model_key(d)] is d]


class ScanManager:
    """Owns the backend, the current device and the scanned pages of a session"""

    def __init__(self, settings, backend=None):
        """Create the manager with a session temp dir; backend defaults to SANE"""
        self.settings = settings
        self.backend = backend or SaneBackend()
        self.devices = []
        self.capabilities = {}
        self.session_dir = tempfile.mkdtemp(prefix="linscanner-")
        self.pages = []  # [{"path": str, "rotation": int, "dpi": int, "mode": str}]
        self._cancel = threading.Event()
        self.busy = False

    # -- background helpers ------------------------------------------------
    def _in_thread(self, work, on_done, on_error):
        """Run work() in a thread; deliver result or error on the GTK thread"""

        def runner():
            try:
                result = work()
            except ScanError as e:
                GLib.idle_add(on_error, str(e))
            except Exception as e:  # unexpected: show it instead of a silent UI
                GLib.idle_add(on_error, f"Unexpected error: {e}")
            else:
                GLib.idle_add(on_done, result)

        threading.Thread(target=runner, daemon=True).start()

    def refresh_devices(self, on_done, on_error):
        """List scanners in the background, filtered for display"""

        def work():
            found = self.backend.list_devices()
            self.devices = found
            return filter_devices(found, self.settings.get("show_all_backends"))

        self._in_thread(work, on_done, on_error)

    def load_capabilities(self, device_id, on_done, on_error):
        """Read (or reuse cached) device capabilities in the background"""
        if device_id in self.capabilities:
            GLib.idle_add(on_done, self.capabilities[device_id])
            return

        def work():
            caps = self.backend.get_capabilities(device_id)
            self.capabilities[device_id] = caps
            return caps

        self._in_thread(work, on_done, on_error)

    # -- scanning ----------------------------------------------------------
    def build_request(self, device_id, source, color_mode, quality, paper, create_dir=True, sheet_mode="all"):
        """create_dir=False builds the request for display only (no temp folder)"""
        caps = self.capabilities[device_id]
        width, height = pick_area(caps, paper)
        source = source if source in caps.sources else caps.default_source
        multi_page, max_pages = sheet_limits(source, sheet_mode)
        out_dir = tempfile.mkdtemp(prefix="scan-", dir=self.session_dir) if create_dir else ""
        return ScanRequest(
            device_id=device_id,
            out_dir=out_dir,
            source=source,
            mode=pick_mode(caps.modes, color_mode, self.settings.get("bw_style")),
            resolution=pick_resolution(caps.resolutions, quality),
            width_mm=width,
            height_mm=height,
            multi_page=multi_page,
            max_pages=max_pages,
        )

    def start_scan(self, request, on_page, on_progress, on_done, on_error):
        """Start a scan in the background; pages are appended as they arrive"""
        self._cancel.clear()
        self.busy = True

        def page_added(path):
            page = {"path": path, "rotation": 0, "dpi": request.resolution, "mode": request.mode}
            self.pages.append(page)
            GLib.idle_add(on_page, page)

        def progress(pct):
            GLib.idle_add(on_progress, pct)

        def work():
            return self.backend.scan(request, page_added, progress, self._cancel)

        def finished(result):
            self.busy = False
            on_done(result, self._cancel.is_set())

        def failed(message):
            self.busy = False
            on_error(message)

        self._in_thread(work, finished, failed)

    def cancel(self):
        """Ask the running scan to stop (pages so far are kept)"""
        self._cancel.set()

    # -- pages -------------------------------------------------------------
    def rotate_page(self, index, degrees):
        """Rotate a page clockwise by degrees (applied at display/export)"""
        self.pages[index]["rotation"] = (self.pages[index]["rotation"] + degrees) % 360

    def delete_page(self, index):
        """Remove a page from the session"""
        del self.pages[index]

    def clear_pages(self):
        """Remove all pages from the session"""
        self.pages = []

    def cleanup(self):
        """Delete session temp files and backend temp config"""
        shutil.rmtree(self.session_dir, ignore_errors=True)
        if hasattr(self.backend, "close"):
            self.backend.close()

    @staticmethod
    def summary(request):
        """One-line human description of a request (mode, dpi, size, source)"""
        size = "full area" if not request.width_mm else f"{request.width_mm:g}×{request.height_mm:g} mm"
        return f"{request.mode} · {request.resolution} dpi · {size} · {request.source or 'default source'}"
