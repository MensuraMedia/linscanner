"""
Quick Edit
Add text and signatures to scanned pages, like mainstream PDF editors.

- Add Text: the pointer becomes a text cursor; click anywhere on the page and
  type. Alignment guides snap softly to earlier text (same edges, centre,
  equal spacing, symmetry) without locking; hold Alt to place freely.
- Signatures: up to 4 saved signatures (transparent PNGs) that persist between
  sessions. Import a PNG, or type your name in a signature font (quick browser
  of every font) and save it as a Signature. Click a saved signature, then
  click on the page to place it; drag the corner square to resize.
- Items can be selected, moved (with guides), resized, edited (double-click
  text), deleted and applied to every page. Edits are overlays stored on the
  page and flattened only when saving (non-destructive).

Overlay model (positions/sizes are fractions of the page):
  {"type": "text", "text": str, "font": family, "size_pt": float, "color": "#rrggbb", "x": f, "y": f}
  {"type": "image", "path": signature.png, "x": f, "y": f, "w": f (width as page fraction)}
"""

import copy
import os

from features import BaseFeature
from utils.util_fonts import import_fonts, render_text, signature_fonts, text_fonts, text_metrics
from utils.util_guides import Box, snap
from utils.util_signatures import (
    MAX_SIGNATURES,
    LibraryFull,
    has_transparency,
    library,
    prepare_png,
    remove_signature,
    save_signature,
    typed_signature,
)

HANDLE = 10  # px: resize handle size on the canvas
SNAP_PX = 8  # px: how close to a guide an item must be to snap
DEFAULT_SIGNATURE_WIDTH = 0.3  # page fraction
SIGNATURE_INK = "#1a1a1a"


def import_signature(path, clear_white=False):
    """Add a PNG to the signature library (optionally making near-white transparent); returns the new path"""
    name = os.path.splitext(os.path.basename(path))[0]
    return save_signature(prepare_png(path, clear_white), name)


def _hex(rgba):
    """Gdk.RGBA -> '#rrggbb'"""
    return "#%02x%02x%02x" % (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))


def on_paper(img, pad=10):
    """A transparent signature on a white "paper" tile, so dark ink shows on the dark theme"""
    from PIL import Image

    tile = Image.new("RGB", (img.width + 2 * pad, img.height + 2 * pad), "white")
    tile.paste(img, (pad, pad), img if img.mode == "RGBA" else None)
    return tile


def _pixbuf(img):
    """Pillow image -> GdkPixbuf (RGBA kept)"""
    from gi.repository import GdkPixbuf, GLib

    img = img if img.mode in ("RGB", "RGBA") else img.convert("RGBA")
    alpha = img.mode == "RGBA"
    stride = img.width * (4 if alpha else 3)
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(img.tobytes()), GdkPixbuf.Colorspace.RGB, alpha, 8, img.width, img.height, stride
    )


class Feature(BaseFeature):
    """Text and signatures on scanned pages"""

    id = "quick_edit"
    name = "Quick Edit (text and signatures)"
    description = (
        "Click anywhere to type text (alignment guides help line it up), and add up to 4 saved "
        "signatures from a PNG or a signature font; move, resize and re-apply them."
    )
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
        """Open the editor for the selected page; store overlays on Apply"""
        pages = preview_page.ctx.scan.pages
        index = preview_page.preview.selected
        if not pages or index < 0:
            return
        editor = QuickEditor(preview_page.ctx, pages, index)
        if editor.run():
            preview_page.ctx.emit("pages-changed")
            preview_page.set_status("Quick Edit applied. Text and signatures are added when you save.")


