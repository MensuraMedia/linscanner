"""
Export Manager
Saves scanned pages (with their rotation applied) as PDF, PNG, JPEG or TIFF.
Multi-page formats (PDF, TIFF) get one file; single-page formats get one file
per page, numbered when there is more than one.
"""

import os

from PIL import Image

from config.config_scan import EXPORT_FORMATS, JPEG_QUALITY


def load_page(page):
    """Open a page image with its rotation applied (rotation is clockwise)"""
    img = Image.open(page["path"])
    img.load()
    if page.get("rotation"):
        img = img.rotate(-page["rotation"], expand=True)
    return img


def format_for_path(path):
    """Export format key from a filename's extension (None if unknown)"""
    ext = os.path.splitext(path)[1].lower()
    for key, fmt in EXPORT_FORMATS.items():
        if ext == fmt["ext"] or (key == "jpeg" and ext == ".jpeg") or (key == "tiff" and ext == ".tif"):
            return key
    return None


def export_pages(pages, path, fmt=None):
    """Write pages to path; returns the list of files written"""
    if not pages:
        raise ValueError("There are no pages to save.")
    fmt = fmt or format_for_path(path) or "pdf"
    spec = EXPORT_FORMATS[fmt]
    if not path.lower().endswith(spec["ext"]) and format_for_path(path) != fmt:
        path += spec["ext"]
    dpi = pages[0].get("dpi") or 300
    images = [load_page(p) for p in pages]

    if fmt == "pdf":
        # PDF pages must be RGB/L/1; resolution sets the physical page size
        converted = [im if im.mode in ("RGB", "L", "1") else im.convert("RGB") for im in images]
        converted[0].save(path, "PDF", save_all=True, append_images=converted[1:], resolution=dpi)
        return [path]
    if fmt == "tiff":
        images[0].save(
            path, "TIFF", save_all=True, append_images=images[1:], dpi=(dpi, dpi), compression="tiff_deflate"
        )
        return [path]

    written = []
    stem, ext = os.path.splitext(path)
    for n, im in enumerate(images, start=1):
        target = path if len(images) == 1 else f"{stem}-{n:03d}{ext}"
        if fmt == "jpeg":
            im = im if im.mode in ("RGB", "L") else im.convert("RGB")
            im.save(target, "JPEG", quality=JPEG_QUALITY, dpi=(dpi, dpi))
        else:
            im.save(target, "PNG", dpi=(dpi, dpi))
        written.append(target)
    return written
