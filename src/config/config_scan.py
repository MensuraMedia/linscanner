"""
Scan Configuration
Colour modes, quality presets, paper sizes and export formats. Everything here
is scanner-independent; backends map these onto what a device supports.
"""

# Network scanning (Wi-Fi / Ethernet) is not supported at this time: only
# cable-connected (USB) scanners are. With this off, no network discovery is
# done at all: SANE drivers get a private config with their network discovery
# disabled, and linscanner's eSCL client only talks to ipp-usb on 127.0.0.1.
NETWORK_SCANNING = False

# Colour choices shown to the user -> SANE mode names to look for, in order.
# "bw" (Black & White) is grayscale by default; Settings can switch it to pure
# black-and-white (lineart), which is smaller but can lose faint text.
COLOR_MODES = {
    "color": {"label": "Color", "sane": ["color", "colour", "24bit color", "rgb"]},
    "bw": {"label": "Black & White", "sane": ["gray", "grey", "grayscale", "8bit gray"]},
}
LINEART_MODE_NAMES = ["lineart", "binary", "black & white", "black and white", "halftone"]
BW_STYLES = {"grayscale": "Grayscale (shades of gray)", "pure": "Pure black & white (lineart)"}
DEFAULT_BW_STYLE = "grayscale"

# Quality presets -> target dpi; snapped to the nearest resolution a device offers
QUALITY_PRESETS = {
    "high": {"label": "High", "dpi": 600},
    "medium": {"label": "Medium", "dpi": 300},
    "low": {"label": "Low", "dpi": 150},
}
DEFAULT_QUALITY = "medium"

# Standard resolutions used when a device reports a continuous range
STANDARD_RESOLUTIONS = [75, 100, 150, 200, 300, 400, 600, 1200]

# Paper sizes in millimetres (width, height), in groups (the Scan page shows a
# separator between groups).
#   mm: None  -> the whole scan area
#   detect    -> scan the whole area, then crop to the paper (Auto-Detect);
#                with mm, that size is used when the paper's edges can't be seen
PAPER_SIZES = {
    "auto_detect": {"group": "", "label": "Auto-Detect (fit to the paper)", "mm": None, "detect": True},
    "letter": {"group": "Documents", "label": "Letter (8.5 × 11 in)", "mm": (215.9, 279.4)},
    "legal": {"group": "Documents", "label": "Legal (8.5 × 14 in)", "mm": (215.9, 355.6)},
    "executive": {"group": "Documents", "label": "Executive (7.25 × 10.5 in)", "mm": (184.2, 266.7)},
    "half_letter": {
        "group": "Documents",
        "label": "Half Letter / Statement (5.5 × 8.5 in)",
        "mm": (139.7, 215.9),
    },
    "a4": {"group": "Documents", "label": "A4 (210 × 297 mm)", "mm": (210.0, 297.0)},
    "a5": {"group": "Documents", "label": "A5 (148 × 210 mm)", "mm": (148.0, 210.0)},
    "a6": {"group": "Documents", "label": "A6 (105 × 148 mm)", "mm": (105.0, 148.0)},
    "b5": {"group": "Documents", "label": "B5 (176 × 250 mm)", "mm": (176.0, 250.0)},
    "receipt_80": {
        "group": "Receipts",
        "label": "Receipt, 80 mm wide (till roll)",
        "mm": (80.0, 297.0),
        "detect": True,
    },
    "receipt_58": {
        "group": "Receipts",
        "label": "Receipt, 58 mm wide (card terminal)",
        "mm": (58.0, 200.0),
        "detect": True,
    },
    "business_card": {
        "group": "Cards",
        "label": "Business card (3.5 × 2 in)",
        "mm": (88.9, 50.8),
        "detect": True,
    },
    "id_card": {
        "group": "Cards",
        "label": "ID / credit card (85.6 × 54 mm)",
        "mm": (85.6, 54.0),
        "detect": True,
    },
    "index_card": {"group": "Cards", "label": "Index card (3 × 5 in)", "mm": (76.2, 127.0), "detect": True},
    "photo_4x6": {"group": "Photos", "label": "Photo 4 × 6 in", "mm": (101.6, 152.4)},
    "photo_5x7": {"group": "Photos", "label": "Photo 5 × 7 in", "mm": (127.0, 177.8)},
    "check": {"group": "Other", "label": "Check (6 × 2.75 in)", "mm": (152.4, 69.9), "detect": True},
    "auto": {"group": "Other", "label": "Full scan area", "mm": None},
}
DEFAULT_PAPER = "auto_detect"

# Source names that mean "document feeder" (scan until the feeder is empty)
FEEDER_SOURCE_HINTS = ["adf", "feeder", "duplex", "automatic document"]
DUPLEX_SOURCE_HINTS = ["duplex"]

# Sheet-fed modes for feeder sources
SHEET_MODES = {
    "all": {"label": "Multi-Page", "help": "Scans every sheet in the feeder in one go"},
    "one": {
        "label": "Single Page",
        "help": "Scans every sheet, each as its own document (viewable and saveable one by one)",
    },
}
DEFAULT_SHEET_MODE = "all"

# Backends preferred when the same scanner is offered by several SANE backends.
# epsonds scanned the ES-400 II reliably; Epson's own epsonscan2 backend is a
# fallback (its Flatpak GUI crashed during scans on the reference host).
PREFERRED_BACKENDS = ["epsonds", "airscan", "escl", "hpaio", "brother4", "epson2", "genesys"]
HIDDEN_BACKENDS_BY_DEFAULT = ["test"]  # SANE's virtual scanner; shown in developer mode

# Extra scanimage arguments per SANE driver (prefix of the device name)
BACKEND_EXTRA_ARGS = {
    "test": ["--test-picture", "Color pattern"],  # default is "Solid black": useless for previews
}

# Export formats for "Save As"
EXPORT_FORMATS = {
    "pdf": {"label": "PDF document (all pages)", "ext": ".pdf", "multi": True},
    "png": {"label": "PNG image", "ext": ".png", "multi": False},
    "jpeg": {"label": "JPEG image", "ext": ".jpg", "multi": False},
    "tiff": {"label": "TIFF image (all pages)", "ext": ".tiff", "multi": True},
}
JPEG_QUALITY = 90

# Timeouts in seconds
LIST_TIMEOUT = 60
OPTIONS_TIMEOUT = 60
PAGE_TIMEOUT = 180  # per page; a scan fails if no page arrives in this time
