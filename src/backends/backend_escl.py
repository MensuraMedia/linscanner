"""
Direct eSCL Backend
linscanner's own driverless client for eSCL (AirScan / Mopria), used when SANE
can't reach a scanner that speaks eSCL. Covers:
  - IPP-over-USB devices (USB class 07/01/04) exposed by ipp-usb on
    http://127.0.0.1:60000+ (loopback), and
  - network scanners announced over mDNS as _uscan._tcp / _uscans._tcp.
Standard library only (urllib + ElementTree). Protocol notes:
docs/research/device-capabilities.md §2.
"""

import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from backends.backend_base import ScanError, ScannerBackend, ScannerCapabilities, ScannerDevice
from backends.parser_sane import redact
from config.config_scan import STANDARD_RESOLUTIONS

PREFIX = "escl-direct:"  # device id prefix, e.g. escl-direct:http://127.0.0.1:60000/eSCL
IPP_USB_PORTS = range(60000, 60016)  # ipp-usb assigns loopback ports from 60000
HTTP_TIMEOUT = 8
NS = {
    "scan": "http://schemas.hp.com/imaging/escl/2011/05/03",
    "pwg": "http://www.pwg.org/schemas/2010/12/sm",
}
# eSCL colour modes <-> the SANE-style names linscanner's mapping understands
MODE_TO_NAME = {
    "RGB24": "Color",
    "RGB48": "Color",
    "Grayscale8": "Gray",
    "Grayscale16": "Gray",
    "BlackAndWhite1": "Lineart",
}
NAME_TO_MODE = {"Color": "RGB24", "Gray": "Grayscale8", "Lineart": "BlackAndWhite1"}
# eSCL AdfState / State -> linscanner error codes (research §2 / SANE escl mapping)
STATUS_CODES = {
    "ScannerAdfEmpty": "no_docs",
    "ScannerAdfJam": "jammed",
    "ScannerAdfDoorOpen": "cover_open",
    "ScannerAdfHatchOpen": "cover_open",
    "ScannerAdfMispick": "jammed",
    "ScannerAdfMultipickDetected": "jammed",
}


def _local(tag):
    """Tag name without its XML namespace"""
    return tag.rsplit("}", 1)[-1]


def _find(elem, name):
    """First descendant with this local name (namespace-agnostic)"""
    for e in elem.iter():
        if _local(e.tag) == name:
            return e
    return None


def _findall(elem, name):
    """All descendants with this local name"""
    return [e for e in elem.iter() if _local(e.tag) == name]


def _text(elem, name, default=""):
    """Text of the first descendant with this local name"""
    e = _find(elem, name)
    return e.text.strip() if e is not None and e.text else default


def parse_capabilities(xml_text):
    """ScannerCapabilities XML -> (ScannerCapabilities, info dict)"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ScanError(f"Scanner capabilities could not be read: {e}", "unsupported")
    sources, modes, resolutions, formats = [], [], set(), []
    max_w = max_h = 0
    platen, adf = _find(root, "Platen"), _find(root, "Adf")
    if platen is not None:
        sources.append("Flatbed")
    if adf is not None:
        if _find(adf, "AdfSimplexInputCaps") is not None:
            sources.append("ADF")
        if _find(adf, "AdfDuplexInputCaps") is not None:
            sources.append("ADF Duplex")
    for caps in _findall(root, "PlatenInputCaps") + _findall(root, "AdfSimplexInputCaps"):
        max_w = max(max_w, int(_text(caps, "MaxWidth", "0") or 0))
        max_h = max(max_h, int(_text(caps, "MaxHeight", "0") or 0))
    for cm in _findall(root, "ColorMode"):
        name = MODE_TO_NAME.get((cm.text or "").strip())
        if name and name not in modes:
            modes.append(name)
    for r in _findall(root, "XResolution"):
        if r.text and r.text.strip().isdigit():
            resolutions.add(int(r.text))
    rng = _find(root, "ResolutionRange")
    if rng is not None:
        lo, hi = int(_text(rng, "Min", "0") or 0), int(_text(rng, "Max", "0") or 0)
        resolutions.update(r for r in STANDARD_RESOLUTIONS if lo <= r <= hi)
    for f in _findall(root, "DocumentFormat") + _findall(root, "DocumentFormatExt"):
        if f.text and f.text.strip() not in formats:
            formats.append(f.text.strip())
    info = {
        "make_and_model": _text(root, "MakeAndModel"),
        "serial": redact(_text(root, "SerialNumber")),
        "version": _text(root, "Version"),
        "admin_uri": _text(root, "AdminURI"),
        "formats": formats,
        "feeder_capacity": _text(root, "FeederCapacity"),
        "blank_page_detection": _find(root, "BlankPageDetection") is not None,
        "adjustments": [
            n.replace("Support", "")
            for n in (
                "BrightnessSupport",
                "ContrastSupport",
                "SharpenSupport",
                "ThresholdSupport",
                "NoiseRemovalSupport",
            )
            if _find(root, n) is not None
        ],
    }
    caps = ScannerCapabilities(
        sources=sources,
        modes=modes,
        resolutions=sorted(resolutions),
        max_width_mm=round(max_w / 300 * 25.4, 1),  # eSCL units: 1/300 inch
        max_height_mm=round(max_h / 300 * 25.4, 1),
        default_source=sources[0] if sources else "",
        options={"escl": info},
    )
    return caps, info


def parse_status(xml_text):
    """ScannerStatus XML -> (state, adf_state)"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "Unknown", ""
    return _text(root, "State", "Unknown"), _text(root, "AdfState")


