"""
Saved Page
Documents saved with LinScanner, as a table sorted by date (newest first),
with a preview of the selected document underneath:

  Date saved | [folder] Folder | File name [document] | Pages | Format | [trash]

- search box: filters the list on the file name and folder as you type
- folder icon: opens the system file manager at that folder (the file is
  highlighted when the file manager supports it)
- one click on a row: previews the document in the pane below (collapsible;
  drag the divider to resize it)
- document icon (or double-click / Enter on a row): opens the document on the
  Document page (with Quick Edit)
- the file name cell is editable: typing a new name renames the file on disk
- trash icon: removes the entry from the list (the file is not touched)
- Clear: All, or entries older than 5 / 10 / 20 / 30 / 60 / 90 days

Icons are Phosphor Icons. The list is stored on this computer only
(~/.local/share/linscanner/recent.json).
"""

import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from config.config_layout import Layout  # noqa: E402
from modules.manager_documents import (  # noqa: E402
    clear_recent,
    forget_recent,
    open_document,
    recent_entries,
    rename_recent,
    safe_name,
)
from pages.page_base import BasePage  # noqa: E402
from ui.components.component_preview import to_pixbuf  # noqa: E402
from utils.util_display import DisplayCache  # noqa: E402
from utils.util_icons import icon_label_button, icon_pixbuf  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")

CLEAR_CHOICES = [("all", "All")] + [(str(d), f"Older than {d} days") for d in (5, 10, 20, 30, 60, 90)]
ICON_PX = 18

# ListStore columns
C_DATE, C_SORT, C_FOLDER_ICON, C_FOLDER, C_NAME, C_DOC_ICON, C_PAGES, C_FORMAT, C_TRASH, C_PATH = range(10)


def short_path(path):
    """Folder part of a path with the home folder shown as ~"""
    folder = os.path.dirname(path)
    home = os.path.expanduser("~")
    if folder == home or folder.startswith(home + os.sep):
        folder = "~" + folder[len(home) :]
    return folder + os.sep


def show_in_file_manager(path, window=None):
    """Open the file manager at the file's folder, highlighting the file if possible"""
    uri = Gio.File.new_for_path(path).get_uri()
    try:  # freedesktop FileManager1 (Nemo, Nautilus, Dolphin, Thunar, Caja...)
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.freedesktop.FileManager1",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1",
            "ShowItems",
            GLib.Variant("(ass)", ([uri], "")),
            None,
            Gio.DBusCallFlags.NONE,
            3000,
            None,
        )
        return True
    except GLib.Error as e:
        log.debug("FileManager1.ShowItems unavailable (%s); opening the folder", e.message)
    folder_uri = Gio.File.new_for_path(os.path.dirname(path)).get_uri()
    try:
        Gtk.show_uri_on_window(window, folder_uri, Gtk.get_current_event_time())
        return True
    except GLib.Error as e:
        log.warning("could not open the folder %s: %s", os.path.dirname(path), e.message)
        return False


