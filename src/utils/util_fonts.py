"""
Font helpers for Quick Edit
- The 20 basic fonts offered for text, resolved to files through fontconfig
  (fc-match). Only families that are really installed are offered.
- Signature fonts: the bundled ones (resources/fonts/signature, SIL Open Font
  License, listed in fonts.json with their credits) plus fonts the user adds
  (~/.local/share/linscanner/fonts; kept on this computer, never bundled).
- render_text(): the one text renderer used by the editor and by Save, so what
  you see is what gets saved.
"""

import functools
import json
import os
import shutil
import subprocess
import zipfile

from utils.util_paths import data_dir, resource

FONT_EXTENSIONS = (".ttf", ".otf")

# From the distro font packages fonts-dejavu-core, fonts-liberation, fonts-noto-core,
# fonts-ubuntu and fonts-urw-base35 (all in the offline pool).
BASIC_FONTS = [
    "DejaVu Sans",
    "DejaVu Serif",
    "DejaVu Sans Mono",
    "Liberation Sans",
    "Liberation Serif",
    "Liberation Mono",
    "Noto Sans",
    "Noto Serif",
    "Noto Sans Mono",
    "Ubuntu",
    "Ubuntu Mono",
    "URW Gothic",
    "Nimbus Sans",
    "Nimbus Sans Narrow",
    "Nimbus Roman",
    "Nimbus Mono PS",
    "C059",
    "P052",
    "URW Bookman",
    "Z003",  # script (chancery) - handy for typed signatures
]


@functools.lru_cache(maxsize=64)
def _match(family):
    """(matched family, file) from fc-match, or (None, None)"""
    if not shutil.which("fc-match"):
        return None, None
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{family[0]}|%{file}", family], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None, None
    if "|" not in out:
        return None, None
    matched, path = out.split("|", 1)
    return matched, path


def font_file(family):
    """Font file for a family (fontconfig picks a fallback if it's missing)"""
    return _match(family)[1]


def available_fonts():
    """The basic fonts that are actually installed (no silent substitutes)"""
    return [f for f in BASIC_FONTS if (_match(f)[0] or "").lower() == f.lower()]


# -- signature fonts ----------------------------------------------------------------


def user_fonts_dir():
    """Fonts the user added (~/.local/share/linscanner/fonts)"""
    return data_dir("fonts")


def _family_of(path):
    """Font family name read from the font file (None if it can't be read)"""
    from PIL import ImageFont

    try:
        return ImageFont.truetype(path, 20).getname()[0]
    except (OSError, ValueError):
        return None


def bundled_signature_fonts():
    """Bundled signature fonts with credits: [{family, path, designer, copyright, license, ...}]"""
    folder = resource("fonts", "signature")
    try:
        with open(os.path.join(folder, "fonts.json")) as f:
            entries = json.load(f)["fonts"]
    except (OSError, ValueError, KeyError):
        return []
    fonts = []
    for e in entries:
        path = os.path.join(folder, e["file"])
        if os.path.exists(path):
            fonts.append(dict(e, path=path, bundled=True))
    return fonts


def user_signature_fonts():
    """Fonts the user added: [{family, path, bundled: False}]"""
    folder = user_fonts_dir()
    fonts = []
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(FONT_EXTENSIONS):
            path = os.path.join(folder, name)
            family = _family_of(path)
            if family:
                fonts.append({"family": family, "path": path, "bundled": False})
    return fonts


def signature_fonts():
    """Bundled + user signature fonts, one entry per family (bundled first)"""
    seen, fonts = set(), []
    for f in bundled_signature_fonts() + user_signature_fonts():
        if f["family"].lower() not in seen:
            seen.add(f["family"].lower())
            fonts.append(f)
    return fonts


def import_fonts(paths):
    """Copy .ttf/.otf files (or the fonts inside .zip files) to the user font folder.

    Returns the families added. Only font files are taken from a zip."""
    added = []
    folder = user_fonts_dir()

    def keep(name, data):
        dest = os.path.join(folder, os.path.basename(name))
        with open(dest, "wb") as f:
            f.write(data)
        family = _family_of(dest)
        if family:
            added.append(family)
        else:
            os.remove(dest)  # not a usable font

    for path in paths:
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.lower().endswith(FONT_EXTENSIONS) and not name.startswith("__MACOSX"):
                        keep(name, z.read(name))
        elif path.lower().endswith(FONT_EXTENSIONS):
            with open(path, "rb") as f:
                keep(path, f.read())
    signature_font_file.cache_clear()
    load_font.cache_clear()
    return added


def remove_user_font(path):
    """Delete a font the user added"""
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(user_fonts_dir()):
        os.remove(path)
        signature_font_file.cache_clear()
        load_font.cache_clear()


@functools.lru_cache(maxsize=64)
def signature_font_file(family):
    """Font file of a signature font family, or None"""
    return next((f["path"] for f in signature_fonts() if f["family"].lower() == family.lower()), None)


def text_fonts():
    """Every family offered for text: the basic fonts, then the signature fonts"""
    return available_fonts() + [f["family"] for f in signature_fonts()]


def resolve_font(family):
    """Font file for any family offered by linscanner (signature fonts first)"""
    return signature_font_file(family) or font_file(family)


@functools.lru_cache(maxsize=256)
def load_font(family, px):
    """Pillow font object for a family at a pixel size (cached)"""
    from PIL import ImageFont

    path = resolve_font(family)
    try:
        return ImageFont.truetype(path, max(4, int(px))) if path else ImageFont.load_default()
    except OSError:
        return ImageFont.load_default()


def text_metrics(text, family, px):
    """(advance width, line height) in pixels: the text's box from its anchor"""
    font = load_font(family, px)
    try:
        ascent, descent = font.getmetrics()
        return font.getlength(text or ""), ascent + descent
    except AttributeError:  # bitmap fallback font
        return 6 * len(text or ""), 11


def render_text(text, family, px, color="#000000"):
    """Text as a transparent RGBA image; returns (image, dx, dy): the image's
    top-left relative to the text anchor (the item's x, y). Script fonts often
    reach left of or above their anchor, so the offsets can be negative."""
    from PIL import Image, ImageDraw

    font = load_font(family, px)
    left, top, right, bottom = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text or " ", font=font)
    left, top = min(left, 0), min(top, 0)
    img = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-left, -top), text or "", font=font, fill=color)
    return img, left, top
