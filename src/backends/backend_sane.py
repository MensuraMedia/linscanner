"""
SANE Backend
Talks to scanners through SANE's `scanimage` tool, so any scanner with a SANE
driver works: USB backends (epsonds, genesys, ...), network scanners via
sane-airscan (eSCL/WSD), HP via hpaio, and SANE's virtual "test" scanner.
"""

import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from backends.backend_base import SANE_EXIT_CODES, ScanError, ScannerBackend
from backends.parser_sane import (
    LIST_FORMAT,
    capabilities_from_options,
    parse_device_list,
    parse_options,
    parse_progress,
)
from config.config_scan import BACKEND_EXTRA_ARGS, LIST_TIMEOUT, OPTIONS_TIMEOUT, PAGE_TIMEOUT
from utils.util_logging import get_logger

log = get_logger("sane")

# A scanner is a single-user device: two scanimage processes opening it at once
# makes one fail with "Device busy". Every SANE call in linscanner (listing,
# options, status, firmware, scans) takes this lock, so linscanner never competes
# with itself. Re-entrant so a scan can call helpers that also lock.
DEVICE_LOCK = threading.RLock()


class SaneBackend(ScannerBackend):
    """SANE via the scanimage command-line tool"""

    name = "sane"
    lock = DEVICE_LOCK

    def __init__(self, only_backends=None):
        """only_backends: restrict SANE to these drivers (e.g. ["test"]) via a
        private SANE_CONFIG_DIR; used by tests and by the Devices page."""
        self._env = dict(os.environ, LC_ALL="C")
        self._config_dir = None
        if only_backends:
            self._config_dir = tempfile.mkdtemp(prefix="linscanner-sane-")
            if os.path.isdir("/etc/sane.d"):
                shutil.copytree("/etc/sane.d", self._config_dir, dirs_exist_ok=True)
            shutil.rmtree(os.path.join(self._config_dir, "dll.d"), ignore_errors=True)
            with open(os.path.join(self._config_dir, "dll.conf"), "w") as f:
                f.write("\n".join(only_backends) + "\n")
            self._env["SANE_CONFIG_DIR"] = self._config_dir

    def close(self):
        """Delete the private SANE config dir created for only_backends"""
        if self._config_dir:
            shutil.rmtree(self._config_dir, ignore_errors=True)

    def available(self):
        """True if SANE's scanimage tool is installed"""
        return shutil.which("scanimage") is not None

    def _run(self, args, timeout):
        """Run scanimage with args; raises ScanError on missing tool or timeout"""
        start = time.monotonic()
        try:
            with DEVICE_LOCK:
                r = subprocess.run(
                    ["scanimage", *args],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=timeout,
                    env=self._env,
                )
        except FileNotFoundError:
            log.error("scanimage not found (sane-utils missing)")
            raise ScanError("SANE is not installed (scanimage not found). Install sane-utils.", "missing")
        except subprocess.TimeoutExpired:
            log.warning("scanimage %s timed out after %s s", " ".join(args), timeout)
            raise ScanError(
                f"The scanner did not answer within {timeout} s. Power-cycle it and retry.", "timeout"
            )
        took = time.monotonic() - start
        log.debug("scanimage %s -> exit %s in %.2f s", " ".join(args), r.returncode, took)
        if r.returncode != 0:
            log.warning(
                "scanimage %s failed (exit %s): %s", " ".join(args), r.returncode, r.stderr.strip()[-1500:]
            )
        return r

    def list_devices(self):
        """List scanners SANE can see (scanimage -f), as ScannerDevice objects"""
        r = self._run(["-f", LIST_FORMAT], LIST_TIMEOUT)
        devices = parse_device_list(r.stdout)
        log.info("SANE listed %d device(s): %s", len(devices), ", ".join(d.id for d in devices) or "none")
        return devices

    def get_capabilities(self, device_id):
        """Read a device's options (scanimage -A) as ScannerCapabilities"""
        r = self._run(["-d", device_id, "-A"], OPTIONS_TIMEOUT)
        options = parse_options(r.stdout)
        log.debug("options for %s: %s", device_id, ", ".join(sorted(options)) or "none")
        if not options:
            detail = (r.stderr.strip().splitlines() or ["no options reported"])[-1]
            code = SANE_EXIT_CODES.get(r.returncode, "no_device" if "open of device" in r.stderr else "error")
            raise ScanError(f"Could not read scanner options: {detail}", code)
        return capabilities_from_options(options)

    def build_command(self, request):
        """scanimage arguments for a request (separate for testing)"""
        cmd = ["scanimage", "-d", request.device_id, "--format=png", "--progress"]
        if request.source:
            cmd += ["--source", request.source]
        if request.mode:
            cmd += ["--mode", request.mode]
        if request.resolution:
            cmd += ["--resolution", str(request.resolution)]
        if request.width_mm and request.height_mm:
            cmd += ["-x", f"{request.width_mm:g}", "-y", f"{request.height_mm:g}"]
        cmd += BACKEND_EXTRA_ARGS.get(request.device_id.split(":", 1)[0], [])
        pattern = os.path.join(request.out_dir, "page-%03d.png")
        cmd += [f"--batch={pattern}", "--batch-print"]
        if request.max_pages:
            cmd += [f"--batch-count={request.max_pages}"]  # one sheet (1 side, or 2 for duplex)
        elif not request.multi_page:
            cmd += ["--batch-count=1"]  # flatbed: one page, never loop
        return cmd

    def scan(self, request, on_page=None, on_progress=None, cancel_event=None):
        """Scan per request; report pages/progress live; honour cancel; return page paths"""
        with DEVICE_LOCK:
            return self._scan_locked(request, on_page, on_progress, cancel_event)

    def _scan_locked(self, request, on_page, on_progress, cancel_event):
        """scan() body; runs with DEVICE_LOCK held"""
        os.makedirs(request.out_dir, exist_ok=True)
        cmd = self.build_command(request)
        started = time.monotonic()
        log.info("scan start: %s", " ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._env, bufsize=0
            )
        except FileNotFoundError:
            raise ScanError("SANE is not installed (scanimage not found). Install sane-utils.", "missing")

        pages, stderr_tail = [], []
        last_activity = [time.monotonic()]

        def read_stderr():
            buf = b""
            while True:
                chunk = proc.stderr.read(256)
                if not chunk:
                    break
                buf = (buf + chunk)[-4096:]
                text = chunk.decode(errors="replace")
                pct = parse_progress(text)
                if pct is not None:
                    last_activity[0] = time.monotonic()
                    if on_progress:
                        on_progress(pct)
            stderr_tail.append(buf.decode(errors="replace"))

        err_thread = threading.Thread(target=read_stderr, daemon=True)
        err_thread.start()

        # --batch-print writes each finished page's filename on stdout
        for raw in iter(proc.stdout.readline, b""):
            path = raw.decode(errors="replace").strip()
            if path and os.path.exists(path):
                log.info(
                    "page %d received after %.1f s: %s",
                    len(pages) + 1,
                    time.monotonic() - started,
                    os.path.basename(path),
                )
                pages.append(path)
                last_activity[0] = time.monotonic()
                if on_page:
                    on_page(path)
            if cancel_event and cancel_event.is_set():
                break

        cancelled = False
        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                cancelled = True
                proc.send_signal(signal.SIGINT)  # scanimage stops cleanly on SIGINT
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            if time.monotonic() - last_activity[0] > PAGE_TIMEOUT:
                log.warning("no page or progress for %s s: killing scanimage", PAGE_TIMEOUT)
                proc.kill()
                raise ScanError("The scanner stopped responding. Power-cycle it and retry.", "timeout")
            time.sleep(0.2)
        err_thread.join(timeout=5)
        stderr = "".join(stderr_tail)
        clean = "\n".join(ln for ln in re.split(r"[\r\n]+", stderr) if ln.strip() and "Progress:" not in ln)
        log.info(
            "scan end: %d page(s), exit %s, %.1f s%s",
            len(pages),
            proc.returncode,
            time.monotonic() - started,
            " (cancelled)" if cancelled else "",
        )
        if clean:
            log.log(logging.DEBUG if pages else logging.WARNING, "scanimage messages:\n%s", clean[-3000:])

        if cancelled:
            return pages
        if not pages:
            raise ScanError(self._explain(stderr), self.classify(proc.returncode, stderr))
        return pages

    @staticmethod
    def classify(returncode, stderr):
        """Error code from scanimage's exit status (= SANE status), falling back to its text"""
        if returncode in SANE_EXIT_CODES:
            return SANE_EXIT_CODES[returncode]
        text = stderr.lower()
        for needle, code in (
            ("out of documents", "no_docs"),
            ("jammed", "jammed"),
            ("cover is open", "cover_open"),
            ("device busy", "busy"),
            ("access", "access"),
            ("i/o", "io"),
            ("timed out", "timeout"),
            ("open of device", "no_device"),
            ("invalid argument", "unsupported"),
        ):
            if needle in text:
                return code
        return "error"

    @staticmethod
    def _explain(stderr):
        """Turn scanimage's error output into a user-facing message"""
        text = stderr.lower()
        if "out of documents" in text or "no docs" in text:
            return "The document feeder is empty. Load pages face down and scan again."
        if "cover is open" in text:
            return "The scanner cover is open. Close it and scan again."
        if "jammed" in text:
            return "Paper jam. Open the scanner, clear the paper and retry."
        if "device busy" in text:
            return "The scanner is busy (another app may be using it). Close other scanning apps."
        if "i/o" in text or "timed out" in text:
            return "The scanner is not responding. Power-cycle it and retry."
        lines = [ln for ln in re.split(r"[\r\n]+", stderr) if ln.strip() and "Progress:" not in ln]
        return lines[-1].strip() if lines else "The scan produced no pages."