def build_scan_settings(request, fmt):
    """ScanSettings XML for a request (regions in 1/300 inch)"""

    def units(mm):
        return int(round(mm / 25.4 * 300))

    source = "Platen" if request.source in ("", "Flatbed") else "Feeder"
    region = ""
    if request.width_mm and request.height_mm:
        region = (
            "<pwg:ScanRegions><pwg:ScanRegion>"
            "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
            f"<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
            f"<pwg:Width>{units(request.width_mm)}</pwg:Width><pwg:Height>{units(request.height_mm)}</pwg:Height>"
            "</pwg:ScanRegion></pwg:ScanRegions>"
        )
    duplex = "<scan:Duplex>true</scan:Duplex>" if "duplex" in request.source.lower() else ""
    res = request.resolution or 300
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<scan:ScanSettings xmlns:scan="{NS["scan"]}" xmlns:pwg="{NS["pwg"]}">'
        "<pwg:Version>2.0</pwg:Version><scan:Intent>Document</scan:Intent>"
        f"{region}<pwg:InputSource>{source}</pwg:InputSource>"
        f"<scan:ColorMode>{NAME_TO_MODE.get(request.mode, 'RGB24')}</scan:ColorMode>"
        f"<scan:XResolution>{res}</scan:XResolution><scan:YResolution>{res}</scan:YResolution>"
        f"<pwg:DocumentFormat>{fmt}</pwg:DocumentFormat>{duplex}"
        "</scan:ScanSettings>"
    )


