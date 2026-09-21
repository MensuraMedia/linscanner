"""
Logging
One log file per day in ~/.local/state/linscanner/logs/ (or $XDG_STATE_HOME),
kept for 14 days and capped in size. Every line is redacted: scanner serial
numbers become "…" and the home folder becomes "~". Logging problems never
stop the app: if the folder can't be written, logging quietly goes nowhere.

Use:  from utils.util_logging import get_logger;  log = get_logger("scan")
"""

import glob
import io
import logging
import logging.handlers
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime

KEEP_DAYS = 14
MAX_BYTES = 5 * 1024 * 1024  # per daily file; 3 rotations kept
ROOT = "linscanner"


def log_dir():
    """Folder holding the log files"""
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "linscanner", "logs")


def redact_text(text):
    """Remove serial numbers and the home folder path from a log line"""
    from backends.parser_sane import redact

    home = os.path.expanduser("~")
    if home and home != "/":
        text = text.replace(home, "~")
    return redact(text)


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts every formatted line (incl. tracebacks)"""

    def format(self, record):
        """Format, then redact"""
        return redact_text(super().format(record))


def _prune(folder):
    """Delete log files older than KEEP_DAYS"""
    cutoff = time.time() - KEEP_DAYS * 86400
    for path in glob.glob(os.path.join(folder, "linscanner-*.log*")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def setup_logging(debug=False):
    """Configure the 'linscanner' logger (idempotent); returns the log file path or None"""
    logger = logging.getLogger(ROOT)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    fmt = RedactingFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    path = None
    try:
        folder = log_dir()
        os.makedirs(folder, exist_ok=True)
        _prune(folder)
        path = os.path.join(folder, f"linscanner-{datetime.now():%Y-%m-%d}.log")
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=MAX_BYTES, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())  # can't write logs: carry on without them
        path = None
    if debug:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        logger.addHandler(console)
    return path


def get_logger(name):
    """Logger for one part of the app, e.g. get_logger('scan') -> 'linscanner.scan'"""
    return logging.getLogger(f"{ROOT}.{name}")


@contextmanager
def timed(logger, what, level=logging.DEBUG):
    """Log how long a block took: 'what took 1.23 s'"""
    start = time.monotonic()
    try:
        yield
    finally:
        logger.log(level, "%s took %.2f s", what, time.monotonic() - start)


def install_excepthook():
    """Log uncaught exceptions (main thread and worker threads) before the default handling"""
    log = get_logger("crash")
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        log.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = hook
    import threading

    def thread_hook(args):
        log.critical(
            "Uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_hook


def system_info():
    """Multi-line description of the environment (versions, desktop, tools)"""
    from utils.util_paths import read_version

    lines = [
        f"linscanner {read_version()}",
        f"Python {platform.python_version()} · {platform.platform()}",
    ]
    try:
        with open("/etc/os-release") as f:
            pretty = next(
                (ln.split("=", 1)[1].strip().strip('"') for ln in f if ln.startswith("PRETTY_NAME=")), "?"
            )
        lines.append(f"OS: {pretty}")
    except OSError:
        pass
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        lines.append(f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}")
    except Exception:
        pass
    lines.append(
        f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP', '?')} · session {os.environ.get('XDG_SESSION_TYPE', '?')}"
    )
    for tool, args in (("scanimage", ["--version"]), ("tesseract", ["--version"]), ("gs", ["--version"])):
        if shutil.which(tool):
            try:
                out = subprocess.run([tool, *args], capture_output=True, text=True, timeout=10)
                first = (out.stdout or out.stderr).strip().splitlines()
                lines.append(f"{tool}: {first[0] if first else '?'}")
            except (OSError, subprocess.SubprocessError):
                lines.append(f"{tool}: present (version unknown)")
        else:
            lines.append(f"{tool}: not installed")
    return "\n".join(lines)


def write_diagnostics(path, extra_sections=None, days=3):
    """Zip the recent logs + system info (+ extra sections) for sending; returns path"""
    buf = io.StringIO()
    buf.write(system_info() + "\n")
    for title, text in (extra_sections or {}).items():
        buf.write(f"\n== {title} ==\n{text}\n")
    cutoff = time.time() - days * 86400
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system-info.txt", redact_text(buf.getvalue()))
        for log in sorted(glob.glob(os.path.join(log_dir(), "linscanner-*.log*"))):
            if os.path.getmtime(log) >= cutoff:
                with open(log, encoding="utf-8", errors="replace") as f:
                    z.writestr(os.path.basename(log), redact_text(f.read()))
    return path
