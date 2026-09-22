"""0.3.0 refinements (docs/design/0.3.0-ui-refinements.md): Scan Type, paper sizes and
Auto-Detect, icons, Quick Edit Apply Signature and pointer zones, Recent table"""

import json
import os
from datetime import datetime, timedelta

import numpy as np
import pytest
from PIL import Image, ImageDraw

from conftest import requires_display


# -- Scan Type ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sources, expected",
    [
        (["ADF Front", "ADF Duplex"], {"front": "ADF Front", "both": "ADF Duplex"}),  # ES-400 II
        (["Flatbed"], {"front": "Flatbed"}),
        (
            ["Flatbed", "Automatic Document Feeder"],
            {"front": "Automatic Document Feeder", "flatbed": "Flatbed"},
        ),
        (
            ["Flatbed", "ADF", "ADF Duplex"],
            {"front": "ADF", "both": "ADF Duplex", "flatbed": "Flatbed"},
        ),
        (["ADF Duplex"], {"front": "ADF Duplex"}),
    ],
)
def test_scan_types(sources, expected):
    from modules.manager_scan import scan_types

    assert scan_types(sources) == expected


# -- paper sizes and Auto-Detect -------------------------------------------------------------
def test_paper_sizes_groups_and_detect():
    from config.config_scan import DEFAULT_PAPER, PAPER_SIZES
    from modules.manager_scan import paper_spec, pick_area
    from backends.backend_base import ScannerCapabilities

    assert DEFAULT_PAPER == "auto_detect" and PAPER_SIZES["auto_detect"]["detect"]
    groups = {s.get("group") for s in PAPER_SIZES.values()}
    assert {"Documents", "Receipts", "Cards", "Photos", "Other"} <= groups
    caps = ScannerCapabilities(max_width_mm=215.9, max_height_mm=393.7)
    assert pick_area(caps, "receipt_80") == (0.0, 0.0)  # scan everything, then fit to the paper
    assert pick_area(caps, "legal") == (215.9, 355.6)
    assert paper_spec("removed-size") is PAPER_SIZES["auto_detect"]


def _scan_like(paper_box, size=(1275, 2362), background=(40, 40, 40), paper=(250, 250, 248)):
    """A 150 dpi 'full area' scan: dark feeder background with a paper rectangle and some text"""
    img = Image.new("RGB", size, background)
    d = ImageDraw.Draw(img)
    d.rectangle(paper_box, fill=paper)
    x0, y0, x1, y1 = paper_box
    for n in range(5):
        d.rectangle([x0 + 20, y0 + 40 + n * 40, x1 - 20, y0 + 52 + n * 40], fill=(20, 20, 20))
    return img


def test_content_box_finds_a_receipt():
    from utils.util_autodetect import content_box

    receipt = (480, 0, 480 + 472, 1400)  # 80 mm wide at 150 dpi, centred, 237 mm long
    box = content_box(_scan_like(receipt), dpi=150)
    assert box is not None
    left, top, right, bottom = box
    assert abs(left - 480) < 20 and abs(right - 952) < 20 and bottom < 1440


def test_content_box_same_colour_background_is_kept():
    from utils.util_autodetect import content_box, detect_crop

    img = _scan_like((100, 0, 1175, 1650), background=(250, 250, 248))  # white on white
    assert content_box(img, dpi=150) is None
    cropped, how = detect_crop(img, 150, (85.6, 54.0))  # a card: nominal size, centred, from the top
    assert how == "nominal" and cropped.size == (506, 319)
    kept, how = detect_crop(img, 150)
    assert how == "kept" and kept.size == img.size


def test_detect_page_crops_the_file(tmp_path):
    from modules.manager_scan import ScanManager
    from modules.manager_settings import SettingsManager

    path = str(tmp_path / "page.png")
    _scan_like((100, 0, 1175, 1650)).save(path)
    page = {"path": path, "rotation": 0, "dpi": 150, "mode": "Color"}
    ScanManager(SettingsManager(str(tmp_path / "s.json")), backend=object()).detect_page(page)
    with Image.open(path) as im:
        assert page["auto_detected"] == "detected" and im.size[1] < 1700 and im.size[0] < 1150


