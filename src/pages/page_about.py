"""
About Page
What LinScanner is, privacy and licence in brief, where your files are,
handy shortcuts, system versions and credits. (Signature-font credits are
kept in the backlog, docs/FOLLOW-UP.md #33, as requested.)
"""

import os
import platform
import shutil
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from pages.page_base import BasePage  # noqa: E402
from utils.util_paths import APP_ROOT, read_version  # noqa: E402


def sane_version():
    """First line of `scanimage --version`, or a short status"""
    if not shutil.which("scanimage"):
        return "not installed"
    try:
        out = subprocess.run(["scanimage", "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.strip().splitlines()[0] if out.strip() else "unknown"


def tilde(path):
    """A path with the home folder shown as ~"""
    home = os.path.expanduser("~")
    return "~" + path[len(home) :] if path.startswith(home) else path


def user_paths():
    """(what, path) for every place LinScanner keeps your data"""
    from modules.manager_settings import default_path
    from utils.util_fonts import user_fonts_dir
    from utils.util_logging import log_dir
    from utils.util_signatures import signatures_dir

    data = os.path.dirname(signatures_dir())
    return [
        ("Settings", default_path()),
        ("Saved signatures (up to 4)", signatures_dir()),
        ("Fonts you added", user_fonts_dir()),
        ("Recent documents list", os.path.join(data, "recent.json")),
        ("Logs (kept 14 days)", log_dir()),
        ("Scans in progress", "/tmp/linscanner-*/ (deleted when LinScanner closes)"),
    ]


class AboutPage(BasePage):
    """About LinScanner"""

    def _text(self, card, text, css="secondary", selectable=False):
        """Add a wrapped label to a card"""
        card.pack_start(self.label(text, css, wrap=True, selectable=selectable), False, False, 0)

    def _grid(self, card, rows):
        """Two-column key / value grid"""
        grid = Gtk.Grid(column_spacing=18, row_spacing=3)
        for n, (key, value) in enumerate(rows):
            grid.attach(self.label(key, "info-key"), 0, n, 1, 1)
            val = self.label(value, "info-value", wrap=True, selectable=True)
            val.set_hexpand(True)
            grid.attach(val, 1, n, 1, 1)
        card.pack_start(grid, False, False, 0)

    def build_content(self):
        """All About sections"""
        self.add_title("LinScanner", f"Version {read_version()} · a document scanner for Linux")

        card = self.add_card("What it is")
        self._text(
            card,
            "Scan documents from any USB-connected scanner that Linux supports (SANE drivers), in "
            "color or black & white at three quality levels. Check and fix the pages, add text and "
            "signatures with Quick Edit, then save as PDF, PNG, JPEG or TIFF.",
        )
        self._text(
            card,
            "Connection: USB cable only. Wi-Fi and network scanning are not supported at this time.",
            "muted",
        )

        card = self.add_card("Compatibility")
        self._text(
            card,
            "LinScanner is ever evolving. Each release adds and verifies more devices and systems, and "
            "reports of what works (or doesn't) on your hardware help it grow. What it works with today:",
            "muted",
        )
        self._grid(
            card,
            [
                (
                    "Scanners",
                    "USB scanners with a SANE driver: 80+ open-source drivers cover most models from Epson, "
                    "Canon, Fujitsu / Ricoh (ScanSnap, fi-series), Brother, HP, Plustek, Avision, Kodak, "
                    "Panasonic, Visioneer, Xerox and more, plus vendor drivers such as Epson Scan 2 and HP hplip",
                ),
                ("Multifunction printers", "USB all-in-ones with driverless scanning (IPP-over-USB / eSCL)"),
                ("Verified", "Epson WorkForce ES-400 II (document feeder, duplex)"),
                (
                    "Scanner types",
                    "Sheet-fed document scanners (single or double-sided), flatbeds, all-in-ones",
                ),
                (
                    "Systems",
                    "Linux Mint 22 (tested). Ubuntu 24.04 and other Debian-based systems with Python 3.10+ "
                    "and GTK 3; other distributions with the same packages should work",
                ),
                (
                    "Paper",
                    "Auto-Detect, Letter, Legal, Executive, Half Letter, A4, A5, A6, B5, receipts (80 / 58 mm), "
                    "business, ID and index cards, photos (4×6, 5×7), checks",
                ),
                ("Saves", "PDF (optionally searchable and PDF/A), PNG, JPEG, TIFF (multi-page)"),
                ("Opens", "PDF, PNG, JPEG, TIFF (multi-page) for review and Quick Edit"),
                (
                    "Not yet",
                    "Wi-Fi / network scanners, text recognition in languages other than English, "
                    "cameras and document cameras",
                ),
                ("Check a scanner", "Devices shows whether a driver can use your scanner and why"),
            ],
        )

        card = self.add_card("Privacy")
        self._text(
            card,
            "Everything happens on this computer. LinScanner never sends your scans, documents, "
            "signatures, settings or any other information to anyone: no cloud, no accounts, no "
            "telemetry, no network scanner search. OCR runs locally. Files leave this computer only "
            "if you copy or send them yourself.",
        )

        card = self.add_card("Licence")
        self._text(
            card,
            "LinScanner Community License (Noncommercial) 1.0. You're welcome to use it free of "
            "charge, and to copy, modify and share it for any noncommercial purpose. Commercial use "
            "needs written permission from MensuraMedia; we're happy to talk. The components "
            "LinScanner builds on keep their own licences.",
        )
        self._text(card, f"Full text: {tilde(os.path.join(APP_ROOT, 'LICENSE'))}", "muted", selectable=True)

        card = self.add_card("Your files")
        self._grid(card, [(what, tilde(path)) for what, path in user_paths()])

        card = self.add_card("Handy shortcuts")
        self._grid(
            card,
            [
                (
                    "Document",
                    "Ctrl + mouse wheel or Ctrl + / Ctrl − to zoom, Ctrl 0 to fit; drag to move around",
                ),
                ("Document", "Page Up / Page Down for the next or previous page"),
                ("Document", "Double-click a thumbnail’s caption (or F2) to name a page"),
                ("Quick Edit", "Add Text, then click anywhere and type; Enter starts a line below"),
                ("Quick Edit", "Guides line text up with earlier text; hold Alt to place freely"),
                ("Quick Edit", "Double-click text to edit it; Delete removes; arrow keys nudge"),
                ("Saved", "Click a row to preview it · double-click to open it · click its name to rename"),
            ],
        )

        card = self.add_card("System")
        try:
            gtk = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        except Exception:
            gtk = "?"
        self._grid(
            card,
            [
                ("LinScanner", read_version()),
                ("Scanning (SANE)", sane_version()),
                ("Python", platform.python_version()),
                ("GTK", gtk),
            ],
        )

        card = self.add_card("Credits")
        self._grid(
            card,
            [
                ("Made by", "MensuraMedia · part of linux-peripherals"),
                ("Interface", "gtk-python-dashboard-starter by mikesdatawork"),
                ("Build process", "MensuraMedia universal-instruction-set"),
                ("Scanning", "SANE project, sane-airscan (Alexander Pevzner), ipp-usb (OpenPrinting)"),
                ("Images and PDF", "Pillow, NumPy, Ghostscript (Artifex)"),
                ("Text recognition", "Tesseract OCR"),
                ("Icons", "Phosphor Icons by Helena Zhang and Tobias Fried (MIT licence)"),
                ("Text fonts", "DejaVu, Liberation, Noto, Ubuntu and URW base35, from your system"),
            ],
        )
