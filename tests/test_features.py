"""Feature registry and every feature module"""

import json
import os
import shutil
import subprocess
import textwrap

import pytest
from PIL import Image, ImageDraw, ImageFont

from features import FeatureRegistry
from modules.manager_export import export_pages
from modules.manager_settings import SettingsManager
from utils.util_fonts import font_file

ALL = {
    "autocrop",
    "deskew",
    "autorotate",
    "batch_split",
    "blank_removal",
    "enhance",
    "ocr",
    "pdf_options",
    "autosave",
    "profiles",
    "quick_edit",
    "import_images",
}
ON_BY_DEFAULT = {"autocrop", "deskew", "blank_removal", "quick_edit", "import_images"}


@pytest.fixture
def settings(tmp_path):
    return SettingsManager(str(tmp_path / "s.json"))


def text_page(w=1275, h=1650, lines=30):
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(font_file("DejaVu Serif"), 28)
    for i in range(lines):
        d.text((110, 110 + i * 42), f"Invoice number {1000 + i} quick brown fox jumps", font=f, fill=0)
    return img


def save_page(tmp_path, img, name="p.png", dpi=150):
    path = str(tmp_path / name)
    img.save(path, dpi=(dpi, dpi))
    return {"path": path, "rotation": 0, "dpi": dpi, "mode": "Gray"}


# -- registry ---------------------------------------------------------------------
def test_registry_finds_all_modules_with_approved_defaults(settings):
    reg = FeatureRegistry(settings)
    assert {f.id for f in reg.features} == ALL and not reg.errors
    assert {f.id for f in reg.features if reg.is_enabled(f)} == ON_BY_DEFAULT


def test_disable_and_isolation_of_broken_or_deleted_features(settings, tmp_path):
    pkg = tmp_path / "features"
    shutil.copytree(os.path.join(os.path.dirname(__file__), "..", "src", "features"), pkg)
    os.remove(pkg / "feature_deskew.py")  # deleted feature: simply absent
    (pkg / "feature_broken.py").write_text("raise RuntimeError('boom at import')\n")
    (pkg / "feature_crashy.py").write_text(
        textwrap.dedent(
            """
            from features import BaseFeature
            class Feature(BaseFeature):
                id = "crashy"; default_enabled = True; order = 1
                def process_page(self, image, page):
                    raise ValueError("processor exploded")
            """
        )
    )
    reg = FeatureRegistry(settings, folder=str(pkg))
    ids = {f.id for f in reg.features}
    assert "deskew" not in ids and "crashy" in ids
    assert any(name == "feature_broken" for name, _ in reg.errors)
    img = text_page()
    out = reg.process_page(img, {})  # crashy fails, the rest still run
    assert out is not None and any(fid == "crashy" for fid, _ in reg.errors)
    reg.set_enabled("blank_removal", False)
    assert json.loads(open(settings.path).read())["features"]["blank_removal"] is False


# -- processors -------------------------------------------------------------------
def test_blank_removal_drops_blank_pages(settings):
    reg = FeatureRegistry(settings)
    assert reg.process_page(Image.new("L", (800, 1000), 252), {}) is None
    assert reg.process_page(text_page(), {}) is not None


def test_blank_pages_become_separators_when_batch_split_is_on(settings, tmp_path):
    reg = FeatureRegistry(settings)
    reg.set_enabled("batch_split", True)
    pages = []
    for n, img in enumerate([text_page(), text_page(), Image.new("L", (1275, 1650), 255), text_page()]):
        page = save_page(tmp_path, img, f"p{n}.png")
        assert reg.process_page(img, page) is not None  # kept (as separator if blank)
        pages.append(page)
    assert [p.get("separator", False) for p in pages] == [False, False, True, False]
    written = export_pages(pages, str(tmp_path / "batch.pdf"), registry=reg)
    assert [os.path.basename(w) for w in written] == ["batch-001.pdf", "batch-002.pdf"]
    counts = [
        int(
            subprocess.run(["pdfinfo", w], capture_output=True, text=True)
            .stdout.split("Pages:")[1]
            .split()[0]
        )
        for w in written
    ]
    assert counts == [2, 1]


def test_deskew_straightens(settings):
    from features.feature_deskew import find_skew

    tilted = text_page().rotate(2.5, fillcolor=255, resample=Image.BICUBIC)
    assert abs(find_skew(tilted) + 2.5) <= 0.25


def test_autocrop_trims_feeder_overrun_only(settings):
    from features.feature_autocrop import Feature

    crop = Feature(settings)
    long = Image.new("L", (1275, 2320), 235)
    long.paste(text_page(), (0, 0))
    assert crop.process_page(long, {}).height < 1700
    same = Image.new("L", (1275, 2320), 255)
    same.paste(text_page(), (0, 0))
    assert crop.process_page(same, {}).height == 2320  # can't tell overrun from paper: no guess
    assert crop.process_page(text_page(), {}).size == (1275, 1650)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_autorotate_turns_upside_down_page(settings):
    from features.feature_autorotate import Feature

    page = {}
    upright = Feature(settings).process_page(text_page().rotate(180), page)
    assert page.get("autorotated") == 180 and upright is not None


def test_enhance_whitens_background(settings):
    from features.feature_enhance import Feature

    grey_paper = Image.new("L", (400, 400), 232)
    assert Feature(settings).process_page(grey_paper, {}).getpixel((200, 200)) == 255


