"""
Settings Manager
Loads and saves user preferences as JSON in ~/.config/linscanner/settings.json
"""

import json
import os

from config.config_scan import DEFAULT_BW_STYLE, DEFAULT_PAPER, DEFAULT_QUALITY
from config.config_themes import DEFAULT_THEME_ID

DEFAULTS = {
    "theme": DEFAULT_THEME_ID,
    "color_mode": "color",
    "quality": DEFAULT_QUALITY,
    "paper": DEFAULT_PAPER,
    "bw_style": DEFAULT_BW_STYLE,
    "save_folder": os.path.join(os.path.expanduser("~"), "Documents"),
    "last_device": "",
    "show_all_backends": False,  # show duplicate backends and SANE's test scanner
}


def default_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "linscanner", "settings.json")


class SettingsManager:
    """Dictionary-style access to persisted settings with defaults"""

    def __init__(self, path=None):
        self.path = path or default_path()
        self.values = dict(DEFAULTS)
        self.overrides = {}  # session-only values (e.g. --test-scanner); never saved
        self.load()

    def load(self):
        try:
            with open(self.path) as f:
                stored = json.load(f)
        except (OSError, ValueError):
            return  # first run or unreadable file: keep defaults
        # only accept known keys with the right type (file is user-editable)
        for key, default in DEFAULTS.items():
            if key in stored and isinstance(stored[key], type(default)):
                self.values[key] = stored[key]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.values, f, indent=2)
        os.replace(tmp, self.path)  # atomic: never leaves a half-written file

    def get(self, key):
        if key in self.overrides:
            return self.overrides[key]
        return self.values.get(key, DEFAULTS.get(key))

    def override(self, key, value):
        """Use value for this session only; it is not written to disk"""
        self.overrides[key] = value

    def set(self, key, value):
        self.values[key] = value
        self.save()
