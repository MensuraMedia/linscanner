"""
SANE Backend
Talks to scanners through SANE's `scanimage` tool, so any scanner with a SANE
driver works: USB backends (epsonds, genesys, ...), network scanners via
sane-airscan (eSCL/WSD), HP via hpaio, and SANE's virtual "test" scanner.
"""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from backends.backend_base import ScanError, ScannerBackend
from backends.parser_sane import (
    LIST_FORMAT,
    capabilities_from_options,
    parse_device_list,
    parse_options,
    parse_progress,
)
from config.config_scan import BACKEND_EXTRA_ARGS, LIST_TIMEOUT, OPTIONS_TIMEOUT, PAGE_TIMEOUT


class SaneBackend(ScannerBackend):
    """SANE via the scanimage command-line tool"""

    name = "sane"

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
        if self._config_dir:
            shutil.rmtree(self._config_dir, ignore_errors=True)

    def available(self):
        return shutil.which("scanimage") is not None

    def _run(self, args, timeout):
        try:
            r = subprocess.run(
                ["scanimage", *args], capture_output=True, text=True, timeout=timeout, env=self._env
            )
        except FileNotFoundError:
            raise ScanError("SANE is not installed (scanimage not found). Install sane-utils.")
        except subprocess.TimeoutExpired:
            raise ScanError(f"The scanner did not answer within {timeout} s. Power-cycle it and retry.")
        return r

    def list_devices(self):
        r = self._run(["-f", LIST_FORMAT], LIST_TIMEOUT)
        return parse_device_list(r.stdout)

    def get_capabilities(self, device_id):
        r = self._run(["-d", device_id, "-A"], OPTIONS_TIMEOUT)
        options = parse_options(r.stdout)
        if not options:
            detail = (r.stderr.strip().splitlines() or ["no options reported"])[-1]
            raise ScanError(f"Could not read scanner options: {detail}")
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
        if not request.multi_page:
            cmd += ["--batch-count=1"]  # flatbed: one page, never loop
        return cmd

    def scan(self, request, on_page=None, on_progress=None, cancel_event=None):
        os.makedirs(request.out_dir, exist_ok=True)
        cmd = self.build_command(request)
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._env, bufsize=0
            )
        except FileNotFoundError:
            raise ScanError("SANE is not installed (scanimage not found). Install sane-utils.")

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
                proc.kill()
                raise ScanError("The scanner stopped responding. Power-cycle it and retry.")
            time.sleep(0.2)
        err_thread.join(timeout=5)

        if cancelled:
            return pages
        if not pages:
            raise ScanError(self._explain("".join(stderr_tail)))
        return pages

    @staticmethod
    def _explain(stderr):
        """Turn scanimage's error output into a user-facing message"""
        text = stderr.lower()
        if "out of documents" in text or "no docs" in text:
            return "The document feeder is empty. Load pages face down and scan again."
        if "jammed" in text:
            return "Paper jam. Open the scanner, clear the paper and retry."
        if "device busy" in text:
            return "The scanner is busy (another app may be using it). Close other scanning apps."
        if "i/o" in text or "timed out" in text:
            return "The scanner is not responding. Power-cycle it and retry."
        lines = [ln for ln in re.split(r"[\r\n]+", stderr) if ln.strip() and "Progress:" not in ln]
        return lines[-1].strip() if lines else "The scan produced no pages."