class RecentPage(BasePage):
    """Saved documents, as a table with a preview pane"""

    def build_content(self):
        """Title, Clear controls and the scrollable table"""
        self.add_title(
            "Saved",
            "Documents you saved, newest first. Click one to preview it, double-click to open it in "
            "Document; click its name to rename the file.",
        )
        row = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search saved documents…")
        self.search.set_width_chars(28)
        self.search.connect("search-changed", lambda *_: self.refresh())
        row.pack_start(self.search, False, False, 0)
        row.pack_start(self.label("Clear", "secondary"), False, False, 0)
        self.clear_combo = Gtk.ComboBoxText()
        for key, text in CLEAR_CHOICES:
            self.clear_combo.append(key, text)
        self.clear_combo.set_active_id("all")
        self.clear_combo.set_halign(Gtk.Align.START)
        row.pack_start(self.clear_combo, False, False, 0)
        self.clear_btn = icon_label_button(
            "trash", "Clear", "Remove these entries from the list (your files are not touched)", self.clear
        )
        row.pack_start(self.clear_btn, False, False, 0)
        self.count = self.label("", "muted")
        row.pack_end(self.count, False, False, 0)
        self.pack_start(row, False, False, 0)

        px = GdkPixbuf.Pixbuf
        self.store = Gtk.ListStore(str, str, px, str, str, px, int, str, px, str)
        self.store.set_sort_column_id(C_SORT, Gtk.SortType.DESCENDING)  # newest first
        self.view = Gtk.TreeView(model=self.store)
        self.view.set_enable_search(False)
        self._add_text_column("Date saved", C_DATE, 150, sort=C_SORT)
        self._add_icon_column(C_FOLDER_ICON, "open_folder", "Open the folder in your file manager")
        self._add_text_column("Folder", C_FOLDER, 260, expand=True, ellipsize=Pango.EllipsizeMode.MIDDLE)
        name_col = self._add_text_column(
            "File name", C_NAME, 250, sort=C_NAME, ellipsize=Pango.EllipsizeMode.END
        )
        cell = name_col.get_cells()[0]
        cell.set_property("editable", True)  # click the name to rename the file
        cell.connect("edited", self.on_rename)
        self._add_icon_column(C_DOC_ICON, "open_document", "Open on the Document page (with Quick Edit)")
        self._add_text_column("Pages", C_PAGES, 60, xalign=1.0)
        self._add_text_column("Format", C_FORMAT, 70)
        self._add_icon_column(C_TRASH, "forget", "Remove from this list (the file is not touched)")
        self.view.set_fixed_height_mode(True)  # uniform rows
        self.view.get_selection().connect("changed", lambda *_: self.on_selection_changed())
        self.view.connect("button-press-event", self.on_click)
        # double-click (or Enter) opens the document on the Document page
        self.view.connect("row-activated", lambda _v, path, _c: self.open_document(self.store[path][C_PATH]))
        self.view.connect("motion-notify-event", self.on_motion)
        self.view.set_has_tooltip(True)
        self.view.connect("query-tooltip", self.on_tooltip)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.add(self.view)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # above the list: under it, it would meet the divider when the preview pane is dragged up
        self.empty = self.label("Nothing here yet. Documents you save will be listed here.", "muted")
        self.empty.set_no_show_all(True)
        top.pack_start(self.empty, False, False, 0)
        top.pack_start(scroller, True, True, 0)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.pack1(top, True, False)
        self.paned.pack2(self.build_preview(), False, True)
        self.paned.connect("size-allocate", self.on_paned_allocated)
        self._divider_placed = False
        self.pack_start(self.paned, True, True, 0)
        self.ctx.on("documents-changed", self.refresh)
        self.refresh()

    # -- preview pane ----------------------------------------------------------------
    def build_preview(self):
        """Collapsible preview of the selected document, under the list"""
        self.preview_expander = Gtk.Expander(label="Preview")
        self.preview_expander.set_expanded(bool(self.setting("saved_preview_open", True)))
        self.preview_expander.connect("notify::expanded", lambda *_: self.on_preview_toggled())
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_vexpand(True)
        bar = Gtk.Box(spacing=8)
        self.preview_title = self.label("Select a document to preview it", "muted", wrap=True)
        bar.pack_start(self.preview_title, True, True, 0)
        self.preview_prev = icon_label_button(
            "arrow-left", "", "Previous page", lambda: self.preview_step(-1)
        )
        self.preview_next = icon_label_button("arrow-right", "", "Next page", lambda: self.preview_step(1))
        bar.pack_end(self.preview_next, False, False, 0)
        bar.pack_end(self.preview_prev, False, False, 0)
        box.pack_start(bar, False, False, 0)
        self.preview_image = Gtk.Image()
        holder = Gtk.ScrolledWindow()
        holder.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        holder.set_min_content_height(Layout.dimensions.PREVIEW_MIN_HEIGHT // 2)
        holder.set_vexpand(True)
        holder.get_style_context().add_class("preview-frame")
        holder.add(self.preview_image)
        box.pack_start(holder, True, True, 0)
        self.preview_expander.set_vexpand(True)
        self.preview_expander.add(box)
        self._preview_pages = []
        self._preview_index = 0
        self._preview_path = ""
        return self.preview_expander

    def setting(self, key, default=None):
        """A setting, tolerating a context without settings (used by lightweight tests)"""
        settings = getattr(self.ctx, "settings", None)
        value = settings.get(key) if settings else None
        return default if value is None else value

    def on_paned_allocated(self, _paned, allocation):
        """Give the preview the lower half the first time the page is shown"""
        if self._divider_placed or allocation.height < 200:
            return
        self._divider_placed = True
        self.place_divider()

    def place_divider(self):
        """Half and half while the preview is open; all list while it is collapsed"""
        height = self.paned.get_allocated_height()
        if height < 200:
            return
        self.paned.set_position(height // 2 if self.preview_expander.get_expanded() else height)

    def on_preview_toggled(self):
        """Remember whether the preview pane is open, and fill it when it opens"""
        settings = getattr(self.ctx, "settings", None)
        if settings:
            settings.set("saved_preview_open", self.preview_expander.get_expanded())
        self.place_divider()
        self.show_preview()

    def on_selection_changed(self):
        """A single click selects a row: show it in the preview pane"""
        self.show_preview()

    def selected_path(self):
        """Path of the selected row ('' if none)"""
        model, it = self.view.get_selection().get_selected()
        return model[it][C_PATH] if it else ""

    def show_preview(self):
        """Render the first page of the selected document (only while the pane is open)"""
        path = self.selected_path()
        if not path:  # nothing selected any more: don't leave the last document on screen
            self._preview_path, self._preview_index, self._preview_pages = "", 0, []
            self.preview_title.set_text("Select a document to preview it")
            self.preview_image.clear()
            self.preview_prev.set_sensitive(False)
            self.preview_next.set_sensitive(False)
            return
        if not self.preview_expander.get_expanded():
            self.preview_title.set_text(os.path.basename(path))
            return
        if path != self._preview_path:
            self._preview_path, self._preview_index, self._preview_pages = path, 0, []
            try:
                self._preview_pages = open_document(path, self.preview_dir())
            except ValueError as e:
                self.preview_title.set_text(f"{os.path.basename(path)}: {e}")
                self.preview_image.clear()
                return
        self.render_preview()

    def preview_dir(self):
        """Where preview images are written (this session's folder)"""
        import tempfile

        scan = getattr(self.ctx, "scan", None)
        base = getattr(scan, "session_dir", None) or tempfile.mkdtemp(prefix="linscanner-saved-")
        return os.path.join(base, "saved-preview")

    def preview_step(self, delta):
        """Previous / next page of the previewed document"""
        if self._preview_pages:
            self._preview_index = max(0, min(self._preview_index + delta, len(self._preview_pages) - 1))
            self.render_preview()

    def render_preview(self):
        """Draw the current preview page and update the header"""
        if not self._preview_pages:
            return
        page = self._preview_pages[self._preview_index]
        total = len(self._preview_pages)
        self.preview_title.set_text(
            f"{os.path.basename(self._preview_path)} · page {self._preview_index + 1} of {total}"
        )
        self.preview_prev.set_sensitive(self._preview_index > 0)
        self.preview_next.set_sensitive(self._preview_index < total - 1)
        try:
            img = self._preview_cache().render(page, 700, 520)
            self.preview_image.set_from_pixbuf(to_pixbuf(img))
        except (OSError, ValueError) as e:
            log.warning("preview of %s failed: %s", self._preview_path, e)
            self.preview_image.clear()

    def _preview_cache(self):
        """One display cache for the preview pane"""
        if not hasattr(self, "_cache"):
            self._cache = DisplayCache(self.preview_dir())
        return self._cache

    # -- renaming ---------------------------------------------------------------------
    def on_rename(self, _cell, path_str, new_text):
        """Rename the file on disk (same folder, same extension) and in the list"""
        row = self.store[path_str]
        old = row[C_PATH]
        stem = safe_name(os.path.splitext(new_text)[0])
        if not stem:
            return
        new_path = os.path.join(os.path.dirname(old), stem + os.path.splitext(old)[1])
        if new_path == old:
            return
        if os.path.exists(new_path):
            self.set_message(f"“{os.path.basename(new_path)}” already exists in that folder.", error=True)
            return
        try:
            os.rename(old, new_path)
        except OSError as e:
            self.set_message(f"Could not rename: {e}", error=True)
            return
        rename_recent(old, new_path)
        log.info("renamed a saved document to %s", os.path.basename(new_path))
        self.refresh()
        self.set_message(f"Renamed to “{os.path.basename(new_path)}”.")

    def set_message(self, text, error=False):
        """Short feedback under the search row"""
        self.count.set_text(text)
        ctx = self.count.get_style_context()
        ctx.remove_class("status-error")
        if error:
            ctx.add_class("status-error")

    # -- columns ---------------------------------------------------------------------
    def _add_text_column(self, title, col, width, sort=None, expand=False, xalign=0.0, ellipsize=None):
        """Fixed-width text column"""
        cell = Gtk.CellRendererText()
        cell.set_property("xalign", xalign)
        if ellipsize is not None:
            cell.set_property("ellipsize", ellipsize)
        column = Gtk.TreeViewColumn(title, cell, text=col)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(width)
        column.set_expand(expand)
        column.set_resizable(True)
        if sort is not None:
            column.set_sort_column_id(sort)
        self.view.append_column(column)
        return column

    def _add_icon_column(self, col, action, tooltip):
        """Narrow column of clickable icons"""
        cell = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", cell, pixbuf=col)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(ICON_PX + 18)
        column.action = (action, tooltip)
        self.view.append_column(column)
        return column

    def _column_at(self, x, y):
        """(row path, column) under a point of the table, or (None, None)"""
        hit = self.view.get_path_at_pos(int(x), int(y))
        return (hit[0], hit[1]) if hit else (None, None)

    # -- data -----------------------------------------------------------------------
    def on_shown(self):
        """Refresh when opened (files may have been moved or deleted)"""
        self.refresh()

    def refresh(self, *_):
        """Reload the table from the recent list (newest first)"""
        self.store.clear()
        entries = recent_entries()
        query = self.search.get_text().strip().lower() if hasattr(self, "search") else ""
        if query:  # search the file name and the folder
            entries = [e for e in entries if query in e["path"].lower()]
        folder = icon_pixbuf("folder-open", ICON_PX)
        doc = icon_pixbuf("file-text", ICON_PX)
        trash = icon_pixbuf("trash", ICON_PX)
        for e in entries:
            try:
                saved = datetime.fromisoformat(e.get("saved_at", ""))
                shown, key = saved.strftime("%Y-%m-%d  %H:%M"), saved.isoformat()
            except ValueError:
                shown, key = "?", ""
            self.store.append(
                [
                    shown,
                    key,
                    folder,
                    short_path(e["path"]),
                    os.path.basename(e["path"]),
                    doc,
                    int(e.get("pages") or 0),
                    str(e.get("format", "?")).upper(),
                    trash,
                    e["path"],
                ]
            )
        self.store.set_sort_column_id(C_SORT, Gtk.SortType.DESCENDING)
        self.clear_btn.set_sensitive(bool(entries))
        self.empty.set_visible(not entries)
        if query and not entries:
            self.empty.set_text(f"Nothing matches “{self.search.get_text().strip()}”.")
        else:
            self.empty.set_text("Nothing here yet. Documents you save will be listed here.")
        self.set_message(
            f"{len(entries)} document(s)" + (f" matching “{query}”" if query else "") if entries else ""
        )
        self.show_preview()

    # -- events ---------------------------------------------------------------------
    def on_click(self, _view, event):
        """A click on an icon cell runs its action"""
        if event.button != 1 or event.type != Gdk.EventType.BUTTON_PRESS:
            return False
        path, column = self._column_at(event.x, event.y)
        action = getattr(column, "action", None)
        if path is None or not action:
            return False
        getattr(self, action[0])(self.store[path][C_PATH])
        return True

    def on_motion(self, view, event):
        """Hand pointer over the icon cells"""
        _path, column = self._column_at(event.x, event.y)
        window = view.get_bin_window()
        name = "pointer" if getattr(column, "action", None) else None
        window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name) if name else None)
        return False

    def on_tooltip(self, view, x, y, keyboard, tooltip):
        """Tooltips for the icon cells"""
        bx, by = view.convert_widget_to_bin_window_coords(x, y)
        path, column = self._column_at(bx, by)
        action = getattr(column, "action", None)
        if path is None or not action:
            return False
        tooltip.set_text(action[1])
        return True

    # -- actions ------------------------------------------------------------------------
    def open_folder(self, path):
        """Folder icon: the system file manager at the file's folder"""
        log.info("recent: show %s in the file manager", path)
        show_in_file_manager(path, self.ctx.window)

    def open_document(self, path):
        """Document icon: open the file on the Document page and start Quick Edit"""
        log.info("recent: open %s", path)
        self.ctx.nav.get_page_widget("preview").open_document(path, quick_edit=True)

    def forget(self, path):
        """Trash icon: remove one entry (the file is not touched)"""
        forget_recent(path)
        self.refresh()

    def clear(self):
        """Clear all entries, or those older than the chosen number of days (after confirming)"""
        key = self.clear_combo.get_active_id() or "all"
        days = None if key == "all" else int(key)
        what = "all entries" if days is None else f"entries older than {days} days"
        dlg = Gtk.MessageDialog(
            transient_for=self.ctx.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Clear {what} from the Recent list?",
        )
        dlg.format_secondary_text("Only the list changes. Your saved files are not touched.")
        ok = dlg.run() == Gtk.ResponseType.OK
        dlg.destroy()
        if ok:
            removed = clear_recent(days)
            log.info("recent: cleared %d entr(ies) (%s)", removed, what)
            self.refresh()
