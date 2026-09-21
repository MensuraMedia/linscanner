"""
Scan profiles
One-click presets on the Scan page (colour, quality, paper, sheets), with
built-in profiles plus your own ("Save current as profile").
"""

from features import BaseFeature

BUILT_IN = {
    "Document (B&W)": {"color_mode": "bw", "quality": "medium", "paper": "letter", "sheet_mode": "all"},
    "Color document": {"color_mode": "color", "quality": "medium", "paper": "letter", "sheet_mode": "all"},
    "Photo / high detail": {"color_mode": "color", "quality": "high", "paper": "letter", "sheet_mode": "one"},
    "Receipt": {"color_mode": "bw", "quality": "low", "paper": "auto", "sheet_mode": "one"},
    "Archive (A4, high)": {"color_mode": "color", "quality": "high", "paper": "a4", "sheet_mode": "all"},
}


class Feature(BaseFeature):
    """Presets for the Scan page"""

    id = "profiles"
    name = "Scan profiles"
    description = "One-click presets (Document, Photo, Receipt, …) and your own saved profiles."
    default_enabled = False
    order = 80

    def all_profiles(self):
        """Built-in profiles plus the user's own"""
        return {**BUILT_IN, **(self.option("user_profiles", {}) or {})}

    def apply(self, scan_page, name):
        """Set the Scan page controls from a profile"""
        prof = self.all_profiles().get(name)
        if not prof:
            return
        scan_page.color.set_active(prof["color_mode"])
        scan_page.quality.set_active(prof["quality"])
        scan_page.paper_combo.set_active_id(prof["paper"])
        scan_page.sheets.set_active(prof.get("sheet_mode", "all"))
        for key in ("color_mode", "quality", "paper", "sheet_mode"):
            scan_page.ctx.settings.set(key, prof.get(key, scan_page.ctx.settings.get(key)))
        scan_page.update_summary()

    def save_current(self, scan_page, name):
        """Store the Scan page's current choices as a user profile"""
        profiles = dict(self.option("user_profiles", {}) or {})
        profiles[name] = {
            "color_mode": scan_page.color.get_active(),
            "quality": scan_page.quality.get_active(),
            "paper": scan_page.paper_combo.get_active_id(),
            "sheet_mode": scan_page.sheets.get_active(),
        }
        self.set_option("user_profiles", profiles)

    def extend_scan_page(self, page):
        """Profile picker + 'Save as profile' at the top of the Options section"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        combo = Gtk.ComboBoxText()

        def refill():
            combo.remove_all()
            combo.append("", "Choose a profile…")
            for name in self.all_profiles():
                combo.append(name, name)
            combo.set_active_id("")

        refill()
        combo.connect("changed", lambda c: c.get_active_id() and self.apply(page, c.get_active_id()))
        save = Gtk.Button(label="Save as profile…")

        def on_save(_btn):
            dlg = Gtk.Dialog(title="Save profile", transient_for=page.ctx.window, modal=True)
            dlg.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.OK)
            entry = Gtk.Entry()
            entry.set_placeholder_text("Profile name")
            entry.set_activates_default(True)
            dlg.set_default_response(Gtk.ResponseType.OK)
            dlg.get_content_area().pack_start(entry, True, True, 8)
            dlg.show_all()
            if dlg.run() == Gtk.ResponseType.OK and entry.get_text().strip():
                self.save_current(page, entry.get_text().strip())
                refill()
            dlg.destroy()

        save.connect("clicked", on_save)
        box = Gtk.Box(spacing=8)
        box.pack_start(combo, True, True, 0)
        box.pack_start(save, False, False, 0)
        row = page.form_row("Profile", box)
        page.options_card.pack_start(row, False, False, 0)
        page.options_card.reorder_child(row, 1)  # right under the section title
        row.set_no_show_all(True)

        def update(*_):
            enabled = page.ctx.features.is_enabled(self)
            row.set_visible(enabled)
            if enabled:
                row.show_all()

        page.ctx.on("features-changed", update)
        update()
