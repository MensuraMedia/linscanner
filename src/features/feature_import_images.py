"""
Import images
Adds image files (PNG, JPEG, TIFF, multi-page TIFF) as pages. This is also the
last-resort acquisition method: if no driver works, scan to a USB stick or
network folder on the scanner itself and import the files here.
"""

import os

from features import BaseFeature

EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def import_files(ctx, paths):
    """Append image files to the session as pages; returns the number of pages added"""
    from PIL import Image, ImageSequence

    added = 0
    for path in paths:
        try:
            with Image.open(path) as img:
                dpi = int(round(img.info.get("dpi", (300, 300))[0])) or 300
                for n, frame in enumerate(ImageSequence.Iterator(img)):
                    out = os.path.join(ctx.scan.session_dir, f"import-{len(ctx.scan.pages) + 1:04d}.png")
                    frame.convert("RGB" if frame.mode not in ("L", "1") else frame.mode).save(
                        out, dpi=(dpi, dpi)
                    )
                    ctx.scan.pages.append({"path": out, "rotation": 0, "dpi": dpi, "mode": "Imported"})
                    added += 1
        except OSError:
            continue  # not an image: skip it
    return added


class Feature(BaseFeature):
    """Add image files as pages"""

    id = "import_images"
    name = "Add Image"
    description = "Adds PNG/JPEG/TIFF files as new pages, e.g. scans the scanner saved to a USB stick."
    default_enabled = True
    order = 90

    def extend_preview(self, page):
        """Add an 'Add Image' button to the Document toolbar's pages group"""
        from utils.util_icons import icon_button

        btn = icon_button(
            "arrow-square-in",
            "Add Image: add image files (PNG, JPEG, TIFF) as new pages",
            lambda: self.choose(page),
        )
        btn.works_without_pages = True
        page.add_tool("pages", btn, self.id, after=getattr(page, "btn_add_page", None))

    def choose(self, page):
        """File dialog, then import"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog(
            title="Import images", transient_for=page.ctx.window, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Import", Gtk.ResponseType.ACCEPT)
        dlg.set_select_multiple(True)
        flt = Gtk.FileFilter()
        flt.set_name("Images")
        for ext in EXTENSIONS:
            flt.add_pattern(f"*{ext}")
            flt.add_pattern(f"*{ext.upper()}")
        dlg.add_filter(flt)
        paths = dlg.get_filenames() if dlg.run() == Gtk.ResponseType.ACCEPT else []
        dlg.destroy()
        if paths:
            before = page._snapshot() if hasattr(page, "_snapshot") else None
            added = import_files(page.ctx, paths)
            if before is not None and added:
                page.checkpoint(before)
            page.changed() if hasattr(page, "changed") else page.ctx.emit("pages-changed")
            page.set_status(f"Added {added} image page(s).")
