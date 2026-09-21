"""
Sidebar Component
Fixed sidebar with logo and navigation (from gtk-python-dashboard-starter).
The active button follows navigation triggered from code as well as clicks.
"""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402

from config.config_layout import Layout  # noqa: E402
from utils.util_paths import resource  # noqa: E402

NAV_ITEMS = [("Scan", "scan"), ("Preview", "preview"), ("Devices", "devices"), ("About", "about")]
BOTTOM_ITEMS = [("Settings", "settings")]


class Sidebar(Gtk.Box):
    """Logo + navigation buttons"""

    def __init__(self, navigation_manager):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.nav_manager = navigation_manager
        self.set_size_request(Layout.dimensions.SIDEBAR_WIDTH, -1)
        self.get_style_context().add_class("sidebar")
        self.nav_buttons = {}
        self.active_button = None

        self.build_logo_area()
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for label, page_id in NAV_ITEMS:
            top.pack_start(self.create_nav_button(label, page_id), False, False, 0)
        self.pack_start(top, False, False, 0)
        self.pack_start(Gtk.Box(), True, True, 0)  # spacer pushes Settings down
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bottom.set_margin_bottom(10)
        for label, page_id in BOTTOM_ITEMS:
            bottom.pack_start(self.create_nav_button(label, page_id), False, False, 0)
        self.pack_start(bottom, False, False, 0)

        self.nav_manager.on_navigate(self.on_navigated)

    def build_logo_area(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(Layout.dimensions.LOGO_AREA_WIDTH, Layout.dimensions.LOGO_AREA_HEIGHT)
        box.get_style_context().add_class("logo-area")
        logo = resource("images", "logo.png")
        if os.path.exists(logo):
            try:
                size = Layout.dimensions.LOGO_IMAGE_SIZE
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(logo, size, size, True)
                box.pack_start(Gtk.Image.new_from_pixbuf(pix), True, True, 0)
            except GLib.Error:
                pass
        text = Gtk.Label(label="linscanner")
        text.get_style_context().add_class("logo-text")
        box.pack_start(text, False, False, 4)
        self.pack_start(box, False, False, 0)

    def create_nav_button(self, label, page_id):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class("nav-button")
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.get_child().set_xalign(0)
        button.connect("clicked", lambda *_: self.nav_manager.navigate_to(page_id))
        self.nav_buttons[page_id] = button
        return button

    def on_navigated(self, page_id):
        button = self.nav_buttons.get(page_id)
        if not button:
            return
        if self.active_button:
            self.active_button.get_style_context().remove_class("active")
        button.get_style_context().add_class("active")
        self.active_button = button