def test_auto_size_driver_option():
    from backends.backend_base import ScanRequest, ScannerCapabilities
    from backends.backend_sane import SaneBackend
    from modules.manager_scan import auto_size_args

    caps = ScannerCapabilities(options={"adf-crp": {}, "resolution": {}})
    assert auto_size_args(caps) == ["--adf-crp=yes"]
    assert auto_size_args(ScannerCapabilities()) == []
    cmd = SaneBackend(only_backends=["test"]).build_command(
        ScanRequest("epsonds:libusb:003:102", "/tmp", extra_args=["--adf-crp=yes"])
    )
    assert "--adf-crp=yes" in cmd


# -- icons ------------------------------------------------------------------------------------
@requires_display
def test_icons_recolour_and_cache():
    from utils import util_icons

    for name in ("folder-open", "file-text", "trash", "signature", "pencil-simple"):
        assert os.path.exists(util_icons.icon_path(name)), name
    a = util_icons.icon_pixbuf("trash", 20, "#ff0000")
    assert a.get_width() == 20 and util_icons.icon_pixbuf("trash", 20, "#ff0000") is a
    px = np.frombuffer(a.get_pixels(), dtype=np.uint8).reshape(a.get_height(), a.get_rowstride())
    rgba = px[:, : 20 * 4].reshape(20, 20, 4)
    ink = rgba[rgba[:, :, 3] > 200]
    assert len(ink) and (ink[:, 0] > 200).all() and (ink[:, 1] < 60).all()  # drawn in red
    assert util_icons.icon_pixbuf("no-such-icon") is None


