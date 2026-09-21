"""
Devices Page
Lists every scanner SANE reports (including duplicates hidden on the Scan
page) with its driver and capabilities.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from backends.parser_sane import redact  # noqa: E402
from modules.manager_scan import filter_devices  # noqa: E402
from pages.page_base import BasePage  # noqa: E402


class DevicesPage(BasePage):
    """Detected scanners and their capabilities"""

    def build_content(self):
        """Title, intro and the device list container"""
        self.add_title(
            "Devices",
            "Scanners found through SANE. When one scanner is offered by several drivers, "
            "the Scan page uses the preferred one (marked ★).",
        )
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.pack_start(self.list_box, False, False, 0)
        self.ctx.on("devices-changed", self.show_devices)
        self.show_devices([])

    def show_devices(self, _visible):
        """Rebuild the device cards from the scan manager's last listing"""
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        all_devices = self.ctx.scan.devices
        preferred = {d.id for d in filter_devices(all_devices)}
        if not all_devices:
            self.list_box.pack_start(self.label("No scanners detected yet.", "muted"), False, False, 0)
        for d in all_devices:
            card, inner = self.make_card(("★ " if d.id in preferred else "") + f"{d.vendor} {d.model}")
            inner.pack_start(
                self.label(f"Driver: {d.backend}   ·   Type: {d.kind}", "secondary"), False, False, 0
            )
            inner.pack_start(self.label(f"Device: {redact(d.id)}", "muted", selectable=True), False, False, 0)
            caps = self.ctx.scan.capabilities.get(d.id)
            if caps:
                res = f"{caps.resolutions[0]}–{caps.resolutions[-1]} dpi" if caps.resolutions else "?"
                inner.pack_start(
                    self.label(
                        f"Sources: {', '.join(caps.sources) or 'default'}\n"
                        f"Modes: {', '.join(caps.modes)}\nResolutions: {res}\n"
                        f"Max area: {caps.max_width_mm:g} × {caps.max_height_mm:g} mm",
                        "secondary",
                    ),
                    False,
                    False,
                    0,
                )
            else:
                inner.pack_start(
                    self.label("Select it on the Scan page to read its capabilities.", "muted"),
                    False,
                    False,
                    0,
                )
            self.list_box.pack_start(card, False, False, 0)
        self.list_box.show_all()

    def on_shown(self):
        """Refresh the cards whenever the page is opened"""
        self.show_devices(None)
