"""End-to-end UI flow in-process: Scan page -> pages in Preview -> export PDF.
Uses SANE's virtual scanner; needs a display."""

import os
import tempfile
import time

from conftest import requires_display, requires_sane

pytestmark = [requires_sane, requires_display]


def wait_for(condition, timeout=60):
    from gi.repository import Gtk

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_scan_preview_save(tmp_path):
    import gi

    gi.require_version("Gtk", "3.0")
    from backends.backend_sane import SaneBackend
    from config.config_themes import get_theme
    from modules.app_context import AppContext
    from modules.manager_export import export_pages
    from modules.manager_navigation import NavigationManager
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow

    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("show_all_backends", True)
    theme = ThemeApplicator()
    assert theme.apply_theme(get_theme("black-yellow-gray"))
    scan = ScanManager(settings, SaneBackend(only_backends=["test"]))
    ctx = AppContext(settings, scan, NavigationManager(), theme)
    window = AppWindow(ctx)
    window.show_all()
    ctx.nav.navigate_to("scan")
    page = ctx.nav.get_page_widget("scan")

    # scanner found and options loaded
    assert wait_for(lambda: page.status.get_text() == "Ready.")
    assert page.device_combo.get_active_id() == "test:0"

    # feeder + Black & White + Low
    page.source_combo.set_active_id("Automatic Document Feeder")
    page.color.set_active("bw")
    page.quality.set_active("low")
    page.paper_combo.set_active_id("a5")
    page.on_scan(None)
    assert wait_for(lambda: not scan.busy and ctx.nav.get_current_page() == "preview")
    assert len(scan.pages) == 10
    assert scan.pages[0]["mode"] == "Gray" and scan.pages[0]["dpi"] == 150

    # preview shows the pages; rotate + delete work
    preview = ctx.nav.get_page_widget("preview")
    assert len(preview.preview.strip.get_children()) == 10
    preview.rotate(180)
    assert scan.pages[0]["rotation"] == 180
    preview.delete_page()
    assert len(scan.pages) == 9

    # save as PDF (the dialog itself is GTK's; export is what it calls)
    out = export_pages(scan.pages, str(tmp_path / "flow.pdf"))
    assert open(out[0], "rb").read().startswith(b"%PDF")
    window.destroy()
    scan.cleanup()
