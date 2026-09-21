"""
App Context
Shared services handed to every page (settings, scan manager, navigation,
theme) plus a tiny event hub so pages can react to each other without
importing each other.

Events: "pages-changed", "devices-changed", "settings-changed", "theme-changed"
"""


class AppContext:
    """Service container + publish/subscribe event hub"""

    def __init__(self, settings, scan_manager, nav_manager, theme_applicator):
        """Hold the shared services; window is set later by AppWindow"""
        self.settings = settings
        self.scan = scan_manager
        self.nav = nav_manager
        self.theme = theme_applicator
        self.window = None  # set once the main window exists (dialog parent)
        self.features = None  # FeatureRegistry (optional modules); None = no features
        self.log_path = None  # today's log file (Settings -> Diagnostics)
        self._listeners = {}

    def on(self, event, callback):
        """Subscribe callback to an event name"""
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event, *args):
        """Call every subscriber of event with args"""
        for callback in list(self._listeners.get(event, [])):
            callback(*args)