class EsclBackend(ScannerBackend):
    """eSCL over HTTP, without SANE"""

    name = "escl-direct"

    def __init__(self, extra_urls=None, probe_ipp_usb=True, browse_mdns=True):
        """extra_urls: known eSCL base URLs (e.g. http://192.168.1.20/eSCL)"""
        self.extra_urls = list(extra_urls or [])
        self.probe_ipp_usb = probe_ipp_usb
        self.browse_mdns = browse_mdns
        self._caps_cache = {}

    def available(self):
        """Always available: needs only the Python standard library"""
        return True

    # -- HTTP ----------------------------------------------------------------
    @staticmethod
    def _request(url, method="GET", data=None, timeout=HTTP_TIMEOUT):
        """(status, headers, body) for an HTTP request; ScanError on network errors"""
        req = urllib.request.Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "text/xml")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {}), e.read() if e.fp else b""
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            raise ScanError(f"Could not reach the scanner at {url}: {e}", "io")

    # -- discovery -------------------------------------------------------------
    def _candidate_urls(self):
        """eSCL base URLs from ipp-usb loopback ports, mDNS and configured URLs"""
        urls = list(self.extra_urls)
        if self.probe_ipp_usb:
            for port in IPP_USB_PORTS:
                with socket.socket() as s:
                    s.settimeout(0.2)
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        urls.append(f"http://127.0.0.1:{port}/eSCL")
        if self.browse_mdns and shutil.which("avahi-browse"):
            for stype, scheme in (("_uscan._tcp", "http"), ("_uscans._tcp", "https")):
                try:
                    out = subprocess.run(
                        ["avahi-browse", "-rtpk", stype], capture_output=True, text=True, timeout=6
                    ).stdout
                except (OSError, subprocess.SubprocessError):
                    continue
                for line in out.splitlines():
                    f = line.split(";")
                    if len(f) >= 10 and f[0] == "=" and f[2] == "IPv4":
                        rs = re.search(r'"rs=([^"]*)"', f[9])
                        path = (rs.group(1) if rs else "eSCL").strip("/")
                        urls.append(f"{scheme}://{f[7]}:{f[8]}/{path}")
        seen, unique = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def list_devices(self):
        """eSCL scanners that answer ScannerCapabilities"""
        devices = []
        for base in self._candidate_urls():
            try:
                status, _h, body = self._request(f"{base}/ScannerCapabilities", timeout=3)
            except ScanError:
                continue
            if status != 200:
                continue  # e.g. an IPP-USB printer with no scanner function
            try:
                caps, info = parse_capabilities(body.decode(errors="replace"))
            except ScanError:
                continue
            self._caps_cache[base] = caps
            where = "USB (ipp-usb)" if "127.0.0.1" in base else "network"
            model = info["make_and_model"] or "eSCL scanner"
            devices.append(
                ScannerDevice(
                    id=PREFIX + base,
                    vendor=model.split()[0] if " " in model else "",
                    model=" ".join(model.split()[1:]) if " " in model else model,
                    kind=f"eSCL scanner via {where}",
                    backend="escl-direct",
                )
            )
        return devices

    def get_capabilities(self, device_id):
        """Capabilities from GET ScannerCapabilities (cached per URL)"""
        base = device_id[len(PREFIX) :]
        if base not in self._caps_cache:
            status, _h, body = self._request(f"{base}/ScannerCapabilities")
            if status != 200:
                raise ScanError(f"Scanner capabilities request failed (HTTP {status})", "unsupported")
            self._caps_cache[base], _info = parse_capabilities(body.decode(errors="replace"))
        return self._caps_cache[base]

    def get_status(self, device_id):
        """(state, adf_state) from GET ScannerStatus"""
        base = device_id[len(PREFIX) :]
        status, _h, body = self._request(f"{base}/ScannerStatus")
        if status != 200:
            raise ScanError(f"Status request failed (HTTP {status})", "io")
        return parse_status(body.decode(errors="replace"))

    # -- scanning --------------------------------------------------------------
    def scan(self, request, on_page=None, on_progress=None, cancel_event=None):
        """POST a scan job, then fetch NextDocument until the job is done"""
        base = request.device_id[len(PREFIX) :]
        caps = self.get_capabilities(request.device_id)
        formats = caps.options.get("escl", {}).get("formats", [])
        fmt = next((f for f in ("image/png", "image/jpeg") if f in formats), "image/jpeg")
        feeder = request.source not in ("", "Flatbed")
        try:
            state, adf = self.get_status(request.device_id)
        except ScanError:
            state, adf = "Unknown", ""
        if feeder and adf in STATUS_CODES:
            raise ScanError(self.explain(adf), STATUS_CODES[adf])
        if state in ("Processing", "Testing"):
            raise ScanError("The scanner is busy with another job.", "busy")

        status, headers, _b = self._request(
            f"{base}/ScanJobs", "POST", build_scan_settings(request, fmt).encode()
        )
        if status == 503:
            raise ScanError("The scanner is busy (HTTP 503).", "busy")
        if status not in (200, 201) or "Location" not in headers:
            raise ScanError(f"The scanner refused the scan job (HTTP {status}).", "unsupported")
        job = headers["Location"]
        if job.startswith("/"):
            origin = re.match(r"^(https?://[^/]+)", base).group(1)
            job = origin + job

        os.makedirs(request.out_dir, exist_ok=True)
        ext = ".png" if fmt == "image/png" else ".jpg"
        pages, busy_retries = [], 0
        limit = request.max_pages or (0 if request.multi_page else 1)
        while not (limit and len(pages) >= limit):
            if cancel_event and cancel_event.is_set():
                self._request(job, "DELETE")
                break
            if on_progress:
                on_progress(0)
            code, _h, body = self._request(f"{job}/NextDocument", timeout=120)
            if code == 200 and body:
                path = os.path.join(request.out_dir, f"page-{len(pages) + 1:03d}{ext}")
                with open(path, "wb") as f:
                    f.write(body)
                pages.append(path)
                if on_progress:
                    on_progress(100)
                if on_page:
                    on_page(path)
            elif code == 404:
                break  # no more documents in this job
            elif code == 503 and busy_retries < 10:
                busy_retries += 1
                time.sleep(1)
            else:
                break
        if not pages and not (cancel_event and cancel_event.is_set()):
            try:
                _state, adf = self.get_status(request.device_id)
            except ScanError:
                adf = ""
            raise ScanError(self.explain(adf), STATUS_CODES.get(adf, "io"))
        return pages

    @staticmethod
    def explain(adf_state):
        """User-facing message for an eSCL AdfState"""
        return {
            "ScannerAdfEmpty": "The document feeder is empty. Load pages and scan again.",
            "ScannerAdfJam": "Paper jam in the feeder. Clear it and retry.",
            "ScannerAdfDoorOpen": "The feeder door is open. Close it and scan again.",
            "ScannerAdfHatchOpen": "The scanner hatch is open. Close it and scan again.",
            "ScannerAdfMispick": "The feeder didn't pick up the page. Reload and retry.",
            "ScannerAdfMultipickDetected": "Double feed detected. Reload the pages and retry.",
        }.get(adf_state, "The scanner returned no pages.")
