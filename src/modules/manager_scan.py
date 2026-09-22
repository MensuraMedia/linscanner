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
from modules.manager_connection import ConnectionEngine
from utils.util_logging import get_logger

log = get_logger("scan")

MAIN_DOC = 1  # the document of Multi-Page scans, opened files and added pages
from backends.parser_sane import model_key
from config.config_scan import (
    DEFAULT_PAPER,
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


def paper_spec(paper):
    """The PAPER_SIZES entry for a key (unknown keys, e.g. from old settings: Auto-Detect)"""
    return PAPER_SIZES.get(paper) or PAPER_SIZES[DEFAULT_PAPER]


def pick_area(caps, paper):
    """Paper size clamped to the device's maximum area; (0, 0) = device default (the whole area).

    Auto-Detect sizes scan the whole area; the page is cropped to the paper afterwards."""
    spec = paper_spec(paper)
    size = spec["mm"]
    if not size or spec.get("detect"):
        return 0.0, 0.0
    w, h = size
    if caps.max_width_mm:
        w = min(w, caps.max_width_mm)
    if caps.max_height_mm:
        h = min(h, caps.max_height_mm)
    return w, h


# Hardware paper-size detection options, by SANE option name -> the value that switches it on
AUTO_SIZE_OPTIONS = {"adf-crp": "yes", "auto-size": "yes", "autocrop": "yes", "adf-auto-scan": "yes"}


def auto_size_args(caps):
    """Driver options that switch on the scanner's own paper-size detection (if it has any)"""
    return [f"--{name}={value}" for name, value in AUTO_SIZE_OPTIONS.items() if name in (caps.options or {})]


def scan_types(sources):
    """The user's Scan Type choices for a device's sources: {"front": src, "both": src, "flatbed": src}.

    Front Page: one side (the feeder's single-sided source, else the flatbed).
    Front & Back: the duplex source, if the scanner has one.
    Flatbed: only offered when the scanner has both a flatbed and a feeder."""
    feeder = [s for s in sources if is_feeder(s)]
    simplex = [s for s in feeder if not is_duplex(s)]
    duplex = [s for s in feeder if is_duplex(s)]
    flatbed = [s for s in sources if not is_feeder(s)]
    types = {}
    if simplex:
        types["front"] = simplex[0]
    elif flatbed:
        types["front"] = flatbed[0]
    elif duplex:
        types["front"] = duplex[0]  # duplex-only feeder: still one choice
    if duplex and types.get("front") != duplex[0]:
        types["both"] = duplex[0]
    if flatbed and feeder and types.get("front") != flatbed[0]:
        types["flatbed"] = flatbed[0]
    return types


def is_feeder(source):
    """True if a source name means a document feeder (scan until empty)"""
    return any(hint in source.lower() for hint in FEEDER_SOURCE_HINTS)


def is_duplex(source):
    """True if a source scans both sides of each sheet"""
    return any(hint in source.lower() for hint in DUPLEX_SOURCE_HINTS)


def sheet_limits(source, sheet_mode):
    """(multi_page, max_pages) for a source and sheet mode ("all" = Multi-Page / "one" = Single Page).

    A feeder always scans every sheet loaded: document feeders such as the
    ES-400 II pull the whole stack through once a job starts, so stopping after
    one page would skip the rest. Single Page instead makes every sheet its
    own document (see ScanRequest.separate)."""
    if not is_feeder(source):
        return False, 1  # flatbed: always one page
    return True, 0  # feeder: until empty


def separate_documents(source, sheet_mode):
    """(separate, pages per sheet): Single Page makes each sheet (front + back for duplex) a document"""
    return sheet_mode == "one", 2 if is_duplex(source) else 1


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


def _page_notes(page):
    """What the page processors recorded on a page, for the log"""
    keys = ("blank_score", "autocropped", "deskew_angle", "autorotated", "separator")
    notes = [
        f"{k}={page[k]:.4f}" if isinstance(page.get(k), float) else f"{k}={page[k]}"
        for k in keys
        if k in page
    ]
    return "[" + ", ".join(notes) + "]" if notes else ""


def equivalent_source(source, caps):
    """The same kind of source (flatbed / feeder / duplex) in another method's names"""
    if source in caps.sources:
        return source
    want_feeder, want_duplex = is_feeder(source), is_duplex(source)
    for s in caps.sources:
        if is_feeder(s) == want_feeder and is_duplex(s) == want_duplex:
            return s
    for s in caps.sources:
        if is_feeder(s) == want_feeder:
            return s
    return caps.default_source


class ScanManager:
    """Owns the connection engine, the current device and the scanned pages of a session"""

    def __init__(self, settings, backend=None, engine=None):
        """Create the manager with a session temp dir.

        engine: a ConnectionEngine (production: SANE + direct eSCL + USB probe).
        backend: a single backend instead (tests, --test-scanner); no USB probe."""
        self.settings = settings
        self.backend = backend or SaneBackend()
        self.engine = engine or ConnectionEngine([self.backend], use_usb_probe=backend is None)
        self.devices = []
        self.capabilities = {}
        self.session_dir = tempfile.mkdtemp(prefix="linscanner-")
        self.pages = []  # [{"path", "rotation", "dpi", "mode", optional "overlays", "separator"}]
        self.features = None  # FeatureRegistry: page processors (crop, deskew, blank removal, …)
        self.dropped_pages = 0  # pages removed by processors during the last scan
        # Documents: each page has a "doc" id. Multi-Page scans, opened files and
        # added pages share MAIN_DOC; Single Page gives every sheet its own id.
        self.documents = {}  # doc id -> {"path", "format"}: the file Save writes to
        self._saved = {}  # doc id -> page signature at its last save (see is_saved)
        self.next_doc = MAIN_DOC + 1
        self._cancel = threading.Event()
        self.busy = False

    # -- background helpers ------------------------------------------------
    def _in_thread(self, work, on_done, on_error):
        """Run work() in a thread; deliver result or error on the GTK thread"""

        def once(callback, value):
            callback(value)
            return False  # never repeat, whatever the callback returns

        def runner():
            try:
                result = work()
            except ScanError as e:
                GLib.idle_add(once, on_error, str(e))
            except Exception as e:  # unexpected: show it instead of a silent UI
                GLib.idle_add(once, on_error, f"Unexpected error: {e}")
            else:
                GLib.idle_add(once, on_done, result)

        threading.Thread(target=runner, daemon=True).start()

    def refresh_devices(self, on_done, on_error):
        """List scanners in the background, filtered for display"""

        def work():
            found = self.engine.discover()
            self.devices = found
            return filter_devices(found, self.settings.get("show_all_backends"))

        self._in_thread(work, on_done, on_error)

    # -- remembered scanner ------------------------------------------------------
    def remember_device(self, physical):
        """Store the scanner in use, so the next start can reach it without a full search"""
        info = {
            "key": physical.key,
            "vendor": physical.vendor,
            "model": physical.model,
            "methods": [
                {
                    "code": m.code,
                    "backend": m.backend.name,
                    "id": m.device.id,
                    "vendor": m.device.vendor,
                    "model": m.device.model,
                    "kind": m.device.kind,
                    "driver": m.device.backend,
                }
                for m in physical.methods
            ],
        }
        if info != self.settings.get("last_device_info"):
            self.settings.set("last_device_info", info)

    def restore_device(self, on_done, on_error):
        """Reach the remembered scanner directly (a few seconds instead of a full search).

        on_done([physical]) if it answers; on_error(message) if there is no
        remembered scanner or it doesn't answer (then do a full search)."""
        info = self.settings.get("last_device_info") or {}

        def work():
            from backends.backend_base import ScannerDevice
            from modules.manager_connection import Method, PhysicalDevice

            backends = {getattr(b, "name", ""): b for b in self.engine.backends}
            methods = [
                Method(
                    m["code"],
                    backends[m["backend"]],
                    ScannerDevice(m["id"], m["vendor"], m["model"], m["kind"], m["driver"]),
                )
                for m in info.get("methods", [])
                if m.get("backend") in backends
            ]
            if not methods:
                raise ScanError("No remembered scanner.", "no_device")
            physical = PhysicalDevice(
                key=info["key"], vendor=info["vendor"], model=info["model"], methods=methods, restored=True
            )
            first = methods[0]
            caps = first.backend.get_capabilities(first.device.id)  # proves it answers
            self.devices = [physical]
            self.engine.devices = [physical]
            self.capabilities[physical.id] = caps
            log.info(
                "remembered scanner %s %s answered via %s",
                physical.vendor,
                physical.model,
                first.device.backend,
            )
            return [physical]

        self._in_thread(work, on_done, on_error)

    def load_capabilities(self, device_id, on_done, on_error):
        """Read (or reuse cached) device capabilities in the background"""
        if device_id in self.capabilities:
            GLib.idle_add(on_done, self.capabilities[device_id])
            return

        def work():
            physical = self.physical(device_id)
            if physical is None or not physical.methods:
                hint = physical.hint if physical else "Scanner not found. Check for devices again."
                raise ScanError(hint, "no_device")
            method = physical.methods[0]
            caps = method.backend.get_capabilities(method.device.id)
            self.capabilities[device_id] = caps
            return caps

        self._in_thread(work, on_done, on_error)

    def physical(self, device_id):
        """The PhysicalDevice with this id, or None"""
        return next((d for d in self.devices if d.id == device_id), None)

    # -- scanning ----------------------------------------------------------
    def build_request(self, device_id, source, color_mode, quality, paper, create_dir=True, sheet_mode="all"):
        """create_dir=False builds the request for display only (no temp folder)"""
        caps = self.capabilities[device_id]
        self.last_choices = (source, color_mode, quality, paper, sheet_mode)
        request = self._request_for(
            device_id, caps, source, color_mode, quality, paper, sheet_mode, create_dir
        )
        if create_dir:  # real scans only (not the summary line)
            log.info(
                "request: choices source=%s color=%s quality=%s paper=%s sheets=%s bw_style=%s -> "
                "device=%s source=%s mode=%s %s dpi area=%sx%s mm multi_page=%s max_pages=%s",
                source,
                color_mode,
                quality,
                paper,
                sheet_mode,
                self.settings.get("bw_style"),
                request.device_id,
                request.source,
                request.mode,
                request.resolution,
                request.width_mm or "full",
                request.height_mm or "full",
                request.multi_page,
                request.max_pages,
            )
        return request

    def _request_for(self, device_id, caps, source, color_mode, quality, paper, sheet_mode, create_dir=True):
        """ScanRequest for one device/method from the user's choices and its capabilities"""
        width, height = pick_area(caps, paper)
        spec = paper_spec(paper)
        source = equivalent_source(source, caps)
        multi_page, max_pages = sheet_limits(source, sheet_mode)
        separate, sheet_pages = separate_documents(source, sheet_mode)
        out_dir = tempfile.mkdtemp(prefix="scan-", dir=self.session_dir) if create_dir else ""
        detect = bool(spec.get("detect"))
        return ScanRequest(
            separate=separate,
            sheet_pages=sheet_pages,
            auto_detect=detect,
            nominal_mm=tuple(spec["mm"] or ()) if detect else (),
            extra_args=auto_size_args(caps) if detect else [],
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
        active = {"request": request}  # the request of the method currently scanning

        self.dropped_pages = 0
        received = [0]  # pages delivered by the scanner in this job (including blanks removed)
        first_doc = self.next_doc
        if request.separate:  # reserve ids for this job's sheets as they arrive
            self.next_doc += 10000

        def page_added(path):
            r = active["request"]
            sheet = received[0] // max(1, r.sheet_pages)
            received[0] += 1
            page = {"path": path, "rotation": 0, "dpi": r.resolution, "mode": r.mode}
            page["doc"] = first_doc + sheet if r.separate else MAIN_DOC
            if r.auto_detect:
                self.detect_page(page, r.nominal_mm)
            if self.features is not None and not self.process_page(page):
                self.dropped_pages += 1
                return  # e.g. a blank page removed
            self.pages.append(page)
            GLib.idle_add(on_page, page)

        def progress(pct):
            GLib.idle_add(on_progress, pct)

        def build(method, caps):
            """First method: the request as built; fallbacks: same choices, their capabilities"""
            if method.device.id == request.device_id:
                active["request"] = request
            else:
                choices = getattr(self, "last_choices", None) or (
                    request.source,
                    "color",
                    "medium",
                    "auto",
                    "all",
                )
                active["request"] = self._request_for(method.device.id, caps, *choices)
            return active["request"]

        def work():
            physical = self.physical(request.device_id)
            if physical is None:  # not from discovery (e.g. a direct test call)
                return self.backend.scan(request, page_added, progress, self._cancel)
            return self.engine.scan(physical, build, page_added, progress, self._cancel)

        def finished(result):
            self.busy = False
            if request.separate:  # the next job's documents follow this job's sheets
                sheets = -(-received[0] // max(1, request.sheet_pages))
                self.next_doc = first_doc + sheets
            on_done(result, self._cancel.is_set())

        def failed(message):
            self.busy = False
            if request.separate:
                self.next_doc = first_doc + -(-received[0] // max(1, request.sheet_pages))
            on_error(message)

        self._in_thread(work, finished, failed)

    def detect_page(self, page, nominal_mm=()):
        """Auto-Detect: crop a page to the paper (in the scan thread); the file is replaced"""
        import os

        from PIL import Image

        from utils.util_autodetect import detect_crop

        name = os.path.basename(page["path"])
        try:
            with Image.open(page["path"]) as img:
                img.load()
                cropped, how = detect_crop(img, page["dpi"] or 300, nominal_mm or None)
                if cropped is not img:
                    cropped.save(page["path"], dpi=(page["dpi"], page["dpi"]))
                page["auto_detected"] = how
                log.info("page %s: auto-detect %s %sx%s -> %sx%s", name, how, *img.size, *cropped.size)
        except OSError as e:
            log.warning("page %s: auto-detect failed (%s); kept as scanned", name, e)

    def process_page(self, page):
        """Run the enabled page processors on a scanned page (in the scan thread).

        Returns False if the page should be dropped. The processed image replaces
        the scan file; any processor failure leaves the page unchanged."""
        import os

        from PIL import Image

        name = os.path.basename(page["path"])
        try:
            with Image.open(page["path"]) as img:
                img.load()
                before = img.size
                result = self.features.process_page(img, page)
                if result is None:
                    log.info(
                        "page %s: DROPPED by %s %s",
                        name,
                        page.get("dropped_by", "a processor"),
                        _page_notes(page),
                    )
                    return False
                if result is not img:
                    result.save(page["path"], dpi=(page["dpi"], page["dpi"]))
                log.info("page %s: %sx%s -> %sx%s %s", name, *before, *result.size, _page_notes(page))
        except OSError as e:
            log.warning("page %s: could not be processed (%s); kept as scanned", name, e)
        return True

    def cancel(self):
        """Ask the running scan to stop (pages so far are kept)"""
        log.info("cancel requested")
        self._cancel.set()

    # -- pages -------------------------------------------------------------
    def rotate_page(self, index, degrees):
        """Rotate a page clockwise by degrees (applied at display/export)"""
        self.pages[index]["rotation"] = (self.pages[index]["rotation"] + degrees) % 360

    def delete_page(self, index):
        """Remove a page from the session"""
        del self.pages[index]

    def clear_pages(self):
        """Remove all pages from the session (the next Save starts a new document)"""
        self.pages = []
        self.documents = {}
        self._saved = {}
        self.next_doc = MAIN_DOC + 1

    # -- documents ---------------------------------------------------------
    @property
    def document(self):
        """The main document's file ({"path", "format"}) or None (single-document sessions)"""
        return self.documents.get(MAIN_DOC)

    @document.setter
    def document(self, value):
        if value is None:
            self.documents.pop(MAIN_DOC, None)
        else:
            self.documents[MAIN_DOC] = value

    def doc_ids(self):
        """The documents in page order"""
        seen = []
        for p in self.pages:
            d = p.get("doc", MAIN_DOC)
            if d not in seen:
                seen.append(d)
        return seen

    def doc_pages(self, doc):
        """The pages of one document"""
        return [p for p in self.pages if p.get("doc", MAIN_DOC) == doc]

    def _signature(self, doc=None):
        """What the pages (of one document) look like now: files, versions, rotation, edits, order"""
        from utils.util_display import page_key

        pages = self.pages if doc is None else self.doc_pages(doc)
        return [page_key(p) for p in pages]

    def mark_saved(self, doc=None):
        """A document (or, with doc=None, every document) was just saved"""
        for d in [doc] if doc is not None else self.doc_ids():
            self._saved[d] = self._signature(d)

    def doc_is_saved(self, doc):
        """True if a document hasn't changed since it was saved"""
        return bool(self.doc_pages(doc)) and self._saved.get(doc) == self._signature(doc)

    def is_saved(self):
        """True if every document is saved (the next Scan then starts a new one)"""
        return bool(self.pages) and all(self.doc_is_saved(d) for d in self.doc_ids())

    def open_document(self, path):
        """Replace the session's pages with a saved document's pages (ValueError if it can't be read)"""
        from modules.manager_documents import open_document
        from modules.manager_export import format_for_path

        pages = open_document(path, self.session_dir)
        self.clear_pages()
        for p in pages:
            p["doc"] = MAIN_DOC
        self.pages = pages
        self.document = {"path": path, "format": format_for_path(path) or "pdf"}
        return pages

    def cleanup(self):
        """Delete session temp files and backend temp config"""
        shutil.rmtree(self.session_dir, ignore_errors=True)
        for backend in {id(b): b for b in [self.backend, *self.engine.backends]}.values():
            if hasattr(backend, "close"):
                backend.close()

    @staticmethod
    def summary(request):
        """One-line human description of a request (mode, dpi, size, source)"""
        size = "full area" if not request.width_mm else f"{request.width_mm:g}×{request.height_mm:g} mm"
        if request.auto_detect:
            size = "full area, then fitted to the paper (Auto-Detect)"
        return f"{request.mode} · {request.resolution} dpi · {size} · {request.source or 'default source'}"
