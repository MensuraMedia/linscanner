"""
Auto-Detect paper size
Finds the paper inside a scan made over the whole scan area, so the page can
be cropped to the document (receipt, card, letter, ...).

How: the background colour is taken from the scan's outer border (the feeder
or lid around the paper). Pixels that clearly differ from it are paper; the
rows and columns holding enough of them give the paper's box, which is kept
(plus a small margin) and the rest cropped away.

Limit: when the paper and the background are the same colour (white paper on
a white backing) the edges can't be seen; content_box() then returns None and
the caller keeps the page (or uses the chosen nominal size).
"""

import numpy as np

ANALYSIS_SIDE = 1000  # the analysis runs on a copy about this big (fast)
DIFF = 35  # colour difference (0-255, per channel) that counts as "not paper"
MARGIN_MM = 1.5  # kept around the detected paper
LINE_SHARE = 0.02  # a row / column with more than this share of non-background pixels is paper
PAPER_SHARE = 0.5  # the found area must be mostly paper (not just ink on a same-colour backing)


def content_box(img, dpi=300, threshold=DIFF, margin_mm=MARGIN_MM):
    """(left, top, right, bottom) of the paper in img, or None if its edges can't be seen"""
    rgb = img.convert("RGB")
    factor = max(1, max(rgb.size) // ANALYSIS_SIDE)
    small = rgb.reduce(factor) if factor > 1 else rgb
    a = np.asarray(small).astype(np.int16)
    h, w, _ = a.shape
    if h < 20 or w < 20:
        return None
    t = max(2, min(h, w) // 100)  # border strip thickness
    border = np.concatenate(
        [a[:t].reshape(-1, 3), a[-t:].reshape(-1, 3), a[:, :t].reshape(-1, 3), a[:, -t:].reshape(-1, 3)]
    )
    background = np.median(border, axis=0)
    differs = np.abs(a - background).max(axis=2) > threshold  # not background

    rows = np.where(differs.mean(axis=1) > LINE_SHARE)[0]
    if rows.size == 0:
        return None
    top, bottom = rows[0], rows[-1] + 1
    cols = np.where(differs[top:bottom].mean(axis=0) > LINE_SHARE)[0]
    if cols.size == 0:
        return None
    left, right = cols[0], cols[-1] + 1

    found = (right - left) * (bottom - top)
    if found >= 0.98 * w * h:  # nothing to trim: edges not visible
        return None
    if found < 0.01 * w * h:  # implausibly small: don't trust it
        return None
    if differs[top:bottom, left:right].mean() < PAPER_SHARE:
        return None  # only ink stands out: paper and background are the same colour
    m = int(round(margin_mm / 25.4 * dpi / factor))
    left, top = max(0, left - m), max(0, top - m)
    right, bottom = min(w, right + m), min(h, bottom + m)
    W, H = rgb.size
    return (
        min(W, left * factor),
        min(H, top * factor),
        min(W, right * factor),
        min(H, bottom * factor),
    )


def nominal_box(img, size_mm, dpi):
    """Box of a nominal paper size (w, h in mm), centred across and from the top"""
    W, H = img.size
    w = min(W, int(round(size_mm[0] / 25.4 * dpi)))
    h = min(H, int(round(size_mm[1] / 25.4 * dpi)))
    left = max(0, (W - w) // 2)
    return left, 0, left + w, h


def detect_crop(img, dpi, nominal_mm=None):
    """(cropped image, how) for Auto-Detect: 'detected', 'nominal' or 'kept'"""
    box = content_box(img, dpi)
    if box:
        return img.crop(box), "detected"
    if nominal_mm:
        return img.crop(nominal_box(img, nominal_mm, dpi)), "nominal"
    return img, "kept"
