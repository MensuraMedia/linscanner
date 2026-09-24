"""
Preview Component
Large view of the selected page (fit to window, or zoomed) plus a thumbnail
strip that scrolls sideways and shows 1 or 2 rows.

Fast page switching: pages are drawn from small display copies
(utils/util_display.DisplayCache, made in the background as pages arrive),
thumbnails are cached, and selecting a page only moves the highlight instead
of rebuilding the strip. Zoom: the - / Fit / + buttons, Ctrl + mouse wheel, or
Ctrl + plus / minus / 0; drag the zoomed page to pan.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from config.config_layout import Layout  # noqa: E402
from utils.util_display import DisplayCache, page_key  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

ZOOM_STEPS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0]  # x fit-to-window
THUMB_CACHE_MAX = 400
LARGE_CACHE_MAX = 6

log = get_logger("ui")


def to_pixbuf(img):
    """Pillow RGB image -> GdkPixbuf"""
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(img.tobytes()),
        GdkPixbuf.Colorspace.RGB,
        False,
        8,
        img.width,
        img.height,
        img.width * 3,
    )


class PagePreview(Gtk.Box):
    """Selected-page view + thumbnail strip; on_select(index) when the page changes"""

    def __init__(self, on_select=None, cache_dir=None, rows=1, on_zoom=None, label_for=None, on_rename=None):
        """Large view (scrolled, zoomable) plus the thumbnail strip (rows: 1 or 2)"""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=Layout.spacing.MEDIUM)
        import tempfile

        self.on_select = on_select
        self.on_zoom = on_zoom
        self.label_for = label_for  # label_for(index, page) -> thumbnail caption (default "Page n")
        self.on_rename = on_rename  # on_rename(index, new name) when a caption is edited
        self.cache = DisplayCache(cache_dir or tempfile.mkdtemp(prefix="linscanner-preview-"))
        self.pages = []
        self.selected = -1
        self.rows = rows
        self.zoom = 1.0  # x fit-to-window
        self._resize_source = None
        self._last_size = (0, 0)
        self._thumbs = {}  # page_key -> pixbuf
        self._large = {}  # (page_key, w, h) -> pixbuf
        self._buttons = []
        self._pan = None
        self._crop = None  # (on_done, start_x, start_y, x, y) while a crop rectangle is being drawn

        # large view
        self.view = Gtk.ScrolledWindow()
        self.view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view.set_min_content_height(Layout.dimensions.PREVIEW_MIN_HEIGHT)
        self.view.get_style_context().add_class("preview-frame")
        self.image = Gtk.Image()
        self.image_box = Gtk.EventBox()  # receives drag-to-pan and Ctrl+wheel
        self.image_box.add(self.image)
        self.image_box.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        self.image_box.connect_after("draw", self._draw_crop)
        self.image_box.connect("button-press-event", self._pan_start)
        self.image_box.connect("button-release-event", self._pan_end)
        self.image_box.connect("motion-notify-event", self._pan_move)
        self.view.connect("scroll-event", self._on_scroll)
        self.empty = Gtk.Label(label="No pages yet. Scan a document to see it here.")
        self.empty.get_style_context().add_class("muted")
        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.image_box, "image")
        self.view.add(self.stack)
        self.view.connect("size-allocate", self._on_resize)
        self.pack_start(self.view, True, True, 0)

        # thumbnail strip: always-visible horizontal scroll bar, thumbnails from the left
        self.strip_scroll = Gtk.ScrolledWindow()
        self.strip_scroll.set_policy(Gtk.PolicyType.ALWAYS, Gtk.PolicyType.NEVER)
        self.strip_scroll.set_overlay_scrolling(False)
        self.strip = Gtk.Grid(column_spacing=Layout.spacing.MEDIUM, row_spacing=Layout.spacing.SMALL)
        self.strip.set_halign(Gtk.Align.START)
        self.strip.set_valign(Gtk.Align.START)
        self.strip_scroll.add(self.strip)
        self.pack_start(self.strip_scroll, False, False, 0)
        self._apply_strip_height()

    # -- public ------------------------------------------------------------
    def set_pages(self, pages, selected=None):
        """Show a page list and select one (keeps selection if possible)"""
        self.pages = pages
        if selected is None:
            selected = min(max(self.selected, 0), len(pages) - 1)
        self.selected = selected if pages else -1
        self.cache.warm([p["path"] for p in pages])
        self._rebuild_strip()
        self._render_large()

    def refresh_selected(self):
        """Re-render after the selected page changed (rotation, Quick Edit)"""
        if 0 <= self.selected < len(self._buttons):
            self._set_thumb(self.selected)
        self._render_large()

    def select(self, index):
        """Show another page (only the highlight moves; nothing is rebuilt)"""
        if not self.pages or not 0 <= index < len(self.pages) or index == self.selected:
            return
        old = self.selected
        self.selected = index
        for i in (old, index):
            if 0 <= i < len(self._buttons):
                ctx = self._buttons[i].get_style_context()
                (ctx.add_class if i == index else ctx.remove_class)("selected")
        self._scroll_to_thumb(index)
        self._render_large()
        if self.on_select:
            self.on_select(index)

    # -- crop --------------------------------------------------------------
    def begin_crop(self, on_done):
        """Next drag over the page draws a crop rectangle; on_done(left, top, right, bottom) in 0..1"""
        if self.selected < 0 or not self.pages:
            return False
        self._crop = (on_done, None, None, None, None)
        win = self.image_box.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(win.get_display(), "crosshair"))
        return True

    def cancel_crop(self):
        """Leave crop mode without cropping"""
        if not self._crop:
            return False
        self._crop = None
        win = self.image_box.get_window()
        if win:
            win.set_cursor(None)
        self.image_box.queue_draw()
        return True

    @property
    def cropping(self):
        return self._crop is not None

    def _image_area(self):
        """The picture's rectangle inside the event box (it is centred when smaller)"""
        pix = self.image.get_pixbuf()
        alloc = self.image_box.get_allocation()
        if pix is None:
            return 0, 0, alloc.width, alloc.height
        w, h = pix.get_width(), pix.get_height()
        return max(0, (alloc.width - w) // 2), max(0, (alloc.height - h) // 2), w, h

    def _crop_fractions(self):
        """The drawn rectangle as fractions of the picture, or None if it is too small"""
        _on_done, x0, y0, x1, y1 = self._crop
        if None in (x0, y0, x1, y1):
            return None
        ix, iy, iw, ih = self._image_area()
        left, right = sorted((x0 - ix, x1 - ix))
        top, bottom = sorted((y0 - iy, y1 - iy))
        left, right = max(0, min(left, iw)) / iw, max(0, min(right, iw)) / iw
        top, bottom = max(0, min(top, ih)) / ih, max(0, min(bottom, ih)) / ih
        if right - left < 0.02 or bottom - top < 0.02:  # a click or a sliver: not a crop
            return None
        return left, top, right, bottom

    def _draw_crop(self, _widget, cr):
        """Dim everything outside the rectangle being dragged"""
        if not self._crop:
            return False
        rect = self._crop[1:]
        if None in rect:
            return False
        x0, y0, x1, y1 = rect
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        alloc = self.image_box.get_allocation()
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.rectangle(left, top, right - left, bottom - top)
        cr.set_fill_rule(1)  # EVEN_ODD: the hole is the part being kept
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.set_line_width(1)
        cr.rectangle(left + 0.5, top + 0.5, right - left - 1, bottom - top - 1)
        cr.stroke()
        return False

    def set_rows(self, rows):
        """1 or 2 rows of thumbnails"""
        rows = 2 if rows == 2 else 1
        if rows != self.rows:
            self.rows = rows
            self._apply_strip_height()
            self._rebuild_strip()

    def set_zoom(self, zoom):
        """Zoom relative to fit-to-window (1.0 = fit)"""
        self.zoom = min(max(zoom, ZOOM_STEPS[0]), ZOOM_STEPS[-1])
        self._render_large()
        if self.on_zoom:
            self.on_zoom(self.zoom)

    def zoom_in(self):
        """Next zoom step"""
        self.set_zoom(next((z for z in ZOOM_STEPS if z > self.zoom + 1e-6), ZOOM_STEPS[-1]))

    def zoom_out(self):
        """Previous zoom step"""
        self.set_zoom(next((z for z in reversed(ZOOM_STEPS) if z < self.zoom - 1e-6), ZOOM_STEPS[0]))

    def zoom_fit(self):
        """Fit the whole page in the window"""
        self.set_zoom(1.0)

    def zoom_fit_width(self):
        """Fill the window's width with the page (tall pages then scroll)"""
        if self.selected < 0 or not self.pages:
            return
        w, h = self._last_size
        fit_w, fit_h = max(w - 24, 200), max(h - 24, 200)
        pw, ph = self.cache.size(self.pages[self.selected])
        fit = min(fit_w / pw, fit_h / ph)
        self.set_zoom((fit_w / pw) / fit)

    # -- thumbnails ------------------------------------------------------------
    def _apply_strip_height(self):
        """Strip tall enough for 1 or 2 rows, plus the scroll bar"""
        one = Layout.dimensions.THUMBNAIL_HEIGHT + 30
        height = one * self.rows + Layout.spacing.SMALL * (self.rows - 1) + 22
        self.strip_scroll.set_max_content_height(-1)  # GTK checks min <= max: widen first
        self.strip_scroll.set_min_content_height(height)
        self.strip_scroll.set_max_content_height(height)

    def _thumb_pixbuf(self, page):
        """Cached thumbnail for a page (redrawn only when the page changed)"""
        key = page_key(page)
        pix = self._thumbs.get(key)
        if pix is None:
            th = Layout.dimensions.THUMBNAIL_HEIGHT
            pix = to_pixbuf(self.cache.render(page, th, th))
            if len(self._thumbs) > THUMB_CACHE_MAX:
                self._thumbs.clear()
            self._thumbs[key] = pix
        return pix

    def _thumb_button(self, i, page):
        """Button with a page thumbnail and its number"""
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("thumb")
        if i == self.selected:
            btn.get_style_context().add_class("selected")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.image = Gtk.Image()
        box.pack_start(box.image, False, False, 0)
        caption = self.label_for(i, page) if self.label_for else f"Page {i + 1}"
        box.stack = Gtk.Stack()  # the caption, or the entry while it is being renamed
        lbl = Gtk.Label(label=caption)
        lbl.get_style_context().add_class("thumb-label")
        lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        lbl.set_max_width_chars(14)
        box.label = lbl
        entry = Gtk.Entry()
        entry.set_width_chars(12)
        entry.set_has_frame(False)
        entry.get_style_context().add_class("thumb-label")
        entry.connect("activate", lambda e, i=i: self._finish_rename(i, e.get_text()))
        entry.connect("focus-out-event", lambda e, _ev, i=i: self._finish_rename(i, e.get_text()))
        entry.connect("key-press-event", self._rename_key)
        box.entry = entry
        box.stack.add_named(lbl, "label")
        box.stack.add_named(entry, "entry")
        box.pack_start(box.stack, False, False, 0)
        btn.add(box)
        btn.connect("clicked", lambda *_: self.select(i))
        btn.connect("button-press-event", lambda _w, ev, i=i: self._thumb_clicked(i, ev))
        return btn

    def _thumb_clicked(self, index, event):
        """Double-click a thumbnail caption to rename it"""
        if event.type == Gdk.EventType._2BUTTON_PRESS and self.on_rename:
            self.begin_rename(index)
            return True
        return False

    def begin_rename(self, index=None):
        """Edit a thumbnail's caption in place (F2 or a double-click)"""
        index = self.selected if index is None else index
        if not self.on_rename or not 0 <= index < len(self._buttons):
            return False
        box = self._buttons[index].get_child()
        box.entry.set_text(self.pages[index].get("name") or box.label.get_text())
        box.stack.set_visible_child_name("entry")
        box.entry.grab_focus()
        box.entry.select_region(0, -1)
        return True

    def _rename_key(self, entry, event):
        """Esc leaves the caption unchanged"""
        if event.keyval == Gdk.KEY_Escape:
            for i, btn in enumerate(self._buttons):
                if btn.get_child().entry is entry:
                    btn.get_child().stack.set_visible_child_name("label")
                    return True
        return False

    def _finish_rename(self, index, text):
        """Store the typed caption (empty text restores the automatic one)"""
        if not 0 <= index < len(self._buttons):
            return False
        box = self._buttons[index].get_child()
        if box.stack.get_visible_child_name() != "entry":
            return False
        box.stack.set_visible_child_name("label")
        if self.on_rename:
            self.on_rename(index, text.strip())
        return False

    def _set_thumb(self, i):
        """Draw (or redraw) thumbnail i"""
        image = self._buttons[i].get_child().image
        try:
            image.set_from_pixbuf(self._thumb_pixbuf(self.pages[i]))
        except (OSError, GLib.Error, ValueError) as e:
            log.warning("thumbnail for page %d failed: %s", i + 1, e)
            image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

    def _rebuild_strip(self):
        """Lay out the thumbnails column by column (1 or 2 rows), from the left"""
        for child in self.strip.get_children():
            self.strip.remove(child)
        self._buttons = []
        for i, page in enumerate(self.pages):
            btn = self._thumb_button(i, page)
            self._buttons.append(btn)
            self.strip.attach(btn, i // self.rows, i % self.rows, 1, 1)
            self._set_thumb(i)
        self.strip.show_all()
        GLib.idle_add(self._scroll_to_thumb, self.selected)

    def _scroll_to_thumb(self, index):
        """Keep the selected thumbnail visible"""
        if not 0 <= index < len(self._buttons):
            return False
        alloc = self._buttons[index].get_allocation()
        adj = self.strip_scroll.get_hadjustment()
        if alloc.x < adj.get_value():
            adj.set_value(alloc.x)
        elif alloc.x + alloc.width > adj.get_value() + adj.get_page_size():
            adj.set_value(alloc.x + alloc.width - adj.get_page_size())
        return False

    # -- large view -----------------------------------------------------------
    def _on_resize(self, _widget, alloc):
        """Re-render the large view after resizing (debounced)"""
        size = (alloc.width, alloc.height)
        if size == self._last_size:
            return
        self._last_size = size
        if self._resize_source:
            GLib.source_remove(self._resize_source)
        self._resize_source = GLib.timeout_add(120, self._render_large)  # debounce

    def _render_large(self):
        """Render the selected page at fit x zoom (one-shot timeout)"""
        self._resize_source = None
        if self.selected < 0 or not self.pages:
            self.stack.set_visible_child_name("empty")
            return False
        w, h = self._last_size
        fit_w, fit_h = max(w - 24, 200), max(h - 24, 200)
        tw, th = int(fit_w * self.zoom), int(fit_h * self.zoom)
        page = self.pages[self.selected]
        key = (page_key(page), tw, th)
        try:
            pix = self._large.get(key)
            if pix is None:
                full = self.cache.size(page) if self.zoom > 1 else None
                pix = to_pixbuf(self.cache.render(page, tw, th, full_size=full))
                if len(self._large) >= LARGE_CACHE_MAX:
                    self._large.pop(next(iter(self._large)))
                self._large[key] = pix
            self.image.set_from_pixbuf(pix)
            self.stack.set_visible_child_name("image")
        except (OSError, GLib.Error, ValueError) as e:
            self.empty.set_text(f"Could not display page: {e}")
            self.stack.set_visible_child_name("empty")
        return False  # one-shot timeout

    # -- zoom and pan -------------------------------------------------------------
    def _on_scroll(self, _widget, event):
        """Ctrl + wheel zooms; the plain wheel scrolls as usual"""
        if not event.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        ok, _dx, dy = event.get_scroll_deltas()
        up = event.direction == Gdk.ScrollDirection.UP or (ok and dy < 0)
        self.zoom_in() if up else self.zoom_out()
        return True

    def _pan_start(self, _widget, event):
        """Start dragging the zoomed page (or the crop rectangle)"""
        if self._crop and event.button == 1:
            self._crop = (self._crop[0], event.x, event.y, event.x, event.y)
            return True
        if event.button == 1 and self.zoom > 1:
            h, v = self.view.get_hadjustment(), self.view.get_vadjustment()
            self._pan = (event.x_root, event.y_root, h.get_value(), v.get_value())
            win = self.image_box.get_window()
            if win:
                win.set_cursor(Gdk.Cursor.new_from_name(win.get_display(), "grabbing"))
        return False

    def _pan_move(self, _widget, event):
        """Pan while dragging (or resize the crop rectangle)"""
        if self._crop and self._crop[1] is not None:
            self._crop = (self._crop[0], self._crop[1], self._crop[2], event.x, event.y)
            self.image_box.queue_draw()
            return True
        if self._pan:
            x0, y0, h0, v0 = self._pan
            self.view.get_hadjustment().set_value(h0 - (event.x_root - x0))
            self.view.get_vadjustment().set_value(v0 - (event.y_root - y0))
        return False

    def _pan_end(self, *_):
        """Stop panning, or finish the crop rectangle"""
        if self._crop:
            on_done, fractions = self._crop[0], self._crop_fractions()
            self.cancel_crop()
            if fractions:
                on_done(*fractions)
            return True
        self._pan = None
        win = self.image_box.get_window()
        if win:
            win.set_cursor(None)
        return False
