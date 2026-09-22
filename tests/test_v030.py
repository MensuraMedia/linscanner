"""0.3.0: alignment guides, signature library and fonts, display cache, Recent and
opening documents, the remembered scanner, and the new editor / preview behaviour"""

import os
import shutil
import time
import zipfile

import pytest
from PIL import Image, ImageDraw

from conftest import requires_display, requires_sane


# -- alignment guides -------------------------------------------------------------------
def test_guides_align_left_edges_and_let_go_beyond_threshold():
    from utils.util_guides import Box, snap

    others = [Box(0.12, 0.10, 0.3, 0.02)]
    left, top, guides = snap(Box(0.123, 0.5, 0.1, 0.02), others, 0.005, 0.005)
    assert left == pytest.approx(0.12) and any(g.axis == "v" and g.kind == "align" for g in guides)
    left, _top, guides = snap(Box(0.2, 0.5, 0.1, 0.02), others, 0.005, 0.005)  # far away: free
    assert left == pytest.approx(0.2) and not [g for g in guides if g.axis == "v"]


def test_guides_equal_spacing_mirror_and_centre():
    from utils.util_guides import Box, snap

    rows = [Box(0.1, 0.10, 0.2, 0.02), Box(0.1, 0.14, 0.2, 0.02)]
    _l, top, guides = snap(Box(0.6, 0.182, 0.2, 0.02), rows, 0.004, 0.004)
    assert top == pytest.approx(0.18) and any(g.kind == "spacing" for g in guides)
    # mirror: an item on the right mirroring one on the left (symmetry about the centre)
    left, _t, guides = snap(Box(0.698, 0.5, 0.2, 0.02), [Box(0.1, 0.1, 0.2, 0.02)], 0.004, 0.001)
    assert left == pytest.approx(0.7) and any(g.kind == "mirror" for g in guides)
    left, _t, _g = snap(Box(0.401, 0.5, 0.2, 0.02), [], 0.004, 0.004)  # centred on the page
    assert left == pytest.approx(0.4)


# -- signatures and fonts ---------------------------------------------------------------------
def test_bundled_signature_fonts_have_credits_and_licence():
    from utils.util_fonts import bundled_signature_fonts

    fonts = bundled_signature_fonts()
    assert len(fonts) == 9
    for f in fonts:
        assert os.path.exists(f["path"]) and f["designer"] and f["license"] == "SIL Open Font License 1.1"
        assert os.path.exists(os.path.join(os.path.dirname(f["path"]), "OFL.txt"))


def test_import_fonts_from_zip_only_takes_fonts(tmp_path):
    from utils.util_fonts import bundled_signature_fonts, import_fonts, signature_fonts, user_signature_fonts

    src = bundled_signature_fonts()[0]["path"]
    z = tmp_path / "fonts.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(src, "My Font/MyFont.ttf")
        zf.writestr("readme.txt", "not a font")
        zf.writestr("bad.ttf", "not really a font")
    added = import_fonts([str(z)])
    assert added == [bundled_signature_fonts()[0]["family"]]
    assert [os.path.basename(f["path"]) for f in user_signature_fonts()] == ["MyFont.ttf"]
    assert len(signature_fonts()) == 9  # same family as a bundled one: listed once


def test_render_text_offsets_keep_script_fonts_on_the_page():
    from utils.util_fonts import bundled_signature_fonts, render_text

    img, dx, dy = render_text("Jane A. Doe", bundled_signature_fonts()[0]["family"], 80, "#000000")
    assert img.mode == "RGBA" and img.getchannel("A").getbbox() is not None
    assert dx <= 0 and dy <= 0


def test_signature_library_holds_four(tmp_path):
    from utils.util_signatures import MAX_SIGNATURES, LibraryFull, library, save_signature, typed_signature

    img = typed_signature("Jane A. Doe", "Great Vibes")
    assert img.getchannel("A").getextrema()[0] == 0  # transparent background
    for n in range(MAX_SIGNATURES):
        save_signature(img, f"sig {n}")
    assert len(library()) == 4
    with pytest.raises(LibraryFull):
        save_signature(img, "fifth")
    once = save_signature(img, "one-off", folder=str(tmp_path))  # "Place on page" without a slot
    assert os.path.exists(once) and len(library()) == 4


