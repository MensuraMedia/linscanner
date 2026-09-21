"""
Batch splitting
Put a blank sheet between documents in the feeder: each blank page starts a
new document, and Save As writes one file per document (name-001.pdf, ...).
Blank pages are detected even when blank-page removal is off.
"""

from features import BaseFeature
from utils.util_imaging import is_blank


class Feature(BaseFeature):
    """Split a scanned stack into documents at blank separator sheets"""

    id = "batch_split"
    name = "Batch splitting"
    description = (
        "A blank sheet between documents starts a new file when saving (name-001.pdf, name-002.pdf, …)."
    )
    default_enabled = False
    order = 35

    def process_page(self, image, page):
        """Mark blank pages as separators (kept until export)"""
        if is_blank(image):
            page["separator"] = True
        return image

    def split_documents(self, pages):
        """Documents between separator pages (empty documents are skipped)"""
        docs, current = [], []
        for page in pages:
            if page.get("separator"):
                if current:
                    docs.append(current)
                current = []
            else:
                current.append(page)
        if current:
            docs.append(current)
        return docs
