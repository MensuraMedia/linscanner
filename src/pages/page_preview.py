"""
Preview Page
Shows scanned (or opened) pages: zoom, rotate, reorder and delete pages, then
Save or Save As PDF, PNG, JPEG or TIFF.

- Save: writes to the document's file (the last Save / Save As, or the file
  opened from Recent). A new document is saved as a PDF in the Save folder
  with an automatic name, without a dialog.
- Save As…: choose the name, folder and format.
- Thumbnails: 1 or 2 rows (the user's choice is remembered).
"""

import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from config.config_scan import EXPORT_FORMATS  # noqa: E402
from modules.manager_export import export_pages, format_for_path  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_preview import PagePreview  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")


class PreviewPage(BasePage):
    """Page viewer with editing actions, zoom, Save and Save As"""

    def build_content(self):
        """Toolbars (page actions, features, zoom, thumbnails), Save / Save As, preview and status"""
        self.add_title("Preview", "Check your pages, fix their orientation, then save.")

        top = Gtk.Box(spacing=12)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        top.pack_start(left, True, True, 0)

        # page actions
        bar = Gtk.Box(spacing=8)
        self.btn_left = self._tool(bar, "Rotate left", lambda: self.rotate(270))
        self.btn_right = self._tool(bar, "Rotate right", lambda: self.rotate(90))
        self.btn_flip = self._tool(bar, "Rotate 180°", lambda: self.rotate(180))
        self.btn_delete = self._tool(bar, "Delete page", self.delete_page)
        self.btn_clear = self._tool(bar, "Clear all", self.clear_pages)
        self.btn_back = self._tool(bar, "Move ←", lambda: self.move(-1))
        self.btn_fwd = self._tool(bar, "Move →", lambda: self.move(1))
        left.pack_start(bar, False, False, 0)

        # optional feature buttons (Quick Edit, Import images, ...) go in this row
        self.feature_toolbar = Gtk.Box(spacing=8)
        self.feature_buttons = {}
        left.pack_start(self.feature_toolbar, False, False, 0)

        # Save above Save As
        saves = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.quick_save_btn = Gtk.Button(label="Save")
        self.quick_save_btn.get_style_context().add_class("primary-pill")
        self.quick_save_btn.set_tooltip_text(
            "Save to this document's file. A new document is saved as a PDF in your Save folder."
        )
        self.quick_save_btn.connect("clicked", lambda *_: self.on_save())
        self.save_btn = Gtk.Button(label="Save As…")
        self.save_btn.connect("clicked", self.on_save_as)
        saves.pack_start(self.quick_save_btn, False, False, 0)
        saves.pack_start(self.save_btn, False, False, 0)
        top.pack_end(saves, False, False, 0)
        self.pack_start(top, False, False, 0)

        # zoom, page info and thumbnail rows
        view_bar = Gtk.Box(spacing=8)
        self.btn_zoom_out = self._tool(view_bar, "−", lambda: self.preview.zoom_out())
        self.btn_zoom_out.set_tooltip_text("Zoom out (Ctrl + mouse wheel)")
        self.zoom_label = Gtk.Label(label="Fit")
        self.zoom_label.set_width_chars(5)
        view_bar.pack_start(self.zoom_label, False, False, 0)
        self.btn_zoom_in = self._tool(view_bar, "+", lambda: self.preview.zoom_in())
        self.btn_zoom_in.set_tooltip_text("Zoom in (Ctrl + mouse wheel); drag the page to move around")
        self.btn_fit = self._tool(view_bar, "Fit", lambda: self.preview.zoom_fit())
        self.btn_fit.set_tooltip_text("Show the whole page")
        self.info = self.label("", "muted")
        view_bar.pack_start(self.info, True, True, 8)
        rows = self.ctx.settings.get("thumbnail_rows")
        self.rows = SegmentedControl(
            [("1", "1 row"), ("2", "2 rows")], active=str(rows), on_changed=self.on_rows_changed
        )
        self.rows.set_tooltip_text("Thumbnails below the page: one row, or two rows")
        view_bar.pack_end(self.rows, False, False, 0)
        view_bar.pack_end(self.label("Thumbnails", "muted"), False, False, 0)
        self.pack_start(view_bar, False, False, 0)

        self.preview = PagePreview(
            on_select=lambda i: self.update_info(),
            cache_dir=os.path.join(self.ctx.scan.session_dir, "display"),
            rows=rows,
            on_zoom=self.on_zoom,
        )
        self.pack_start(self.preview, True, True, 0)
        self.status = self.label("", "muted", wrap=True, selectable=True)
        self.pack_start(self.status, False, False, 0)

        self.connect("realize", lambda *_: self.get_toplevel().connect("key-press-event", self.on_key))
        self.ctx.on("pages-changed", self.reload)
        if self.ctx.features:
            self.ctx.features.extend("extend_preview", self)
            self.ctx.on("features-changed", self.update_feature_buttons)
        self.update_feature_buttons()
        self.reload()

    def update_feature_buttons(self, *_):
        """Show buttons of enabled features only"""
        for fid, btn in self.feature_buttons.items():
            feature = self.ctx.features.get(fid) if self.ctx.features else None
            btn.set_no_show_all(True)
            btn.set_visible(bool(feature and self.ctx.features.is_enabled(feature)))
        self.feature_toolbar.set_visible(any(b.get_visible() for b in self.feature_buttons.values()))

    def _tool(self, bar, text, action):
        """Add a toolbar button that calls action()"""
        btn = Gtk.Button(label=text)
        btn.connect("clicked", lambda *_: action())
        bar.pack_start(btn, False, False, 0)
        return btn

    def on_shown(self):
        """Reload pages when the page is opened"""
        self.reload()

    def set_status(self, text, error=False):
        """Status line under the preview (errors in red)"""
        ctx = self.status.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("status-error")
        self.status.set_text(text)

    # -- view ----------------------------------------------------------------
    def on_zoom(self, zoom):
        """Show the zoom level ('Fit' or a percentage of fit)"""
        self.zoom_label.set_text("Fit" if abs(zoom - 1) < 1e-6 else f"{zoom * 100:.0f}%")

    def on_rows_changed(self, key):
        """1 or 2 rows of thumbnails; remembered"""
        self.ctx.settings.set("thumbnail_rows", int(key))
        self.preview.set_rows(int(key))

    def on_key(self, _widget, event):
        """Page Up / Page Down change page; Ctrl + plus / minus / 0 zoom"""
        from gi.repository import Gdk

        if self.ctx.nav.get_current_page() != "preview" or not self.ctx.scan.pages:
            return False
        focus = self.get_toplevel().get_focus()
        if isinstance(focus, Gtk.Entry):
            return False  # typing in a text field
        key, ctrl = event.keyval, bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if key in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
            self.preview.select(self.preview.selected + (1 if key == Gdk.KEY_Page_Down else -1))
            return True
        if ctrl and key in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.preview.zoom_in()
            return True
        if ctrl and key in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.preview.zoom_out()
            return True
        if ctrl and key in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.preview.zoom_fit()
            return True
        return False

    # -- state -------------------------------------------------------------
    def reload(self, *_):
        """Show the session's pages and enable/disable actions"""
        pages = self.ctx.scan.pages
        self.preview.set_pages(pages)
        has = bool(pages)
        for b in (
            self.btn_left,
            self.btn_right,
            self.btn_flip,
            self.btn_delete,
            self.btn_clear,
            self.btn_back,
            self.btn_fwd,
            self.save_btn,
            self.quick_save_btn,
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_fit,
        ):
            b.set_sensitive(has)
        self.update_info()

    def update_info(self):
        """Show 'Page n of m · mode · dpi' (and the document's file) for the selected page"""
        pages = self.ctx.scan.pages
        if not pages:
            self.info.set_text("")
            return
        p = pages[self.preview.selected]
        doc = self.ctx.scan.document
        name = f" · {os.path.basename(doc['path'])}" if doc else ""
        self.info.set_text(
            f"Page {self.preview.selected + 1} of {len(pages)} · {p['mode']} · {p['dpi']} dpi{name}"
        )

    # -- actions -----------------------------------------------------------
    def rotate(self, degrees):
        """Rotate the selected page and re-render"""
        if self.preview.selected >= 0:
            self.ctx.scan.rotate_page(self.preview.selected, degrees)
            self.preview.refresh_selected()

    def move(self, step):
        """Move the selected page one place earlier (-1) or later (+1)"""
        pages, i = self.ctx.scan.pages, self.preview.selected
        j = i + step
        if 0 <= i < len(pages) and 0 <= j < len(pages):
            pages[i], pages[j] = pages[j], pages[i]
            self.preview.set_pages(pages, selected=j)
            self.update_info()

    def delete_page(self):
        """Delete the selected page and select its neighbour"""
        i = self.preview.selected
        if i >= 0:
            self.ctx.scan.delete_page(i)
            self.preview.set_pages(self.ctx.scan.pages, selected=max(0, i - 1))
            self.reload()

    def clear_pages(self):
        """Remove all pages after confirmation"""
        if self._confirm("Remove all pages?", "Pages that haven't been saved will be lost."):
            self.ctx.scan.clear_pages()
            self.reload()

    def _confirm(self, title, detail):
        """Modal OK/Cancel question; True if OK"""
        dlg = Gtk.MessageDialog(
            transient_for=self.ctx.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=title,
        )
        dlg.format_secondary_text(detail)
        ok = dlg.run() == Gtk.ResponseType.OK
        dlg.destroy()
        return ok

    def open_document(self, path, quick_edit=False):
        """Open a saved document (from Recent) as the current pages; optionally start Quick Edit"""
        if self.ctx.scan.pages and not self._confirm(
            "Open this document?", "The pages shown now will be replaced. Save them first if you need them."
        ):
            return False
        try:
            self.ctx.scan.open_document(path)
        except ValueError as e:
            self.ctx.nav.navigate_to("preview")
            self.set_status(str(e), error=True)
            return False
        self.preview.selected = -1
        self.ctx.nav.navigate_to("preview")
        self.reload()
        self.preview.select(0)
        self.set_status(f"Opened {path}. Save writes your changes back to this file.")
        feature = self.ctx.features.get("quick_edit") if self.ctx.features else None
        if quick_edit and feature and self.ctx.features.is_enabled(feature):
            feature.open_editor(self)
        return True

    # -- saving --------------------------------------------------------------
    def on_save(self):
        """Save to the document's file; a new document goes to the Save folder as a PDF"""
        pages = self.ctx.scan.pages
        if not pages:
            return
        doc = self.ctx.scan.document
        if doc:
            path, fmt = doc["path"], doc["format"]
        else:
            folder = self.ctx.settings.get("save_folder")
            if not os.path.isdir(folder):
                folder = os.path.expanduser("~")
            path, fmt = os.path.join(folder, f"scan-{datetime.now():%Y%m%d-%H%M%S}.pdf"), "pdf"
        self._write(pages, path, fmt)

    def on_save_as(self, _btn):
        """Save As dialog (PDF/PNG/JPEG/TIFF), export, remember the folder"""
        pages = self.ctx.scan.pages
        if not pages:
            return
        dlg = Gtk.FileChooserDialog(
            title="Save scanned document",
            transient_for=self.ctx.window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        doc = self.ctx.scan.document
        folder = os.path.dirname(doc["path"]) if doc else self.ctx.settings.get("save_folder")
        if os.path.isdir(folder):
            dlg.set_current_folder(folder)
        dlg.set_current_name(
            os.path.basename(doc["path"]) if doc else f"scan-{datetime.now():%Y%m%d-%H%M%S}.pdf"
        )
        filters = {}
        for key, fmt in EXPORT_FORMATS.items():
            f = Gtk.FileFilter()
            f.set_name(fmt["label"])
            f.add_pattern(f"*{fmt['ext']}")
            dlg.add_filter(f)
            filters[key] = f

        # keep the extension in sync with the chosen filter
        def filter_changed(*_):
            chosen = next((k for k, f in filters.items() if f == dlg.get_filter()), "pdf")
            name = dlg.get_current_name() or "scan"
            dlg.set_current_name(os.path.splitext(name)[0] + EXPORT_FORMATS[chosen]["ext"])

        dlg.connect("notify::filter", filter_changed)
        response = dlg.run()
        path = dlg.get_filename()
        chosen = next((k for k, f in filters.items() if f == dlg.get_filter()), None)
        dlg.destroy()
        if response != Gtk.ResponseType.ACCEPT or not path:
            return
        self._write(pages, path, format_for_path(path) or chosen or "pdf")

    def _write(self, pages, path, fmt):
        """Export, remember the document and the folder, report the result"""
        try:
            written = export_pages(pages, path, fmt, registry=self.ctx.features)
        except (OSError, ValueError, RuntimeError) as e:
            log.warning("save %s failed: %s", fmt, e)
            self.set_status(f"Could not save: {e}", error=True)
            return None
        self.ctx.scan.document = {"path": written[0], "format": fmt}
        self.ctx.settings.set("save_folder", os.path.dirname(written[0]))
        more = f" (+{len(written) - 1} more)" if len(written) > 1 else ""
        self.set_status(f"Saved {len(pages)} page(s) to {written[0]}{more}")
        self.update_info()
        self.ctx.emit("documents-changed")
        return written
