"""
Image enhancement
Brightness, contrast, sharpening, despeckle and background whitening applied
to each scanned page (colour and grayscale; pure black-and-white is left alone).
"""

from PIL import ImageEnhance, ImageFilter

from features import BaseFeature

DEFAULTS = {"brightness": 1.0, "contrast": 1.1, "sharpen": True, "despeckle": False, "whiten": True}


class Feature(BaseFeature):
    """Improve legibility of scanned pages"""

    id = "enhance"
    name = "Image enhancement"
    description = "Brightness, contrast, sharpening, despeckle and a whiter background."
    default_enabled = False
    order = 45

    def process_page(self, image, page):
        """Apply the configured adjustments"""
        if image.mode not in ("L", "RGB"):
            return image
        o = {k: self.option(k, v) for k, v in DEFAULTS.items()}
        if o["despeckle"]:
            image = image.filter(ImageFilter.MedianFilter(3))
        if o["brightness"] != 1.0:
            image = ImageEnhance.Brightness(image).enhance(o["brightness"])
        if o["contrast"] != 1.0:
            image = ImageEnhance.Contrast(image).enhance(o["contrast"])
        if o["whiten"]:  # push near-white paper to pure white
            image = image.point(lambda v: 255 if v > 225 else v)
        if o["sharpen"]:
            image = image.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=3))
        return image

    def settings_widget(self, ctx):
        """Sliders and switches for the adjustments"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for key, label in (("brightness", "Brightness"), ("contrast", "Contrast")):
            adj = Gtk.Adjustment(
                value=self.option(key, DEFAULTS[key]), lower=0.5, upper=1.8, step_increment=0.05
            )
            scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj, digits=2)
            scale.set_size_request(220, -1)
            scale.connect("value-changed", lambda s, k=key: self.set_option(k, round(s.get_value(), 2)))
            row = Gtk.Box(spacing=8)
            row.pack_start(Gtk.Label(label=label), False, False, 0)
            row.pack_start(scale, False, False, 0)
            box.pack_start(row, False, False, 0)
        for key, label in (
            ("sharpen", "Sharpen"),
            ("despeckle", "Despeckle"),
            ("whiten", "Whiter background"),
        ):
            check = Gtk.CheckButton(label=label)
            check.set_active(self.option(key, DEFAULTS[key]))
            check.connect("toggled", lambda c, k=key: self.set_option(k, c.get_active()))
            box.pack_start(check, False, False, 0)
        return box
