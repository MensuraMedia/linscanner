"""
About Page
Version, scanning stack versions and credits.
"""

import shutil
import subprocess

from pages.page_base import BasePage
from utils.util_paths import read_version


def sane_version():
    if not shutil.which("scanimage"):
        return "not installed"
    try:
        out = subprocess.run(["scanimage", "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.strip().splitlines()[0] if out.strip() else "unknown"


class AboutPage(BasePage):
    """About linscanner"""

    def build_content(self):
        self.add_title("linscanner", f"Version {read_version()}")
        card = self.add_card("What it is")
        card.pack_start(
            self.label(
                "A universal document scanner for Linux. It works with any scanner that has a "
                "SANE driver: USB scanners, network scanners through sane-airscan (eSCL/WSD), "
                "HP devices through hplip, and more. Scan in color or black & white at three "
                "quality levels, preview and fix pages, then save as PDF, PNG, JPEG or TIFF.",
                "secondary",
                wrap=True,
            ),
            False,
            False,
            0,
        )
        card = self.add_card("System")
        card.pack_start(self.label(sane_version(), "secondary", selectable=True), False, False, 0)
        card = self.add_card("Credits")
        card.pack_start(
            self.label(
                "UI framework: gtk-python-dashboard-starter by mikesdatawork\n"
                "Build process and color scheme: MensuraMedia universal-instruction-set\n"
                "Part of MensuraMedia/linux-peripherals",
                "secondary",
                wrap=True,
            ),
            False,
            False,
            0,
        )
