"""
Path helpers
Locations of the app root and bundled resources, independent of the cwd.
"""

import os

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource(*parts):
    return os.path.join(APP_ROOT, "resources", *parts)


def read_version():
    try:
        with open(os.path.join(APP_ROOT, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "unknown"