def test_flatten_uses_signature_fonts_for_text(tmp_path):
    from utils.util_imaging import flatten

    path = str(tmp_path / "p.png")
    Image.new("RGB", (1275, 1650), "white").save(path)
    page = {"path": path, "rotation": 0, "dpi": 150, "mode": "Color"}
    page["overlays"] = [
        {
            "type": "text",
            "text": "Jane",
            "font": "Great Vibes",
            "size_pt": 40,
            "color": "#000080",
            "x": 0.0,
            "y": 0.0,
        }
    ]
    out = flatten(page)
    assert out.size == (1275, 1650) and out.convert("L").getextrema()[0] < 100  # ink drawn at the edge


# -- display cache --------------------------------------------------------------------------
def test_display_cache_proxy_render_and_keys(tmp_path):
    from utils.util_display import PROXY_MAX_SIDE, DisplayCache, page_key

    path = str(tmp_path / "big.png")
    img = Image.new("RGB", (5100, 6600), "white")
    ImageDraw.Draw(img).rectangle([100, 100, 1000, 400], fill="black")
    img.save(path)
    cache = DisplayCache(str(tmp_path / "display"))
    proxy, factor = cache.proxy(path)
    with Image.open(proxy) as p:
        assert max(p.size) <= PROXY_MAX_SIDE and factor == 3
    page = {"path": path, "rotation": 90, "dpi": 600, "mode": "Color"}
    out = cache.render(page, 400, 400)
    assert out.size[0] > out.size[1]  # rotated: landscape
    assert cache.proxy(path)[0] == proxy  # reused
    key = page_key(page)
    page["rotation"] = 180
    assert page_key(page) != key


# -- recent and opening documents -----------------------------------------------------------
def test_recent_list_order_dedupe_forget(tmp_path):
    from modules.manager_documents import add_recent, clear_recent, forget_recent, recent_entries

    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"%PDF")
    b.write_bytes(b"%PDF")
    add_recent([str(a)], 2, "pdf")
    add_recent([str(b)], 1, "pdf")
    add_recent([str(a)], 3, "pdf")  # re-saved: moves to the top, no duplicate
    assert [os.path.basename(e["path"]) for e in recent_entries()] == ["a.pdf", "b.pdf"]
    b.unlink()
    assert [os.path.basename(e["path"]) for e in recent_entries()] == ["a.pdf"]  # missing files hidden
    forget_recent(str(a))
    assert recent_entries() == []
    add_recent([str(a)], 1, "pdf")
    clear_recent()
    assert recent_entries() == []


def test_export_records_recent(tmp_path):
    from modules.manager_documents import recent_entries
    from modules.manager_export import export_pages

    path = str(tmp_path / "p.png")
    Image.new("RGB", (300, 400), "white").save(path)
    out = export_pages([{"path": path, "rotation": 0, "dpi": 100, "mode": "Gray"}], str(tmp_path / "doc.pdf"))
    assert recent_entries()[0]["path"] == os.path.abspath(out[0])


@pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript not installed")
def test_open_pdf_and_multipage_tiff(tmp_path):
    from modules.manager_documents import open_document

    frames = [Image.new("RGB", (850, 1100), c) for c in ("white", "lightgray", "white")]
    pdf = str(tmp_path / "three.pdf")
    frames[0].save(pdf, "PDF", save_all=True, append_images=frames[1:], resolution=100)
    pages = open_document(pdf, str(tmp_path))
    assert len(pages) == 3 and pages[0]["dpi"] == 300
    with Image.open(pages[0]["path"]) as im:
        assert im.size == (2550, 3300)  # 8.5 x 11 in at 300 dpi
    tif = str(tmp_path / "two.tif")
    frames[0].save(tif, save_all=True, append_images=frames[1:2])
    assert len(open_document(tif, str(tmp_path))) == 2
    with pytest.raises(ValueError):
        open_document(str(tmp_path / "missing.pdf"), str(tmp_path))


# -- remembered scanner ----------------------------------------------------------------------------
def _pump_until(cond, timeout=60):
    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        if cond():
            return True
        time.sleep(0.02)
    return False


