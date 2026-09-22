"""
Recent Page
Documents saved with linscanner, newest first. Each entry is a small path with
a folder icon at the start and a document icon at the end of the file name:

- folder icon: opens the system file manager at that folder (with the file
  highlighted when the file manager supports it)
- document icon: opens the document in linscanner (Preview + Quick Edit)

The list is stored on this computer only (~/.local/share/linscanner/recent.json).
"""

import os
from datetime import datetime

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402

from modules.manager_documents import clear_recent, forget_recent, recent_entries  # noqa: E402
from pages.page_base import BasePage  # noqa: E402
from utils.util_logging import get_logger  # noqa: E402

log = get_logger("ui")


def short_path(path):
    """Folder part of a path with the home folder shown as ~"""
    folder = os.path.dirname(path)
    home = os.path.expanduser("~")
    if folder == home or folder.startswith(home + os.sep):
        folder = "~" + folder[len(home) :]
    return folder + os.sep


def document_icon(path):
    """Icon name for a file type (PDF, image, generic document)"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "application-pdf"
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        return "image-x-generic"
    return "text-x-generic"


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
    """Recently saved documents"""

    ICON_SIZE = Gtk.IconSize.LARGE_TOOLBAR

    def build_content(self):
        """Title, Clear list, and the list of documents"""
        self.add_title(
            "Recent",
            "Documents you saved. Click the folder to open it in your file manager, or the document "
            "icon to open it here for Quick Edit.",
        )
        row = Gtk.Box(spacing=10)
        self.clear_btn = Gtk.Button(label="Clear list")
        self.clear_btn.set_tooltip_text("Empty this list (your files are not touched)")
        self.clear_btn.connect("clicked", lambda *_: self.clear())
        row.pack_start(self.clear_btn, False, False, 0)
        self.pack_start(row, False, False, 0)
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pack_start(self.list_box, False, False, 0)
        self.ctx.on("documents-changed", self.refresh)
        self.refresh()

    def on_shown(self):
        """Refresh when opened (files may have been moved or deleted)"""
        self.refresh()

    def refresh(self, *_):
        """Rebuild the list from the recent file"""
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        entries = recent_entries()
        self.clear_btn.set_sensitive(bool(entries))
        if not entries:
            self.list_box.pack_start(
                self.label("Nothing here yet. Documents you save will be listed here.", "muted"),
                False,
                False,
                0,
            )
        for e in entries:
            self.list_box.pack_start(self.entry_row(e), False, False, 0)
        self.list_box.show_all()

    def _icon_button(self, icon, tooltip, action):
        """Flat button showing only an icon"""
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.add(Gtk.Image.new_from_icon_name(icon, self.ICON_SIZE))
        btn.set_tooltip_text(tooltip)
        btn.connect("clicked", lambda *_: action())
        return btn

    def entry_row(self, entry):
        """[folder] ~/path/ name.pdf [document]  ·  details"""
        path = entry["path"]
        card, inner = self.make_card()
        line = Gtk.Box(spacing=4)
        line.pack_start(
            self._icon_button("folder", "Show in the file manager", lambda: self.open_folder(path)),
            False,
            False,
            0,
        )
        folder = self.label(short_path(path), "muted")
        folder.set_ellipsize(Pango.EllipsizeMode.MIDDLE)  # long folders shrink, the name stays
        folder.set_selectable(True)
        line.pack_start(folder, False, True, 0)
        name = self.label(os.path.basename(path), "secondary")
        name.set_selectable(True)
        line.pack_start(name, False, False, 0)
        line.pack_start(
            self._icon_button(
                document_icon(path), "Open in linscanner (Quick Edit)", lambda: self.open_document(path)
            ),
            False,
            False,
            0,
        )
        forget = self._icon_button(
            "window-close-symbolic", "Remove from this list", lambda: self.forget(path)
        )
        line.pack_end(forget, False, False, 0)
        inner.pack_start(line, False, False, 0)
        try:
            when = datetime.fromisoformat(entry.get("saved_at", "")).strftime("%d %b %Y, %H:%M")
        except ValueError:
            when = "?"
        pages = entry.get("pages")
        details = f"{pages} page(s) · {entry.get('format', '?').upper()} · saved {when}"
        inner.pack_start(self.label(details, "muted"), False, False, 0)
        return card

    # -- actions ---------------------------------------------------------------
    def open_folder(self, path):
        """Folder icon: the system file manager at the file's folder"""
        log.info("recent: show %s in the file manager", path)
        show_in_file_manager(path, self.ctx.window)

    def open_document(self, path):
        """Document icon: open the file in Preview and start Quick Edit"""
        log.info("recent: open %s", path)
        preview = self.ctx.nav.get_page_widget("preview")
        preview.open_document(path, quick_edit=True)

    def forget(self, path):
        """Remove one entry (the file is not touched)"""
        forget_recent(path)
        self.refresh()

    def clear(self):
        """Empty the list (files are not touched)"""
        clear_recent()
        self.refresh()
