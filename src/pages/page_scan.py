"""
Scan Page
Choose scanner, source, colour, quality and paper; scan with live progress.
Pages go to the Preview page as they arrive.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from config.config_scan import COLOR_MODES, PAPER_SIZES, QUALITY_PRESETS, SHEET_MODES  # noqa: E402
from modules.manager_scan import ScanManager, is_duplex, is_feeder  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402


class ScanPage(BasePage):
    """Scanner selection, scan options and the Scan button"""

    def build_content(self):
        """Scanner card, options card, Scan/Cancel, progress and status"""
        self.devices = []
        self.request = None
        s = self.ctx.settings

        self.add_title("Scan", "Load your pages, choose the options and press Scan.")

        # -- scanner card
        card = self.add_card("Scanner")
        row = Gtk.Box(spacing=10)
        self.device_combo = Gtk.ComboBoxText()
        self.device_combo.connect("changed", self.on_device_changed)
        row.pack_start(self.device_combo, True, True, 0)
        self.refresh_btn = Gtk.Button(label="Refresh")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh_devices())
        row.pack_start(self.refresh_btn, False, False, 0)
        info_btn = Gtk.Button(label="Device info")
        info_btn.connect("clicked", lambda *_: self.ctx.nav.navigate_to("devices"))
        row.pack_start(info_btn, False, False, 0)
        card.pack_start(row, False, False, 0)
        self.device_status = self.label("", "muted", wrap=True)
        card.pack_start(self.device_status, False, False, 0)

        # -- options card
        card = self.add_card("Options")
        self.source_combo = Gtk.ComboBoxText()
        self.source_combo.connect("changed", lambda *_: self.on_source_changed())
        card.pack_start(self.form_row("Source", self.source_combo), False, False, 0)

        # Sheet-fed mode: only shown for feeder sources
        self.sheets = SegmentedControl(
            [(k, v["label"]) for k, v in SHEET_MODES.items()],
            active=s.get("sheet_mode"),
            on_changed=lambda k: self.remember("sheet_mode", k),
        )
        self.sheets_row = self.form_row("Sheets", self.sheets)
        self.sheets_row.set_no_show_all(True)
        card.pack_start(self.sheets_row, False, False, 0)

        self.color = SegmentedControl(
            [(k, v["label"]) for k, v in COLOR_MODES.items()],
            active=s.get("color_mode"),
            on_changed=lambda k: self.remember("color_mode", k),
        )
        card.pack_start(self.form_row("Color", self.color), False, False, 0)

        self.quality = SegmentedControl(
            [(k, v["label"]) for k, v in QUALITY_PRESETS.items()],
            active=s.get("quality"),
            on_changed=lambda k: self.remember("quality", k),
        )
        card.pack_start(self.form_row("Quality", self.quality), False, False, 0)

        self.paper_combo = Gtk.ComboBoxText()
        for key, spec in PAPER_SIZES.items():
            self.paper_combo.append(key, spec["label"])
        self.paper_combo.set_active_id(s.get("paper"))
        self.paper_combo.connect("changed", lambda c: self.remember("paper", c.get_active_id()))
        card.pack_start(self.form_row("Paper size", self.paper_combo), False, False, 0)

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
        self.done_btn = Gtk.Button(label="Done → Preview")
        self.done_btn.connect("clicked", lambda *_: self.ctx.nav.navigate_to("preview"))
        self.done_btn.set_no_show_all(True)
        actions.pack_start(self.done_btn, False, False, 0)
        self.pack_start(actions, False, False, 4)

        self.progress = Gtk.ProgressBar()
        self.pack_start(self.progress, False, False, 0)
        self.status = self.label("Looking for scanners…", "muted", wrap=True)
        self.pack_start(self.status, False, False, 0)

        self.ctx.on("settings-changed", self.on_settings_changed)
        self.ctx.on("devices-changed", self.devices_loaded)
        self.ctx.on("request-device-refresh", self.refresh_devices)
        self.set_busy(True)
        GLib.idle_add(self.refresh_devices)  # after every page has subscribed

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
        """Show a status message styled muted / ok / error / busy"""
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
            self.source_combo,
            self.color,
            self.quality,
            self.paper_combo,
            self.sheets,
            self.done_btn,
        ):
            w.set_sensitive(not busy)
        self.cancel_btn.set_sensitive(scanning)

    def current_device(self):
        """The ScannerDevice selected in the combo, or None"""
        dev_id = self.device_combo.get_active_id()
        return next((d for d in self.devices if d.id == dev_id), None)

    # -- devices -----------------------------------------------------------
    def refresh_devices(self):
        """Start a background device listing (ignored while scanning)"""
        if self.ctx.scan.busy:
            return False
        self.set_busy(True)
        self.set_status("Looking for scanners… (this can take about 10–20 seconds)", "status-busy")
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
            self.set_status(
                "No scanners found. Check the cable and power, then press Refresh.", "status-error"
            )
            return
        last = self.ctx.settings.get("last_device")
        if not self.device_combo.set_active_id(last):
            self.device_combo.set_active(0)

    def devices_failed(self, message):
        """Show a listing or options error"""
        self.set_busy(False)
        self.set_status(message, "status-error")

    def on_device_changed(self, combo):
        """Remember the device and load its capabilities"""
        dev = self.current_device()
        if not dev:
            return
        self.ctx.settings.set("last_device", dev.id)
        if not dev.methods:  # detected on USB, but nothing can drive it
            self.set_busy(False)
            self.scan_btn.set_sensitive(False)
            self.device_status.set_text("Detected on USB · no working driver (see Device Info)")
            self.set_status(dev.hint, "status-error")
            return
        self.set_busy(True)
        methods = " → ".join(m.device.backend for m in dev.methods)
        self.device_status.set_text(f"{dev.kind} · connection methods: {methods}")
        self.set_status(f"Reading {dev.model} options…", "status-busy")
        self.ctx.scan.load_capabilities(dev.id, self.caps_loaded, self.devices_failed)

    def caps_loaded(self, caps):
        """Fill the source combo from capabilities and mark Ready"""
        self.source_combo.remove_all()
        for src in caps.sources or ["Default"]:
            self.source_combo.append(src, src)
        if not self.source_combo.set_active_id(caps.default_source):
            self.source_combo.set_active(0)
        self.set_busy(False)
        self.set_status("Ready.", "status-ok")
        self.update_summary()

    def sheet_mode(self):
        """Current sheet mode ("all" / "one"); only meaningful for feeder sources"""
        return self.sheets.get_active()

    def on_source_changed(self):
        """Show the Sheets choice for feeder sources only, then refresh the summary"""
        source = self.source_combo.get_active_id() or ""
        self.sheets_row.set_visible(is_feeder(source))
        if is_feeder(source):
            self.sheets_row.show_all()
        self.update_summary()

    def update_summary(self):
        """Show exactly what will be sent to the scanner"""
        dev = self.current_device()
        if not dev or dev.id not in self.ctx.scan.capabilities:
            self.summary.set_text("")
            return
        req = self.build_request(dry_run=True)
        if req.multi_page:
            how = "Feeder: scans every loaded sheet."
        elif is_feeder(req.source):
            side = "both sides" if is_duplex(req.source) else "one side"
            how = f"One sheet per press ({side}); pages are added to the same document."
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
        self.request = self.build_request()
        self.set_busy(True, scanning=True)
        self.progress.set_fraction(0)
        self.pages_this_scan = 0
        if self.request.multi_page:
            what = "all sheets from the feeder"
        elif is_feeder(self.request.source):
            what = "one sheet"
        else:
            what = "page"
        self.set_status(f"Scanning {what}…", "status-busy")
        self.ctx.scan.start_scan(self.request, self.on_page, self.on_progress, self.on_done, self.on_error)

    def on_page(self, _page):
        """Count a finished page and notify the Preview page"""
        self.pages_this_scan += 1
        self.set_status(f"Scanned page {self.pages_this_scan}…", "status-busy")
        self.ctx.emit("pages-changed")

    def on_progress(self, pct):
        """Update the progress bar for the page in progress"""
        self.progress.set_fraction(min(pct, 100) / 100)

    def on_done(self, pages, cancelled):
        """Report the result; open Preview, or wait for the next sheet in one-sheet mode"""
        self.set_busy(False)
        self.progress.set_fraction(1 if pages else 0)
        n = len(pages)
        one_sheet = self.request and is_feeder(self.request.source) and not self.request.multi_page
        total = len(self.ctx.scan.pages)
        if cancelled:
            self.set_status(f"Cancelled. {n} page(s) kept.", "muted")
        elif one_sheet and n:
            self.scan_btn.set_label("Scan next sheet")
            self.done_btn.show()
            self.set_status(
                f"Sheet added ({n} page(s)); document now has {total} page(s). "
                "Load the next sheet and press Scan next sheet, or Done → Preview.",
                "status-ok",
            )
            return  # stay here for the next sheet
        else:
            self.set_status(f"Done: {n} page(s) scanned. Opening preview…", "status-ok")
        self.scan_btn.set_label("Scan")
        self.done_btn.hide()
        if n:
            self.ctx.nav.navigate_to("preview")

    def on_shown(self):
        """Back on the Scan page after a one-sheet session: start fresh labels"""
        if not self.ctx.scan.busy and self.ctx.nav.get_current_page() == "scan":
            if not self.ctx.scan.pages:
                self.scan_btn.set_label("Scan")
                self.done_btn.hide()

    def on_error(self, message):
        """Show a scan error"""
        self.set_busy(False)
        self.progress.set_fraction(0)
        self.set_status(message, "status-error")
