"""
Quick Edit
Add text (20 basic fonts, size, colour) and signatures (transparent PNG
library) to scanned pages. Items can be selected, moved, resized, deleted and
applied to other pages, like mainstream PDF editors. Edits are stored as
overlays on the page and flattened only on Save As (non-destructive).

Overlay model (positions/sizes are fractions of the page, so they survive
rotation-free resizing and work at any dpi):
  {"type": "text", "text": str, "font": family, "size_pt": float, "color": "#rrggbb", "x": f, "y": f}
  {"type": "image", "path": signature.png, "x": f, "y": f, "w": f (width as page fraction)}
"""

import copy
import os
import shutil

from features import BaseFeature
from utils.util_fonts import available_fonts

HANDLE = 10  # px: resize handle size on the canvas


def signatures_dir():
    """Signature library folder (~/.local/share/linscanner/signatures)"""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "linscanner", "signatures")
    os.makedirs(path, exist_ok=True)
    return path


def has_transparency(path):
    """True if a PNG has any transparent pixels"""
    from PIL import Image

    with Image.open(path) as img:
        if img.mode not in ("RGBA", "LA", "P"):
            return False
        alpha = img.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255


def import_signature(path, clear_white=False):
    """Copy a PNG into the library (optionally making near-white transparent); returns the new path"""
    from PIL import Image

    name = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(signatures_dir(), f"{name}.png")
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(signatures_dir(), f"{name}-{n}.png")
        n += 1
    img = Image.open(path).convert("RGBA")
    if clear_white:
        pixels = [(r, g, b, 0 if r > 200 and g > 200 and b > 200 else a) for r, g, b, a in img.getdata()]
        img.putdata(pixels)
        bbox = img.getchannel("A").getbbox()  # trim the now-empty border
        if bbox:
            img = img.crop(bbox)
    img.save(dest)
    return dest


def library():
    """Signature PNGs in the library, newest first"""
    folder = signatures_dir()
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".png")]
    return sorted(files, key=os.path.getmtime, reverse=True)


