"""
Blank-page removal
Drops pages with (almost) no ink, e.g. the empty backs of duplex scans. If
batch splitting is on, blank pages are kept as document separators instead.
"""

from features import BaseFeature
from utils.util_imaging import ink_ratio


class Feature(BaseFeature):
    """Remove blank pages"""

    id = "blank_removal"
    name = "Blank-page removal"
    description = "Removes empty pages (e.g. blank backs of duplex scans). Sensitivity is adjustable."
    default_enabled = True
    order = 40

    def process_page(self, image, page):
        """None (drop) for blank pages; mark as separator when batch splitting is on"""
        threshold = float(self.option("threshold", 0.002))
        if ink_ratio(image) >= threshold:
            return image
        states = self.settings.get("features") or {}
        if states.get("batch_split"):
            page["separator"] = True  # keep: batch splitting starts a new document here
            return image
        return None

    def settings_widget(self, ctx):
        """Sensitivity slider"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        adj = Gtk.Adjustment(
            value=float(self.option("threshold", 0.002)) * 1000, lower=0.5, upper=10, step_increment=0.5
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj, digits=1)
        scale.set_size_request(220, -1)
        scale.connect("value-changed", lambda s: self.set_option("threshold", s.get_value() / 1000))
        box = Gtk.Box(spacing=8)
        box.pack_start(Gtk.Label(label="Sensitivity (ink ‰ below which a page is blank)"), False, False, 0)
        box.pack_start(scale, False, False, 0)
        return box
