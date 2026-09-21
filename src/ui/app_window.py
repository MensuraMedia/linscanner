"""
Main Window
Sidebar + content area (layout from gtk-python-dashboard-starter).
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from config.config_layout import Layout  # noqa: E402
from ui.content_area import ContentArea  # noqa: E402
from ui.sidebar import Sidebar  # noqa: E402
from utils.util_paths import resource  # noqa: E402


class AppWindow(Gtk.Window):
    """Main application window"""

    def __init__(self, ctx):
        super().__init__(title="linscanner")
        ctx.window = self
        self.set_default_size(Layout.dimensions.WINDOW_DEFAULT_WIDTH, Layout.dimensions.WINDOW_DEFAULT_HEIGHT)
        self.set_position(Gtk.WindowPosition.CENTER)
        try:
            self.set_icon_from_file(resource("images", "logo.png"))
        except Exception:  # missing icon is cosmetic
            pass
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(box)
        self.sidebar = Sidebar(ctx.nav)  # registers its callback before pages navigate
        box.pack_start(self.sidebar, False, False, 0)
        box.pack_start(ContentArea(ctx), True, True, 0)
