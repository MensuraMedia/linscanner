"""
Auto-crop
Removes the extra length a sheet feeder scans past the end of the sheet: a
uniform band at the bottom whose tone differs from the paper. Page margins are
never cut. If the overrun looks identical to the paper, nothing is trimmed
(use the Paper size setting instead).
"""

import numpy as np

from features import BaseFeature
from utils.util_imaging import small_gray


def trailing_band(a):
    """Row (in the small image) where the uniform overrun band starts, or None"""
    h = a.shape[0]
    paper = float(np.percentile(a[: h // 2], 90))  # paper tone from the upper half
    std, mean = a.std(axis=1), a.mean(axis=1)
    tone = float(mean[-3:].mean())  # tone of the very last rows = the overrun
    start = h
    # grow upward while rows are uniform AND have the overrun's tone (not the paper margin's)
    while start > 0 and std[start - 1] < 2.5 and abs(mean[start - 1] - tone) < 1.5:
        start -= 1
    if h - start < 0.03 * h or start < 0.3 * h:
        return None  # no real band, or it would remove most of the page
    if abs(tone - paper) < 3:
        return None  # indistinguishable from the paper: don't guess
    return start


class Feature(BaseFeature):
    """Trim the feeder overrun at the end of the sheet"""

    id = "autocrop"
    name = "Auto-crop"
    description = "Removes the extra length a feeder scans past the end of a sheet. Never cuts page margins."
    default_enabled = True
    order = 10

    def process_page(self, image, page):
        """Crop off a detected overrun band (plus a small margin kept)"""
        g = small_gray(image, 800)
        a = np.asarray(g, dtype=np.float32)
        start = trailing_band(a)
        if start is None:
            return image
        scale = image.height / g.height
        keep = min(image.height, int((start + max(2, 0.005 * a.shape[0])) * scale))
        page["autocropped"] = image.height - keep
        return image.crop((0, 0, image.width, keep))
