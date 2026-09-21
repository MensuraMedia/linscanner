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
    assert theme.apply_theme(get_theme("default"))
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


def build_app(with_features=False):
    """Real window wired to SANE's virtual scanner with throwaway settings"""
    import gi

    gi.require_version("Gtk", "3.0")
    from backends.backend_sane import SaneBackend
    from config.config_themes import get_theme
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow

    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("show_all_backends", True)
    theme = ThemeApplicator()
    theme.apply_theme(get_theme("default"))
    scan = ScanManager(settings, SaneBackend(only_backends=["test"]))
    ctx = AppContext(settings, scan, NavigationManager(), theme)
    if with_features:
        from features import FeatureRegistry

        ctx.features = FeatureRegistry(settings)
        scan.features = ctx.features
    window = AppWindow(ctx)
    window.show_all()
    ctx.nav.navigate_to("scan")
    return ctx, window, scan


def test_one_sheet_at_a_time_builds_one_document():
    ctx, window, scan = build_app()
    page = ctx.nav.get_page_widget("scan")
    assert wait_for(lambda: page.status.get_text() == "Ready.")
    page.source_combo.set_active_id("Automatic Document Feeder")
    assert page.sheets_row.get_visible()  # Sheets choice appears for feeder sources
    page.sheets.set_active("one")
    for sheet in (1, 2):
        page.on_scan(None)
        assert wait_for(lambda: not scan.busy and page.scan_btn.get_label() == "Scan next sheet")
        assert len(scan.pages) == sheet  # one sheet per press, same document
    assert ctx.nav.get_current_page() == "scan"  # waits for the next sheet
    page.done_btn.clicked()
    assert ctx.nav.get_current_page() == "preview"
    window.destroy()
    scan.cleanup()


def test_features_in_the_window(tmp_path, monkeypatch):
    """Feature buttons, Settings toggles, Quick Edit editor and profiles in the real UI"""
    from PIL import Image, ImageDraw

    from features.feature_quick_edit import QuickEditor, import_signature

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    ctx, window, scan = build_app(with_features=True)
    page = ctx.nav.get_page_widget("scan")
    assert wait_for(lambda: page.status.get_text() == "Ready.")
    page.source_combo.set_active_id("Automatic Document Feeder")
    page.sheets.set_active("all")
    page.on_scan(None)
    assert wait_for(lambda: not scan.busy and ctx.nav.get_current_page() == "preview")
    assert len(scan.pages) == 10  # colour test pattern: nothing blank, nothing removed

    preview = ctx.nav.get_page_widget("preview")
    assert set(preview.feature_buttons) == {"quick_edit", "import_images"}
    assert preview.feature_buttons["quick_edit"].get_visible()
    ctx.features.set_enabled("quick_edit", False)  # what the Settings checkbox does
    ctx.emit("features-changed")
    assert not preview.feature_buttons["quick_edit"].get_visible()
    ctx.features.set_enabled("quick_edit", True)
    ctx.emit("features-changed")

    sig = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(sig).line([(10, 80), (290, 20)], fill=(0, 0, 150, 255), width=8)
    sig_path = str(tmp_path / "me.png")
    sig.save(sig_path)
    lib_path = import_signature(sig_path)

    editor = QuickEditor(ctx, scan.pages, 0)
    editor.text_entry.set_text("Received 2026-09-21")
    editor.add_text()
    editor.place_signature(lib_path)
    editor.move_item(editor.selected, 0.6, 0.7)
    editor.apply_to_all()
    editor.commit()
    editor.dialog.destroy()
    assert [o["type"] for o in scan.pages[0]["overlays"]] == ["text", "image"]
    assert scan.pages[0]["overlays"][1]["x"] == 0.6
    assert all(len(p.get("overlays", [])) == 1 for p in scan.pages[1:])  # signature re-applied

    ctx.nav.navigate_to("scan")
    profiles = ctx.features.get("profiles")
    ctx.features.set_enabled("profiles", True)
    ctx.emit("features-changed")
    profiles.apply(page, "Receipt")
    assert (page.color.get_active(), page.quality.get_active()) == ("bw", "low")
    window.destroy()
    scan.cleanup()
