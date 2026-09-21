"""
Font helpers for Quick Edit
The 20 basic fonts offered for text, resolved to files through fontconfig
(fc-match). Only families that are really installed are offered.
"""

import functools
import shutil
import subprocess

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
