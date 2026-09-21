"""
Scan Configuration
Colour modes, quality presets, paper sizes and export formats. Everything here
is scanner-independent; backends map these onto what a device supports.
"""

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

# Paper sizes in millimetres (width, height). "auto" = full scan area.
PAPER_SIZES = {
    "letter": {"label": "Letter (8.5 × 11 in)", "mm": (215.9, 279.4)},
    "legal": {"label": "Legal (8.5 × 14 in)", "mm": (215.9, 355.6)},
    "a4": {"label": "A4 (210 × 297 mm)", "mm": (210.0, 297.0)},
    "a5": {"label": "A5 (148 × 210 mm)", "mm": (148.0, 210.0)},
    "auto": {"label": "Full scan area", "mm": None},
}
DEFAULT_PAPER = "letter"

# Source names that mean "document feeder" (scan until the feeder is empty)
FEEDER_SOURCE_HINTS = ["adf", "feeder", "duplex", "automatic document"]

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