class QuickEditor:
    """Modal editor window: canvas + tools. run() returns True if changes were applied."""

    def __init__(self, ctx, pages, index):
        """Build the dialog for pages[index] (overlays are edited on a copy)"""
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gdk, GLib, Gtk

        self.Gtk, self.Gdk, self.GLib = Gtk, Gdk, GLib
        self.ctx, self.pages, self.index = ctx, pages, index
        self.page = pages[index]
        self.items = copy.deepcopy(self.page.get("overlays") or [])
        self.others = {}  # page index -> overlays added via "Apply to all pages"
        self.selected = None
        self.editing = None  # text item being typed into
        self.mode = "select"  # select | text | place
        self.pending_signature = None  # path placed by the next click (place mode)
        self.drag = None  # ("move"|"resize", start canvas x, y, item snapshot)
        self.hover = None  # Box of what a click would create (text / place mode)
        self.guides = []
        self.caret_on = True
        self._loading = False
        self._base = None
        self._base_pix = {}  # canvas size -> scaled page pixbuf
        self._text_pix = {}  # (text, font, size, colour, scale) -> (pixbuf, dx, dy)
        self._sig_cache = {}  # path -> Pillow image
        self._sig_pix = {}  # (path, w, h) -> scaled pixbuf

        self.dialog = Gtk.Dialog(title=f"Quick Edit: page {index + 1}", transient_for=ctx.window, modal=True)
        self.dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Apply", Gtk.ResponseType.OK)
        self.dialog.set_default_size(1200, 860)
        body = Gtk.Box(spacing=12)
        body.set_margin_start(10)
        body.set_margin_end(10)
        self.dialog.get_content_area().pack_start(body, True, True, 0)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(620, 760)
        self.canvas.set_can_focus(True)
        self.canvas.add_events(
            self._mask(
                "BUTTON_PRESS_MASK",
                "BUTTON_RELEASE_MASK",
                "POINTER_MOTION_MASK",
                "KEY_PRESS_MASK",
                "LEAVE_NOTIFY_MASK",
                "FOCUS_CHANGE_MASK",
            )
        )
        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("button-press-event", self.on_press)
        self.canvas.connect("motion-notify-event", self.on_motion)
        self.canvas.connect("button-release-event", self.on_release)
        self.canvas.connect("key-press-event", self.on_key)
        self.canvas.connect("leave-notify-event", self.on_leave)
        self.canvas.connect("realize", self.on_realize)
        body.pack_start(self.canvas, True, True, 0)
        body.pack_start(self._tools(), False, False, 0)

        # typing (with dead keys / compose / input methods)
        self.im = Gtk.IMMulticontext()
        self.im.connect("commit", self.on_commit)
        self.canvas.connect("focus-in-event", lambda *_: self.im.focus_in())
        self.canvas.connect("focus-out-event", lambda *_: self.im.focus_out())
        self._blink = GLib.timeout_add(530, self._toggle_caret)
        self.dialog.connect("destroy", lambda *_: self._stop_blink())
        self.dialog.show_all()

    def _stop_blink(self):
        """Stop the caret timer when the dialog closes"""
        if self._blink:
            self.GLib.source_remove(self._blink)
            self._blink = None

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
        """Right-hand panel: tools, text style, guides, signature slots, item actions"""
        Gtk, Gdk = self.Gtk, self.Gdk
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(380, -1)

        panel.pack_start(self._heading("Tools"), False, False, 0)
        row = Gtk.Box(spacing=0)
        row.get_style_context().add_class("segment")  # the active tool is highlighted
        row.set_halign(Gtk.Align.START)
        self.select_tool = Gtk.RadioButton.new_with_label(None, "Select / move")
        self.text_tool = Gtk.RadioButton.new_with_label_from_widget(self.select_tool, "Add Text")
        for b in (self.select_tool, self.text_tool):
            b.set_mode(False)  # look like toggle buttons
            row.pack_start(b, False, False, 0)
        self.text_tool.connect("toggled", self._on_tool_toggled)
        panel.pack_start(row, False, False, 0)

        panel.pack_start(self._heading("Text"), False, False, 0)
        self.font_combo = Gtk.ComboBoxText()
        for family in text_fonts():
            self.font_combo.append(family, family)
        self.font_combo.set_active(0)
        self.size_spin = Gtk.SpinButton.new_with_range(6, 96, 1)
        self.size_spin.set_value(14)
        self.color_btn = Gtk.ColorButton()
        black = Gdk.RGBA()
        black.parse("#000000")
        self.color_btn.set_rgba(black)
        row = Gtk.Box(spacing=6)
        row.pack_start(self.font_combo, True, True, 0)
        row.pack_start(self.size_spin, False, False, 0)
        row.pack_start(self.color_btn, False, False, 0)
        panel.pack_start(row, False, False, 0)
        for w, signal in (
            (self.font_combo, "changed"),
            (self.size_spin, "value-changed"),
            (self.color_btn, "color-set"),
        ):
            w.connect(signal, lambda *_: self.style_changed())
        # kept for scripted use and tests: text set here is added by add_text()
        self.text_entry = Gtk.Entry()

        self.guides_check = Gtk.CheckButton(label="Alignment guides (hold Alt to place freely)")
        self.guides_check.set_active(True)
        panel.pack_start(self.guides_check, False, False, 0)

        panel.pack_start(self._heading("Signatures"), False, False, 0)
        self.slots = Gtk.Grid(column_spacing=6, row_spacing=6)
        self.slots.set_column_homogeneous(True)
        panel.pack_start(self.slots, False, False, 0)
        self.slot_info = Gtk.Label()
        self.slot_info.set_xalign(0)
        self.slot_info.get_style_context().add_class("muted")
        panel.pack_start(self.slot_info, False, False, 0)
        row = Gtk.Box(spacing=6)
        imp = Gtk.Button(label="Import PNG…")
        imp.connect("clicked", lambda *_: self.import_png())
        typed = Gtk.Button(label="Signature fonts…")
        typed.connect("clicked", lambda *_: self.type_signature())
        self.remove_btn = Gtk.Button(label="Remove")
        self.remove_btn.set_tooltip_text("Remove the selected signature from its slot")
        self.remove_btn.connect("clicked", lambda *_: self.remove_selected_signature())
        for b in (imp, typed, self.remove_btn):
            row.pack_start(b, False, False, 0)
        panel.pack_start(row, False, False, 0)
        self.slot_selected = None
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
        self.hint = Gtk.Label()
        self.hint.set_line_wrap(True)
        self.hint.set_xalign(0)
        self.hint.get_style_context().add_class("muted")
        panel.pack_start(self.hint, False, False, 0)
        self.show_hint()
        return panel

    def _heading(self, text):
        """Section heading label"""
        lbl = self.Gtk.Label(label=text)
        lbl.set_xalign(0)
        lbl.get_style_context().add_class("card-title")
        return lbl

    def show_hint(self, text=None):
        """Help text for the current tool (or a message)"""
        default = {
            "select": "Click an item to select it · drag to move · drag the corner square to resize · "
            "double-click text to edit · Delete removes · arrow keys nudge",
            "text": "Click anywhere on the page and type. Enter starts a new line below, Esc finishes. "
            "Guides appear when your text lines up with earlier text.",
            "place": "Click on the page where the signature should go (Esc cancels). "
            "Drag its corner square afterwards to resize it.",
        }[self.mode]
        self.hint.set_text(text or default)

    # -- signature slots ------------------------------------------------------------
    def refresh_library(self):
        """Show the 4 signature slots (saved signatures, then empty slots)"""
        Gtk = self.Gtk
        for child in self.slots.get_children():
            self.slots.remove(child)
        saved = library()
        if self.slot_selected not in saved:
            self.slot_selected = None
        for n in range(MAX_SIGNATURES):
            btn = Gtk.Button()
            btn.set_size_request(170, 72)
            btn.get_style_context().add_class("thumb")
            if n < len(saved):
                path = saved[n]
                try:
                    sig = self._signature_image(path).copy()
                    sig.thumbnail((140, 46))
                    btn.add(Gtk.Image.new_from_pixbuf(_pixbuf(on_paper(sig, 6))))
                except Exception:
                    btn.add(Gtk.Label(label=os.path.basename(path)))
                btn.set_tooltip_text("Click, then click on the page to place this signature")
                btn.connect("clicked", lambda _b, p=path: self.choose_signature(p))
                if path == self.slot_selected:
                    btn.get_style_context().add_class("selected")
            else:
                lbl = Gtk.Label(label="Empty slot")
                lbl.get_style_context().add_class("muted")
                btn.add(lbl)
                btn.set_tooltip_text("Add a signature: import a PNG or use a signature font")
                btn.connect("clicked", lambda b: self._empty_slot_menu(b))
            self.slots.attach(btn, n % 2, n // 2, 1, 1)
        self.slots.show_all()
        self.slot_info.set_text(f"{len(saved)} of {MAX_SIGNATURES} saved · kept between sessions")
        self.remove_btn.set_sensitive(self.slot_selected is not None)

    def _empty_slot_menu(self, button):
        """Menu on an empty slot: import a PNG or use a signature font"""
        Gtk = self.Gtk
        menu = Gtk.Menu()
        for text, action in (("Import PNG…", self.import_png), ("Signature fonts…", self.type_signature)):
            item = Gtk.MenuItem(label=text)
            item.connect("activate", lambda *_a, f=action: f())
            menu.append(item)
        menu.show_all()
        menu.popup_at_widget(button, self.Gdk.Gravity.SOUTH_WEST, self.Gdk.Gravity.NORTH_WEST, None)

    def choose_signature(self, path):
        """Select a saved signature and arm placing it with the next click"""
        self.slot_selected = path
        self.refresh_library()
        self.place_signature_on_click(path)

    def remove_selected_signature(self):
        """Delete the selected saved signature (copies already placed stay on the page)"""
        path = self.slot_selected
        if not path:
            return
        keep = os.path.join(self.ctx.scan.session_dir, os.path.basename(path))
        img = self._signature_image(path)
        if img is not None:
            img.save(keep)  # placed copies keep working this session
            for item in self.items:
                if item.get("path") == path:
                    item["path"] = keep
        remove_signature(path)
        self._sig_cache.pop(path, None)
        self.slot_selected = None
        if self.mode == "place":
            self.set_mode("select")
        self.refresh_library()

    def _library_full_message(self):
        """Explain that the 4 slots are used"""
        self.show_hint(
            f"All {MAX_SIGNATURES} signature slots are used. Select one and press Remove to free a slot."
        )

    def import_png(self):
        """Pick a PNG, offer to clear a white background, save it to a slot"""
        Gtk = self.Gtk
        if len(library()) >= MAX_SIGNATURES:
            self._library_full_message()
            return
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
        try:
            saved = import_signature(path, clear_white=clear)
        except LibraryFull:
            self._library_full_message()
            return
        self.choose_signature(saved)

    def type_signature(self):
        """Signature font browser: type a name, pick a font, place it and/or save it"""
        dlg = SignatureFontDialog(self.dialog, self.Gtk, self.Gdk, self.GLib)
        result = dlg.run()
        if not result:
            return
        action, img, name = result
        if action == "save":
            try:
                path = save_signature(img, name)
            except LibraryFull:
                self._library_full_message()
                return
            self.choose_signature(path)
        else:  # place once, without using a slot
            path = save_signature(img, name, folder=self.ctx.scan.session_dir)
            self.place_signature_on_click(path)

    # -- modes -------------------------------------------------------------------
    def _on_tool_toggled(self, button):
        """Tool buttons: Add Text / Select"""
        wanted = "text" if button.get_active() else "select"
        if self.mode != wanted and not (self.mode == "place" and wanted == "select"):
            self.set_mode(wanted)

    def set_mode(self, mode):
        """Switch tool: select | text | place (pointer shape follows)"""
        self.finish_editing()
        self.mode = mode
        if mode != "place":
            self.pending_signature = None
        want_text = mode == "text"
        if self.text_tool.get_active() != want_text:
            (self.text_tool if want_text else self.select_tool).set_active(True)
        self.hover = None
        self.guides = []
        self._set_cursor()
        self.show_hint()
        self.canvas.queue_draw()

    def _set_cursor(self):
        """Text cursor for Add Text, crosshair while placing, default otherwise"""
        window = self.canvas.get_window()
        if not window:
            return
        name = {"text": "text", "place": "crosshair"}.get(self.mode, "default")
        window.set_cursor(self.Gdk.Cursor.new_from_name(window.get_display(), name))

    def on_realize(self, widget):
        """Connect the input method to the canvas window"""
        self.im.set_client_window(widget.get_window())
        self._set_cursor()

    def place_signature_on_click(self, path):
        """Arm place mode: the next click on the page places this signature"""
        self.set_mode("select")
        self.mode = "place"
        self.pending_signature = path
        self._set_cursor()
        self.show_hint()

    # -- text style ----------------------------------------------------------------
    def current_style(self):
        """(font, size_pt, colour) from the panel"""
        return (
            self.font_combo.get_active_id() or "DejaVu Sans",
            self.size_spin.get_value(),
            _hex(self.color_btn.get_rgba()),
        )

    def style_changed(self):
        """Font / size / colour changed: restyle the text being edited or selected"""
        if self._loading:
            return
        item = self.editing or self.selected
        if item and item["type"] == "text":
            item["font"], item["size_pt"], item["color"] = self.current_style()
            self.canvas.queue_draw()

    def _load_style(self, item):
        """Show a text item's style in the panel (without restyling it)"""
        self._loading = True
        self.font_combo.set_active_id(item["font"])
        self.size_spin.set_value(item["size_pt"])
        c = self.Gdk.RGBA()
        c.parse(item["color"])
        self.color_btn.set_rgba(c)
        self._loading = False

    # -- actions (also used by tests) ------------------------------------------------
    def new_text_item(self, x, y, text=""):
        """Create a text item at page fractions (x, y) with the panel's style"""
        font, size, color = self.current_style()
        item = {"type": "text", "text": text, "font": font, "size_pt": size, "color": color, "x": x, "y": y}
        self.items.append(item)
        self.selected = item
        return item

    def add_text(self):
        """Add the text from text_entry near the top-left (scripted use)"""
        text = self.text_entry.get_text().strip()
        if text:
            self.new_text_item(0.1, 0.1 + 0.04 * len(self.items) % 0.8, text)
            self.canvas.queue_draw()

    def start_editing(self, item):
        """Type into a text item on the canvas"""
        self.finish_editing()
        self.editing = item
        self.selected = item
        self._load_style(item)
        self.caret_on = True
        self.canvas.grab_focus()
        self.canvas.queue_draw()

    def finish_editing(self):
        """Stop typing; an empty text item is removed"""
        item = self.editing
        self.editing = None
        if item is not None and not item["text"].strip():
            if item in self.items:
                self.items.remove(item)
            if self.selected is item:
                self.selected = None
        self.canvas.queue_draw()

    def type_text(self, text):
        """Insert typed text into the item being edited"""
        if self.editing is not None:
            self.editing["text"] += text
            self.caret_on = True
            self.canvas.queue_draw()

    def on_commit(self, _im, text):
        """Characters from the input method"""
        self.type_text(text)

    def place_signature(self, path, x=0.55, y=0.8):
        """Place a signature with its top-left at page fractions (x, y)"""
        item = {"type": "image", "path": path, "x": x, "y": y, "w": DEFAULT_SIGNATURE_WIDTH}
        self.items.append(item)
        self.selected = item
        self.canvas.queue_draw()
        return item

    def delete_selected(self):
        """Remove the selected item"""
        if self.selected in self.items:
            if self.editing is self.selected:
                self.editing = None
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
        self.show_hint(f"Will also be added to the other {len(self.pages) - 1} page(s) when you press Apply.")

    def move_item(self, item, fx, fy):
        """Move an item to page fractions (clamped to the page)"""
        item["x"], item["y"] = min(max(fx, 0.0), 0.98), min(max(fy, 0.0), 0.98)

    # -- geometry -------------------------------------------------------------------
    def _layout(self):
        """(scale, offset_x, offset_y, page_w, page_h) mapping page pixels to the canvas"""
        base = self._base_image()
        cw, ch = max(self.canvas.get_allocated_width(), 1), max(self.canvas.get_allocated_height(), 1)
        scale = min(cw / base.width, ch / base.height) if base.width and base.height else 1
        ox, oy = (cw - base.width * scale) / 2, (ch - base.height * scale) / 2
        return scale, ox, oy, base.width, base.height

    def _base_image(self):
        """The page with rotation applied (no overlays), cached"""
        if self._base is None:
            from utils.util_imaging import flatten

            self._base = flatten(dict(self.page, overlays=[]))
        return self._base

    def _dpi(self):
        """Page resolution (text sizes are in points)"""
        return self.page.get("dpi") or 300

    def _signature_image(self, path):
        """Signature as a Pillow RGBA image (cached)"""
        if path not in self._sig_cache:
            from PIL import Image

            try:
                self._sig_cache[path] = Image.open(path).convert("RGBA")
            except OSError:
                self._sig_cache[path] = None
        return self._sig_cache[path]

    def item_box(self, item):
        """Item rectangle in page fractions (text: from its anchor, advance and line height)"""
        _s, _ox, _oy, pw, ph = self._layout()
        if item["type"] == "text":
            px = item["size_pt"] * self._dpi() / 72
            adv, line = text_metrics(item["text"] or " ", item["font"], px)
            return Box(item["x"], item["y"], adv / pw, line / ph, "text")
        sig = self._signature_image(item["path"])
        w = item["w"]
        h = (w * pw * sig.height / sig.width) / ph if sig else w / 3
        return Box(item["x"], item["y"], w, h, "image")

    def _bbox(self, item):
        """Item rectangle on the canvas: (x, y, w, h)"""
        scale, ox, oy, pw, ph = self._layout()
        b = self.item_box(item)
        return ox + b.left * pw * scale, oy + b.top * ph * scale, b.width * pw * scale, b.height * ph * scale

    def to_page(self, ex, ey):
        """Canvas pixels -> page fractions"""
        scale, ox, oy, pw, ph = self._layout()
        return (ex - ox) / (pw * scale), (ey - oy) / (ph * scale)

    def snapped(self, box, moving=None, free=False):
        """(left, top) for box snapped to the alignment guides; sets self.guides"""
        if free or not self.guides_check.get_active():
            self.guides = []
            return box.left, box.top
        scale, _ox, _oy, pw, ph = self._layout()
        others = [
            self.item_box(i)
            for i in self.items
            if i is not moving and not (i["type"] == "text" and not i["text"].strip())
        ]
        left, top, self.guides = snap(box, others, SNAP_PX / (pw * scale), SNAP_PX / (ph * scale))
        return left, top

    def _ghost_box(self, fx, fy):
        """Box of what the next click would create at (fx, fy)"""
        _s, _ox, _oy, pw, ph = self._layout()
        if self.mode == "place" and self.pending_signature:
            sig = self._signature_image(self.pending_signature)
            w = DEFAULT_SIGNATURE_WIDTH
            h = (w * pw * sig.height / sig.width) / ph if sig else w / 3
            return Box(fx - w / 2, fy - h / 2, w, h, "image")  # centred on the pointer
        font, size, _c = self.current_style()
        _adv, line = text_metrics(" ", font, size * self._dpi() / 72)
        return Box(fx, fy - line / ph / 2, 0, line / ph, "text")

    # -- drawing ------------------------------------------------------------------
    def _page_pixbuf(self, w, h):
        """The page scaled to (w, h), cached per canvas size (drawing stays fast while dragging)"""
        key = (w, h)
        if key not in self._base_pix:
            from PIL import Image

            small = self._base_image().convert("RGB").resize((max(1, w), max(1, h)), Image.BILINEAR)
            self._base_pix = {key: _pixbuf(small)}
        return self._base_pix[key]

    def _text_pixbuf(self, item, scale):
        """(pixbuf, dx, dy) for a text item at canvas scale, cached"""
        key = (item["text"], item["font"], item["size_pt"], item["color"], round(scale, 5))
        if key not in self._text_pix:
            px = item["size_pt"] * self._dpi() / 72 * scale
            img, dx, dy = render_text(item["text"], item["font"], px, item["color"])
            if len(self._text_pix) > 200:
                self._text_pix.clear()
            self._text_pix[key] = (_pixbuf(img), dx, dy)
        return self._text_pix[key]

    def _signature_pixbuf(self, path, w, h):
        """Signature scaled to (w, h) on the canvas, cached"""
        key = (path, w, h)
        if key not in self._sig_pix:
            from PIL import Image

            sig = self._signature_image(path)
            if sig is None:
                return None
            if len(self._sig_pix) > 50:
                self._sig_pix.clear()
            self._sig_pix[key] = _pixbuf(sig.resize((max(1, w), max(1, h)), Image.LANCZOS))
        return self._sig_pix[key]

    GUIDE_COLORS = {
        "align": (0.0, 0.47, 0.84),
        "center": (0.85, 0.2, 0.55),
        "mirror": (0.85, 0.2, 0.55),
        "spacing": (0.1, 0.65, 0.35),
    }

    def on_draw(self, widget, cr):
        """Draw the page, the overlays, guides, the caret and the selection frame"""
        Gdk = self.Gdk
        scale, ox, oy, pw, ph = self._layout()
        cr.set_source_rgb(0.12, 0.12, 0.12)
        cr.paint()
        Gdk.cairo_set_source_pixbuf(cr, self._page_pixbuf(int(pw * scale), int(ph * scale)), ox, oy)
        cr.paint()
        for item in self.items:
            x, y, w, h = self._bbox(item)
            if item["type"] == "text":
                if item["text"]:
                    pix, dx, dy = self._text_pixbuf(item, scale)
                    Gdk.cairo_set_source_pixbuf(cr, pix, x + dx, y + dy)
                    cr.paint()
                if item is self.editing:
                    w = w if item["text"] else 0
                    if self.caret_on:
                        cr.set_source_rgb(0.0, 0.47, 0.84)
                        cr.rectangle(x + w + 1, y, 2, h)
                        cr.fill()
            else:
                pix = self._signature_pixbuf(item["path"], int(w), int(h))
                if pix:
                    Gdk.cairo_set_source_pixbuf(cr, pix, x, y)
                    cr.paint()
            if item is self.selected and item is not self.editing:
                cr.set_source_rgb(0.0, 0.47, 0.84)  # framework accent
                cr.set_line_width(1.5)
                cr.rectangle(x - 3, y - 3, w + 6, h + 6)
                cr.stroke()
                cr.rectangle(x + w + 3 - HANDLE, y + h + 3 - HANDLE, HANDLE, HANDLE)
                cr.fill()

        # ghost of what a click would create
        if self.hover and self.mode in ("text", "place"):
            b = self.hover
            gx, gy = ox + b.left * pw * scale, oy + b.top * ph * scale
            cr.set_source_rgba(0.0, 0.47, 0.84, 0.8)
            if self.mode == "text":
                cr.rectangle(gx, gy, 2, b.height * ph * scale)
                cr.fill()
            else:
                cr.set_line_width(1)
                cr.set_dash([4, 3])
                cr.rectangle(gx, gy, b.width * pw * scale, b.height * ph * scale)
                cr.stroke()
                cr.set_dash([])

        # alignment guides
        cr.set_line_width(1)
        for g in self.guides:
            cr.set_source_rgba(*self.GUIDE_COLORS.get(g.kind, (0.0, 0.47, 0.84)), 0.9)
            cr.set_dash([5, 4])
            if g.axis == "v":
                gx = ox + g.value * pw * scale
                cr.move_to(gx, oy)
                cr.line_to(gx, oy + ph * scale)
            else:
                gy = oy + g.value * ph * scale
                cr.move_to(ox, gy)
                cr.line_to(ox + pw * scale, gy)
            cr.stroke()
        cr.set_dash([])

    def _toggle_caret(self):
        """Blink the caret while typing"""
        if self.editing is not None:
            self.caret_on = not self.caret_on
            self.canvas.queue_draw()
        return True

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

    def _free(self, event):
        """Alt held: place / move without snapping"""
        return bool(event.state & self.Gdk.ModifierType.MOD1_MASK)

    def on_press(self, widget, event):
        """Select, start typing, place a signature or start moving / resizing"""
        Gdk = self.Gdk
        self.canvas.grab_focus()
        if event.button != 1:
            return False
        fx, fy = self.to_page(event.x, event.y)
        item, mode = self._hit(event.x, event.y)

        if self.mode == "place" and self.pending_signature:
            box = self._ghost_box(fx, fy)
            left, top = self.snapped(box, free=self._free(event))
            placed = self.place_signature(
                self.pending_signature, min(max(left, 0), 0.98), min(max(top, 0), 0.98)
            )
            self.set_mode("select")
            self.selected = placed
            self.canvas.queue_draw()
            return True

        if self.mode == "text":
            if item is not None and item["type"] == "text":
                self.start_editing(item)  # click into existing text to continue it
                return True
            self.finish_editing()
            box = self._ghost_box(fx, fy)
            left, top = self.snapped(box, free=self._free(event))
            self.start_editing(self.new_text_item(min(max(left, 0), 0.98), min(max(top, 0), 0.98)))
            self.guides = []
            return True

        # select mode
        if self.editing is not None and item is not self.editing:
            self.finish_editing()
        self.selected = item
        if item and event.type == Gdk.EventType._2BUTTON_PRESS and item["type"] == "text":
            self.start_editing(item)
            return True
        if item and item["type"] == "text":
            self._load_style(item)
        self.drag = (mode, event.x, event.y, dict(item)) if item else None
        self.canvas.queue_draw()
        return True

    def on_motion(self, widget, event):
        """Move / resize the dragged item, or show where a click would place something"""
        if self.mode in ("text", "place") and not self.drag:
            fx, fy = self.to_page(event.x, event.y)
            box = self._ghost_box(fx, fy)
            box.left, box.top = self.snapped(box, free=self._free(event))
            self.hover = box
            self.canvas.queue_draw()
            return True
        if not self.drag or not self.selected:
            return False
        mode, sx, sy, start = self.drag
        scale, _ox, _oy, pw, ph = self._layout()
        dx, dy = (event.x - sx) / (pw * scale), (event.y - sy) / (ph * scale)
        item = self.selected
        if mode == "move":
            box = self.item_box(dict(start, x=start["x"] + dx, y=start["y"] + dy))
            left, top = self.snapped(box, moving=item, free=self._free(event))
            self.move_item(item, left, top)
        elif item["type"] == "image":
            item["w"] = min(max(start["w"] + dx, 0.03), 1.0)
        else:  # text: scale the font size with the drag
            w0 = self.item_box(dict(start)).width * pw * scale
            factor = max(0.2, (w0 + (event.x - sx)) / max(w0, 1))
            item["size_pt"] = round(min(max(start["size_pt"] * factor, 4), 200), 1)
            self._load_style(item)
        self.canvas.queue_draw()
        return True

    def on_release(self, widget, event):
        """End a drag"""
        self.drag = None
        self.guides = []
        self.canvas.queue_draw()
        return True

    def on_leave(self, *_):
        """Pointer left the canvas: hide the ghost and guides"""
        if not self.drag:
            self.hover = None
            self.guides = []
            self.canvas.queue_draw()

    def on_key(self, widget, event):
        """Typing, Enter (new line below), Esc, Delete and arrow-key nudging"""
        Gdk = self.Gdk
        key = event.keyval
        if self.editing is not None:
            if key == Gdk.KEY_Escape:
                self.finish_editing()
                return True
            if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.new_line()
                return True
            if key == Gdk.KEY_BackSpace:
                self.editing["text"] = self.editing["text"][:-1]
                self.canvas.queue_draw()
                return True
            return bool(self.im.filter_keypress(event))
        if key == Gdk.KEY_Escape and self.mode != "select":
            self.set_mode("select")
            return True
        if key in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            self.delete_selected()
            return True
        nudge = {Gdk.KEY_Left: (-1, 0), Gdk.KEY_Right: (1, 0), Gdk.KEY_Up: (0, -1), Gdk.KEY_Down: (0, 1)}
        if key in nudge and self.selected:
            scale, _ox, _oy, pw, ph = self._layout()
            nx, ny = nudge[key]
            self.move_item(
                self.selected, self.selected["x"] + nx / (pw * scale), self.selected["y"] + ny / (ph * scale)
            )
            self.canvas.queue_draw()
            return True
        return False

    def new_line(self):
        """Enter while typing: finish this line and start the next one below it, same left edge"""
        item = self.editing
        box = self.item_box(item)
        self.finish_editing()
        if item in self.items:
            y = min(item["y"] + box.height * 1.5, 0.98)  # the same spacing the guides suggest
            self.start_editing(self.new_text_item(item["x"], y))

    # -- result -----------------------------------------------------------------------
    def commit(self):
        """Write the edited overlays back to the page(s)"""
        self.finish_editing()
        self.page["overlays"] = self.items
        for i, extra in self.others.items():
            self.pages[i].setdefault("overlays", []).extend(extra)
        from utils.util_logging import get_logger

        texts = sum(1 for o in self.items if o["type"] == "text")  # counts only, never the text
        get_logger("quick_edit").info(
            "page %d: %d text item(s), %d signature(s); copied to %d other page(s)",
            self.index + 1,
            texts,
            len(self.items) - texts,
            len(self.others),
        )

    def run(self):
        """Show modally; True if the user applied the changes"""
        applied = self.dialog.run() == self.Gtk.ResponseType.OK
        if applied:
            self.commit()
        self.dialog.destroy()
        return applied


class SignatureFontDialog:
    """Type a name and see it in every signature font; place it, or save it as a Signature"""

    PREVIEW_PX = 44
    PLACE, SAVE = 1, 2  # dialog responses

    def __init__(self, parent, Gtk, Gdk, GLib):
        """Name entry, ink colour, font list with live previews, Add fonts…"""
        self.Gtk, self.Gdk, self.GLib = Gtk, Gdk, GLib
        self.dialog = Gtk.Dialog(title="Signature fonts", transient_for=parent, modal=True)
        self.dialog.set_default_size(640, 660)
        self.dialog.add_buttons(
            "_Cancel", Gtk.ResponseType.CANCEL, "_Place on page", self.PLACE, "_Save as Signature", self.SAVE
        )
        box = self.dialog.get_content_area()
        box.set_spacing(8)
        for m in (box.set_margin_start, box.set_margin_end, box.set_margin_top):
            m(12)

        row = Gtk.Box(spacing=8)
        self.name = Gtk.Entry()
        self.name.set_placeholder_text("Type your name…")
        self.name.connect("changed", lambda *_: self._schedule())
        self.ink = Gtk.ColorButton()
        ink = Gdk.RGBA()
        ink.parse(SIGNATURE_INK)
        self.ink.set_rgba(ink)
        self.ink.set_tooltip_text("Ink colour")
        self.ink.connect("color-set", lambda *_: self._schedule())
        row.pack_start(self.name, True, True, 0)
        row.pack_start(self.ink, False, False, 0)
        box.pack_start(row, False, False, 0)

        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.connect("row-activated", lambda *_: self.dialog.response(self.PLACE))
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.add(self.list)
        box.pack_start(scroller, True, True, 0)

        row = Gtk.Box(spacing=8)
        add = Gtk.Button(label="Add fonts…")
        add.connect("clicked", lambda *_: self.add_fonts())
        note = Gtk.Label(label="Add .ttf, .otf or .zip font files. Fonts you add stay on this computer.")
        note.get_style_context().add_class("muted")
        note.set_xalign(0)
        note.set_line_wrap(True)
        row.pack_start(add, False, False, 0)
        row.pack_start(note, True, True, 0)
        box.pack_start(row, False, False, 0)
        self._pending = None
        self.fonts = []
        self.rebuild()
        self.dialog.show_all()

    def _schedule(self):
        """Re-render previews shortly after typing stops"""
        if self._pending:
            self.GLib.source_remove(self._pending)
        self._pending = self.GLib.timeout_add(200, self.rebuild)

    def text(self):
        """The name to render"""
        return self.name.get_text().strip() or "Your Name"

    def rebuild(self):
        """One row per signature font showing the name in that font"""
        Gtk = self.Gtk
        self._pending = None
        selected = self.list.get_selected_row()
        keep = selected.family if selected else None
        for child in self.list.get_children():
            self.list.remove(child)
        self.fonts = signature_fonts()
        color = _hex(self.ink.get_rgba())
        for f in self.fonts:
            img, _dx, _dy = render_text(self.text(), f["family"], self.PREVIEW_PX, color)
            row = Gtk.ListBoxRow()
            row.family = f["family"]
            inner = Gtk.Box(spacing=12)
            for m in (
                inner.set_margin_start,
                inner.set_margin_end,
                inner.set_margin_top,
                inner.set_margin_bottom,
            ):
                m(6)
            inner.pack_start(Gtk.Image.new_from_pixbuf(_pixbuf(on_paper(img))), False, False, 0)
            label = Gtk.Label(label=f["family"] + ("" if f["bundled"] else "  (your font)"))
            label.get_style_context().add_class("muted")
            label.set_xalign(1)
            inner.pack_end(label, False, False, 0)
            row.add(inner)
            self.list.add(row)
            if f["family"] == keep:
                self.list.select_row(row)
        if not self.list.get_selected_row() and self.list.get_children():
            self.list.select_row(self.list.get_children()[0])
        self.list.show_all()
        return False

    def add_fonts(self):
        """Import font files (or zips of fonts) into the user font folder"""
        Gtk = self.Gtk
        dlg = Gtk.FileChooserDialog(
            title="Add signature fonts", transient_for=self.dialog, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Add", Gtk.ResponseType.ACCEPT)
        dlg.set_select_multiple(True)
        flt = Gtk.FileFilter()
        flt.set_name("Fonts (.ttf, .otf, .zip)")
        for pattern in ("*.ttf", "*.otf", "*.zip", "*.TTF", "*.OTF", "*.ZIP"):
            flt.add_pattern(pattern)
        dlg.add_filter(flt)
        paths = dlg.get_filenames() if dlg.run() == Gtk.ResponseType.ACCEPT else []
        dlg.destroy()
        if paths:
            import_fonts(paths)
            self.rebuild()

    def result(self, response):
        """(action "place"|"save", RGBA image, name) for a response, or None"""
        row = self.list.get_selected_row()
        if response not in (self.PLACE, self.SAVE) or row is None:
            return None
        img = typed_signature(self.text(), row.family, _hex(self.ink.get_rgba()))
        return ("save" if response == self.SAVE else "place", img, self.text())

    def run(self):
        """Show modally; returns result()"""
        response = self.dialog.run()
        result = self.result(response)
        self.dialog.destroy()
        return result
