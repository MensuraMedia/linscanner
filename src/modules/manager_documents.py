"""
Documents Manager
- Recent documents: every file LinScanner saves is remembered (newest first)
  in ~/.local/share/linscanner/recent.json, for the Recent page. Only the
  path, time, page count and format are stored; the list stays on this
  computer.
- Opening a document: a saved PDF (rendered with Ghostscript) or image file
  (PNG, JPEG, TIFF, multi-page TIFF) becomes pages again, so it can be
  checked, edited with Quick Edit and saved.
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime

from utils.util_logging import get_logger
from utils.util_paths import data_dir

RECENT_MAX = 30
OPEN_DPI = 300  # resolution PDFs are rendered at when opened
OPENABLE = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")

log = get_logger("documents")


# -- recent -------------------------------------------------------------------------
def recent_path():
    """The recent-documents list file"""
    return os.path.join(data_dir(), "recent.json")


def recent_entries(existing_only=True):
    """Recent documents, newest first: [{path, saved_at, pages, format}]"""
    try:
        with open(recent_path()) as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return []
    entries = [e for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)]
    entries.sort(key=_saved_ts, reverse=True)  # newest first
    return [e for e in entries if os.path.exists(e["path"])] if existing_only else entries


def add_recent(paths, pages, fmt):
    """Remember saved files (the newest go first; a re-saved file moves to the top)"""
    entries = recent_entries(existing_only=False)
    now = datetime.now().isoformat(timespec="seconds")
    new = [{"path": os.path.abspath(p), "saved_at": now, "pages": pages, "format": fmt} for p in paths]
    known = {e["path"] for e in new}
    entries = (new + [e for e in entries if e["path"] not in known])[:RECENT_MAX]
    tmp = recent_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, recent_path())


def rename_recent(old_path, new_path):
    """Follow a renamed file in the list (the entry keeps its date and page count)"""
    entries = recent_entries(existing_only=False)
    changed = False
    for entry in entries:
        if entry.get("path") == old_path:
            entry["path"] = new_path
            changed = True
    if changed:
        with open(recent_path(), "w") as f:
            json.dump(entries, f, indent=2)
    return changed


def forget_recent(path):
    """Remove one file from the recent list (the file itself is not touched)"""
    entries = [e for e in recent_entries(existing_only=False) if e["path"] != path]
    with open(recent_path(), "w") as f:
        json.dump(entries, f, indent=2)


def clear_recent(older_than_days=None):
    """Empty the recent list, or drop entries saved more than N days ago; returns how many were removed.

    Only the list changes: the files themselves are never touched."""
    entries = recent_entries(existing_only=False)
    if older_than_days is None:
        keep = []
    else:
        cutoff = datetime.now().timestamp() - older_than_days * 86400
        keep = [e for e in entries if _saved_ts(e) >= cutoff]
    with open(recent_path(), "w") as f:
        json.dump(keep, f, indent=2)
    return len(entries) - len(keep)


def _saved_ts(entry):
    """When an entry was saved (epoch seconds; 0 if unknown)"""
    try:
        return datetime.fromisoformat(entry.get("saved_at", "")).timestamp()
    except ValueError:
        return 0


# -- opening ------------------------------------------------------------------------
def safe_name(name, limit=60):
    """A page or file name a user typed, made safe for a file system (empty if nothing is left)"""
    name = (name or "").strip().strip(".")
    for bad in ("/", "\\", "\0", "\n", "\r", "\t"):
        name = name.replace(bad, " ")
    name = " ".join(name.split())  # collapse runs of spaces
    return name[:limit].strip()


def crop_name(pages, source_name):
    """The next free 'crop n' for that source page ('crop 1', 'crop 2', ...)"""
    taken = set()
    for p in pages:
        name = p.get("name") or ""
        if p.get("crop_of") == source_name and name.lower().startswith("crop "):
            tail = name[5:].strip()
            if tail.isdigit():
                taken.add(int(tail))
    n = 1
    while n in taken:
        n += 1
    return f"crop {n}"


def open_document(path, out_dir):
    """Pages for a saved document: [{"path", "rotation", "dpi", "mode"}].

    PDFs are rendered at OPEN_DPI with Ghostscript; image files are copied
    frame by frame. Raises ValueError with a plain message on failure."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in OPENABLE:
        raise ValueError("LinScanner can open PDF, PNG, JPEG and TIFF files.")
    if not os.path.exists(path):
        raise ValueError("The file isn't there any more. It may have been moved or deleted.")
    stamp = int(time.time() * 1000)
    target = os.path.join(out_dir, f"open-{stamp}")
    os.makedirs(target, exist_ok=True)
    start = time.monotonic()
    pages = _open_pdf(path, target) if ext == ".pdf" else _open_image(path, target)
    log.info("opened %s: %d page(s) in %.1f s", path, len(pages), time.monotonic() - start)
    if not pages:
        raise ValueError("No pages could be read from this file.")
    return pages


def _open_pdf(path, target):
    """Render every PDF page to PNG with Ghostscript"""
    if not shutil.which("gs"):
        raise ValueError("Opening PDFs needs Ghostscript (package ghostscript).")
    out = os.path.join(target, "page-%03d.png")
    cmd = ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=png16m", f"-r{OPEN_DPI}"]
    cmd += ["-dTextAlphaBits=4", "-dGraphicsAlphaBits=4", f"-sOutputFile={out}", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        raise ValueError(f"The PDF could not be opened: {e}")
    if r.returncode != 0:
        log.warning("gs failed (%s): %s", r.returncode, r.stderr.strip()[-500:])
        raise ValueError("The PDF could not be opened. It may be damaged or password-protected.")
    files = sorted(f for f in os.listdir(target) if f.endswith(".png"))
    return [
        {"path": os.path.join(target, f), "rotation": 0, "dpi": OPEN_DPI, "mode": "Opened"} for f in files
    ]


def _open_image(path, target):
    """Copy each frame of an image file to PNG"""
    from PIL import Image, ImageSequence

    pages = []
    try:
        with Image.open(path) as img:
            dpi = int(round(img.info.get("dpi", (OPEN_DPI, OPEN_DPI))[0])) or OPEN_DPI
            for n, frame in enumerate(ImageSequence.Iterator(img), start=1):
                out = os.path.join(target, f"page-{n:03d}.png")
                frame.convert("RGB" if frame.mode not in ("L", "1") else frame.mode).save(out, dpi=(dpi, dpi))
                pages.append({"path": out, "rotation": 0, "dpi": dpi, "mode": "Opened"})
    except OSError as e:
        raise ValueError(f"The image could not be opened: {e}")
    return pages
