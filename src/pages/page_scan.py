"""
Scan Page
Choose scanner, source, colour, quality and paper; scan with live progress.
Pages go to the Document page as they arrive.
"""

import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from config.config_scan import COLOR_MODES, PAPER_SIZES, QUALITY_PRESETS, SHEET_MODES  # noqa: E402
from modules.manager_scan import ScanManager, is_feeder, scan_types  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_icons import icon_image  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

OPTION_BUTTON_WIDTH = 150  # every option button the same width, so the choices line up in columns


class ScanPage(BasePage):
    """Scanner selection, scan options and the Scan button"""

    def build_content(self):
        """Scanner card, options card, Scan/Cancel, progress and status"""
        self.devices = []
        self.request = None
        s = self.ctx.settings

        self.add_title("Scan", "Load your pages, choose the options and press Scan.")

        # -- scanner card
        card = self.add_card("Detect Scanner")
        row = Gtk.Box(spacing=10)
        self.refresh_btn = Gtk.Button(label="Find")
        self.refresh_btn.set_tooltip_text("Search for scanners (USB) again")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh_devices())
        row.pack_start(self.refresh_btn, False, False, 0)
        self.device_combo = Gtk.ComboBoxText()
        self.device_combo.connect("changed", self.on_device_changed)
        # the scanner list, its power mark and Devices take half the width (like Document Size)
        half = Gtk.Box(homogeneous=True)
        scanner_box = Gtk.Box(spacing=10)
        scanner_box.pack_start(self.device_combo, True, True, 0)
        half.pack_start(scanner_box, True, True, 0)
        half.pack_start(Gtk.Box(), True, True, 0)
        row.pack_start(half, True, True, 0)
        # power mark after the scanner name: spinner while looking, green when connected, red when not
        theme = getattr(self.ctx.theme, "current_theme", None)
        self.mark = Gtk.Stack()
        self.mark.set_size_request(24, 24)
        self.spinner = Gtk.Spinner()
        self.mark.add_named(self.spinner, "looking")
        self.power_on_icon = icon_image("power", 22, getattr(theme, "success", None) or "#3fd059")
        self.power_on_icon.set_tooltip_text("Scanner connected and ready")
        self.mark.add_named(self.power_on_icon, "on")
        self.power_off_icon = icon_image("power", 22, getattr(theme, "error", None) or "#e8555d")
        self.mark.add_named(self.power_off_icon, "off")
        self.mark.add_named(Gtk.Box(), "none")
        scanner_box.pack_start(self.mark, False, False, 0)  # right after the scanner name
        self.power_state = "none"
        info_btn = Gtk.Button(label="Devices")
        info_btn.set_tooltip_text("Every scanner found, with its connection and capabilities")
        info_btn.connect("clicked", lambda *_: self.ctx.nav.navigate_to("devices"))
        scanner_box.pack_start(info_btn, False, False, 0)
        card.pack_start(row, False, False, 0)
        self.device_status = self.label("", "status-error", wrap=True)
        self.device_status.set_no_show_all(True)  # only shown when the scanner can't be used
        card.pack_start(self.device_status, False, False, 0)

        # -- options card
        card = self.add_card("Scan Options")
        self.options_card = card  # features (e.g. profiles) add rows here
        # Scan Type (Front Page / Front & Back / Flatbed) chooses the device source;
        # the device's own source names stay in a hidden combo (the request uses them)
        self.source_combo = Gtk.ComboBoxText()
        self.source_combo.connect("changed", lambda *_: self.on_source_changed())
        self.types = {}
        self.scan_type = None
        self.scan_type_slot = Gtk.Box()
        card.pack_start(
            self.form_row("", self.scan_type_slot), False, False, 0
        )  # no label: the choices say it

        # Sheet-fed mode: only shown for feeder sources
        self.sheets = SegmentedControl(
            [(k, v["label"]) for k, v in SHEET_MODES.items()],
            active=s.get("sheet_mode"),
            on_changed=lambda k: self.remember("sheet_mode", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        self.sheets_row = self.form_row("Sheets", self.sheets)
        self.sheets_row.set_no_show_all(True)
        card.pack_start(self.sheets_row, False, False, 0)

        self.color = SegmentedControl(
            [(k, v["label"]) for k, v in COLOR_MODES.items()],
            active=s.get("color_mode"),
            on_changed=lambda k: self.remember("color_mode", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        card.pack_start(self.form_row("Color", self.color), False, False, 0)

        self.quality = SegmentedControl(
            [(k, v["label"]) for k, v in QUALITY_PRESETS.items()],
            active=s.get("quality"),
            on_changed=lambda k: self.remember("quality", k),
            button_width=OPTION_BUTTON_WIDTH,
        )
        card.pack_start(self.form_row("Quality", self.quality), False, False, 0)

        # Blank Pages: a shortcut for the Blank-page removal module (same switch as Settings → Features)
        self.blank = SegmentedControl(
            [("keep", "Keep"), ("remove", "Remove")],
            active="remove" if self._blank_enabled() else "keep",
            on_changed=self.on_blank_changed,
            button_width=OPTION_BUTTON_WIDTH,
        )
        self.blank.set_tooltip_text("Remove blank pages (for example the empty backs of single-sided sheets)")
        self.blank_row = self.form_row("Blank Pages", self.blank)
        self.blank_row.set_no_show_all(self._blank_feature() is None)
        card.pack_start(self.blank_row, False, False, 0)

        self.paper_combo = Gtk.ComboBoxText()
        group = None
        for key, spec in PAPER_SIZES.items():
            if spec.get("group") != group and group is not None:
                self.paper_combo.append(f"-{spec['group']}", "")  # separator between groups
            group = spec.get("group")
            self.paper_combo.append(key, spec["label"])
        self.paper_combo.set_row_separator_func(lambda model, it: (model[it][1] or "").startswith("-"))
        self.paper_combo.set_tooltip_text(
            "Auto-Detect fits each page to the paper that was scanned (when its edges can be seen)"
        )
        if not self.paper_combo.set_active_id(s.get("paper")):
            self.paper_combo.set_active_id("auto_detect")
        self.paper_combo.connect("changed", lambda c: self.remember("paper", c.get_active_id()))
        half = Gtk.Box(homogeneous=True)  # the list takes half the width
        half.pack_start(self.paper_combo, True, True, 0)
        half.pack_start(Gtk.Box(), True, True, 0)
        card.pack_start(self.form_row("Document Size", half), False, False, 0)

        self.summary = self.label("", "muted", wrap=True)
        card.pack_start(self.summary, False, False, 0)

        # -- action row
        actions = Gtk.Box(spacing=12)
        self.scan_btn = Gtk.Button(label="Scan")
        self.scan_btn.get_style_context().add_class("primary-pill")
        self.scan_btn.connect("clicked", self.on_scan)
        actions.pack_start(self.scan_btn, False, False, 0)
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.connect("clicked", lambda *_: self.ctx.scan.cancel())
        self.cancel_btn.set_sensitive(False)
        actions.pack_start(self.cancel_btn, False, False, 0)
        self.pack_start(actions, False, False, 4)

        self.progress = Gtk.ProgressBar()
        self.pack_start(self.progress, False, False, 0)
        self.status = self.label("", "muted", wrap=True)  # scanning progress and scan errors
        self.pack_start(self.status, False, False, 0)

        if self.ctx.features:
            self.ctx.features.extend("extend_scan_page", self)
        self.ctx.on("settings-changed", self.on_settings_changed)
        self.ctx.on("features-changed", self.sync_blank)
        self.ctx.on("devices-changed", self.devices_loaded)
        self.ctx.on("request-device-refresh", self.refresh_devices)
        self.set_busy(True)
        GLib.idle_add(self.startup)  # after every page has subscribed

    # -- blank pages ---------------------------------------------------------
    def _blank_feature(self):
        """The Blank-page removal module, or None if it was removed"""
        return self.ctx.features.get("blank_removal") if getattr(self.ctx, "features", None) else None

    def _blank_enabled(self):
        """True if blank pages are removed"""
        feature = self._blank_feature()
        return bool(feature and self.ctx.features.is_enabled(feature))

    def on_blank_changed(self, key):
        """Keep / Remove: switch the Blank-page removal module (Settings → Features follows)"""
        if self._blank_feature() is not None:
            self.ctx.features.set_enabled("blank_removal", key == "remove")
            self.ctx.emit("features-changed")

    def sync_blank(self, *_):
        """Follow the module's switch when it changes in Settings"""
        self.blank.set_active("remove" if self._blank_enabled() else "keep")

    # -- helpers -----------------------------------------------------------
    def on_settings_changed(self, key):
        """Re-list devices if driver visibility changed; else refresh the summary"""
        if key == "show_all_backends":
            self.refresh_devices()  # device list filtering changed
        else:
            self.update_summary()  # e.g. Black & White style

    def remember(self, key, value):
        """Persist an option choice and refresh the summary"""
        self.ctx.settings.set(key, value)
        self.update_summary()

    def set_status(self, text, css="muted"):
        """Show a status message styled muted / ok / error / busy (errors and results are logged)"""
        level = {"status-error": logging.WARNING, "status-ok": logging.INFO}.get(css, logging.DEBUG)
        log.log(level, "scan page: %s", text)
        ctx = self.status.get_style_context()
        for c in ("muted", "status-ok", "status-error", "status-busy"):
            ctx.remove_class(c)
        ctx.add_class(css)
        self.status.set_text(text)

    def set_busy(self, busy, scanning=False):
        """Enable or disable controls while working; Cancel only while scanning"""
        for w in (
            self.scan_btn,
            self.refresh_btn,
            self.device_combo,
            self.scan_type_slot,
            self.color,
            self.quality,
            self.paper_combo,
            self.sheets,
            self.blank,
        ):
            w.set_sensitive(not busy)
        self.cancel_btn.set_sensitive(scanning)

    def current_device(self):
        """The ScannerDevice selected in the combo, or None"""
        dev_id = self.device_combo.get_active_id()
        return next((d for d in self.devices if d.id == dev_id), None)

    # -- devices -----------------------------------------------------------
    POWER_OFF_MESSAGE = "Device may be off. Check power settings."

    def show_device_issue(self, text=None):
        """The red line under the scanner list: shown only when the scanner can't be used"""
        self.device_status.set_text(text or "")
        self.device_status.set_visible(bool(text))

    def looking(self, on):
        """Spinner in place of the power mark while looking for the scanner"""
        (self.spinner.start if on else self.spinner.stop)()
        if on:
            self.power_state = "looking"
            self.show_device_issue(None)
        self.mark.set_visible_child_name(
            "looking" if on else self.power_state if self.power_state != "looking" else "none"
        )

    def power(self, on, message=None, detail=""):
        """Green power mark when the scanner answered; red with a plain message when it didn't"""
        self.spinner.stop()
        self.power_state = "on" if on else "off"
        self.mark.set_visible_child_name(self.power_state)
        if on:
            self.show_device_issue(None)
            log.info("scan page: scanner connected")
        else:
            message = message or self.POWER_OFF_MESSAGE
            self.power_off_icon.set_tooltip_text(message + (f"\n{detail}" if detail else ""))
            self.show_device_issue(message)
            log.warning("scan page: %s %s", message, detail)

    def startup(self):
        """At start: reach the remembered scanner directly; otherwise do a full search"""
        info = self.ctx.settings.get("last_device_info")
        if not info or not info.get("methods"):
            return self.refresh_devices()
        self.set_busy(True)
        self.looking(True)

        def failed(message):
            log.info("remembered scanner didn't answer (%s); searching for scanners", message)
            self.refresh_devices()

        self.ctx.scan.restore_device(lambda devs: self.ctx.emit("devices-changed", devs), failed)
        return False

    def refresh_devices(self):
        """Start a background device search (ignored while scanning)"""
        if self.ctx.scan.busy:
            return False
        self.set_busy(True)
        self.looking(True)
        self.ctx.emit("devices-refreshing")
        self.ctx.scan.refresh_devices(
            lambda devs: self.ctx.emit("devices-changed", devs), self.devices_failed
        )
        return False  # one-shot when scheduled with GLib.idle_add

    def devices_loaded(self, devices):
        """Fill the scanner combo; reselect the last used scanner"""
        self.devices = devices
        self.device_combo.remove_all()
        for d in devices:
            self.device_combo.append(
                d.id, d.label if d.methods else f"{d.vendor} {d.model}  (no working driver)"
            )
        if not devices:
            self.set_busy(False)
            self.scan_btn.set_sensitive(False)
            self.power(False, detail="No scanner found. Check the USB cable, then press Find.")
            return
        last = self.ctx.settings.get("last_device")
        if not self.device_combo.set_active_id(last):
            self.device_combo.set_active(0)

    def devices_failed(self, message):
        """A search or options error: plain words on screen, the details in the log"""
        log.warning("scanner not reachable: %s", message)
        self.set_busy(False)
        self.power(False, detail="The scanner didn't answer. Check the USB cable, then press Find.")

    def on_device_changed(self, combo):
        """Remember the device and load its capabilities"""
        dev = self.current_device()
        if not dev:
            return
        self.ctx.settings.set("last_device", dev.id)
        if not dev.methods:  # detected on USB, but nothing can drive it
            self.set_busy(False)
            self.scan_btn.set_sensitive(False)
            self.power(
                False, "This scanner is connected, but no driver can use it yet (see Devices).", dev.hint
            )
            return
        self.set_busy(True)
        self.looking(True)
        self.ctx.scan.load_capabilities(dev.id, self.caps_loaded, self.devices_failed)

    def caps_loaded(self, caps):
        """Offer the scanner's Scan Types (from its sources) and mark it found"""
        self.source_combo.remove_all()
        for src in caps.sources or ["Default"]:
            self.source_combo.append(src, src)
        self.build_scan_types(caps.sources or ["Default"])
        wanted = self.ctx.settings.get("scan_type")
        key = wanted if wanted in self.types else next(iter(self.types), None)
        if key:
            self.choose_scan_type(key)
        elif not self.source_combo.set_active_id(caps.default_source):
            self.source_combo.set_active(0)
        self.set_busy(False)
        self.power(True)
        dev = self.current_device()
        if dev and dev.methods:
            self.ctx.scan.remember_device(dev)  # reached directly at the next start
        self.update_summary()

    SCAN_TYPE_LABELS = {"front": "Front Page", "both": "Front & Back", "flatbed": "Flatbed"}

    def build_scan_types(self, sources):
        """Segmented Scan Type control for this scanner (Front & Back only if it can scan duplex)"""
        self.types = scan_types(sources)
        for child in self.scan_type_slot.get_children():
            self.scan_type_slot.remove(child)
        items = [(k, self.SCAN_TYPE_LABELS[k]) for k in ("front", "both", "flatbed") if k in self.types]
        if not items:
            self.scan_type = None
            return
        self.scan_type = SegmentedControl(
            items, on_changed=self.on_scan_type, button_width=OPTION_BUTTON_WIDTH
        )
        self.scan_type.set_tooltip_text("Front Page scans one side of each sheet; Front & Back scans both")
        self.scan_type_slot.pack_start(self.scan_type, False, False, 0)
        self.scan_type_slot.show_all()

    def on_scan_type(self, key):
        """User picked a Scan Type: remember it and use its source"""
        self.ctx.settings.set("scan_type", key)
        self.choose_scan_type(key)

    def choose_scan_type(self, key):
        """Select the device source behind a Scan Type"""
        if self.scan_type:
            self.scan_type.set_active(key)
        self.source_combo.set_active_id(self.types[key])

    def sheet_mode(self):
        """Current sheet mode: "all" (Multi-Page) / "one" (Single Page); feeder sources only"""
        return self.sheets.get_active()

    def on_source_changed(self):
        """Show the Sheets choice for feeder sources only, then refresh the summary"""
        source = self.source_combo.get_active_id() or ""
        key = next((k for k, v in self.types.items() if v == source), None)
        if key and self.scan_type and self.scan_type.get_active() != key:
            self.scan_type.set_active(key)  # the source was set directly (profiles, tests)
        self.sheets_row.set_visible(is_feeder(source))
        if is_feeder(source):
            for child in self.sheets_row.get_children():  # show_all() skips a no-show-all row's children
                child.show_all()
        self.update_summary()

    def update_summary(self):
        """Show exactly what will be sent to the scanner"""
        dev = self.current_device()
        if not dev or dev.id not in self.ctx.scan.capabilities:
            self.summary.set_text("")
            return
        req = self.build_request(dry_run=True)
        if req.multi_page and req.separate:
            side = " (front and back together)" if req.sheet_pages == 2 else ""
            how = f"Single Page: scans every loaded sheet, each as its own document{side}."
        elif req.multi_page:
            how = "Multi-Page: scans every loaded sheet into one document."
        else:
            how = "Single page."
        self.summary.set_text(f"Will scan: {ScanManager.summary(req)}. {how}")

    def build_request(self, dry_run=False):
        """Build a ScanRequest from the controls (dry_run: no temp folder)"""
        dev = self.current_device()
        source = self.source_combo.get_active_id() or ""
        return self.ctx.scan.build_request(
            dev.id,
            source,
            self.color.get_active(),
            self.quality.get_active(),
            self.paper_combo.get_active_id(),
            create_dir=not dry_run,
            sheet_mode=self.sheet_mode(),
        )

    # -- scanning ----------------------------------------------------------
    def on_scan(self, _btn):
        """Start scanning with the current options"""
        if not self.current_device():
            return
        if self.ctx.scan.pages and self.ctx.scan.is_saved():
            self.ctx.scan.clear_pages()  # the last document was saved: this scan starts a new one
            self.ctx.emit("pages-changed")
            started_new = True
        else:
            started_new = False
        self.request = self.build_request()
        self.set_busy(True, scanning=True)
        self.progress.set_fraction(0)
        self.pages_this_scan = 0
        if self.request.multi_page and self.request.separate:
            what = "every sheet, each as its own document"
        elif self.request.multi_page:
            what = "all sheets from the feeder"
        else:
            what = "page"
        new = " New document (the last one is saved)." if started_new else ""
        self.set_status(f"Scanning {what}…{new}", "status-busy")
        self.ctx.scan.start_scan(self.request, self.on_page, self.on_progress, self.on_done, self.on_error)

    def on_page(self, _page):
        """Count a finished page and notify the Document page"""
        self.pages_this_scan += 1
        self.set_status(f"Scanned page {self.pages_this_scan}…", "status-busy")
        self.ctx.emit("pages-changed")

    def on_progress(self, pct):
        """Update the progress bar for the page in progress"""
        self.progress.set_fraction(min(pct, 100) / 100)

    def on_done(self, pages, cancelled):
        """Report the result; open the Document page, or wait for the next sheet in one-sheet mode"""
        self.set_busy(False)
        self.progress.set_fraction(1 if pages else 0)
        dropped = self.ctx.scan.dropped_pages
        n = len(pages) - dropped
        removed = f" ({dropped} blank page(s) removed)" if dropped else ""
        if cancelled:
            self.set_status(f"Cancelled. {n} page(s) kept.", "muted")
        else:
            total = len(self.ctx.scan.pages)
            docs = len(self.ctx.scan.doc_ids())
            if self.request and self.request.separate and docs > 1:
                self.set_status(
                    f"Done: {n} page(s) scanned{removed} as {docs} separate documents. In Document, Save saves "
                    "the selected document and Save All saves each one.",
                    "status-ok",
                )
            else:
                added = f"; the document has {total} page(s)" if total > n else ""
                self.set_status(
                    f"Done: {n} page(s) scanned{removed}{added}. Save it in Document.", "status-ok"
                )
            self.after_scan(final=True)
        if n:
            self.ctx.nav.navigate_to("preview")  # check and save; press Scan again for the next page

    def after_scan(self, final):
        """Tell feature modules a scan ended (final = the document is complete)"""
        if self.ctx.features:
            self.ctx.features.after_scan(self.ctx, self.ctx.scan.pages, final)

    def on_error(self, message):
        """Show a scan error"""
        self.set_busy(False)
        self.progress.set_fraction(0)
        self.set_status(message, "status-error")
