"""
Imaging helpers shared by the core and feature modules (Pillow + numpy).
Kept in the core so features never depend on each other.
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils.util_fonts import font_file


def small_gray(img, width=600):
    """Grayscale copy scaled to about `width` pixels wide (fast analysis)"""
    g = img.convert("L")
    if g.width > width:
        g = g.resize((width, max(1, int(g.height * width / g.width))), Image.BILINEAR)
    return g


def ink_ratio(img, margin=0.05):
    """Share of pixels that differ from the paper, ignoring a margin (edges, shadows).

    The paper colour is estimated per channel, and a pixel counts as content if
    it differs strongly in any channel, darker or lighter. Colour charts, photos
    and coloured text therefore count as content, while blank coloured paper
    (uniform) stays blank."""
    rgb = img.convert("RGB")
    if rgb.width > 600:
        rgb = rgb.resize((600, max(1, int(rgb.height * 600 / rgb.width))), Image.BILINEAR)
    a = np.asarray(rgb, dtype=np.int16)
    h, w = a.shape[:2]
    mh, mw = int(h * margin), int(w * margin)
    inner = a[mh : h - mh or h, mw : w - mw or w].reshape(-1, 3)
    if inner.size == 0:
        return 0.0
    paper = np.median(inner, axis=0)  # the dominant (background) colour
    content = (np.abs(inner - paper) > 60).any(axis=1)
    return float(content.mean())


def is_blank(img, threshold=0.002):
    """True if the page has (almost) no ink"""
    return ink_ratio(img) < threshold


def overlay_pixels(page, size):
    """Overlay position helper: fractions of the page -> pixels for an image of `size`"""
    w, h = size
    return lambda fx, fy: (int(fx * w), int(fy * h))


def flatten(page, img=None):
    """Page image with rotation and Quick Edit overlays applied"""
    if img is None:
        img = Image.open(page["path"])
        img.load()
    if page.get("rotation"):
        img = img.rotate(-page["rotation"], expand=True)
    overlays = page.get("overlays") or []
    if not overlays:
        return img
    base = img.convert("RGBA")
    w, h = base.size
    dpi = page.get("dpi") or 300
    draw = ImageDraw.Draw(base)
    for item in overlays:
        x, y = int(item["x"] * w), int(item["y"] * h)
        if item["type"] == "text":
            px = max(6, int(item.get("size_pt", 14) * dpi / 72))
            path = font_file(item.get("font", "DejaVu Sans"))
            try:
                font = ImageFont.truetype(path, px) if path else ImageFont.load_default()
            except OSError:
                font = ImageFont.load_default()
            draw.text((x, y), item.get("text", ""), font=font, fill=item.get("color", "#000000"))
        elif item["type"] == "image" and os.path.exists(item.get("path", "")):
            sig = Image.open(item["path"]).convert("RGBA")  # keep the PNG's transparency
            sw = max(1, int(item["w"] * w))
            sh = max(1, int(sig.height * sw / sig.width))
            base.alpha_composite(sig.resize((sw, sh), Image.LANCZOS), (x, y))
    return (
        base.convert("RGB")
        if img.mode in ("RGB", "RGBA", "P")
        else base.convert(img.mode if img.mode != "1" else "L")
    )
