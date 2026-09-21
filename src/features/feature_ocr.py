"""
Searchable PDF (OCR)
Saves PDFs with an invisible text layer made by Tesseract (English), so the
text can be searched, selected and copied.
"""

import os
import shutil
import subprocess
import tempfile

from features import BaseFeature
from utils.util_imaging import flatten

LANGUAGE = "eng"


class Feature(BaseFeature):
    """Make saved PDFs searchable"""

    id = "ocr"
    name = "Searchable PDF (OCR)"
    description = (
        "Adds an invisible text layer to saved PDFs (Tesseract, English) so text can be searched and copied."
    )
    default_enabled = False
    order = 50

    def export_pdf(self, pages, path):
        """Write a searchable PDF with Tesseract; False if Tesseract isn't available"""
        if not shutil.which("tesseract"):
            return False
        with tempfile.TemporaryDirectory() as tmp:
            listing = os.path.join(tmp, "pages.txt")
            with open(listing, "w") as f:
                for n, page in enumerate(pages):
                    img = flatten(page)
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    dpi = page.get("dpi") or 300
                    png = os.path.join(tmp, f"p{n:04d}.png")
                    img.save(png, dpi=(dpi, dpi))
                    f.write(png + "\n")
            base = os.path.join(tmp, "out")
            r = subprocess.run(
                ["tesseract", listing, base, "-l", LANGUAGE, "pdf"],
                capture_output=True,
                text=True,
                timeout=60 + 60 * len(pages),
            )
            if r.returncode != 0 or not os.path.exists(base + ".pdf"):
                raise RuntimeError(f"tesseract failed: {r.stderr.strip()[-200:]}")
            shutil.move(base + ".pdf", path)
        return True
