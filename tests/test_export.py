"""Saving pages as PDF / TIFF / PNG / JPEG"""

from PIL import Image

from modules.manager_export import export_pages, format_for_path


def make_pages(tmp_path, n=2, size=(200, 300), mode="RGB"):
    pages = []
    for i in range(n):
        p = tmp_path / f"p{i}.png"
        Image.new(mode, size, "white" if mode != "1" else 1).save(p)
        pages.append({"path": str(p), "rotation": 0, "dpi": 150, "mode": "Color"})
    return pages


def test_pdf_multi_page(tmp_path):
    pages = make_pages(tmp_path, 3)
    out = export_pages(pages, str(tmp_path / "doc.pdf"))
    data = open(out[0], "rb").read()
    assert out == [str(tmp_path / "doc.pdf")] and data.startswith(b"%PDF")
    assert b"/Count 3" in data  # page tree holds all three pages


def test_rotation_applied(tmp_path):
    pages = make_pages(tmp_path, 1, size=(200, 300))
    pages[0]["rotation"] = 90
    out = export_pages(pages, str(tmp_path / "rot.png"))
    assert Image.open(out[0]).size == (300, 200)


def test_single_page_formats_number_multiple_pages(tmp_path):
    out = export_pages(make_pages(tmp_path, 2), str(tmp_path / "scan.jpg"))
    assert [p.split("/")[-1] for p in out] == ["scan-001.jpg", "scan-002.jpg"]


def test_tiff_multi_page_and_grayscale(tmp_path):
    out = export_pages(make_pages(tmp_path, 2, mode="L"), str(tmp_path / "scan.tiff"))
    img = Image.open(out[0])
    assert img.n_frames == 2


def test_extension_added_and_detected(tmp_path):
    out = export_pages(make_pages(tmp_path, 1), str(tmp_path / "noext"), "pdf")
    assert out[0].endswith(".pdf")
    assert format_for_path("a.JPEG") == "jpeg" and format_for_path("a.tif") == "tiff"


def test_no_pages_rejected(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        export_pages([], str(tmp_path / "x.pdf"))