class Feature(BaseFeature):
    """Text and signatures on scanned pages"""

    id = "quick_edit"
    name = "Quick Edit (text and signatures)"
    description = "Add text (20 basic fonts) and transparent PNG signatures; move, resize and re-apply them."
    default_enabled = True
    order = 85

    def extend_preview(self, page):
        """Add a 'Quick Edit' button to the Preview toolbar"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        btn = Gtk.Button(label="Quick Edit…")
        btn.connect("clicked", lambda *_: self.open_editor(page))
        page.feature_toolbar.pack_start(btn, False, False, 0)
        page.feature_buttons[self.id] = btn

    def open_editor(self, preview_page):
        """Open the editor for the selected page; store overlays on OK"""
        pages = preview_page.ctx.scan.pages
        index = preview_page.preview.selected
        if not pages or index < 0:
            return
        editor = QuickEditor(preview_page.ctx, pages, index)
        if editor.run():
            preview_page.ctx.emit("pages-changed")
            preview_page.status.set_text("Quick Edit applied. Text and signatures are added when you save.")


class QuickEditor:
    """Modal editor window: canvas + tools. run() returns True if changes were applied."""

    def __init__(self, ctx, pages, index):
        """Build the dialog for pages[index] (overlays are edited on a copy)"""
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gtk

        self.Gtk = Gtk
        self.ctx, self.pages, self.index = ctx, pages, index
        self.page = pages[index]
        self.items = copy.deepcopy(self.page.get("overlays") or [])
        self.others = {}  # page index -> overlays added via "Apply to all pages"
        self.selected = None
        self.drag = None  # ("move"|"resize", start canvas x, y, item snapshot)
        self._base = None
        self._pix_cache = {}

        self.dialog = Gtk.Dialog(title=f"Quick Edit: page {index + 1}", transient_for=ctx.window, modal=True)
        self.dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Apply", Gtk.ResponseType.OK)
        self.dialog.set_default_size(1100, 800)
        body = Gtk.Box(spacing=12)
        body.set_margin_start(10)
        body.set_margin_end(10)
        self.dialog.get_content_area().pack_start(body, True, True, 0)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(620, 760)
        self.canvas.set_can_focus(True)
        self.canvas.add_events(
            self._mask("BUTTON_PRESS_MASK", "BUTTON_RELEASE_MASK", "POINTER_MOTION_MASK", "KEY_PRESS_MASK")
        )
        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("button-press-event", self.on_press)
        self.canvas.connect("motion-notify-event", self.on_motion)
        self.canvas.connect("button-release-event", self.on_release)
        self.canvas.connect("key-press-event", self.on_key)
        body.pack_start(self.canvas, True, True, 0)
        body.pack_start(self._tools(), False, False, 0)
        self.dialog.show_all()

    @staticmethod
    def _mask(*names):
        """Combine Gdk event mask names"""
        from gi.repository import Gdk

        mask = 0
        for n in names:
            mask |= getattr(Gdk.EventMask, n)
        return mask

    # -- tool panel --------------------------------------------------------------
    def _tools(self):
        """Right-hand panel: text tools, signature library, item actions"""
        Gtk = self.Gtk
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(360, -1)

        panel.pack_start(self._heading("Text"), False, False, 0)
        self.text_entry = Gtk.Entry()
        self.text_entry.set_placeholder_text("Type text to add…")
        panel.pack_start(self.text_entry, False, False, 0)
        row = Gtk.Box(spacing=6)
        self.font_combo = Gtk.ComboBoxText()
        for family in available_fonts():
            self.font_combo.append(family, family)
        self.font_combo.set_active(0)
        self.size_spin = Gtk.SpinButton.new_with_range(6, 96, 1)
        self.size_spin.set_value(14)
        self.color_btn = Gtk.ColorButton()
        from gi.repository import Gdk

        black = Gdk.RGBA()
        black.parse("#000000")
        self.color_btn.set_rgba(black)
        row.pack_start(self.font_combo, True, True, 0)
        row.pack_start(self.size_spin, False, False, 0)
        row.pack_start(self.color_btn, False, False, 0)
        panel.pack_start(row, False, False, 0)
        row = Gtk.Box(spacing=6)
        add_text = Gtk.Button(label="Add text")
        add_text.connect("clicked", lambda *_: self.add_text())
        self.update_text_btn = Gtk.Button(label="Update selected text")
        self.update_text_btn.connect("clicked", lambda *_: self.update_text())
        row.pack_start(add_text, False, False, 0)
        row.pack_start(self.update_text_btn, False, False, 0)
        panel.pack_start(row, False, False, 0)

        panel.pack_start(self._heading("Signatures"), False, False, 0)
        self.sig_list = Gtk.FlowBox()
        self.sig_list.set_max_children_per_line(3)
        self.sig_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroller = Gtk.ScrolledWindow()
        scroller.set_min_content_height(160)
        scroller.add(self.sig_list)
        panel.pack_start(scroller, False, False, 0)
        row = Gtk.Box(spacing=6)
        imp = Gtk.Button(label="Import PNG…")
        imp.connect("clicked", lambda *_: self.import_png())
        place = Gtk.Button(label="Place signature")
        place.connect("clicked", lambda *_: self.place_signature())
        remove = Gtk.Button(label="Remove from library")
        remove.connect("clicked", lambda *_: self.remove_signature())
        for b in (imp, place, remove):
            row.pack_start(b, False, False, 0)
        panel.pack_start(row, False, False, 0)
        self.refresh_library()

        panel.pack_start(self._heading("Selected item"), False, False, 0)
        row = Gtk.Box(spacing=6)
        delete = Gtk.Button(label="Delete")
        delete.connect("clicked", lambda *_: self.delete_selected())
        apply_all = Gtk.Button(label="Apply to all pages")
        apply_all.connect("clicked", lambda *_: self.apply_to_all())
        row.pack_start(delete, False, False, 0)
        row.pack_start(apply_all, False, False, 0)
        panel.pack_start(row, False, False, 0)
        self.hint = Gtk.Label(
            label="Click an item to select it · drag to move · drag the corner square to resize · "
            "Delete key removes · double-click text to edit it"
        )
        self.hint.set_line_wrap(True)
        self.hint.set_xalign(0)
        self.hint.get_style_context().add_class("muted")
        panel.pack_start(self.hint, False, False, 0)
        return panel

    def _heading(self, text):
        """Section heading label"""
        lbl = self.Gtk.Label(label=text)
        lbl.set_xalign(0)
        lbl.get_style_context().add_class("card-title")
        return lbl

    def refresh_library(self):
        """Show signature thumbnails"""
        from gi.repository import GdkPixbuf

        for child in self.sig_list.get_children():
            self.sig_list.remove(child)
        for path in library():
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 100, 50, True)
            except Exception:
                continue
            img = self.Gtk.Image.new_from_pixbuf(pix)
            img.sig_path = path
            self.sig_list.add(img)
        self.sig_list.show_all()

    def _selected_signature(self):
        """Path of the signature selected in the library, or None"""
        chosen = self.sig_list.get_selected_children()
        return chosen[0].get_child().sig_path if chosen else None

    # -- actions ------------------------------------------------------------------
    def add_text(self):
        """Add the typed text near the top-left of the visible page"""
        text = self.text_entry.get_text().strip()
        if not text:
            return
        rgba = self.color_btn.get_rgba()
        item = {
            "type": "text",
            "text": text,
            "font": self.font_combo.get_active_id() or "DejaVu Sans",
            "size_pt": self.size_spin.get_value(),
            "color": "#%02x%02x%02x" % (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)),
            "x": 0.1,
            "y": 0.1 + 0.04 * len(self.items) % 0.8,
        }
        self.items.append(item)
        self.selected = item
        self.canvas.queue_draw()

    def update_text(self):
        """Apply the panel's text/font/size/colour to the selected text item"""
        item = self.selected
        if not item or item["type"] != "text":
            return
        rgba = self.color_btn.get_rgba()
        item.update(
            text=self.text_entry.get_text() or item["text"],
            font=self.font_combo.get_active_id() or item["font"],
            size_pt=self.size_spin.get_value(),
            color="#%02x%02x%02x" % (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)),
        )
        self.canvas.queue_draw()

    def import_png(self):
        """Pick a PNG, offer to clear a white background, add it to the library"""
        Gtk = self.Gtk
        dlg = Gtk.FileChooserDialog(
            title="Import signature (PNG)", transient_for=self.dialog, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Import", Gtk.ResponseType.ACCEPT)
        flt = Gtk.FileFilter()
        flt.set_name("PNG images")
        flt.add_pattern("*.png")
        flt.add_pattern("*.PNG")
        dlg.add_filter(flt)
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not path:
            return
        clear = False
        if not has_transparency(path):
            ask = Gtk.MessageDialog(
                transient_for=self.dialog,
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="This PNG has no transparent background.",
            )
            ask.format_secondary_text("Make its white background transparent so only the ink shows?")
            clear = ask.run() == Gtk.ResponseType.YES
            ask.destroy()
        import_signature(path, clear_white=clear)
        self.refresh_library()

    def place_signature(self, path=None):
        """Place the selected library signature on the page"""
        path = path or self._selected_signature()
        if not path:
            self.hint.set_text("Select a signature in the library first (or import one).")
            return
        item = {"type": "image", "path": path, "x": 0.55, "y": 0.8, "w": 0.3}
        self.items.append(item)
        self.selected = item
        self.canvas.queue_draw()

    def remove_signature(self):
        """Delete the selected signature file from the library (placed copies stay)"""
        path = self._selected_signature()
        if path and os.path.exists(path):
            keep = os.path.join(self.ctx.scan.session_dir, os.path.basename(path))
            shutil.copy2(path, keep)  # items already placed keep working this session
            for item in self.items:
                if item.get("path") == path:
                    item["path"] = keep
            os.remove(path)
            self.refresh_library()

    def delete_selected(self):
        """Remove the selected item"""
        if self.selected in self.items:
            self.items.remove(self.selected)
            self.selected = None
            self.canvas.queue_draw()

    def apply_to_all(self):
        """Copy the selected item to the same position on every other page"""
        if not self.selected:
            return
        for i in range(len(self.pages)):
            if i != self.index:
                self.others.setdefault(i, []).append(copy.deepcopy(self.selected))
        self.hint.set_text(
            f"Will also be added to the other {len(self.pages) - 1} page(s) when you press Apply."
        )

    def move_item(self, item, fx, fy):
        """Move an item to page fractions (clamped to the page)"""
        item["x"], item["y"] = min(max(fx, 0.0), 0.98), min(max(fy, 0.0), 0.98)

    # -- geometry -------------------------------------------------------------------
    def _layout(self):
        """(scale, offset_x, offset_y, page_w, page_h) mapping page pixels to the canvas"""
        base = self._base_image()
        cw, ch = self.canvas.get_allocated_width(), self.canvas.get_allocated_height()
        scale = min(cw / base.width, ch / base.height) if base.width and base.height else 1
        ox, oy = (cw - base.width * scale) / 2, (ch - base.height * scale) / 2
        return scale, ox, oy, base.width, base.height

    def _base_image(self):
        """The page with rotation applied (no overlays), cached"""
        if self._base is None:
            from utils.util_imaging import flatten

            self._base = flatten(dict(self.page, overlays=[]))
        return self._base

    def _bbox(self, item, cr=None):
        """Item rectangle on the canvas: (x, y, w, h)"""
        scale, ox, oy, pw, ph = self._layout()
        x, y = ox + item["x"] * pw * scale, oy + item["y"] * ph * scale
        if item["type"] == "image":
            pix = self._sig_pixbuf(item["path"])
            w = item["w"] * pw * scale
            h = w * pix.get_height() / pix.get_width() if pix else w / 3
            return x, y, w, h
        px = item["size_pt"] * (self.page.get("dpi") or 300) / 72 * scale
        if cr is not None:
            cr.select_font_face(item["font"])
            cr.set_font_size(px)
            ext = cr.text_extents(item["text"])
            return x, y, ext.x_advance, px * 1.2
        return x, y, px * 0.6 * len(item["text"]), px * 1.2

    def _sig_pixbuf(self, path):
        """Full-size signature pixbuf (cached)"""
        from gi.repository import GdkPixbuf

        if path not in self._pix_cache:
            try:
                self._pix_cache[path] = GdkPixbuf.Pixbuf.new_from_file(path)
            except Exception:
                self._pix_cache[path] = None
        return self._pix_cache[path]

    # -- drawing ------------------------------------------------------------------
    def on_draw(self, widget, cr):
        """Draw the page, the overlays and the selection frame"""
        from gi.repository import Gdk, GdkPixbuf

        scale, ox, oy, pw, ph = self._layout()
        cr.set_source_rgb(0.12, 0.12, 0.12)
        cr.paint()
        base = self._base_image().convert("RGB")
        small = base.resize((max(1, int(pw * scale)), max(1, int(ph * scale))))
        data = small.tobytes()
        pix = GdkPixbuf.Pixbuf.new_from_data(
            data, GdkPixbuf.Colorspace.RGB, False, 8, small.width, small.height, small.width * 3
        )
        Gdk.cairo_set_source_pixbuf(cr, pix, ox, oy)
        cr.paint()
        for item in self.items:
            x, y, w, h = self._bbox(item, cr)
            if item["type"] == "text":
                c = Gdk.RGBA()
                c.parse(item["color"])
                cr.set_source_rgba(c.red, c.green, c.blue, 1)
                cr.select_font_face(item["font"])
                cr.set_font_size(h / 1.2)
                ascent = cr.font_extents()[0]
                cr.move_to(x, y + ascent)
                cr.show_text(item["text"])
            else:
                sig = self._sig_pixbuf(item["path"])
                if sig:
                    scaled = sig.scale_simple(max(1, int(w)), max(1, int(h)), GdkPixbuf.InterpType.BILINEAR)
                    Gdk.cairo_set_source_pixbuf(cr, scaled, x, y)
                    cr.paint()
            if item is self.selected:
                cr.set_source_rgb(0.0, 0.47, 0.84)  # framework accent
                cr.set_line_width(1.5)
                cr.rectangle(x - 3, y - 3, w + 6, h + 6)
                cr.stroke()
                cr.rectangle(x + w + 3 - HANDLE, y + h + 3 - HANDLE, HANDLE, HANDLE)
                cr.fill()

    # -- mouse / keyboard -------------------------------------------------------
    def _hit(self, ex, ey):
        """(item, 'resize'|'move') under the pointer, topmost first"""
        for item in reversed(self.items):
            x, y, w, h = self._bbox(item)
            if x + w + 3 - HANDLE <= ex <= x + w + 3 and y + h + 3 - HANDLE <= ey <= y + h + 3:
                return item, "resize"
            if x - 3 <= ex <= x + w + 3 and y - 3 <= ey <= y + h + 3:
                return item, "move"
        return None, None

    def on_press(self, widget, event):
        """Select / start moving or resizing; double-click text loads it for editing"""
        from gi.repository import Gdk

        self.canvas.grab_focus()
        item, mode = self._hit(event.x, event.y)
        self.selected = item
        if item and event.type == Gdk.EventType._2BUTTON_PRESS and item["type"] == "text":
            self.text_entry.set_text(item["text"])
            self.font_combo.set_active_id(item["font"])
            self.size_spin.set_value(item["size_pt"])
        self.drag = (mode, event.x, event.y, dict(item)) if item else None
        self.canvas.queue_draw()
        return True

    def on_motion(self, widget, event):
        """Move or resize the dragged item"""
        if not self.drag or not self.selected:
            return False
        mode, sx, sy, snap = self.drag
        scale, _ox, _oy, pw, ph = self._layout()
        dx, dy = (event.x - sx) / (pw * scale), (event.y - sy) / (ph * scale)
        item = self.selected
        if mode == "move":
            self.move_item(item, snap["x"] + dx, snap["y"] + dy)
        elif item["type"] == "image":
            item["w"] = min(max(snap["w"] + dx, 0.03), 1.0)
        else:  # text: scale the font size with the drag
            _x, _y, w0, _h = self._bbox(dict(snap))
            factor = max(0.2, (w0 + (event.x - sx)) / max(w0, 1))
            item["size_pt"] = min(max(snap["size_pt"] * factor, 4), 200)
        self.canvas.queue_draw()
        return True

    def on_release(self, widget, event):
        """End a drag"""
        self.drag = None
        return True

    def on_key(self, widget, event):
        """Delete / BackSpace removes the selected item"""
        from gi.repository import Gdk

        if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            self.delete_selected()
            return True
        return False

    # -- result -----------------------------------------------------------------------
    def commit(self):
        """Write the edited overlays back to the page(s)"""
        self.page["overlays"] = self.items
        for i, extra in self.others.items():
            self.pages[i].setdefault("overlays", []).extend(extra)

    def run(self):
        """Show modally; True if the user applied the changes"""
        applied = self.dialog.run() == self.Gtk.ResponseType.OK
        if applied:
            self.commit()
        self.dialog.destroy()
        return applied
