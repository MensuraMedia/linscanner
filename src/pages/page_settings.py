"""
Settings Page
Theme, default save folder, Black & White style, network scanning (shown as
Not Supported), features, driver visibility and diagnostics.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from config.config_scan import BW_STYLES, NETWORK_SCANNING  # noqa: E402
from config.config_themes import DEFAULT_THEME_ID, get_all_themes, get_theme  # noqa: E402
from pages.page_base import BasePage  # noqa: E402


class SettingsPage(BasePage):
    """User preferences (saved to ~/.config/linscanner/settings.json)"""

    def build_content(self):
        """Theme, scanning and driver setting cards"""
        s = self.ctx.settings
        self.add_title("Settings")

        # theme
        card = self.add_card("Theme")
        self.theme_combo = Gtk.ComboBoxText()
        for tid, theme in get_all_themes().items():
            self.theme_combo.append(tid, theme.name)
        if not self.theme_combo.set_active_id(s.get("theme")):  # e.g. a removed theme
            self.theme_combo.set_active_id(DEFAULT_THEME_ID)
        self.theme_combo.connect("changed", self.on_theme)
        row = Gtk.Box(spacing=12)
        row.pack_start(self.theme_combo, False, False, 0)
        self.swatches = Gtk.Box(spacing=6)
        row.pack_start(self.swatches, False, False, 0)
        card.pack_start(self.form_row("Color scheme", row), False, False, 0)
        self.draw_swatches(get_theme(s.get("theme")))

        # scanning
        card = self.add_card("Scanning")
        self.bw_combo = Gtk.ComboBoxText()
        for key, text in BW_STYLES.items():
            self.bw_combo.append(key, text)
        self.bw_combo.set_active_id(s.get("bw_style"))
        self.bw_combo.connect("changed", lambda c: self.save("bw_style", c.get_active_id()))
        card.pack_start(self.form_row("Black & White", self.bw_combo), False, False, 0)

        self.folder_btn = Gtk.FileChooserButton(
            title="Default save folder", action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        self.folder_btn.set_filename(s.get("save_folder"))
        self.folder_btn.connect("file-set", lambda b: self.save("save_folder", b.get_filename()))
        card.pack_start(self.form_row("Save folder", self.folder_btn), False, False, 0)

        # network scanning: kept visible, but switched off and not selectable
        row = Gtk.Box(spacing=10)
        self.network_check = Gtk.CheckButton(label="Network scanning (Wi-Fi / Ethernet)")
        self.network_check.set_active(NETWORK_SCANNING)
        self.network_check.set_sensitive(False)
        row.pack_start(self.network_check, False, False, 0)
        row.pack_start(self.label("Not Supported", "muted"), False, False, 0)
        card.pack_start(row, False, False, 0)
        desc = self.label(
            "Only scanners connected by USB cable are supported at this time. linscanner does "
            "not search the network for scanners.",
            "muted",
            wrap=True,
        )
        desc.set_margin_start(26)
        card.pack_start(desc, False, False, 0)

        # optional features
        if self.ctx.features:
            card = self.add_card("Features")
            card.pack_start(
                self.label(
                    "Optional modules. Turn any of them off (or delete its file in src/features/) "
                    "without affecting scanning.",
                    "muted",
                    wrap=True,
                ),
                False,
                False,
                0,
            )
            for feature in self.ctx.features.features:
                check = Gtk.CheckButton(label=feature.name)
                check.set_active(self.ctx.features.is_enabled(feature))
                check.connect("toggled", self.on_feature_toggled, feature)
                card.pack_start(check, False, False, 0)
                desc = self.label(feature.description, "muted", wrap=True)
                desc.set_margin_start(26)
                card.pack_start(desc, False, False, 0)
                if hasattr(feature, "settings_widget"):
                    try:
                        widget = feature.settings_widget(self.ctx)
                    except Exception as e:  # a feature's settings UI must not break Settings
                        widget = self.label(f"(settings unavailable: {e})", "status-error")
                    if widget is not None:
                        widget.set_margin_start(26)
                        card.pack_start(widget, False, False, 4)
            for name, error in self.ctx.features.errors:
                card.pack_start(self.label(f"⚠ {name}: {error}", "status-error", wrap=True), False, False, 0)

        # drivers
        card = self.add_card("Drivers")
        self.show_all = Gtk.CheckButton(
            label="Show every driver for each scanner, and SANE's virtual test scanner"
        )
        self.show_all.set_active(s.get("show_all_backends"))
        self.show_all.connect("toggled", self.on_show_all)
        card.pack_start(self.show_all, False, False, 0)
        card.pack_start(
            self.label(
                "Off (recommended): when a scanner is offered by several drivers, only the most "
                "reliable one is listed on the Scan page.",
                "muted",
                wrap=True,
            ),
            False,
            False,
            0,
        )

        # diagnostics (logging)
        card = self.add_card("Diagnostics")
        path = self.ctx.log_path or "logging unavailable"
        card.pack_start(
            self.label(f"Today's log: {path}", "muted", wrap=True, selectable=True), False, False, 0
        )
        row = Gtk.Box(spacing=8)
        open_btn = Gtk.Button(label="Open log folder")
        open_btn.connect("clicked", lambda *_: self.open_log_folder())
        save_btn = Gtk.Button(label="Save diagnostics…")
        save_btn.connect("clicked", lambda *_: self.save_diagnostics())
        row.pack_start(open_btn, False, False, 0)
        row.pack_start(save_btn, False, False, 0)
        card.pack_start(row, False, False, 0)
        self.diag_status = self.label(
            "Logs record detection, every scan (command, pages, what each feature did) and every save. "
            "Serial numbers are removed. Start with --debug for more detail.",
            "muted",
            wrap=True,
        )
        card.pack_start(self.diag_status, False, False, 0)

    def save(self, key, value):
        """Persist a setting and broadcast settings-changed"""
        self.ctx.settings.set(key, value)
        self.ctx.emit("settings-changed", key)

    def on_theme(self, combo):
        """Apply and remember the selected theme"""
        theme = get_theme(combo.get_active_id())
        self.ctx.settings.set("theme", combo.get_active_id())
        self.ctx.theme.apply_theme(theme)
        self.draw_swatches(theme)

    def on_feature_toggled(self, check, feature):
        """Enable or disable a feature module; pages update immediately"""
        self.ctx.features.set_enabled(feature.id, check.get_active())
        self.ctx.emit("features-changed")

    def open_log_folder(self):
        """Open the log folder in the file manager"""
        from gi.repository import Gio

        from utils.util_logging import log_dir

        folder = log_dir()
        os.makedirs(folder, exist_ok=True)
        try:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(folder).get_uri(), None)
        except Exception as e:  # no file manager: show the path instead
            self.diag_status.set_text(f"Log folder: {folder} ({e})")

    def save_diagnostics(self):
        """Save a zip with recent logs, system info, device info and feature states"""
        from datetime import datetime

        from modules import manager_device_info as info
        from utils.util_logging import get_logger, write_diagnostics

        dlg = Gtk.FileChooserDialog(
            title="Save diagnostics", transient_for=self.ctx.window, action=Gtk.FileChooserAction.SAVE
        )
        dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.ACCEPT)
        dlg.set_do_overwrite_confirmation(True)
        dlg.set_current_folder(self.ctx.settings.get("save_folder"))
        dlg.set_current_name(f"linscanner-diagnostics-{datetime.now():%Y%m%d-%H%M}.zip")
        path = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if not path:
            return
        sections = {}
        for d in self.ctx.scan.devices:
            lines = []
            for title, rows in info.sections(d, self.ctx.scan.capabilities.get(d.id)):
                lines.append(f"[{title}]")
                lines += [f"  {k}: {v}" for k, v in rows]
            sections[f"Scanner: {d.vendor} {d.model}"] = "\n".join(lines)
        if self.ctx.features:
            reg = self.ctx.features
            sections["Features"] = "\n".join(
                f"{f.id}: {'on' if reg.is_enabled(f) else 'off'}" for f in reg.features
            ) + ("\nErrors:\n" + "\n".join(f"  {n}: {e}" for n, e in reg.errors) if reg.errors else "")
        sections["Settings"] = "\n".join(
            f"{k}: {self.ctx.settings.get(k)}"
            for k in ("theme", "color_mode", "quality", "paper", "sheet_mode", "bw_style")
        )
        try:
            write_diagnostics(path, sections)
        except OSError as e:
            self.diag_status.set_text(f"Could not save diagnostics: {e}")
            return
        get_logger("ui").info("diagnostics saved to %s", path)
        self.diag_status.set_text(f"Diagnostics saved: {path}")

    def on_show_all(self, btn):
        """Toggle showing all drivers and the test scanner"""
        self.save("show_all_backends", btn.get_active())

    def draw_swatches(self, theme):
        """Show colour dots for the theme's main colours"""
        for child in self.swatches.get_children():
            self.swatches.remove(child)
        for color in (
            theme.window_bg,
            theme.card_bg,
            theme.raised_bg,
            theme.accent_color,
            theme.text_secondary,
        ):
            area = Gtk.DrawingArea()
            area.set_size_request(22, 22)
            rgba = Gdk.RGBA()
            rgba.parse(color)
            area.connect("draw", self._draw_dot, rgba)
            self.swatches.pack_start(area, False, False, 0)
        self.swatches.show_all()

    @staticmethod
    def _draw_dot(area, cr, rgba):
        """Cairo draw handler for one swatch"""
        w, h = area.get_allocated_width(), area.get_allocated_height()
        cr.arc(w / 2, h / 2, min(w, h) / 2 - 1, 0, 6.2832)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1)
        cr.fill_preserve()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.6)
        cr.set_line_width(1)
        cr.stroke()
