"""0.4.0: page names, crops as new pages, and the Saved page (search, rename, preview).

The pure parts run anywhere; the page test needs a display (xvfb-run is enough)."""

import os
import tempfile
import time

from conftest import requires_display
from modules.manager_documents import crop_name, safe_name


# -- names ----------------------------------------------------------------------------------------
def test_safe_name_cleans_what_a_user_types():
    assert safe_name("  Invoice totals  ") == "Invoice totals"
    assert safe_name("a/b\\c") == "a b c"
    assert safe_name("two   spaces") == "two spaces"
    assert safe_name("...") == ""
    assert safe_name("") == "" and safe_name(None) == ""
    assert len(safe_name("x" * 200)) == 60


def test_crop_name_counts_per_source_page():
    pages = [{"name": "Page 1"}]
    assert crop_name(pages, "Page 1") == "crop 1"
    pages.append({"name": "crop 1", "crop_of": "Page 1"})
    assert crop_name(pages, "Page 1") == "crop 2"
    # another page's crops are numbered on their own
    assert crop_name(pages, "Page 2") == "crop 1"


def test_crop_name_fills_a_gap_left_by_a_deleted_crop():
    pages = [{"name": "Page 1"}, {"name": "crop 2", "crop_of": "Page 1"}]
    assert crop_name(pages, "Page 1") == "crop 1"


def test_crop_name_ignores_a_renamed_crop():
    pages = [{"name": "Page 1"}, {"name": "Invoice totals", "crop_of": "Page 1"}]
    assert crop_name(pages, "Page 1") == "crop 1"


# -- the Document page ------------------------------------------------------------------------------
def build_app(tmp_path):
    """A window with the real pages, no scanner involved"""
    import gi

    gi.require_version("Gtk", "3.0")
    from backends.backend_sane import SaneBackend
    from config.config_themes import get_theme
    from features import FeatureRegistry
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager
    from modules.manager_theme_applicator import ThemeApplicator
    from ui.app_window import AppWindow

    saved = tmp_path / "saved"
    saved.mkdir()
    settings = SettingsManager(os.path.join(tempfile.mkdtemp(), "s.json"))
    settings.override("save_folder", str(saved))
    theme = ThemeApplicator()
    theme.apply_theme(get_theme("default"))
    scan = ScanManager(settings, SaneBackend(only_backends=["test"]))
    ctx = AppContext(settings, scan, NavigationManager(), theme)
    ctx.features = FeatureRegistry(settings)
    window = AppWindow(ctx)
    window.show_all()
    return ctx, window, str(saved)


def pump(seconds=0.5):
    from gi.repository import Gtk

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def a_pdf(path, pages=2):
    from PIL import Image, ImageDraw

    images = []
    for _ in range(pages):
        im = Image.new("RGB", (620, 877), "white")
        ImageDraw.Draw(im).rectangle((60, 60, 350, 105), fill=(0, 90, 170))
        images.append(im)
    images[0].save(path, save_all=True, append_images=images[1:], resolution=150)
    return path


@requires_display
def test_crops_are_new_pages_and_names_become_file_names(tmp_path):
    ctx, window, saved = build_app(tmp_path)
    try:
        doc = ctx.nav.get_page_widget("preview")
        ctx.nav.navigate_to("preview")
        doc.add_pages([a_pdf(str(tmp_path / "in.pdf"))])
        pump(2)
        assert len(ctx.scan.pages) == 2

        # two crops of page 1: two extra pages, in the order they were made, source untouched
        first = ctx.scan.pages[0]["path"]
        for box in ((0.15, 0.08, 0.85, 0.45), (0.2, 0.5, 0.8, 0.9)):
            doc.preview.select(0)
            pump(0.3)
            doc.apply_crop(*box)
            pump(1)
        assert [p.get("name") for p in ctx.scan.pages] == [None, "crop 1", "crop 2", None]
        assert ctx.scan.pages[0]["path"] == first, "the page a crop came from is not replaced"
        assert ctx.scan.pages[1]["crop_of"] == "Page 1"

        # a mixed document has no obvious file name; renaming every page gives it one
        doc.rename_page(2, "Invoice totals")
        pump(0.5)
        assert ctx.scan.pages[2]["name"] == "Invoice totals"
        assert doc.suggested_name(ctx.scan.pages) == ""
        assert doc.suggested_name([ctx.scan.pages[2]]) == "Invoice totals.pdf"

        # undo puts the name back, and undoing again removes the crop
        doc.undo()
        pump(0.5)
        assert ctx.scan.pages[2]["name"] == "crop 2"
        doc.undo()
        pump(0.5)
        assert [p.get("name") for p in ctx.scan.pages] == [None, "crop 1", None]

        doc.on_save()
        pump(2)
        assert [f for f in os.listdir(saved) if f.endswith(".pdf")], "the document was saved"
    finally:
        window.destroy()
        ctx.scan.cleanup()


@requires_display
def test_saved_page_searches_renames_and_previews(tmp_path):
    from modules.manager_documents import add_recent, recent_entries

    ctx, window, saved = build_app(tmp_path)
    try:
        one = a_pdf(os.path.join(saved, "Invoice 7.pdf"))
        two = a_pdf(os.path.join(saved, "Letter.pdf"))
        add_recent([one, two], 2, "pdf")
        page = ctx.nav.get_page_widget("recent")
        ctx.nav.navigate_to("recent")
        page.refresh()
        pump(1)
        assert len(page.store) == 2

        # search filters the list
        page.search.set_text("invoice")
        pump(0.5)
        assert [row[0] for row in page.store] and len(page.store) == 1
        page.search.set_text("nothing here")
        pump(0.5)
        assert len(page.store) == 0 and page.empty.get_visible()
        page.search.set_text("")
        pump(0.5)
        assert len(page.store) == 2

        # single click previews the selected document
        page.view.get_selection().select_path(page.store.get_path(page.store.get_iter_first()))
        pump(2)
        assert page._preview_pages, "the preview pane rendered the selected document"
        assert "page 1 of 2" in page.preview_title.get_text()

        # renaming the file name cell renames the file and follows it in the list
        row = next(i for i, r in enumerate(page.store) if r[-1] == one)
        page.on_rename(None, str(row), "Invoice seven")
        pump(1)
        new = os.path.join(saved, "Invoice seven.pdf")
        assert os.path.exists(new) and not os.path.exists(one)
        assert new in [e["path"] for e in recent_entries(existing_only=False)]

        # a name already taken is refused, and the file stays where it is
        row = next(i for i, r in enumerate(page.store) if r[-1] == new)
        page.on_rename(None, str(row), "Letter")
        pump(0.5)
        assert os.path.exists(new) and os.path.exists(two)
    finally:
        window.destroy()
        ctx.scan.cleanup()
