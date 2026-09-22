"""
Quick Edit
Add text and signatures to scanned pages, like mainstream PDF editors.

- Add Text: the pointer becomes a text cursor; click anywhere on the page and
  type. Alignment guides snap softly to earlier text (same edges, centre,
  equal spacing, symmetry) without locking; hold Alt to place freely.
- Apply Signature places the chosen signature (click where it goes, drag the
  corner square to resize). The edit icon next to it opens the signature
  chooser: up to 4 saved signatures (kept between sessions), delete, and
  Create Signature (type your name in a signature font, or upload a PNG).
  Quick Edit applies signatures; creating them happens in that dialog.
- Pointer: a hand on an item's frame (drag to move), a text cursor inside
  text (click to edit), a diagonal arrow on the resize corner.
- Items can be moved (with guides), resized, edited, deleted and applied to
  every page. Edits are overlays stored on the page and flattened only when
  saving (non-destructive).

Overlay model (positions/sizes are fractions of the page):
  {"type": "text", "text": str, "font": family, "size_pt": float, "color": "#rrggbb", "x": f, "y": f}
  {"type": "image", "path": signature.png, "x": f, "y": f, "w": f (width as page fraction)}
"""

import copy
import json
import os

from features import BaseFeature
from utils.util_fonts import (
    import_fonts,
    layout_runs,
    render_runs,
    render_text,
    signature_fonts,
    text_fonts,
    text_metrics,
)
from utils.util_icons import icon_button, icon_image, icon_label_button
from utils.util_guides import Box, snap
from utils.util_textruns import delete, insert, plain, restyle, runs_of, set_runs, style_at, word_at
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
        """Add Text and Signature buttons to the Preview toolbar's content group"""
        page.add_tool(
            "content",
            icon_button(
                "text-t",
                "Add Text: click anywhere on the page and type",
                lambda: self.open_editor(page, "text"),
            ),
            self.id,
        )
        page.add_tool(
            "content",
            icon_button(
                "user-list",
                "Signature: place your signature on the page",
                lambda: self.open_editor(page, "signature"),
            ),
            self.id,
        )

    def open_editor(self, preview_page, start=None):
        """Open the editor for the selected page (start: "text" or "signature"); store overlays on Apply"""
        pages = preview_page.ctx.scan.pages
        index = preview_page.preview.selected
        if not pages or index < 0:
            return
        before = preview_page._snapshot() if hasattr(preview_page, "_snapshot") else None
        editor = QuickEditor(preview_page.ctx, pages, index)
        if start == "text":
            editor.set_mode("text")
        elif start == "signature":
            editor.apply_signature()
        if editor.run():
            if before is not None:
                preview_page.checkpoint(before)  # Undo removes the whole edit
            (
                preview_page.changed()
                if hasattr(preview_page, "changed")
                else preview_page.ctx.emit("pages-changed")
            )
            preview_page.set_status("Edits applied. Text and signatures are added to the file when you save.")


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
        self.caret = 0  # caret position (characters) in the text being edited
        self.anchor = None  # other end of the highlight (None: nothing highlighted)
        self.selecting = False  # dragging to highlight
        self.mode = "select"  # select | text | place
        self.pending_signature = None  # path placed by the next click (place mode)
        self.drag = None  # ("move"|"resize", start canvas x, y, item snapshot)
        self.hover = None  # Box of what a click would create (text / place mode)
        self.guides = []
        self.caret_on = True
        self._loading = False
        self._current_sig = None  # used when there are no settings (tests)
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
        """Right-hand panel: tools, text style, Apply Signature, item actions (icons: Phosphor)"""
        Gtk, Gdk = self.Gtk, self.Gdk
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(340, -1)

        panel.pack_start(self._heading("Tools"), False, False, 0)
        row = Gtk.Box(spacing=0)
        row.get_style_context().add_class("segment")  # the active tool is highlighted
        row.set_halign(Gtk.Align.START)
        self.select_tool = Gtk.RadioButton.new_from_widget(None)
        self.text_tool = Gtk.RadioButton.new_from_widget(self.select_tool)
        for b, icon, tip in (
            (
                self.select_tool,
                "cursor",
                "Select / move (drag the frame to move, click inside text to edit)",
            ),
            (self.text_tool, "text-t", "Add Text: click anywhere on the page and type"),
        ):
            b.set_mode(False)  # look like toggle buttons
            b.add(icon_image(icon, 18))
            b.set_tooltip_text(tip)
            b.get_style_context().add_class("icon-button")
            row.pack_start(b, False, False, 0)
        self.text_tool.connect("toggled", self._on_tool_toggled)
        self.guides_check = icon_button(
            "ruler", "Alignment guides on/off (hold Alt to place freely)", toggle=True
        )
        self.guides_check.set_active(True)
        tools = Gtk.Box(spacing=12)
        tools.pack_start(row, False, False, 0)
        tools.pack_start(self.guides_check, False, False, 0)
        panel.pack_start(tools, False, False, 0)

        panel.pack_start(self._heading("Text"), False, False, 0)
        self.font_combo = Gtk.ComboBoxText()
        for family in text_fonts():
            self.font_combo.append(family, family)
        self.font_combo.set_active(0)
        self.size_spin = Gtk.SpinButton.new_with_range(6, 96, 1)
        self.size_spin.set_value(14)
        self.size_spin.set_tooltip_text("Text size (points)")
        self.color_btn = Gtk.ColorButton()
        self.color_btn.set_tooltip_text("Text colour")
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

        panel.pack_start(self._heading("Signature"), False, False, 0)
        row = Gtk.Box(spacing=6)
        self.apply_sig_btn = icon_label_button(
            "signature",
            "Apply Signature",
            "Place your signature: click on the page where it goes",
            self.apply_signature,
        )
        self.edit_sig_btn = icon_button(
            "pencil-simple", "Choose or create a different signature", self.open_signature_chooser
        )
        row.pack_start(self.apply_sig_btn, False, False, 0)
        row.pack_start(self.edit_sig_btn, False, False, 0)
        panel.pack_start(row, False, False, 0)
        self.current_sig_image = Gtk.Image()
        self.current_sig_label = Gtk.Label()
        self.current_sig_label.set_xalign(0)
        self.current_sig_label.get_style_context().add_class("muted")
        panel.pack_start(self.current_sig_image, False, False, 0)
        panel.pack_start(self.current_sig_label, False, False, 0)
        self.show_current_signature()

        panel.pack_start(self._heading("Selected item"), False, False, 0)
        row = Gtk.Box(spacing=6)
        row.pack_start(
            icon_button("trash", "Delete the selected item (Delete key)", self.delete_selected),
            False,
            False,
            0,
        )
        row.pack_start(
            icon_button("copy", "Apply the selected item to all pages", self.apply_to_all),
            False,
            False,
            0,
        )
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
            "select": "Click inside text to edit it; drag across words (or Shift + arrows) to highlight them, "
            "then change the font, size or colour · drag an item's frame (hand pointer) to move it · drag a "
            "signature's corner to resize it · Delete removes · arrow keys nudge",
            "text": "Click anywhere on the page and type. Enter starts a new line below, Esc finishes. "
            "Guides appear when your text lines up with earlier text.",
            "place": "Click on the page where the signature should go (Esc cancels). "
            "Drag its corner square afterwards to resize it.",
        }[self.mode]
        self.hint.set_text(text or default)

    # -- signature ------------------------------------------------------------------
    def current_signature(self):
        """Path of the chosen signature (remembered between sessions), or None"""
        settings = getattr(self.ctx, "settings", None)
        path = settings.get("current_signature") if settings is not None else self._current_sig
        return path if path in library() else None

    def set_current_signature(self, path):
        """Remember the chosen signature"""
        self._current_sig = path
        settings = getattr(self.ctx, "settings", None)
        if settings is not None:
            settings.set("current_signature", path or "")
        self.show_current_signature()

    def show_current_signature(self):
        """Small preview of the chosen signature under Apply Signature"""
        path = self.current_signature()
        img = self._signature_image(path) if path else None
        if img is None:
            self.current_sig_image.clear()
            self.current_sig_label.set_text(
                "No signature chosen yet: use the edit icon to choose or create one."
            )
            return
        thumb = img.copy()
        thumb.thumbnail((220, 60))
        self.current_sig_image.set_from_pixbuf(_pixbuf(on_paper(thumb, 6)))
        self.current_sig_label.set_text("")

    def apply_signature(self):
        """Apply Signature: place the chosen signature with the next click (or choose one first)"""
        path = self.current_signature()
        if path:
            self.place_signature_on_click(path)
        else:
            self.open_signature_chooser()

    def open_signature_chooser(self):
        """Edit icon: choose a saved signature, remove one, or create a new one"""
        chooser = SignatureChooser(self)
        chooser.popup()

    def signature_chosen(self, path):
        """A signature was picked or created: make it current and place it with the next click"""
        self.set_current_signature(path)
        self.place_signature_on_click(path)

    def signature_removed(self, path):
        """A saved signature was deleted: keep copies already placed working this session"""
        img = self._signature_image(path)
        keep = os.path.join(self.ctx.scan.session_dir, os.path.basename(path))
        if img is not None:
            img.save(keep)
            for item in self.items:
                if item.get("path") == path:
                    item["path"] = keep
        remove_signature(path)
        self._sig_cache.pop(path, None)
        if self.pending_signature == path:
            self.set_mode("select")
        self.show_current_signature()

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

    def selection(self):
        """(start, end) of the highlighted characters in the text being edited, or None"""
        if self.editing is None or self.anchor is None or self.anchor == self.caret:
            return None
        return min(self.anchor, self.caret), max(self.anchor, self.caret)

    def style_changed(self):
        """Font / size / colour changed in the panel.

        Highlighted words take the new style; with nothing highlighted the whole
        text item does (and what is typed next continues it)."""
        if self._loading:
            return
        item = self.editing or self.selected
        if not item or item["type"] != "text":
            return
        font, size, color = self.current_style()
        runs = runs_of(item)
        sel = self.selection()
        start, end = sel if sel else (0, len(plain(runs)))
        if start == end:  # an empty item: set the style for the text to come
            runs = [dict(r, font=font, size_pt=size, color=color) for r in runs]
        else:
            runs = restyle(runs, start, end, font=font, size_pt=size, color=color)
        set_runs(item, runs)
        self.canvas.queue_draw()

    def _load_style(self, item, pos=None):
        """Show the style at a position of a text item in the panel (without restyling it)"""
        runs = runs_of(item)
        style = style_at(runs, pos) if pos is not None else runs[0]
        self._loading = True
        self.font_combo.set_active_id(style["font"])
        self.size_spin.set_value(style["size_pt"])
        c = self.Gdk.RGBA()
        c.parse(style["color"])
        self.color_btn.set_rgba(c)
        self._loading = False

    # -- actions (also used by tests) ------------------------------------------------
    def new_text_item(self, x, y, text=""):
        """Create a text item at page fractions (x, y) with the panel's style"""
        font, size, color = self.current_style()
        item = set_runs(
            {"type": "text", "x": x, "y": y}, [{"text": text, "font": font, "size_pt": size, "color": color}]
        )
        self.items.append(item)
        self.selected = item
        return item

    def add_text(self):
        """Add the text from text_entry near the top-left (scripted use)"""
        text = self.text_entry.get_text().strip()
        if text:
            self.new_text_item(0.1, 0.1 + 0.04 * len(self.items) % 0.8, text)
            self.canvas.queue_draw()

    def start_editing(self, item, caret=None):
        """Type into a text item on the canvas (caret: character position; default the end)"""
        if self.editing is not item:
            self.finish_editing()
        set_runs(item, runs_of(item))  # older items become runs
        self.editing = item
        self.selected = item
        self.caret = len(item["text"]) if caret is None else max(0, min(caret, len(item["text"])))
        self.anchor = None
        self._load_style(item, self.caret)
        self.caret_on = True
        self.canvas.grab_focus()
        self.canvas.queue_draw()

    def finish_editing(self):
        """Stop typing; an empty text item is removed"""
        item = self.editing
        self.editing = None
        self.anchor = None
        self.selecting = False
        if item is not None and not item["text"].strip():
            if item in self.items:
                self.items.remove(item)
            if self.selected is item:
                self.selected = None
        self.canvas.queue_draw()

    def select_range(self, start, end):
        """Highlight characters start..end of the text being edited (the caret goes to end)"""
        if self.editing is not None:
            n = len(self.editing["text"])
            self.anchor, self.caret = max(0, min(start, n)), max(0, min(end, n))
            self._load_style(self.editing, self.caret)
            self.canvas.queue_draw()

    def _replace_selection(self, text=""):
        """Delete the highlighted characters (if any) and insert text at the caret"""
        item = self.editing
        runs = runs_of(item)
        sel = self.selection()
        if sel:
            style = style_at(runs, sel[0] + 1)
            runs = delete(runs, *sel)
            self.caret = sel[0]
        else:
            style = style_at(runs, self.caret)
        if text:
            runs = insert(runs, self.caret, text, style)
            self.caret += len(text)
        self.anchor = None
        set_runs(item, runs)

    def type_text(self, text):
        """Insert typed text at the caret (replacing highlighted words)"""
        if self.editing is not None:
            self._replace_selection(text)
            self.caret_on = True
            self.canvas.queue_draw()

    def on_commit(self, _im, text):
        """Characters from the input method"""
        self.type_text(text)

    def backspace(self, forward=False):
        """Backspace (or Delete): remove the highlighted words, or one character"""
        item = self.editing
        if item is None:
            return
        if self.selection():
            self._replace_selection("")
        elif forward and self.caret < len(item["text"]):
            set_runs(item, delete(runs_of(item), self.caret, self.caret + 1))
        elif not forward and self.caret > 0:
            set_runs(item, delete(runs_of(item), self.caret - 1, self.caret))
            self.caret -= 1
        self.canvas.queue_draw()

    def move_caret(self, pos, extend=False):
        """Move the caret (extend: grow the highlight, as with Shift)"""
        if self.editing is None:
            return
        if extend and self.anchor is None:
            self.anchor = self.caret
        elif not extend:
            self.anchor = None
        self.caret = max(0, min(pos, len(self.editing["text"])))
        self._load_style(self.editing, self.caret)
        self.caret_on = True
        self.canvas.queue_draw()

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

    def _text_layout(self, item):
        """(width, line height, baseline, character x positions) of a text item, in page pixels"""
        runs = runs_of(item)
        width, line, baseline, xs = layout_runs(runs, self._dpi() / 72)
        if not item.get("text"):
            width = layout_runs([dict(runs[0], text=" ")], self._dpi() / 72)[0]
        return width, line, baseline, xs

    def item_box(self, item):
        """Item rectangle in page fractions (text: its line box; signature: its image)"""
        _s, _ox, _oy, pw, ph = self._layout()
        if item["type"] == "text":
            width, line, _b, _xs = self._text_layout(item)
            return Box(item["x"], item["y"], width / pw, line / ph, "text")
        sig = self._signature_image(item["path"])
        w = item["w"]
        h = (w * pw * sig.height / sig.width) / ph if sig else w / 3
        return Box(item["x"], item["y"], w, h, "image")

    def _bbox(self, item):
        """Item rectangle on the canvas: (x, y, w, h)"""
        scale, ox, oy, pw, ph = self._layout()
        b = self.item_box(item)
        return ox + b.left * pw * scale, oy + b.top * ph * scale, b.width * pw * scale, b.height * ph * scale

    def char_x(self, item, pos):
        """Canvas x of the caret position pos in a text item"""
        scale, ox, _oy, pw, _ph = self._layout()
        _w, _l, _b, xs = self._text_layout(item)
        return ox + item["x"] * pw * scale + xs[max(0, min(pos, len(xs) - 1))] * scale

    def pos_at(self, item, ex):
        """The caret position nearest to canvas x ex in a text item"""
        scale, ox, _oy, pw, _ph = self._layout()
        _w, _l, _b, xs = self._text_layout(item)
        local = (ex - ox) / scale - item["x"] * pw
        return min(range(len(xs)), key=lambda k: abs(xs[k] - local))

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
        """(pixbuf, dx, dy) for a text item's styled runs at canvas scale, cached"""
        runs = runs_of(item)
        key = (json.dumps(runs, sort_keys=True), round(scale, 5))
        if key not in self._text_pix:
            img, dx, dy = render_runs(runs, self._dpi() / 72 * scale)
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
        """Draw the page, the overlays, the text highlight and caret, guides and the selection frame"""
        Gdk = self.Gdk
        scale, ox, oy, pw, ph = self._layout()
        cr.set_source_rgb(0.12, 0.12, 0.12)
        cr.paint()
        Gdk.cairo_set_source_pixbuf(cr, self._page_pixbuf(int(pw * scale), int(ph * scale)), ox, oy)
        cr.paint()
        for item in self.items:
            x, y, w, h = self._bbox(item)
            if item["type"] == "text":
                if item is self.editing and self.selection():
                    a, b = self.selection()
                    x0, x1 = self.char_x(item, a), self.char_x(item, b)
                    cr.set_source_rgba(0.0, 0.47, 0.84, 0.30)  # highlighted words
                    cr.rectangle(x0, y, x1 - x0, h)
                    cr.fill()
                if item["text"]:
                    pix, dx, dy = self._text_pixbuf(item, scale)
                    Gdk.cairo_set_source_pixbuf(cr, pix, x + dx, y + dy)
                    cr.paint()
                if item is self.editing and self.caret_on:
                    cr.set_source_rgb(0.0, 0.47, 0.84)
                    cr.rectangle(self.char_x(item, self.caret), y, 2, h)
                    cr.fill()
            else:
                pix = self._signature_pixbuf(item["path"], int(w), int(h))
                if pix:
                    Gdk.cairo_set_source_pixbuf(cr, pix, x, y)
                    cr.paint()
            if item is self.selected:
                cr.set_source_rgba(0.0, 0.47, 0.84, 0.6 if item is self.editing else 1.0)  # framework accent
                cr.set_line_width(1.5)
                cr.rectangle(x - 3, y - 3, w + 6, h + 6)
                cr.stroke()
                if item["type"] == "image":  # only signatures resize
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
    FRAME_PX = 6  # the band around an item where the pointer becomes a hand (move)

    def _hit(self, ex, ey):
        """(item, zone) under the pointer, topmost first; zone: resize (signatures only) | frame | inside"""
        f = self.FRAME_PX
        for item in reversed(self.items):
            x, y, w, h = self._bbox(item)
            if (
                item["type"] == "image"
                and item is self.selected
                and x + w + 3 - HANDLE <= ex <= x + w + 3
                and y + h + 3 - HANDLE <= ey <= y + h + 3
            ):
                return item, "resize"
            if x <= ex <= x + w and y <= ey <= y + h:
                return item, "inside"
            if x - f <= ex <= x + w + f and y - f <= ey <= y + h + f:
                return item, "frame"
        return None, None

    @staticmethod
    def cursor_for(item, zone, mode, dragging=False):
        """Pointer name for what a click would do (hand = move, text = edit, arrows = resize)"""
        if dragging:
            return "grabbing"
        if mode == "place":
            return "crosshair"
        if zone == "resize":
            return "nwse-resize"
        if zone == "frame" or (zone == "inside" and item["type"] == "image"):
            return "grab"
        if zone == "inside" or mode == "text":
            return "text"
        return "default"

    def _pointer(self, name):
        """Set the canvas pointer by name"""
        window = self.canvas.get_window()
        if window:
            window.set_cursor(self.Gdk.Cursor.new_from_name(window.get_display(), name))

    def _free(self, event):
        """Alt held: place / move without snapping"""
        return bool(event.state & self.Gdk.ModifierType.MOD1_MASK)

    def on_press(self, widget, event):
        """Place text or a signature; click inside text to put the caret there (drag to highlight);
        drag an item's frame (or a signature) to move it; drag a signature's corner to resize"""
        Gdk = self.Gdk
        self.canvas.grab_focus()
        if event.button != 1:
            return False
        fx, fy = self.to_page(event.x, event.y)
        item, zone = self._hit(event.x, event.y)

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

        if item is not None and item["type"] == "text" and zone == "inside":
            pos = self.pos_at(item, event.x)
            if event.type == Gdk.EventType._2BUTTON_PRESS and item is self.editing:
                self.select_range(*word_at(item["text"], pos))  # double-click: the word
                self.selecting = False
                return True
            if item is self.editing and event.state & Gdk.ModifierType.SHIFT_MASK:
                self.move_caret(pos, extend=True)
            else:
                self.start_editing(item, caret=pos)
                self.anchor = pos
            self.selecting = True  # drag to highlight
            return True

        if self.mode == "text" and zone != "frame":
            self.finish_editing()
            box = self._ghost_box(fx, fy)
            left, top = self.snapped(box, free=self._free(event))
            self.start_editing(self.new_text_item(min(max(left, 0), 0.98), min(max(top, 0), 0.98)))
            self.guides = []
            return True

        # the frame (or a signature) moves, a signature's corner resizes, empty page deselects
        if self.editing is not None and item is not self.editing:
            self.finish_editing()
        self.selected = item
        if item is not None and item["type"] == "text":
            self._load_style(item)
        self.drag = ("resize" if zone == "resize" else "move", event.x, event.y, dict(item)) if item else None
        if self.drag:
            self._pointer("grabbing" if self.drag[0] == "move" else "nwse-resize")
        self.canvas.queue_draw()
        return True

    def on_motion(self, widget, event):
        """Highlight while dragging in text; move / resize the dragged item; ghost and pointer"""
        if self.selecting and self.editing is not None:
            self.move_caret(self.pos_at(self.editing, event.x), extend=True)
            return True
        if self.mode in ("text", "place") and not self.drag:
            fx, fy = self.to_page(event.x, event.y)
            box = self._ghost_box(fx, fy)
            box.left, box.top = self.snapped(box, free=self._free(event))
            self.hover = box
            item, zone = self._hit(event.x, event.y)
            self._pointer(self.cursor_for(item, zone, self.mode))
            self.canvas.queue_draw()
            return True
        if not self.drag or not self.selected:
            item, zone = self._hit(event.x, event.y)
            self._pointer(self.cursor_for(item, zone, self.mode))
            return False
        mode, sx, sy, start = self.drag
        scale, _ox, _oy, pw, ph = self._layout()
        dx, dy = (event.x - sx) / (pw * scale), (event.y - sy) / (ph * scale)
        item = self.selected
        if mode == "move":
            box = self.item_box(dict(start, x=start["x"] + dx, y=start["y"] + dy))
            left, top = self.snapped(box, moving=item, free=self._free(event))
            self.move_item(item, left, top)
        elif item["type"] == "image":  # only signatures resize; text size is set in the panel
            item["w"] = min(max(start["w"] + dx, 0.03), 1.0)
        self.canvas.queue_draw()
        return True

    def on_release(self, widget, event):
        """End a drag or a highlight"""
        self.drag = None
        self.selecting = False
        if self.editing is not None and self.anchor == self.caret:
            self.anchor = None  # a click without dragging: just the caret
        self.guides = []
        item, zone = self._hit(event.x, event.y)
        self._pointer(self.cursor_for(item, zone, self.mode))
        self.canvas.queue_draw()
        return True

    def on_leave(self, *_):
        """Pointer left the canvas: hide the ghost and guides"""
        if not self.drag:
            self.hover = None
            self.guides = []
            self.canvas.queue_draw()

    def on_key(self, widget, event):
        """Typing and text keys while editing; otherwise Esc, Delete and arrow-key nudging"""
        Gdk = self.Gdk
        key = event.keyval
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        item = self.editing
        if item is not None:
            if key == Gdk.KEY_Escape:
                self.finish_editing()
                return True
            if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.new_line()
                return True
            if key == Gdk.KEY_BackSpace:
                self.backspace()
                return True
            if key in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
                self.backspace(forward=True)
                return True
            if ctrl and key in (Gdk.KEY_a, Gdk.KEY_A):
                self.select_range(0, len(item["text"]))
                return True
            moves = {
                Gdk.KEY_Left: self.caret - 1,
                Gdk.KEY_Right: self.caret + 1,
                Gdk.KEY_Home: 0,
                Gdk.KEY_End: len(item["text"]),
            }
            if key in moves:
                sel = self.selection()
                if sel and not shift and key in (Gdk.KEY_Left, Gdk.KEY_Right):
                    self.move_caret(sel[0] if key == Gdk.KEY_Left else sel[1])  # collapse the highlight
                else:
                    self.move_caret(moves[key], extend=shift)
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
        """Enter while typing: finish this line and start the next one below it, same left edge and style"""
        item = self.editing
        box = self.item_box(item)
        style = style_at(runs_of(item), self.caret)
        self.finish_editing()
        if item in self.items:
            y = min(item["y"] + box.height * 1.5, 0.98)  # the same spacing the guides suggest
            new = self.new_text_item(item["x"], y)
            set_runs(new, [dict(style, text="")])
            self.start_editing(new)

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


