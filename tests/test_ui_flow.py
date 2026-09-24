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
    assert wait_for(lambda: page.power_state == "on")
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


def test_single_page_makes_each_sheet_its_own_document(tmp_path):
    """Single Page: every sheet in the feeder becomes its own document; each can be saved on its own"""
    import os

    ctx, window, scan = build_app()
    ctx.settings.override("save_folder", str(tmp_path))
    page = ctx.nav.get_page_widget("scan")
    assert wait_for(lambda: page.power_state == "on")
    assert page.power_on_icon.get_visible() and not page.device_status.get_visible()  # green, no message
    page.source_combo.set_active_id("Automatic Document Feeder")
    assert page.sheets_row.get_visible()  # Sheets choice appears for feeder sources
    assert [b.get_label() for b in page.sheets.buttons.values()] == ["Multi-Page", "Single Page"]
    page.sheets.set_active("one")
    page.on_scan(None)
    assert wait_for(lambda: not scan.busy and ctx.nav.get_current_page() == "preview")
    docs = scan.doc_ids()
    assert len(scan.pages) == 10 and len(docs) == 10  # the whole tray, one document per sheet
    preview = ctx.nav.get_page_widget("preview")
    assert preview.save_all_btn.get_visible()
    assert preview.preview._buttons[3].get_child().label.get_label() == "Doc 4"
    preview.preview.select(3)
    preview.on_save()  # Save: only the selected document
    assert scan.doc_is_saved(docs[3]) and not scan.doc_is_saved(docs[0]) and not scan.is_saved()
    assert "✓" in preview.thumb_label(3, scan.pages[3])
    preview.on_save_all()  # Save All: one PDF per document
    assert scan.is_saved() and len({scan.documents[d]["path"] for d in docs}) == 10
    assert all(os.path.exists(scan.documents[d]["path"]) for d in docs)
    page.on_scan(None)  # everything saved: the next Scan starts afresh
    assert wait_for(lambda: not scan.busy and ctx.nav.get_current_page() == "preview")
    assert len(scan.doc_ids()) == 10 and not scan.is_saved()
    page.sheets.set_active("all")
    preview.on_save_all()
    page.on_scan(None)  # Multi-Page: one document
    assert wait_for(lambda: not scan.busy and len(scan.pages) == 10)
    assert len(scan.doc_ids()) == 1 and not preview.save_all_btn.get_visible()
    window.destroy()
    scan.cleanup()


def test_power_mark_when_no_scanner():
    ctx, window, scan = build_app()
    page = ctx.nav.get_page_widget("scan")
    assert wait_for(lambda: page.power_state == "on")
    page.devices_loaded([])  # e.g. the scanner was switched off
    assert page.power_state == "off" and page.device_status.get_text() == page.POWER_OFF_MESSAGE
    assert page.mark.get_visible_child_name() == "off" and page.status.get_text() == ""
    window.destroy()
    scan.cleanup()


def test_features_in_the_window(tmp_path, monkeypatch):
    """Feature buttons, Settings toggles, Quick Edit editor and profiles in the real UI"""
    from PIL import Image, ImageDraw

    from features.feature_quick_edit import QuickEditor, import_signature

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    ctx, window, scan = build_app(with_features=True)
    page = ctx.nav.get_page_widget("scan")
    assert wait_for(lambda: page.power_state == "on")
    page.source_combo.set_active_id("Automatic Document Feeder")
    page.sheets.set_active("all")
    page.on_scan(None)
    assert wait_for(lambda: not scan.busy and ctx.nav.get_current_page() == "preview")
    assert len(scan.pages) == 10  # colour test pattern: nothing blank, nothing removed

    preview = ctx.nav.get_page_widget("preview")
    assert set(preview.feature_buttons) == {"quick_edit", "import_images"}
    assert all(b.get_visible() for b in preview.feature_buttons["quick_edit"])  # Add Text, Signature
    ctx.features.set_enabled("quick_edit", False)  # what the Settings checkbox does
    ctx.emit("features-changed")
    assert not any(b.get_visible() for b in preview.feature_buttons["quick_edit"])
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


def test_preview_document_tools_and_undo(tmp_path):
    """Add Page (PDF), duplicate, reverse, delete with undo / redo; groups; window min size"""
    import shutil

    from PIL import Image

    ctx, window, scan = build_app(with_features=True)
    preview = ctx.nav.get_page_widget("preview")
    ctx.nav.navigate_to("preview")
    pdf = str(tmp_path / "two.pdf")
    Image.new("RGB", (425, 550), "white").save(
        pdf, "PDF", save_all=True, append_images=[Image.new("RGB", (425, 550), "gray")], resolution=50
    )
    if shutil.which("gs"):
        assert preview.add_pages([pdf]) == 2 and len(scan.pages) == 2
    else:
        scan.pages += [{"path": pdf, "rotation": 0, "dpi": 100, "mode": "x"}] * 2
    preview.reload()
    preview.preview.select(0)
    first = scan.pages[0]["path"]
    preview.duplicate_page()
    assert len(scan.pages) == 3 and scan.pages[1]["path"] == first
    preview.reverse_pages()
    assert scan.pages[-1]["path"] == first
    preview.delete_page()
    assert len(scan.pages) == 2
    for expected in (3, 3, 2):  # undo delete, undo reverse (still 3), undo duplicate
        preview.undo()
        assert len(scan.pages) == expected
    preview.redo()
    assert len(scan.pages) == 3
    names = [b.get_tooltip_text().split(":")[0] for b in preview.groups["pages"].get_children()]
    assert names[:2] == ["Add Page", "Add Image"]
    # editing tools sit together: crop first, then the feature modules
    assert [b.get_tooltip_text().split(":")[0] for b in preview.groups["content"].get_children()] == [
        "Crop",
        "Add Text",
        "Signature",
    ]
    # exporting sits together too: this page, then Save / Save All / Save As
    exports = [b.get_tooltip_text() for b in preview.groups["export"].get_children()]
    assert len(exports) == 4 and exports[0].startswith("Save this page as")
    assert exports[1].startswith("Save to this document") and exports[3].startswith("Save As")
    for pid in ("scan", "preview", "recent", "devices", "settings", "about"):
        ctx.nav.navigate_to(pid)
        wait_for(lambda: True, 0.3)
        minimum, _natural = window.get_preferred_size()
        assert minimum.width <= 1280 and minimum.height <= 540, pid  # fits a quarter of a 2560x1080 screen
    window.destroy()
    scan.cleanup()
