"""
Preview Page
Shows scanned pages; rotate / delete pages; Save As PDF, PNG, JPEG or TIFF.
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
from utils.util_logging import get_logger  # noqa: E402


class PreviewPage(BasePage):
    """Page viewer with editing actions and Save As"""

    def build_content(self):
        """Toolbar (rotate, delete, clear, Save As), preview and status"""
        self.add_title("Preview", "Check your pages, fix their orientation, then save.")

        # toolbar
        bar = Gtk.Box(spacing=8)
        self.btn_left = self._tool(bar, "Rotate left", lambda: self.rotate(270))
        self.btn_right = self._tool(bar, "Rotate right", lambda: self.rotate(90))
        self.btn_flip = self._tool(bar, "Rotate 180°", lambda: self.rotate(180))
        self.btn_delete = self._tool(bar, "Delete page", self.delete_page)
        self.btn_clear = self._tool(bar, "Clear all", self.clear_pages)
        self.btn_back = self._tool(bar, "Move ←", lambda: self.move(-1))
        self.btn_fwd = self._tool(bar, "Move →", lambda: self.move(1))
        self.info = self.label("", "muted")
        bar.pack_start(self.info, True, True, 8)
        self.save_btn = Gtk.Button(label="Save As…")
        self.save_btn.get_style_context().add_class("primary-pill")
        self.save_btn.connect("clicked", self.on_save_as)
        bar.pack_end(self.save_btn, False, False, 0)
        self.pack_start(bar, False, False, 0)

        # optional feature buttons (Quick Edit, Import images, ...) go in this row
        self.feature_toolbar = Gtk.Box(spacing=8)
        self.feature_buttons = {}
        self.pack_start(self.feature_toolbar, False, False, 0)

        self.preview = PagePreview(on_select=lambda i: self.update_info())
        self.pack_start(self.preview, True, True, 0)
        self.status = self.label("", "muted", wrap=True, selectable=True)
        self.pack_start(self.status, False, False, 0)

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
        ):
            b.set_sensitive(has)
        self.update_info()

    def update_info(self):
        """Show 'Page n of m · mode · dpi' for the selected page"""
        pages = self.ctx.scan.pages
        if not pages:
            self.info.set_text("")
            return
        p = pages[self.preview.selected]
        self.info.set_text(f"Page {self.preview.selected + 1} of {len(pages)} · {p['mode']} · {p['dpi']} dpi")

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
        if self._confirm("Remove all scanned pages?", "Pages that haven't been saved will be lost."):
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
        folder = self.ctx.settings.get("save_folder")
        if os.path.isdir(folder):
            dlg.set_current_folder(folder)
        dlg.set_current_name(f"scan-{datetime.now():%Y%m%d-%H%M%S}.pdf")
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

        fmt = format_for_path(path) or chosen or "pdf"
        try:
            written = export_pages(pages, path, fmt, registry=self.ctx.features)
        except (OSError, ValueError, RuntimeError) as e:
            get_logger("ui").warning("save as %s failed: %s", fmt, e)
            self.status.get_style_context().add_class("status-error")
            self.status.set_text(f"Could not save: {e}")
            return
        self.ctx.settings.set("save_folder", os.path.dirname(written[0]))
        self.status.get_style_context().remove_class("status-error")
        more = f" (+{len(written) - 1} more)" if len(written) > 1 else ""
        self.status.set_text(f"Saved {len(pages)} page(s) to {written[0]}{more}")
