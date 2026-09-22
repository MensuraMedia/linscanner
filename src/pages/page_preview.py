"""
Preview Page
Shows scanned (or opened) pages with a PDF-editor style toolbar (Phosphor icons,
captions on hover), grouped left to right:

  History   undo, redo
  Pages     add page (PDF / images), add image, duplicate, save page as,
            delete page, clear all
  Arrange   rotate left / right / 180°, move left / right, reverse order
  Content   add text, signature (Quick Edit feature)
                                                              Save / Save As…
  View bar  first / previous / next / last page, zoom out / in, fit page,
            fit width, thumbnails in 1 or 2 rows

The groups wrap onto a second row in narrow windows. Every change to the pages
can be undone (Ctrl+Z) and redone (Ctrl+Shift+Z / Ctrl+Y).

- Save: writes to the document's file (the last Save / Save As, or the file
  opened from Recent). A new document is saved as a PDF in the Save folder
  with an automatic name, without a dialog.
- Save As…: choose the name, folder and format.
"""

import copy
import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango  # noqa: E402

from config.config_scan import EXPORT_FORMATS  # noqa: E402
from modules.manager_export import export_pages, format_for_path  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_preview import PagePreview  # noqa: E402
from ui.components.component_segmented import SegmentedControl  # noqa: E402
from utils.util_icons import icon_button  # noqa: E402
from modules.manager_scan import MAIN_DOC  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

HISTORY_MAX = 30  # undo steps kept
TOOL_GROUPS = ("history", "pages", "arrange", "content")
ADDABLE = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


