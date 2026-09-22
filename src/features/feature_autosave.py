"""
Auto-save
Saves each finished scan automatically as a PDF in a chosen folder, named from
a template: {date} {time} {n} {pages} {mode}. Example: {date}-{time}-scan.pdf
"""

import os
from datetime import datetime

from features import BaseFeature

DEFAULT_TEMPLATE = "{date}-{time}-scan"


def render_name(template, pages, when=None, n=1):
    """File name (without folder) from a template"""
    when = when or datetime.now()
    name = template.format(
        date=when.strftime("%Y-%m-%d"),
        time=when.strftime("%H%M%S"),
        n=f"{n:03d}",
        pages=len(pages),
        mode=(pages[0].get("mode", "scan") if pages else "scan").lower(),
    )
    name = "".join(c for c in name if c not in '/\\:*?"<>|').strip() or "scan"
    return name if name.lower().endswith(".pdf") else name + ".pdf"


class Feature(BaseFeature):
    """Save finished scans automatically"""

    id = "autosave"
    name = "Auto-save with file-name template"
    description = (
        "Saves each finished scan as a PDF in a folder, named from a template like {date}-{time}-scan."
    )
    default_enabled = False
    order = 70

    def after_scan(self, ctx, pages, final):
        """Save the session's pages when a document is complete"""
        if not final or not pages:
            return
        from modules.manager_export import export_pages

        folder = self.option("folder", ctx.settings.get("save_folder"))
        os.makedirs(folder, exist_ok=True)
        scan = getattr(ctx, "scan", None)
        docs = scan.doc_ids() if scan is not None and hasattr(scan, "doc_ids") else [None]
        written = []
        for n, doc in enumerate(docs, start=1):  # Single Page: one file per document
            doc_pages = scan.doc_pages(doc) if doc is not None else pages
            name = render_name(self.option("template", DEFAULT_TEMPLATE), doc_pages, n=n)
            if len(docs) > 1 and "{n}" not in self.option("template", DEFAULT_TEMPLATE):
                name = name[:-4] + f"-{n:03d}.pdf"
            files = export_pages(
                doc_pages, os.path.join(folder, name), "pdf", registry=getattr(ctx, "features", None)
            )
            written += files
            if doc is not None:
                scan.documents[doc] = {"path": files[0], "format": "pdf"}
                scan.mark_saved(doc)
        ctx.emit("autosaved", written)

    def settings_widget(self, ctx):
        """Folder and template"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        box = Gtk.Box(spacing=8)
        folder = Gtk.FileChooserButton(title="Auto-save folder", action=Gtk.FileChooserAction.SELECT_FOLDER)
        folder.set_filename(self.option("folder", ctx.settings.get("save_folder")))
        folder.connect("file-set", lambda b: self.set_option("folder", b.get_filename()))
        entry = Gtk.Entry()
        entry.set_text(self.option("template", DEFAULT_TEMPLATE))
        entry.set_width_chars(24)
        entry.set_tooltip_text("Tokens: {date} {time} {n} {pages} {mode}")
        entry.connect("changed", lambda e: self.set_option("template", e.get_text()))
        box.pack_start(folder, False, False, 0)
        box.pack_start(Gtk.Label(label="Name"), False, False, 0)
        box.pack_start(entry, False, False, 0)
        return box
