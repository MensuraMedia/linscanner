"""
Scan Devices Found Page (sidebar: Devices)
Every detected scanner with identity, connection path, connection methods in
fallback order, permissions, capabilities, live status and firmware. Populates
automatically; "Check for devices again" re-runs detection (SANE, eSCL, USB).
"""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from modules import manager_device_info as info  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

LEVEL_CSS = {"ok": "status-ok", "warn": "status-busy", "busy": "status-busy", "error": "status-error"}


def run_in_background(work, on_done, on_fail):
    """Run work() in a thread; on_done(result) or on_fail(message) on the GTK thread"""

    def runner():
        try:
            result = work()
        except Exception as e:  # a probe must never crash the page
            GLib.idle_add(on_fail, str(e))
        else:
            GLib.idle_add(on_done, result)

    threading.Thread(target=runner, daemon=True).start()


class DevicesPage(BasePage):
    """Scan Devices Found"""

    def build_content(self):
        """Title, check-again button, summary line and the device sections"""
        self.add_title(
            "Scan Devices Found",
            "Scanners LinScanner can see, how it reaches each one (in fallback order), and what they can do.",
        )
        row = Gtk.Box(spacing=10)
        self.check_btn = Gtk.Button(label="Check for devices again")
        self.check_btn.get_style_context().add_class("primary-pill")
        self.check_btn.connect("clicked", lambda *_: self.ctx.emit("request-device-refresh"))
        row.pack_start(self.check_btn, False, False, 0)
        self.summary = self.label("Looking for scanners…", "status-busy")
        row.pack_start(self.summary, False, False, 6)
        self.pack_start(row, False, False, 0)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pack_start(self.list_box, False, False, 0)
        self.firmware_cache = {}
        self.ctx.on("devices-changed", self.show_devices)
        self.ctx.on("devices-refreshing", self.on_refreshing)

    def on_refreshing(self):
        """Show that detection is running"""
        self.check_btn.set_sensitive(False)
        self._summary("Checking for scanners (SANE drivers, eSCL, USB)… about 10–20 seconds", "status-busy")

    def _summary(self, text, css):
        """Set the summary line text and colour"""
        ctx = self.summary.get_style_context()
        for c in ("status-busy", "status-ok", "status-error"):
            ctx.remove_class(c)
        ctx.add_class(css)
        self.summary.set_text(text)

    def show_devices(self, _visible=None):
        """Rebuild one section per physical scanner"""
        self.check_btn.set_sensitive(True)
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        devices = self.ctx.scan.devices
        working = [d for d in devices if d.methods]
        if working:
            self._summary(f"{len(working)} scanner(s) detected and responding to a driver.", "status-ok")
        elif devices:
            self._summary("Scanner hardware found, but no driver works yet. See below.", "status-error")
        else:
            self._summary("No scanners detected. Check cable and power, then check again.", "status-error")
        for d in devices:
            self.list_box.pack_start(self.device_section(d), False, False, 0)
        self.list_box.show_all()

    def device_section(self, d):
        """Section for one scanner: status row, then an info grid"""
        box, inner = self.make_card(f"{d.vendor} {d.model}".strip())
        status_row = Gtk.Box(spacing=10)
        status_btn = Gtk.Button(label="Check status")
        status_lbl = self.label("", "muted", wrap=True)
        status_btn.connect("clicked", lambda *_: self.check_status(d, status_lbl, status_btn))
        status_btn.set_sensitive(bool(d.methods))
        status_row.pack_start(status_btn, False, False, 0)
        status_row.pack_start(status_lbl, True, True, 0)
        inner.pack_start(status_row, False, False, 0)
        if not d.methods:
            status_lbl.get_style_context().add_class("status-error")
            status_lbl.set_text(d.hint)

        caps = self.ctx.scan.capabilities.get(d.id)
        grid = Gtk.Grid(column_spacing=18, row_spacing=3)
        row = 0
        for title, rows in info.sections(d, caps):
            head = self.label(title, "secondary")
            head.set_margin_top(8)
            grid.attach(head, 0, row, 2, 1)
            row += 1
            for key, value in rows:
                grid.attach(self.label(key, "info-key"), 0, row, 1, 1)
                val = self.label(value, "info-value", wrap=True, selectable=True)
                val.set_hexpand(True)
                grid.attach(val, 1, row, 1, 1)
                row += 1
        fw_val = self.label(self.firmware_cache.get(d.id, "reading…"), "info-value", selectable=True)
        grid.attach(self.label("Firmware", "info-key"), 0, row, 1, 1)
        grid.attach(fw_val, 1, row, 1, 1)
        inner.pack_start(grid, False, False, 0)

        if d.methods and caps is None and not self.ctx.scan.busy:  # load, then redraw
            self.ctx.scan.load_capabilities(d.id, lambda *_: self.show_devices(), lambda *_: None)
        if d.id not in self.firmware_cache and not self.ctx.scan.busy:
            self.firmware_cache[d.id] = "reading…"
            run_in_background(
                lambda: info.firmware(d),
                lambda fw: self._firmware_done(d, fw, fw_val),
                lambda err: self._firmware_done(d, f"unavailable ({err})", fw_val),
            )
        return box

    def _firmware_done(self, d, fw, label):
        """Store and show a firmware string read in the background"""
        self.firmware_cache[d.id] = fw
        label.set_text(fw)

    def check_status(self, d, label, button):
        """Probe the scanner in the background and show a plain-language status"""
        if self.ctx.scan.busy:
            label.set_text("A scan is running; check again when it finishes.")
            return
        button.set_sensitive(False)
        label.set_text("Checking…")

        def show(level, text):
            get_logger("ui").info("status of %s %s: %s (%s)", d.vendor, d.model, text, level)
            ctx = label.get_style_context()
            for c in ("muted", *LEVEL_CSS.values()):
                ctx.remove_class(c)
            ctx.add_class(LEVEL_CSS.get(level, "muted"))
            label.set_text(text)
            button.set_sensitive(True)

        run_in_background(lambda: info.check_status(d), lambda r: show(*r), lambda e: show("error", e))

    def on_shown(self):
        """Refresh the sections when the page is opened; a remembered scanner gets a full check"""
        devices = self.ctx.scan.devices
        if any(getattr(d, "restored", False) for d in devices) and not self.ctx.scan.busy:
            self.ctx.emit("request-device-refresh")  # USB facts, every driver, other scanners
        elif devices:
            self.show_devices()