class PreviewPage(BasePage):
    """Page viewer with editing actions, undo, zoom, Save and Save As"""

    def build_content(self):
        """Toolbar groups, Save / Save As, view bar, preview and status"""
        self.add_title("Preview", "Check your pages, fix their orientation, then save.")
        self.undo_stack, self.redo_stack = [], []
        self._own_change = False
        self.feature_buttons = {}

        top = Gtk.Box(spacing=12)
        # tool groups wrap onto a second row when the window is narrow
        self.tools = Gtk.FlowBox()
        self.tools.set_selection_mode(Gtk.SelectionMode.NONE)
        self.tools.set_max_children_per_line(len(TOOL_GROUPS))
        self.tools.set_column_spacing(4)
        self.tools.set_row_spacing(6)
        self.tools.set_homogeneous(False)
        self.tools.set_valign(Gtk.Align.START)
        self.groups = {}
        for name in TOOL_GROUPS:
            box = Gtk.Box(spacing=4)
            box.get_style_context().add_class("toolbar-group")
            self.groups[name] = box
            child = Gtk.FlowBoxChild()
            child.set_can_focus(False)
            child.add(box)
            self.tools.add(child)
        top.pack_start(self.tools, True, True, 0)

        self.btn_undo = self.tool("history", "arrow-u-up-left", "Undo (Ctrl+Z)", self.undo)
        self.btn_redo = self.tool("history", "arrow-u-up-right", "Redo (Ctrl+Shift+Z)", self.redo)
        self.btn_add_page = self.tool(
            "pages",
            "file-plus",
            "Add Page: insert the pages of a PDF (or images) after this page",
            self.add_pages,
        )
        self.btn_add_page.works_without_pages = True
        self.btn_duplicate = self.tool("pages", "copy", "Duplicate page", self.duplicate_page)
        self.btn_extract = self.tool(
            "pages", "export", "Save this page as… (extract it to its own file)", self.extract_page
        )
        self.btn_delete = self.tool("pages", "file-x", "Delete page", self.delete_page)
        self.btn_clear = self.tool("pages", "trash-simple", "Clear all pages", self.clear_pages)
        self.btn_left = self.tool(
            "arrange", "arrow-counter-clockwise", "Rotate left (90° anticlockwise)", lambda: self.rotate(270)
        )
        self.btn_right = self.tool(
            "arrange", "arrow-clockwise", "Rotate right (90° clockwise)", lambda: self.rotate(90)
        )
        self.btn_flip = self.tool(
            "arrange", "arrows-clockwise", "Rotate 180° (upside down)", lambda: self.rotate(180)
        )
        self.btn_back = self.tool("arrange", "arrow-left", "Move page left (earlier)", lambda: self.move(-1))
        self.btn_fwd = self.tool("arrange", "arrow-right", "Move page right (later)", lambda: self.move(1))
        self.btn_reverse = self.tool(
            "arrange",
            "arrows-left-right",
            "Reverse page order (e.g. a stack fed last page first)",
            self.reverse_pages,
        )
        # the "content" group is filled by feature modules (Add Text, Signature)
        self.groups["content"].get_parent().set_no_show_all(True)

        # Save above Save As
        saves = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.quick_save_btn = Gtk.Button(label="Save")
        self.quick_save_btn.get_style_context().add_class("primary-pill")
        self.quick_save_btn.set_tooltip_text(
            "Save to this document's file. A new document is saved as a PDF in your Save folder."
        )
        self.quick_save_btn.connect("clicked", lambda *_: self.on_save())
        self.save_all_btn = Gtk.Button(label="Save All")
        self.save_all_btn.set_tooltip_text(
            "Save every document as its own PDF in your default save location (Single Page scans)"
        )
        self.save_all_btn.connect("clicked", lambda *_: self.on_save_all())
        self.save_all_btn.set_no_show_all(True)
        self.save_btn = Gtk.Button(label="Save As…")
        self.save_btn.connect("clicked", self.on_save_as)
        for b in (self.quick_save_btn, self.save_all_btn, self.save_btn):
            b.set_halign(Gtk.Align.END)  # each button as wide as its label
            saves.pack_start(b, False, False, 0)
        top.pack_end(saves, False, False, 0)
        self.pack_start(top, False, False, 0)

        # view bar: page navigation, zoom, page info, thumbnail rows
        view_bar = Gtk.Box(spacing=4)
        nav = Gtk.Box(spacing=4)
        nav.get_style_context().add_class("toolbar-group")
        self.btn_first = self._icon(
            nav, "caret-double-left", "First page (Home)", lambda: self.preview.select(0)
        )
        self.btn_prev = self._icon(nav, "caret-left", "Previous page (Page Up)", lambda: self.step(-1))
        self.btn_next = self._icon(nav, "caret-right", "Next page (Page Down)", lambda: self.step(1))
        self.btn_last = self._icon(
            nav,
            "caret-double-right",
            "Last page (End)",
            lambda: self.preview.select(len(self.ctx.scan.pages) - 1),
        )
        view_bar.pack_start(nav, False, False, 0)
        zoom = Gtk.Box(spacing=4)
        zoom.get_style_context().add_class("toolbar-group")
        self.btn_zoom_out = self._icon(
            zoom, "magnifying-glass-minus", "Zoom out (Ctrl −, Ctrl + wheel)", lambda: self.preview.zoom_out()
        )
        self.zoom_label = Gtk.Label(label="Fit")
        self.zoom_label.set_width_chars(5)
        zoom.pack_start(self.zoom_label, False, False, 0)
        self.btn_zoom_in = self._icon(
            zoom,
            "magnifying-glass-plus",
            "Zoom in (Ctrl +, Ctrl + wheel); drag the page to move around",
            lambda: self.preview.zoom_in(),
        )
        self.btn_fit = self._icon(
            zoom, "arrows-in", "Fit the whole page (Ctrl 0)", lambda: self.preview.zoom_fit()
        )
        self.btn_fit_width = self._icon(
            zoom, "arrows-out-line-horizontal", "Fit the page width", lambda: self.preview.zoom_fit_width()
        )
        view_bar.pack_start(zoom, False, False, 6)
        self.info = self.label("", "muted")
        self.info.set_ellipsize(Pango.EllipsizeMode.END)  # narrow windows shorten the page info
        view_bar.pack_start(self.info, True, True, 6)
        rows = self.ctx.settings.get("thumbnail_rows")
        self.rows = SegmentedControl(
            [("1", "1 row"), ("2", "2 rows")], active=str(rows), on_changed=self.on_rows_changed
        )
        self.rows.set_tooltip_text("Thumbnails below the page: one row, or two rows")
        view_bar.pack_end(self.rows, False, False, 0)
        view_bar.pack_end(self.label("Thumbnails", "muted"), False, False, 4)
        self.pack_start(view_bar, False, False, 0)

        self.preview = PagePreview(
            on_select=lambda i: self.update_info(),
            cache_dir=os.path.join(self.ctx.scan.session_dir, "display"),
            rows=rows,
            on_zoom=self.on_zoom,
            label_for=self.thumb_label,
        )
        self.pack_start(self.preview, True, True, 0)
        self.status = self.label("", "muted", wrap=True, selectable=True)
        self.pack_start(self.status, False, False, 0)

        self.connect("realize", lambda *_: self.get_toplevel().connect("key-press-event", self.on_key))
        self.ctx.on("pages-changed", self.on_pages_changed)
        if self.ctx.features:
            self.ctx.features.extend("extend_preview", self)
            self.ctx.on("features-changed", self.update_feature_buttons)
        self.update_feature_buttons()
        self.reload()

    # -- toolbar ---------------------------------------------------------------
    @staticmethod
    def _icon(box, name, caption, action):
        """Add an icon button with a hover caption to a box"""
        btn = icon_button(name, caption, action)
        box.pack_start(btn, False, False, 0)
        return btn

    def tool(self, group, name, caption, action, feature_id=None):
        """Add an icon button (with a hover caption) to a toolbar group; features pass their id"""
        btn = self._icon(self.groups[group], name, caption, action)
        if feature_id:
            self.feature_buttons.setdefault(feature_id, []).append(btn)
            self.groups[group].get_parent().set_no_show_all(False)
        return btn

    def add_tool(self, group, button, feature_id, after=None):
        """Add a ready-made button to a group (for feature modules), optionally right after another"""
        box = self.groups[group]
        box.pack_start(button, False, False, 0)
        if after is not None and after in box.get_children():
            box.reorder_child(button, box.get_children().index(after) + 1)
        self.feature_buttons.setdefault(feature_id, []).append(button)
        self.groups[group].get_parent().set_no_show_all(False)

    def update_feature_buttons(self, *_):
        """Show buttons of enabled features only; hide a group left empty"""
        for fid, buttons in self.feature_buttons.items():
            feature = self.ctx.features.get(fid) if self.ctx.features else None
            on = bool(feature and self.ctx.features.is_enabled(feature))
            for btn in buttons:
                btn.set_no_show_all(not on)  # hidden buttons stay hidden when the window is shown
                btn.show_all() if on else btn.hide()
        for box in self.groups.values():
            child = box.get_parent()
            if any(not c.get_no_show_all() for c in box.get_children()):
                child.set_no_show_all(False)
                child.show_all()
            else:
                child.set_no_show_all(True)
                child.hide()

    def on_shown(self):
        """Reload pages when the page is opened"""
        self.reload()

    def set_status(self, text, error=False):
        """Status line under the preview (errors in red)"""
        ctx = self.status.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("status-error")
        self.status.set_text(text)

    # -- undo / redo ---------------------------------------------------------------
    def _snapshot(self):
        """The pages and documents as they are now"""
        scan = self.ctx.scan
        return (
            copy.deepcopy(scan.pages),
            (copy.deepcopy(scan.documents), copy.deepcopy(scan._saved), scan.next_doc),
            self.preview.selected,
        )

    def checkpoint(self, snapshot=None):
        """Remember the pages before a change (features call this too, with a snapshot taken earlier)"""
        self.undo_stack.append(snapshot or self._snapshot())
        del self.undo_stack[:-HISTORY_MAX]
        self.redo_stack.clear()
        self._update_history_buttons()

    def _restore(self, snap):
        """Put a snapshot back"""
        pages, (documents, saved, next_doc), selected = snap
        self.ctx.scan.pages[:] = pages
        self.ctx.scan.documents, self.ctx.scan._saved, self.ctx.scan.next_doc = documents, saved, next_doc
        self.preview.set_pages(self.ctx.scan.pages, selected=min(max(selected, 0), len(pages) - 1))
        self.reload()

    def undo(self):
        """Undo the last change to the pages"""
        if self.undo_stack:
            self.redo_stack.append(self._snapshot())
            self._restore(self.undo_stack.pop())
            self.set_status("Undone.")

    def redo(self):
        """Redo a change that was undone"""
        if self.redo_stack:
            self.undo_stack.append(self._snapshot())
            self._restore(self.redo_stack.pop())
            self.set_status("Redone.")

    def _update_history_buttons(self):
        """Undo / redo available only when there is something to undo / redo"""
        self.btn_undo.set_sensitive(bool(self.undo_stack))
        self.btn_redo.set_sensitive(bool(self.redo_stack))

    def on_pages_changed(self, *_):
        """Pages changed elsewhere (a scan, an import): start a fresh history"""
        if not self._own_change:
            self.undo_stack.clear()
            self.redo_stack.clear()
        self.reload()

    def changed(self):
        """Tell other pages this page changed the pages (history is kept)"""
        self._own_change = True
        try:
            self.ctx.emit("pages-changed")
        finally:
            self._own_change = False

    # -- view ----------------------------------------------------------------
    def on_zoom(self, zoom):
        """Show the zoom level ('Fit' or a percentage of fit)"""
        self.zoom_label.set_text("Fit" if abs(zoom - 1) < 1e-6 else f"{zoom * 100:.0f}%")

    def on_rows_changed(self, key):
        """1 or 2 rows of thumbnails; remembered"""
        self.ctx.settings.set("thumbnail_rows", int(key))
        self.preview.set_rows(int(key))

    def step(self, delta):
        """Previous / next page"""
        self.preview.select(self.preview.selected + delta)

    def on_key(self, _widget, event):
        """Page keys, Home / End, zoom and undo / redo shortcuts"""
        from gi.repository import Gdk

        if self.ctx.nav.get_current_page() != "preview" or not self.ctx.scan.pages:
            return False
        focus = self.get_toplevel().get_focus()
        if isinstance(focus, Gtk.Entry):
            return False  # typing in a text field
        key = event.keyval
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        if key in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
            self.step(1 if key == Gdk.KEY_Page_Down else -1)
            return True
        if key in (Gdk.KEY_Home, Gdk.KEY_End) and not ctrl:
            self.preview.select(0 if key == Gdk.KEY_Home else len(self.ctx.scan.pages) - 1)
            return True
        if ctrl and key in (Gdk.KEY_z, Gdk.KEY_Z):
            self.redo() if shift else self.undo()
            return True
        if ctrl and key in (Gdk.KEY_y, Gdk.KEY_Y):
            self.redo()
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
            self.btn_reverse,
            self.btn_duplicate,
            self.btn_extract,
            self.btn_first,
            self.btn_prev,
            self.btn_next,
            self.btn_last,
            self.save_btn,
            self.quick_save_btn,
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_fit,
            self.btn_fit_width,
        ):
            b.set_sensitive(has)
        several = len(self.ctx.scan.doc_ids()) > 1
        self.save_all_btn.set_no_show_all(not several)
        self.save_all_btn.show() if several else self.save_all_btn.hide()
        self.quick_save_btn.set_tooltip_text(
            "Save the selected document (each Single Page sheet is its own document)"
            if several
            else "Save to this document's file. A new document is saved as a PDF in your default save location."
        )
        for buttons in self.feature_buttons.values():
            for b in buttons:
                b.set_sensitive(has or getattr(b, "works_without_pages", False))
        self._update_history_buttons()
        self.update_info()

    def current_doc(self):
        """Document id of the selected page"""
        pages = self.ctx.scan.pages
        i = self.preview.selected
        return pages[i].get("doc", MAIN_DOC) if 0 <= i < len(pages) else MAIN_DOC

    def thumb_label(self, i, page):
        """Thumbnail caption: 'Page n', or 'Doc d' (+ ✓ when saved) when there are several documents"""
        scan = self.ctx.scan
        docs = scan.doc_ids()
        if len(docs) <= 1:
            return f"Page {i + 1}"
        doc = page.get("doc", MAIN_DOC)
        pages = scan.doc_pages(doc)
        part = f" · p{pages.index(page) + 1}" if len(pages) > 1 and page in pages else ""
        return f"Doc {docs.index(doc) + 1}{part}" + ("  ✓" if scan.doc_is_saved(doc) else "")

    def update_info(self):
        """Show 'Page n of m · mode · dpi' (and the document and its file) for the selected page"""
        scan = self.ctx.scan
        pages = scan.pages
        if not pages:
            self.info.set_text("")
            return
        p = pages[self.preview.selected]
        docs = scan.doc_ids()
        doc = p.get("doc", MAIN_DOC)
        file = scan.documents.get(doc)
        name = f" · {os.path.basename(file['path'])}" if file else ""
        if len(docs) > 1:
            saved = " (saved)" if scan.doc_is_saved(doc) else " (not saved)"
            where = f"Document {docs.index(doc) + 1} of {len(docs)}{saved}"
        else:
            where = f"Page {self.preview.selected + 1} of {len(pages)}"
        self.info.set_text(f"{where} · {p['mode']} · {p['dpi']} dpi{name}")

    # -- actions -----------------------------------------------------------
    def rotate(self, degrees):
        """Rotate the selected page and re-render"""
        if self.preview.selected >= 0:
            self.checkpoint()
            self.ctx.scan.rotate_page(self.preview.selected, degrees)
            self.preview.refresh_selected()

    def move(self, step):
        """Move the selected page one place earlier (-1) or later (+1)"""
        pages, i = self.ctx.scan.pages, self.preview.selected
        j = i + step
        if 0 <= i < len(pages) and 0 <= j < len(pages):
            self.checkpoint()
            pages[i], pages[j] = pages[j], pages[i]
            self.preview.set_pages(pages, selected=j)
            self.update_info()

    def reverse_pages(self):
        """Reverse the page order"""
        pages = self.ctx.scan.pages
        if len(pages) > 1:
            self.checkpoint()
            pages.reverse()
            self.preview.set_pages(pages, selected=len(pages) - 1 - self.preview.selected)
            self.update_info()
            self.set_status("Page order reversed.")

    def duplicate_page(self):
        """Insert a copy of the selected page right after it"""
        i = self.preview.selected
        if i >= 0:
            self.checkpoint()
            self.ctx.scan.pages.insert(i + 1, copy.deepcopy(self.ctx.scan.pages[i]))
            self.preview.set_pages(self.ctx.scan.pages, selected=i + 1)
            self.reload()
            self.set_status(f"Page {i + 1} duplicated.")

    def delete_page(self):
        """Delete the selected page and select its neighbour"""
        i = self.preview.selected
        if i >= 0:
            self.checkpoint()
            self.ctx.scan.delete_page(i)
            self.preview.set_pages(self.ctx.scan.pages, selected=max(0, i - 1))
            self.reload()

    def clear_pages(self):
        """Remove all pages after confirmation (Undo brings them back)"""
        if self._confirm(
            "Remove all pages?", "You can bring them back with Undo until you close LinScanner."
        ):
            self.checkpoint()
            self.ctx.scan.clear_pages()
            self.reload()

    def add_pages(self, paths=None):
        """Add Page: insert the pages of PDFs or images after the selected page"""
        from modules.manager_documents import open_document

        if paths is None:
            paths = self._choose_files("Add pages from a PDF or images")
        if not paths:
            return 0
        added = []
        for path in paths:
            try:
                added += open_document(path, self.ctx.scan.session_dir)
            except ValueError as e:
                self.set_status(f"{os.path.basename(path)}: {e}", error=True)
        if not added:
            return 0
        self.checkpoint()
        doc = self.current_doc() if self.ctx.scan.pages else MAIN_DOC
        for page in added:
            page["doc"] = doc  # added pages join the document they're inserted into
        at = self.preview.selected + 1 if self.ctx.scan.pages else 0
        self.ctx.scan.pages[at:at] = added
        self.preview.set_pages(self.ctx.scan.pages, selected=at)
        self.reload()
        self.changed()
        self.set_status(
            f"Added {len(added)} page(s) after page {at}." if at else f"Added {len(added)} page(s)."
        )
        return len(added)

    def _choose_files(self, title):
        """File dialog for PDFs and images (several at once)"""
        dlg = Gtk.FileChooserDialog(
            title=title, transient_for=self.ctx.window, action=Gtk.FileChooserAction.OPEN
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Add", Gtk.ResponseType.ACCEPT)
        dlg.set_select_multiple(True)
        flt = Gtk.FileFilter()
        flt.set_name("PDF and images")
        for ext in ADDABLE:
            flt.add_pattern(f"*{ext}")
            flt.add_pattern(f"*{ext.upper()}")
        dlg.add_filter(flt)
        paths = dlg.get_filenames() if dlg.run() == Gtk.ResponseType.ACCEPT else []
        dlg.destroy()
        return paths

    def extract_page(self):
        """Save only the selected page to a file of its own (the document is unchanged)"""
        i = self.preview.selected
        if i >= 0:
            self.on_save_as(
                None, pages=[self.ctx.scan.pages[i]], title=f"Save page {i + 1} as", remember=False
            )

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
        self.undo_stack.clear()
        self.redo_stack.clear()
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
    def _doc_to_save(self):
        """(doc id, its pages): the selected page's document (all pages when there is only one)"""
        scan = self.ctx.scan
        docs = scan.doc_ids()
        if len(docs) <= 1:
            return (docs[0] if docs else MAIN_DOC), scan.pages
        doc = self.current_doc()
        return doc, scan.doc_pages(doc)

    def _default_path(self, n=None):
        """A new file name in the default save location (Settings)"""
        folder = self.ctx.settings.get("save_folder")
        if not os.path.isdir(folder):
            folder = os.path.expanduser("~")
        part = f"-{n:03d}" if n is not None else ""
        return os.path.join(folder, f"scan-{datetime.now():%Y%m%d-%H%M%S}{part}.pdf")

    def on_save(self):
        """Save the document to its file; a new document goes to the default save location as a PDF"""
        if not self.ctx.scan.pages:
            return
        doc, pages = self._doc_to_save()
        file = self.ctx.scan.documents.get(doc)
        if file:
            path, fmt = file["path"], file["format"]
        else:
            several = len(self.ctx.scan.doc_ids()) > 1
            n = self.ctx.scan.doc_ids().index(doc) + 1 if several else None
            path, fmt = self._default_path(n), "pdf"
        self._write(pages, path, fmt, doc=doc)

    def on_save_all(self):
        """Save every document (Single Page sheets) as its own PDF in the default save location"""
        scan = self.ctx.scan
        saved = 0
        for n, doc in enumerate(scan.doc_ids(), start=1):
            file = scan.documents.get(doc)
            path, fmt = (file["path"], file["format"]) if file else (self._default_path(n), "pdf")
            if self._write(scan.doc_pages(doc), path, fmt, doc=doc, report=False):
                saved += 1
        folder = self.ctx.settings.get("save_folder")
        self.set_status(f"Saved {saved} document(s) in {folder}.")
        self.preview.set_pages(scan.pages)  # the ✓ marks
        self.update_info()

    def on_save_as(self, _btn, pages=None, title="Save scanned document", remember=True):
        """Save As dialog (PDF/PNG/JPEG/TIFF) for the document (or given pages), export, report"""
        doc = None
        if pages is None:
            doc, pages = self._doc_to_save()
        if not pages:
            return
        dlg = Gtk.FileChooserDialog(
            title=title, transient_for=self.ctx.window, action=Gtk.FileChooserAction.SAVE
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        file = self.ctx.scan.documents.get(doc) if doc is not None else None
        folder = os.path.dirname(file["path"]) if file else self.ctx.settings.get("save_folder")
        if not os.path.isdir(folder):
            folder = self.ctx.settings.get("save_folder")  # the default save location (Settings)
        if os.path.isdir(folder):
            dlg.set_current_folder(folder)
        if remember and file:
            dlg.set_current_name(os.path.basename(file["path"]))
        else:
            dlg.set_current_name(f"{'page' if not remember else 'scan'}-{datetime.now():%Y%m%d-%H%M%S}.pdf")
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
        self._write(pages, path, format_for_path(path) or chosen or "pdf", doc=doc if remember else None)

    def _write(self, pages, path, fmt, doc=None, report=True, remember=None):
        """Export pages; with a doc id, remember its file and mark it saved; report the result"""
        if remember is False:
            doc = None
        try:
            written = export_pages(pages, path, fmt, registry=self.ctx.features)
        except (OSError, ValueError, RuntimeError) as e:
            log.warning("save %s failed: %s", fmt, e)
            self.set_status(f"Could not save: {e}", error=True)
            return None
        if doc is not None:
            self.ctx.scan.documents[doc] = {"path": written[0], "format": fmt}
            self.ctx.scan.mark_saved(doc)  # once every document is saved, the next scan starts afresh
        if report:
            more = f" (+{len(written) - 1} more)" if len(written) > 1 else ""
            docs = self.ctx.scan.doc_ids()
            which = (
                f"Document {docs.index(doc) + 1} of {len(docs)}: " if doc in docs and len(docs) > 1 else ""
            )
            self.set_status(f"{which}saved {len(pages)} page(s) to {written[0]}{more}")
            self.preview.set_pages(self.ctx.scan.pages)  # the ✓ marks
            self.update_info()
        self.ctx.emit("documents-changed")
        return written
