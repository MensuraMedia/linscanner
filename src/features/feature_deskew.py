"""
Deskew
Straightens pages fed at a slight angle (up to ±5°) using a projection
profile: text lines are sharpest when they're horizontal.
"""

import numpy as np
from PIL import Image

from features import BaseFeature
from utils.util_imaging import ink_ratio, small_gray

MAX_ANGLE = 5.0
STEP = 0.25


def find_skew(image):
    """Angle in degrees (counter-clockwise positive) that straightens the text"""
    g = small_gray(image, 900)
    a = np.asarray(g, dtype=np.int16)
    ink = (a < np.percentile(a, 90) - 60).astype(np.uint8) * 255
    mask = Image.fromarray(ink)
    best, best_score = 0.0, -1.0
    for angle in np.arange(-MAX_ANGLE, MAX_ANGLE + STEP / 2, STEP):
        rows = np.asarray(mask.rotate(angle, resample=Image.NEAREST), dtype=np.float32).sum(axis=1)
        score = float(np.var(rows))
        if score > best_score:
            best, best_score = float(angle), score
    return best


class Feature(BaseFeature):
    """Straighten slightly rotated pages"""

    id = "deskew"
    name = "Auto-straighten (deskew)"
    description = "Straightens pages that went through the feeder at a slight angle (up to ±5°)."
    default_enabled = True
    order = 20

    def process_page(self, image, page):
        """Rotate the page by the detected skew (skipped for near-empty pages)"""
        if ink_ratio(image) < 0.003:
            return image  # nothing to measure on
        angle = find_skew(image)
        if abs(angle) < 0.3:
            return image
        fill = 255 if image.mode in ("L", "1") else (255, 255, 255)
        page["deskew_angle"] = angle
        return image.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=fill)