# -- export features ---------------------------------------------------------------
@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_ocr_makes_searchable_pdf(settings, tmp_path):
    reg = FeatureRegistry(settings)
    reg.set_enabled("ocr", True)
    page = save_page(tmp_path, text_page(), dpi=150)
    out = export_pages([page], str(tmp_path / "ocr.pdf"), registry=reg)[0]
    text = subprocess.run(["pdftotext", out, "-"], capture_output=True, text=True).stdout
    assert "Invoice" in text and "1005" in text


@pytest.mark.skipif(not shutil.which("gs"), reason="ghostscript not installed")
def test_pdfa_option(settings, tmp_path):
    reg = FeatureRegistry(settings)
    reg.set_enabled("pdf_options", True)
    out = export_pages([save_page(tmp_path, text_page())], str(tmp_path / "a.pdf"), registry=reg)[0]
    assert b"pdfaid" in open(out, "rb").read()  # PDF/A identification metadata


def test_autosave_template_and_save(settings, tmp_path):
    from datetime import datetime

    from features.feature_autosave import Feature, render_name
    from modules.app_context import AppContext

    pages = [save_page(tmp_path, text_page())]
    assert render_name("{date}-{n}-{pages}p", pages, datetime(2026, 9, 21), 7) == "2026-09-21-007-1p.pdf"
    feat = Feature(settings)
    feat.set_option("folder", str(tmp_path / "auto"))
    feat.set_option("template", "doc-{pages}")
    ctx = AppContext(settings, None, None, None)
    saved = []
    ctx.on("autosaved", saved.append)
    feat.after_scan(ctx, pages, final=True)
    assert os.path.exists(tmp_path / "auto" / "doc-1.pdf") and saved


def test_import_multipage_tiff(settings, tmp_path):
    from types import SimpleNamespace

    from features.feature_import_images import import_files

    tiff = str(tmp_path / "in.tiff")
    frames = [text_page(), Image.new("L", (1275, 1650), 200)]
    frames[0].save(tiff, save_all=True, append_images=frames[1:], dpi=(200, 200))
    ctx = SimpleNamespace(scan=SimpleNamespace(session_dir=str(tmp_path), pages=[]))
    assert import_files(ctx, [tiff, str(tmp_path / "not-an-image.txt")]) == 2
    assert ctx.scan.pages[0]["dpi"] == 200


# -- Quick Edit ---------------------------------------------------------------------
def signature_png(tmp_path, transparent=True):
    img = Image.new("RGBA", (300, 100), (255, 255, 255, 0 if transparent else 255))
    ImageDraw.Draw(img).line([(10, 80), (150, 20), (290, 70)], fill=(20, 20, 160, 255), width=8)
    path = str(tmp_path / ("sig.png" if transparent else "sig-white.png"))
    img.save(path)
    return path


def test_signature_import_and_clear_white(tmp_path, monkeypatch):
    from features.feature_quick_edit import has_transparency, import_signature, library

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert has_transparency(signature_png(tmp_path, True))
    opaque = signature_png(tmp_path, False)
    assert not has_transparency(opaque)
    cleared = import_signature(opaque, clear_white=True)
    assert has_transparency(cleared) and cleared in library()


def test_overlays_flatten_text_and_transparent_signature(tmp_path):
    from utils.util_imaging import flatten

    page = save_page(tmp_path, Image.new("RGB", (1275, 1650), "white"), dpi=150)
    page["overlays"] = [
        {
            "type": "text",
            "text": "APPROVED",
            "font": "DejaVu Sans",
            "size_pt": 24,
            "color": "#cc0000",
            "x": 0.1,
            "y": 0.1,
        },
        {"type": "image", "path": signature_png(tmp_path), "x": 0.5, "y": 0.8, "w": 0.3},
    ]
    out = flatten(page)
    assert out.size == (1275, 1650)
    region = out.crop((127, 165, 500, 240))  # the text area has red ink
    assert any(r > 150 and g < 80 for r, g, b in region.getdata())
    sig_w = int(0.3 * 1275)
    assert out.getpixel((int(0.5 * 1275) + 2, int(0.8 * 1650) + 2)) == (255, 255, 255)  # transparent corner
    inked = out.crop((int(0.5 * 1275), int(0.8 * 1650), int(0.5 * 1275) + sig_w, int(0.8 * 1650) + 128))
    assert any(b > 120 and r < 80 for r, g, b in inked.getdata())  # blue signature ink


def test_colourful_pages_are_not_blank_but_coloured_paper_is():
    from utils.util_imaging import is_blank

    stripes = Image.new("RGB", (800, 1000), (120, 120, 120))
    d = ImageDraw.Draw(stripes)
    for i, colour in enumerate([(200, 30, 30), (30, 160, 30), (30, 30, 200), (230, 230, 40)] * 10):
        d.rectangle([0, i * 25, 800, i * 25 + 12], fill=colour)
    assert not is_blank(stripes)  # regression: SANE's colour test pattern was dropped
    assert is_blank(Image.new("RGB", (800, 1000), (250, 240, 200)))  # blank cream paper
    photo_like = Image.linear_gradient("L").resize((800, 1000)).convert("RGB")
    assert not is_blank(photo_like)
