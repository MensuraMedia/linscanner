"""
Signature library
Up to MAX_SIGNATURES saved signatures (transparent PNGs) in
~/.local/share/linscanner/signatures/, kept between sessions. A signature is
either an imported PNG or a name typed in a signature font.
"""

import os

from utils.util_fonts import render_text
from utils.util_paths import data_dir

MAX_SIGNATURES = 4
TYPED_SIGNATURE_PX = 160  # font size used to render typed signatures (sharp when printed)


class LibraryFull(Exception):
    """The library already holds MAX_SIGNATURES signatures"""


def signatures_dir():
    """Signature library folder (~/.local/share/linscanner/signatures)"""
    return data_dir("signatures")


def library():
    """Saved signature PNGs, oldest first (so slots keep their place)"""
    folder = signatures_dir()
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".png")]
    return sorted(files, key=os.path.getmtime)


def is_full():
    """True if no more signatures can be saved"""
    return len(library()) >= MAX_SIGNATURES


def has_transparency(path):
    """True if a PNG has any transparent pixels"""
    from PIL import Image

    with Image.open(path) as img:
        if img.mode not in ("RGBA", "LA", "P"):
            return False
        alpha = img.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255


def _unique_path(folder, name):
    """folder/name.png, or name-2.png, name-3.png, ... if taken"""
    dest = os.path.join(folder, f"{name}.png")
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(folder, f"{name}-{n}.png")
        n += 1
    return dest


def _trim(img):
    """Crop an RGBA image to its visible pixels (plus a small margin)"""
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img
    m = 4
    return img.crop(
        (max(0, bbox[0] - m), max(0, bbox[1] - m), min(img.width, bbox[2] + m), min(img.height, bbox[3] + m))
    )


def prepare_png(path, clear_white=False):
    """An imported PNG as RGBA (optionally with near-white made transparent), trimmed"""
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    if clear_white:
        pixels = [(r, g, b, 0 if r > 200 and g > 200 and b > 200 else a) for r, g, b, a in img.getdata()]
        img.putdata(pixels)
        img = _trim(img)
    return img


def typed_signature(text, family, color="#1a1a1a", px=TYPED_SIGNATURE_PX):
    """A name rendered in a signature font, as a trimmed transparent RGBA image"""
    img, _dx, _dy = render_text(text, family, px, color)
    return _trim(img)


def save_signature(img, name, folder=None):
    """Save an RGBA image to the library; raises LibraryFull when 4 are saved. Returns the path."""
    if is_full() and folder is None:
        raise LibraryFull(f"You already have {MAX_SIGNATURES} saved signatures. Remove one to add another.")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-")[:40] or "signature"
    dest = _unique_path(folder or signatures_dir(), safe)
    img.save(dest)
    return dest


def remove_signature(path):
    """Delete a saved signature"""
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(signatures_dir()) and os.path.exists(path):
        os.remove(path)
