"""Direct eSCL backend against a fake eSCL scanner (HTTP server in-process)"""

import io
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from backends.backend_base import ScanError, ScanRequest
from backends.backend_escl import PREFIX, EsclBackend, build_scan_settings, parse_capabilities

CAPS = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
    xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
  <pwg:Version>2.63</pwg:Version>
  <pwg:MakeAndModel>Brother MFC-TEST</pwg:MakeAndModel>
  <pwg:SerialNumber>0123456789ABCDEF</pwg:SerialNumber>
  <scan:Platen><scan:PlatenInputCaps>
    <scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>3508</scan:MaxHeight>
    <scan:SettingProfiles><scan:SettingProfile>
      <scan:ColorModes><scan:ColorMode>BlackAndWhite1</scan:ColorMode>
        <scan:ColorMode>Grayscale8</scan:ColorMode><scan:ColorMode>RGB24</scan:ColorMode></scan:ColorModes>
      <scan:DocumentFormats><pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>
        <pwg:DocumentFormat>application/pdf</pwg:DocumentFormat></scan:DocumentFormats>
      <scan:SupportedResolutions><scan:DiscreteResolutions>
        <scan:DiscreteResolution><scan:XResolution>150</scan:XResolution><scan:YResolution>150</scan:YResolution></scan:DiscreteResolution>
        <scan:DiscreteResolution><scan:XResolution>300</scan:XResolution><scan:YResolution>300</scan:YResolution></scan:DiscreteResolution>
        <scan:DiscreteResolution><scan:XResolution>600</scan:XResolution><scan:YResolution>600</scan:YResolution></scan:DiscreteResolution>
      </scan:DiscreteResolutions></scan:SupportedResolutions>
    </scan:SettingProfile></scan:SettingProfiles>
  </scan:PlatenInputCaps></scan:Platen>
  <scan:Adf>
    <scan:AdfSimplexInputCaps><scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>4200</scan:MaxHeight></scan:AdfSimplexInputCaps>
    <scan:AdfDuplexInputCaps><scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>4200</scan:MaxHeight></scan:AdfDuplexInputCaps>
    <scan:FeederCapacity>50</scan:FeederCapacity>
  </scan:Adf>
  <scan:BrightnessSupport><scan:Min>0</scan:Min><scan:Max>100</scan:Max></scan:BrightnessSupport>
</scan:ScannerCapabilities>"""


class FakeScanner:
    """State shared with the request handler"""

    pages_in_feeder = 3
    adf_state = "ScannerAdfLoaded"
    busy_on_post = False
    posted = []


def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(buf, "JPEG")
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body=b"", ctype="text/xml", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/eSCL/ScannerCapabilities":
            self._send(200, CAPS.encode())
        elif self.path == "/eSCL/ScannerStatus":
            xml = (
                '<scan:ScannerStatus xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03" '
                'xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"><pwg:State>Idle</pwg:State>'
                f"<scan:AdfState>{FakeScanner.adf_state}</scan:AdfState></scan:ScannerStatus>"
            )
            self._send(200, xml.encode())
        elif self.path.endswith("/NextDocument"):
            if FakeScanner.pages_in_feeder > 0:
                FakeScanner.pages_in_feeder -= 1
                self._send(200, jpeg_bytes(), "image/jpeg")
            else:
                self._send(404)
        else:
            self._send(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        FakeScanner.posted.append(self.rfile.read(length).decode())
        if FakeScanner.busy_on_post:
            self._send(503)
        else:
            self._send(201, headers={"Location": "/eSCL/ScanJobs/1"})

    def do_DELETE(self):
        self._send(200)


@pytest.fixture
def scanner():
    FakeScanner.pages_in_feeder, FakeScanner.adf_state, FakeScanner.busy_on_post = (
        3,
        "ScannerAdfLoaded",
        False,
    )
    FakeScanner.posted = []
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/eSCL"
    yield EsclBackend(extra_urls=[base], probe_ipp_usb=False, browse_mdns=False), base
    server.shutdown()


def test_capabilities_parsed():
    caps, info = parse_capabilities(CAPS)
    assert caps.sources == ["Flatbed", "ADF", "ADF Duplex"]
    assert caps.modes == ["Lineart", "Gray", "Color"]
    assert caps.resolutions == [150, 300, 600]
    assert (caps.max_width_mm, caps.max_height_mm) == (215.9, 355.6)  # 2550 x 4200 /300 in
    assert info["feeder_capacity"] == "50" and "Brightness" in info["adjustments"]
    assert "0123456789ABCDEF" not in info["serial"]  # redacted


def test_discovery_and_feeder_scan(scanner, tmp_path):
    backend, base = scanner
    devices = backend.list_devices()
    assert [d.id for d in devices] == [PREFIX + base] and devices[0].model == "MFC-TEST"
    req = ScanRequest(PREFIX + base, str(tmp_path), "ADF", "Gray", 300, 215.9, 279.4, multi_page=True)
    pages = backend.scan(req)
    assert len(pages) == 3 and Image.open(pages[0]).format == "JPEG"
    xml = FakeScanner.posted[-1]
    assert (
        "<pwg:InputSource>Feeder</pwg:InputSource>" in xml
        and "Grayscale8" in xml
        and "<pwg:Width>2550" in xml
    )


def test_one_sheet_limit(scanner, tmp_path):
    backend, base = scanner
    req = ScanRequest(PREFIX + base, str(tmp_path), "ADF", "Color", 150, 0, 0, max_pages=1)
    assert len(backend.scan(req)) == 1


def test_empty_feeder_needs_user(scanner, tmp_path):
    backend, base = scanner
    FakeScanner.adf_state = "ScannerAdfEmpty"
    with pytest.raises(ScanError) as err:
        backend.scan(ScanRequest(PREFIX + base, str(tmp_path), "ADF", "Color", 150, multi_page=True))
    assert err.value.code == "no_docs" and err.value.needs_user


def test_busy_falls_through(scanner, tmp_path):
    backend, base = scanner
    FakeScanner.busy_on_post = True
    with pytest.raises(ScanError) as err:
        backend.scan(ScanRequest(PREFIX + base, str(tmp_path), "Flatbed", "Color", 150))
    assert err.value.code == "busy" and not err.value.needs_user


def test_duplex_setting():
    req = ScanRequest("x", "/tmp", "ADF Duplex", "Color", 300)
    assert "<scan:Duplex>true</scan:Duplex>" in build_scan_settings(req, "image/jpeg")
