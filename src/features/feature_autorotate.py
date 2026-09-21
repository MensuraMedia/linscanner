"""
Auto-rotate
Detects page orientation with Tesseract OSD and turns upside-down or sideways
pages upright (e.g. sheets loaded the wrong way round).
"""

import os
import re
import shutil
import subprocess
import tempfile

from features import BaseFeature
from utils.util_imaging import ink_ratio


def detect_rotation(image):
    """Clockwise degrees Tesseract says the page needs (0/90/180/270), or 0 if unsure"""
    if not shutil.which("tesseract"):
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.png")
        img = image.convert("L")
        if img.width > 2000:
            img = img.resize((2000, int(img.height * 2000 / img.width)))
        img.save(path, dpi=(300, 300))
        try:
            out = subprocess.run(
                ["tesseract", path, "-", "--psm", "0"], capture_output=True, text=True, timeout=60
            )
        except (OSError, subprocess.SubprocessError):
            return 0
    text = out.stdout + out.stderr
    rotate = re.search(r"Rotate:\s*(\d+)", text)
    confidence = re.search(r"Orientation confidence:\s*([\d.]+)", text)
    if not rotate or not confidence or float(confidence.group(1)) < 2.0:
        return 0
    return int(rotate.group(1)) % 360


class Feature(BaseFeature):
    """Turn pages upright using orientation detection"""

    id = "autorotate"
    name = "Auto-rotate"
    description = (
        "Turns upside-down or sideways pages upright (Tesseract orientation detection; pages need text)."
    )
    default_enabled = False
    order = 30

    def process_page(self, image, page):
        """Rotate the page upright if Tesseract is confident"""
        if ink_ratio(image) < 0.003:
            return image
        degrees = detect_rotation(image)
        if degrees:
            page["autorotated"] = degrees
            return image.rotate(-degrees, expand=True)
        return image
