"""0.3.3 (docs/design/0.3.3-scan-flow-text-styling.md): styled text runs, text editing,
signature-only resizing, default save location"""

import os

from PIL import Image

from conftest import requires_display


def R(text, font="DejaVu Sans", size=14.0, color="#000000"):
    return {"text": text, "font": font, "size_pt": size, "color": color}


def test_runs_restyle_insert_delete():
    from utils.util_textruns import delete, insert, plain, restyle, runs_of, style_at, word_at

    runs = [R("Hello brave world")]
    styled = restyle(runs, 6, 11, size_pt=28.0, font="Great Vibes")
    assert [(r["text"], r["size_pt"]) for r in styled] == [
        ("Hello ", 14.0),
        ("brave", 28.0),
        (" world", 14.0),
    ]
    assert style_at(styled, 8)["font"] == "Great Vibes"
    typed = insert(styled, 11, "st")  # continues the style before the caret
    assert plain(typed) == "Hello bravest world" and typed[1]["text"] == "bravest"
    assert plain(delete(typed, 5, 13)) == "Hello world"
    assert restyle(restyle(runs, 0, 5, color="#ff0000"), 0, 5, color="#000000") == runs  # merged back
    assert word_at("Hello brave world", 8) == (6, 11)
    legacy = {"type": "text", "text": "Old", "font": "DejaVu Serif", "size_pt": 12, "color": "#123456"}
    assert runs_of(legacy) == [R("Old", "DejaVu Serif", 12, "#123456")]
    emptied = delete([R("abc", size=30.0)], 0, 3)
    assert plain(emptied) == "" and emptied[0]["size_pt"] == 30.0  # keeps the style for new typing


def test_render_runs_widths_follow_sizes():
    from utils.util_fonts import layout_runs, render_runs

    small, *_ = layout_runs([R("Size")], 300 / 72)
    mixed_w, line, baseline, xs = layout_runs([R("Si"), R("ze", size=28.0)], 300 / 72)
    assert mixed_w > small and len(xs) == 5 and xs == sorted(xs) and line > baseline > 0
    img, dx, dy = render_runs([R("Si"), R("ze", size=28.0, color="#ff0000")], 300 / 72)
    reds = [p for p in img.getdata() if p[3] > 200 and p[0] > 200 and p[1] < 80]
    assert reds and dx <= 0 and dy <= 0


def test_flatten_draws_runs(tmp_path):
    from utils.util_imaging import flatten

    path = str(tmp_path / "p.png")
    Image.new("RGB", (1275, 1650), "white").save(path)
    page = {"path": path, "rotation": 0, "dpi": 150, "mode": "Color"}
    page["overlays"] = [
        {"type": "text", "x": 0.1, "y": 0.1, "runs": [R("Paid", color="#ff0000"), R(" in full")]}
    ]
    out = flatten(page).convert("RGB")
    assert any(r > 200 and g < 80 for r, g, b in out.crop((100, 150, 400, 260)).getdata())


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
def test_editor_highlight_and_restyle(tmp_path):
    from features.feature_quick_edit import QuickEditor

    ed = QuickEditor(_Ctx(tmp_path), _page(tmp_path), 0)
    item = ed.new_text_item(0.1, 0.1, "Invoice paid today")
    ed.start_editing(item, caret=8)
    ed.select_range(8, 12)  # "paid"
    ed.size_spin.set_value(30)  # the panel change restyles only the highlight
    assert [(r["text"], r["size_pt"]) for r in item["runs"]] == [
        ("Invoice ", 14.0),
        ("paid", 30.0),
        (" today", 14.0),
    ]
    ed.type_text("PAID")  # typing replaces the highlight, in its style
    assert item["text"] == "Invoice PAID today" and item["runs"][1] == dict(
        item["runs"][1], text="PAID", size_pt=30.0
    )
    ed.move_caret(len(item["text"]))
    ed.backspace()
    assert item["text"].endswith("toda")
    ed.select_range(0, 0)
    ed.anchor = None
    ed.color_btn.get_rgba()
    x, y, w, h = ed._bbox(item)
    assert ed._hit(x + w - 1, y + h - 1)[1] == "inside"  # no resize corner on text
    ed.finish_editing()
    ed.selected = item
    assert ed._hit(x + w + 2, y + h + 2)[1] == "frame"  # (the old corner square is now just the frame)
    ed.commit()
    ed.dialog.destroy()


@requires_display
def test_signature_still_resizes(tmp_path):
    from features.feature_quick_edit import QuickEditor
    from utils.util_signatures import save_signature, typed_signature

    ed = QuickEditor(_Ctx(tmp_path), _page(tmp_path), 0)
    sig = ed.place_signature(save_signature(typed_signature("Jane", "Great Vibes"), "j"), 0.3, 0.3)
    x, y, w, h = ed._bbox(sig)
    assert ed._hit(x + w + 1, y + h + 1)[1] == "resize"
    ed.dialog.destroy()


def test_default_save_location_is_kept(tmp_path):
    from modules.manager_settings import SettingsManager

    settings = SettingsManager(str(tmp_path / "s.json"))
    settings.set("save_folder", str(tmp_path / "default"))
    os.makedirs(tmp_path / "elsewhere")
    # what PreviewPage._write does after saving to another folder: the default must not change
    from pages import page_preview

    src = open(page_preview.__file__).read()
    assert 'settings.set("save_folder"' not in src
    assert SettingsManager(str(tmp_path / "s.json")).get("save_folder") == str(tmp_path / "default")


def test_single_page_duplex_keeps_each_sheets_sides_together(tmp_path):
    """Front & Back + Single Page: pages 1-2 are document A, 3-4 document B, ..."""
    import time

    from gi.repository import GLib

    from backends.backend_base import ScanRequest
    from modules.manager_scan import MAIN_DOC, ScanManager
    from modules.manager_settings import SettingsManager

    class FakeFeeder:
        name = "fake"

        def scan(self, request, on_page, on_progress, cancel):
            paths = []
            for n in range(6):  # 3 sheets, front + back
                path = str(tmp_path / f"p{n}.png")
                Image.new("RGB", (100, 140), "white").save(path)
                on_page(path)
                paths.append(path)
            return paths

    scan = ScanManager(SettingsManager(str(tmp_path / "s.json")), backend=FakeFeeder())
    done = []
    req = ScanRequest("fake:0", str(tmp_path), "ADF Duplex", multi_page=True, separate=True, sheet_pages=2)
    scan.start_scan(
        req, lambda p: None, lambda p: None, lambda r, c: done.append(r), lambda e: done.append(e)
    )
    ctx = GLib.MainContext.default()
    end = time.monotonic() + 10
    while not done and time.monotonic() < end:
        ctx.iteration(False)
    docs = [p["doc"] for p in scan.pages]
    assert len(docs) == 6 and docs[0] == docs[1] != docs[2] == docs[3] != docs[4] == docs[5]
    assert MAIN_DOC not in docs and len(scan.doc_ids()) == 3
    assert scan.next_doc == docs[-1] + 1  # the next job continues after these sheets
    scan.cleanup()
