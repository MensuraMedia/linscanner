"""
Export Manager
Saves scanned pages (with their rotation applied) as PDF, PNG, JPEG or TIFF.
Multi-page formats (PDF, TIFF) get one file; single-page formats get one file
per page, numbered when there is more than one.
"""

import os
import time


from config.config_scan import EXPORT_FORMATS, JPEG_QUALITY
from utils.util_imaging import flatten
from utils.util_logging import get_logger

log = get_logger("export")


def load_page(page):
    """Open a page image with its rotation and Quick Edit overlays applied"""
    return flatten(page)


def format_for_path(path):
    """Export format key from a filename's extension (None if unknown)"""
    ext = os.path.splitext(path)[1].lower()
    for key, fmt in EXPORT_FORMATS.items():
        if ext == fmt["ext"] or (key == "jpeg" and ext == ".jpeg") or (key == "tiff" and ext == ".tif"):
            return key
    return None


def export_pages(pages, path, fmt=None, registry=None):
    """Write pages to path; returns the list of files written.

    registry (FeatureRegistry, optional) may split the pages into several
    documents (numbered files), write the PDF itself (OCR) and post-process it."""
    if not pages:
        raise ValueError("There are no pages to save.")
    fmt = fmt or format_for_path(path) or "pdf"
    spec = EXPORT_FORMATS[fmt]
    if not path.lower().endswith(spec["ext"]) and format_for_path(path) != fmt:
        path += spec["ext"]
    docs = registry.split_documents(pages) if registry else [[p for p in pages if not p.get("separator")]]
    docs = [d for d in docs if d]
    overlays = sum(len(p.get("overlays") or []) for p in pages)
    log.info(
        "export %s: %d page(s) -> %d document(s), %d Quick Edit item(s), to %s",
        fmt,
        len(pages),
        len(docs),
        overlays,
        path,
    )
    if not docs:
        log.warning("export aborted: every page was a blank separator")
        raise ValueError("Every page was a blank separator: nothing to save.")
    start = time.monotonic()
    try:
        if len(docs) == 1:
            written = _export_document(docs[0], path, fmt, registry)
        else:
            stem, ext = os.path.splitext(path)
            written = []
            for n, doc in enumerate(docs, start=1):
                written += _export_document(doc, f"{stem}-{n:03d}{ext}", fmt, registry)
    except Exception:
        log.exception("export failed")
        raise
    sizes = ", ".join(
        f"{os.path.basename(w)} ({os.path.getsize(w) // 1024} KB)" for w in written if os.path.exists(w)
    )
    log.info("export done in %.1f s: %s", time.monotonic() - start, sizes)
    return written


def _export_document(pages, path, fmt, registry=None):
    """Write one document (list of pages) in one format"""
    dpi = pages[0].get("dpi") or 300
    images = [load_page(p) for p in pages]

    if fmt == "pdf":
        if not (registry and registry.export_pdf(pages, path)):  # e.g. OCR writes it itself
            # PDF pages must be RGB/L/1; resolution sets the physical page size
            converted = [im if im.mode in ("RGB", "L", "1") else im.convert("RGB") for im in images]
            converted[0].save(path, "PDF", save_all=True, append_images=converted[1:], resolution=dpi)
        if registry:
            registry.postprocess_pdf(path)  # e.g. PDF/A, smaller file
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