class SignatureChooser:
    """Popover card from the edit icon: the saved signatures (pick one, or delete it) and Create Signature"""

    def __init__(self, editor):
        """Build the card next to the edit icon"""
        Gtk = editor.Gtk
        self.editor, self.Gtk = editor, Gtk
        self.popover = Gtk.Popover()
        self.popover.set_relative_to(editor.edit_sig_btn)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for m in (
            self.box.set_margin_start,
            self.box.set_margin_end,
            self.box.set_margin_top,
            self.box.set_margin_bottom,
        ):
            m(12)
        self.popover.add(self.box)
        self.rebuild()

    def rebuild(self):
        """Tiles for the saved signatures, empty slots, and Create Signature"""
        Gtk = self.Gtk
        for child in self.box.get_children():
            self.box.remove(child)
        saved = library()
        title = Gtk.Label(label=f"Your signatures ({len(saved)} of {MAX_SIGNATURES})")
        title.set_xalign(0)
        title.get_style_context().add_class("card-title")
        self.box.pack_start(title, False, False, 0)
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        self.tiles = []
        for n in range(MAX_SIGNATURES):
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            if n < len(saved):
                path = saved[n]
                img = self.editor._signature_image(path)
                tile = Gtk.Button()
                tile.get_style_context().add_class("thumb")
                tile.set_size_request(180, 70)
                if img is not None:
                    thumb = img.copy()
                    thumb.thumbnail((160, 52))
                    tile.add(Gtk.Image.new_from_pixbuf(_pixbuf(on_paper(thumb, 6))))
                if path == self.editor.current_signature():
                    tile.get_style_context().add_class("selected")
                tile.set_tooltip_text("Use this signature, then click on the page to place it")
                tile.connect("clicked", lambda _b, p=path: self.choose(p))
                cell.pack_start(tile, False, False, 0)
                cell.pack_start(
                    icon_button("trash", "Delete this signature", lambda p=path: self.delete(p)),
                    False,
                    False,
                    0,
                )
                self.tiles.append((path, tile))
            else:
                empty = Gtk.Label(label="Empty slot")
                empty.get_style_context().add_class("muted")
                empty.set_size_request(180, 70)
                cell.pack_start(empty, False, False, 0)
            grid.attach(cell, n % 2, n // 2, 1, 1)
        self.box.pack_start(grid, False, False, 0)
        create = icon_label_button(
            "plus", "Create Signature", "Type your name in a signature font, or upload a PNG", self.create
        )
        full = len(saved) >= MAX_SIGNATURES
        create.set_sensitive(not full)
        if full:
            create.set_tooltip_text(f"All {MAX_SIGNATURES} slots are used: delete one to create another")
        self.box.pack_start(create, False, False, 0)
        self.box.show_all()

    def popup(self):
        """Show the card"""
        self.popover.show_all()
        self.popover.popup()

    def choose(self, path):
        """Pick a signature: it becomes current and is placed with the next click"""
        self.popover.popdown()
        self.editor.signature_chosen(path)

    def delete(self, path):
        """Delete a saved signature (after confirming)"""
        Gtk = self.Gtk
        ask = Gtk.MessageDialog(
            transient_for=self.editor.dialog,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Delete this signature?",
        )
        ask.format_secondary_text("Copies already placed on pages stay until you remove them.")
        ok = ask.run() == Gtk.ResponseType.OK
        ask.destroy()
        if ok:
            self.editor.signature_removed(path)
            self.rebuild()

    def create(self):
        """Create Signature: the creation dialog; a new signature becomes current"""
        self.popover.popdown()
        editor = self.editor
        path = SignatureCreator(editor.dialog, editor.Gtk, editor.Gdk, editor.GLib).run()
        if path:
            editor.signature_chosen(path)


class SignatureCreator:
    """Create Signature dialog: type your name in a signature font, or upload a PNG; saves to a slot"""

    PREVIEW_PX = 44

    def __init__(self, parent, Gtk, Gdk, GLib):
        """Two ways in (Type it / Upload a PNG), Save Signature"""
        self.Gtk, self.Gdk, self.GLib = Gtk, Gdk, GLib
        self.dialog = Gtk.Dialog(title="Create Signature", transient_for=parent, modal=True)
        self.dialog.set_default_size(640, 680)
        self.dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save Signature", Gtk.ResponseType.OK)
        box = self.dialog.get_content_area()
        box.set_spacing(8)
        for m in (box.set_margin_start, box.set_margin_end, box.set_margin_top):
            m(12)
        self.stack = Gtk.Stack()
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.get_style_context().add_class("segment")
        switcher.set_halign(Gtk.Align.START)
        box.pack_start(switcher, False, False, 0)
        box.pack_start(self.stack, True, True, 0)
        self.stack.add_titled(self._type_page(), "type", "Type it")
        self.stack.add_titled(self._upload_page(), "upload", "Upload a PNG")
        self.message = Gtk.Label()
        self.message.set_xalign(0)
        self.message.set_line_wrap(True)
        self.message.get_style_context().add_class("status-error")
        box.pack_start(self.message, False, False, 0)
        self._pending = None
        self.rebuild()
        self.dialog.show_all()

    # -- type it ------------------------------------------------------------------
    def _type_page(self):
        """Name, ink colour and the font list with live previews"""
        Gtk, Gdk = self.Gtk, self.Gdk
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
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
        page.pack_start(row, False, False, 0)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.connect("row-activated", lambda *_: self.dialog.response(Gtk.ResponseType.OK))
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.add(self.list)
        page.pack_start(scroller, True, True, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(
            icon_label_button("upload-simple", "Add fonts…", None, self.add_fonts), False, False, 0
        )
        note = Gtk.Label(label="Add .ttf, .otf or .zip font files. Fonts you add stay on this computer.")
        note.get_style_context().add_class("muted")
        note.set_xalign(0)
        note.set_line_wrap(True)
        row.pack_start(note, True, True, 0)
        page.pack_start(row, False, False, 0)
        return page

    def _schedule(self):
        """Re-render previews shortly after typing stops"""
        if self._pending:
            self.GLib.source_remove(self._pending)
        self._pending = self.GLib.timeout_add(200, self.rebuild)

    def text(self):
        """The name to render"""
        return self.name.get_text().strip() or "Your Name"

    def rebuild(self):
        """One row per signature font showing the name in that font (on white paper)"""
        Gtk = self.Gtk
        self._pending = None
        selected = self.list.get_selected_row()
        keep = selected.family if selected else None
        for child in self.list.get_children():
            self.list.remove(child)
        color = _hex(self.ink.get_rgba())
        for f in signature_fonts():
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

    # -- upload ---------------------------------------------------------------------
    def _upload_page(self):
        """Pick a PNG; optionally make its white background transparent; preview"""
        Gtk = self.Gtk
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.png = Gtk.FileChooserButton(title="Signature image (PNG)", action=Gtk.FileChooserAction.OPEN)
        flt = Gtk.FileFilter()
        flt.set_name("PNG images")
        flt.add_pattern("*.png")
        flt.add_pattern("*.PNG")
        self.png.add_filter(flt)
        self.png.connect("file-set", lambda *_: self.png_changed(auto=True))
        page.pack_start(self.png, False, False, 0)
        self.clear_white = Gtk.CheckButton(label="Make a white background transparent (only the ink shows)")
        self.clear_white.connect("toggled", lambda *_: self.png_changed())
        page.pack_start(self.clear_white, False, False, 0)
        self.png_preview = Gtk.Image()
        page.pack_start(self.png_preview, True, True, 0)
        return page

    def png_changed(self, auto=False):
        """Preview the chosen PNG as it will be saved"""
        path = self.png.get_filename()
        if not path:
            return
        if auto:  # a PNG without transparency usually has a white background to clear
            self.clear_white.set_active(not has_transparency(path))
        img = prepare_png(path, self.clear_white.get_active())
        img.thumbnail((560, 300))
        self.png_preview.set_from_pixbuf(_pixbuf(on_paper(img)))

    # -- result -----------------------------------------------------------------------
    def build(self):
        """(image, name) from the visible tab, or (None, reason)"""
        if self.stack.get_visible_child_name() == "upload":
            path = self.png.get_filename()
            if not path:
                return None, "Choose a PNG image first."
            name = os.path.splitext(os.path.basename(path))[0]
            return prepare_png(path, self.clear_white.get_active()), name
        row = self.list.get_selected_row()
        if row is None:
            return None, "Choose a font first."
        return typed_signature(self.text(), row.family, _hex(self.ink.get_rgba())), self.text()

    def run(self):
        """Show modally; the saved signature's path, or None"""
        path = None
        while self.dialog.run() == self.Gtk.ResponseType.OK:
            img, name = self.build()
            if img is None:
                self.message.set_text(name)
                continue
            try:
                path = save_signature(img, name)
                break
            except LibraryFull as e:
                self.message.set_text(str(e))
        self.dialog.destroy()
        return path