# -- Quick Edit ---------------------------------------------------------------------------------
class _Settings(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def set(self, key, value):
        self[key] = value


class _Ctx:
    def __init__(self, tmp_path):
        self.window = None
        self.settings = _Settings()
        self.scan = type("S", (), {"session_dir": str(tmp_path)})()


def _page(tmp_path):
    path = str(tmp_path / "p.png")
    Image.new("RGB", (850, 1100), "white").save(path)
    return [{"path": path, "rotation": 0, "dpi": 100, "mode": "Color"}]


@requires_display
def test_pointer_zones_and_cursors(tmp_path):
    from features.feature_quick_edit import QuickEditor

    ed = QuickEditor(_Ctx(tmp_path), _page(tmp_path), 0)
    item = ed.new_text_item(0.2, 0.2, "Hello there")
    x, y, w, h = ed._bbox(item)
    assert ed._hit(x + w / 2, y + h / 2) == (item, "inside")
    assert ed._hit(x - 3, y + h / 2) == (item, "frame")
    assert ed._hit(x - 30, y - 30) == (None, None)
    assert ed.cursor_for(item, "inside", "select") == "text"
    assert ed.cursor_for(item, "frame", "select") == "grab"
    assert ed.cursor_for(item, "resize", "select") == "nwse-resize"
    assert ed.cursor_for(None, None, "text") == "text"
    assert ed.cursor_for(None, None, "place") == "crosshair"
    sig = {"type": "image", "path": "x.png", "x": 0, "y": 0, "w": 0.1}
    assert ed.cursor_for(sig, "inside", "select") == "grab"  # signatures move from anywhere
    ed.dialog.destroy()


@requires_display
def test_apply_signature_flow(tmp_path, monkeypatch):
    from features import feature_quick_edit as qe
    from utils.util_signatures import save_signature, typed_signature

    ed = qe.QuickEditor(_Ctx(tmp_path), _page(tmp_path), 0)
    opened = []
    monkeypatch.setattr(ed, "open_signature_chooser", lambda: opened.append(True))
    ed.apply_signature()  # nothing chosen yet: the chooser opens
    assert opened and ed.mode == "select"
    path = save_signature(typed_signature("Jane Doe", "Sacramento"), "jane")
    ed.signature_chosen(path)  # picked in the chooser: current + armed
    assert ed.ctx.settings["current_signature"] == path and ed.mode == "place"
    ed.set_mode("select")
    ed.apply_signature()  # now Apply Signature places it directly
    assert ed.mode == "place" and ed.pending_signature == path
    ed.signature_removed(path)
    assert not os.path.exists(path) and ed.current_signature() is None and ed.mode == "select"
    ed.dialog.destroy()


# -- Recent -------------------------------------------------------------------------------------
def _write_recent(entries):
    from modules.manager_documents import recent_path

    with open(recent_path(), "w") as f:
        json.dump(entries, f)


def test_clear_recent_older_than(tmp_path):
    from modules.manager_documents import clear_recent, recent_entries

    now = datetime.now()
    files = []
    for days in (1, 7, 15, 40):
        p = tmp_path / f"d{days}.pdf"
        p.write_bytes(b"%PDF")
        files.append(
            {
                "path": str(p),
                "saved_at": (now - timedelta(days=days)).isoformat(),
                "pages": 1,
                "format": "pdf",
            }
        )
    _write_recent(list(reversed(files)))  # stored oldest first
    assert [os.path.basename(e["path"]) for e in recent_entries()] == [
        "d1.pdf",
        "d7.pdf",
        "d15.pdf",
        "d40.pdf",
    ]
    assert clear_recent(10) == 2
    assert [os.path.basename(e["path"]) for e in recent_entries()] == ["d1.pdf", "d7.pdf"]
    assert clear_recent(5) == 1 and clear_recent() == 1 and recent_entries() == []


@requires_display
def test_recent_table_sorted_and_trash(tmp_path):
    from modules.app_context import AppContext
    from modules.manager_navigation import NavigationManager
    from pages.page_recent import C_NAME, C_PATH, RecentPage

    now = datetime.now()
    entries = []
    for n, days in enumerate((3, 1, 2)):
        p = tmp_path / f"f{n}.pdf"
        p.write_bytes(b"%PDF")
        entries.append(
            {
                "path": str(p),
                "saved_at": (now - timedelta(days=days)).isoformat(),
                "pages": 1,
                "format": "pdf",
            }
        )
    _write_recent(entries)
    ctx = AppContext(None, None, NavigationManager(), None)
    page = RecentPage(ctx)
    names = [row[C_NAME] for row in page.store]
    assert names == ["f1.pdf", "f2.pdf", "f0.pdf"]  # newest first
    page.forget(page.store[0][C_PATH])
    assert [row[C_NAME] for row in page.store] == ["f2.pdf", "f0.pdf"]
    assert os.path.exists(tmp_path / "f1.pdf")  # the file itself is kept


# -- 0.3.1 polish (docs/design/0.3.1-ui-polish.md) --------------------------------------------
@requires_display
def test_uniform_segment_width_and_app_icon():
    from gi.repository import Gtk

    from ui.app_window import ICON_SIZES, set_app_icon
    from ui.components.component_segmented import SegmentedControl

    seg = SegmentedControl([("a", "A"), ("b", "A much longer label")], button_width=150)
    assert all(b.get_size_request()[0] == 150 for b in seg.buttons.values())
    set_app_icon()
    icons = Gtk.Window.get_default_icon_list()
    assert sorted(i.get_width() for i in icons) == sorted(ICON_SIZES)


def test_phosphor_icons_bundled_with_licence():
    from utils.util_icons import icon_path
    from utils.util_paths import resource

    for name in (
        "arrow-counter-clockwise",
        "arrow-clockwise",
        "arrows-clockwise",
        "file-x",
        "trash-simple",
        "arrow-left",
        "arrow-right",
        "check",
    ):
        assert os.path.exists(icon_path(name)), name
    assert "Phosphor Icons" in open(resource("icons", "phosphor", "LICENSE")).read()
    assert not os.path.exists(resource("icons", "heroicons"))
