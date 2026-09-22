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
    name = "Import images"
    description = "Adds PNG/JPEG/TIFF files as pages, e.g. scans the scanner saved to a USB stick."
    default_enabled = True
    order = 90

    def extend_preview(self, page):
        """Add an 'Import images…' button to the Preview toolbar"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        btn = Gtk.Button(label="Import images…")
        btn.connect("clicked", lambda *_: self.choose(page))
        page.feature_toolbar.pack_start(btn, False, False, 0)
        page.feature_buttons[self.id] = btn

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
            added = import_files(page.ctx, paths)
            page.ctx.emit("pages-changed")
            page.set_status(f"Imported {added} page(s).")