@requires_sane
def test_remember_and_restore_scanner(tmp_path):
    from backends.backend_sane import SaneBackend
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager

    settings = SettingsManager(str(tmp_path / "s.json"))
    scan = ScanManager(settings, SaneBackend(only_backends=["test"]))
    result = {}
    scan.refresh_devices(lambda d: result.setdefault("found", d), lambda e: result.setdefault("err", e))
    assert _pump_until(lambda: result)
    physical = scan.physical("test:0")
    scan.remember_device(physical)
    assert settings.get("last_device_info")["methods"][0]["id"] == "test:0"

    fresh = ScanManager(SettingsManager(str(tmp_path / "s.json")), SaneBackend(only_backends=["test"]))
    got = {}
    fresh.restore_device(lambda d: got.setdefault("ok", d), lambda e: got.setdefault("err", e))
    assert _pump_until(lambda: got)
    assert "ok" in got and got["ok"][0].restored and "test:0" in fresh.capabilities

    info = settings.get("last_device_info")
    info["methods"][0]["id"] = "test:99"  # the scanner is gone
    settings.set("last_device_info", info)
    gone = ScanManager(SettingsManager(str(tmp_path / "s.json")), SaneBackend(only_backends=["test"]))
    got = {}
    gone.restore_device(lambda d: got.setdefault("ok", d), lambda e: got.setdefault("err", e))
    assert _pump_until(lambda: got) and "err" in got
    for m in (scan, fresh, gone):
        m.cleanup()


# -- editor and preview behaviour --------------------------------------------------------------------
def _pages(tmp_path, n=4):
    pages = []
    for i in range(n):
        path = str(tmp_path / f"page-{i}.png")
        Image.new("RGB", (850, 1100), (255, 255 - i * 20, 255)).save(path)
        pages.append({"path": path, "rotation": 0, "dpi": 100, "mode": "Color"})
    return pages


class _Ctx:
    """Just enough app context for the editor"""

    def __init__(self, tmp_path):
        self.window = None
        self.scan = type("S", (), {"session_dir": str(tmp_path)})()


@requires_display
def test_quick_edit_click_and_type_with_new_line(tmp_path):
    from features.feature_quick_edit import QuickEditor

    pages = _pages(tmp_path, 1)
    ed = QuickEditor(_Ctx(tmp_path), pages, 0)
    _pump_until(lambda: ed.canvas.get_allocated_width() > 1, 5)
    ed.set_mode("text")
    assert ed.text_tool.get_active()
    item = ed.new_text_item(0.1, 0.1)
    ed.start_editing(item)
    ed.type_text("Invoice ")
    ed.type_text("42")
    ed.new_line()  # Enter: next line, same left edge, below
    second = ed.editing
    assert item["text"] == "Invoice 42" and second["x"] == item["x"] and second["y"] > item["y"]
    ed.finish_editing()  # the empty second line disappears
    assert second not in ed.items
    ed.set_mode("select")
    assert not ed.text_tool.get_active()
    ed.commit()
    ed.dialog.destroy()
    assert [o["text"] for o in pages[0]["overlays"]] == ["Invoice 42"]


@requires_display
def test_preview_select_rows_and_zoom(tmp_path):
    from ui.components.component_preview import PagePreview

    pages = _pages(tmp_path, 5)
    chosen = []
    pv = PagePreview(on_select=chosen.append, cache_dir=str(tmp_path / "display"), rows=1)
    pv.set_pages(pages, selected=0)
    first = pv._buttons[0]
    pv.select(3)
    assert chosen == [3] and pv._buttons[0] is first  # nothing rebuilt
    assert pv._buttons[3].get_style_context().has_class("selected")
    assert not first.get_style_context().has_class("selected")
    pv.set_rows(2)
    assert pv.strip.child_get_property(pv._buttons[3], "top-attach") == 1  # column-major, 2 rows
    assert pv.strip.child_get_property(pv._buttons[3], "left-attach") == 1
    pv.zoom_in()
    assert pv.zoom > 1
    pv.zoom_fit()
    assert pv.zoom == 1.0
