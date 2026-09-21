"""
Preview Component
Large fit-to-window view of the selected page plus a thumbnail strip.
Images are decoded at display size (a 600 dpi colour page is ~100 MB raw).
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402

from config.config_layout import Layout  # noqa: E402

_ROTATE = {
    90: GdkPixbuf.PixbufRotation.CLOCKWISE,
    180: GdkPixbuf.PixbufRotation.UPSIDEDOWN,
    270: GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE,
}


def load_pixbuf(page, max_w, max_h):
    """Page image scaled to fit max_w x max_h, rotation applied"""
    rot = page.get("rotation", 0)
    w, h = (max_h, max_w) if rot in (90, 270) else (max_w, max_h)
    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(page["path"], max(w, 1), max(h, 1), True)
    return pix.rotate_simple(_ROTATE[rot]) if rot in _ROTATE else pix


class PagePreview(Gtk.Box):
    """Selected-page view + thumbnail strip; on_select(index) on thumbnail click"""

    def __init__(self, on_select=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=Layout.spacing.MEDIUM)
        self.on_select = on_select
        self.pages = []
        self.selected = -1
        self._resize_source = None
        self._last_size = (0, 0)

        # large view
        self.view = Gtk.ScrolledWindow()
        self.view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view.set_min_content_height(Layout.dimensions.PREVIEW_MIN_HEIGHT)
        self.view.get_style_context().add_class("preview-frame")
        self.image = Gtk.Image()
        self.empty = Gtk.Label(label="No pages yet. Scan a document to see it here.")
        self.empty.get_style_context().add_class("muted")
        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(self.image, "image")
        self.view.add(self.stack)
        self.view.connect("size-allocate", self._on_resize)
        self.pack_start(self.view, True, True, 0)

        # thumbnail strip
        strip_scroll = Gtk.ScrolledWindow()
        strip_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        strip_scroll.set_min_content_height(Layout.dimensions.THUMBNAIL_HEIGHT + 40)
        self.strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=Layout.spacing.MEDIUM)
        strip_scroll.add(self.strip)
        self.pack_start(strip_scroll, False, False, 0)

    # -- public ------------------------------------------------------------
    def set_pages(self, pages, selected=None):
        self.pages = pages
        if selected is None:
            selected = min(max(self.selected, 0), len(pages) - 1)
        self.selected = selected if pages else -1
        self._rebuild_strip()
        self._render_large()

    def refresh_selected(self):
        """Re-render after a rotation of the selected page"""
        self._rebuild_strip()
        self._render_large()

    # -- internals ---------------------------------------------------------
    def _rebuild_strip(self):
        for child in self.strip.get_children():
            self.strip.remove(child)
        th = Layout.dimensions.THUMBNAIL_HEIGHT
        for i, page in enumerate(self.pages):
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("thumb")
            if i == self.selected:
                btn.get_style_context().add_class("selected")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            try:
                box.pack_start(Gtk.Image.new_from_pixbuf(load_pixbuf(page, th, th)), False, False, 0)
            except GLib.Error:
                box.pack_start(Gtk.Label(label="?"), False, False, 0)
            lbl = Gtk.Label(label=f"Page {i + 1}")
            lbl.get_style_context().add_class("thumb-label")
            box.pack_start(lbl, False, False, 0)
            btn.add(box)
            btn.connect("clicked", self._thumb_clicked, i)
            self.strip.pack_start(btn, False, False, 0)
        self.strip.show_all()

    def _thumb_clicked(self, _btn, index):
        self.selected = index
        self._rebuild_strip()
        self._render_large()
        if self.on_select:
            self.on_select(index)

    def _on_resize(self, _widget, alloc):
        size = (alloc.width, alloc.height)
        if size == self._last_size:
            return
        self._last_size = size
        if self._resize_source:
            GLib.source_remove(self._resize_source)
        self._resize_source = GLib.timeout_add(120, self._render_large)  # debounce

    def _render_large(self):
        self._resize_source = None
        if self.selected < 0 or not self.pages:
            self.stack.set_visible_child_name("empty")
            return False
        w, h = self._last_size
        try:
            pix = load_pixbuf(self.pages[self.selected], max(w - 24, 200), max(h - 24, 200))
            self.image.set_from_pixbuf(pix)
            self.stack.set_visible_child_name("image")
        except GLib.Error as e:
            self.empty.set_text(f"Could not display page: {e.message}")
            self.stack.set_visible_child_name("empty")
        return False  # one-shot timeout
