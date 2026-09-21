#!/usr/bin/env python3
"""
linscanner
Universal document scanner for Linux (SANE). Entry point.
"""

import argparse
import os
import sys
import tempfile

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from backends.backend_escl import EsclBackend  # noqa: E402
from backends.backend_sane import SaneBackend  # noqa: E402
from modules.manager_connection import ConnectionEngine  # noqa: E402
from config.config_themes import get_theme  # noqa: E402
from modules.app_context import AppContext  # noqa: E402
from modules.manager_navigation import NavigationManager  # noqa: E402
from modules.manager_scan import ScanManager  # noqa: E402
from modules.manager_settings import SettingsManager  # noqa: E402
from modules.manager_theme_applicator import ThemeApplicator  # noqa: E402
from ui.app_window import AppWindow  # noqa: E402
from utils.util_paths import read_version  # noqa: E402


def parse_args(argv):
    """Parse command-line options (--version, --test-scanner, --page, --quit-after)"""
    p = argparse.ArgumentParser(prog="linscanner", description="Universal document scanner (SANE)")
    p.add_argument("--version", action="version", version=f"linscanner {read_version()}")
    p.add_argument(
        "--test-scanner", action="store_true", help="use only SANE's virtual test scanner (no hardware)"
    )
    p.add_argument("--page", default="scan", help="page to open: scan, preview, devices, settings, about")
    p.add_argument(
        "--quit-after", type=int, default=0, metavar="SECONDS", help="close automatically (for UI tests)"
    )
    return p.parse_args(argv)


def main(argv=None):
    """Build services and the window, run the GTK loop, clean up temp scans on exit"""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.test_scanner:
        # isolated session: throwaway settings file, only SANE's virtual scanner
        settings = SettingsManager(
            path=os.path.join(tempfile.mkdtemp(prefix="linscanner-test-"), "settings.json")
        )
        settings.override("show_all_backends", True)  # test:0 is normally hidden
        backend = SaneBackend(only_backends=["test"])
    else:
        settings = SettingsManager()
        backend = None  # production: SANE + linscanner's eSCL client + USB probe

    theme = ThemeApplicator()
    theme.apply_theme(get_theme(settings.get("theme")))
    if backend is None:
        engine = ConnectionEngine([SaneBackend(), EsclBackend()])
        scan = ScanManager(settings, engine.backends[0], engine=engine)
    else:
        scan = ScanManager(settings, backend)
    ctx = AppContext(settings, scan, NavigationManager(), theme)

    window = AppWindow(ctx)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    ctx.nav.navigate_to(args.page)
    if args.quit_after:
        GLib.timeout_add_seconds(args.quit_after, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        scan.cleanup()  # remove this session's temporary scan images
    return 0


if __name__ == "__main__":
    sys.exit(main())
