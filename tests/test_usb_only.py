"""USB-only mode: no network discovery by SANE drivers or the eSCL client"""

import os
import subprocess

from backends import backend_sane
from backends.backend_escl import EsclBackend, is_loopback_url
from backends.backend_sane import SaneBackend, usb_only_config
from config.config_scan import NETWORK_SCANNING


def test_network_scanning_is_off_by_default():
    assert NETWORK_SCANNING is False


def make_sane_d(folder):
    files = {
        "dll.conf": "epson2\nepsonds\nnet\nescl\ndell1600n_net\npixma\n",
        "epsonds.conf": "usb\nnet autodiscovery\n",
        "epson2.conf": "usb\n  net 192.168.1.5\n# net autodiscovery\n",
        "pixma.conf": "# networking=no\n",
        "airscan.conf": "[options]\ndiscovery = enable\n",
    }
    for name, text in files.items():
        (folder / name).write_text(text)


def active(path):
    return [
        ln.strip() for ln in open(path).read().splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_usb_only_config_disables_network_discovery(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_sane, "ipp_usb_urls", lambda: ["http://127.0.0.1:60000/eSCL"])
    make_sane_d(tmp_path)
    usb_only_config(str(tmp_path))
    assert active(tmp_path / "dll.conf") == ["epson2", "epsonds", "pixma"]
    assert active(tmp_path / "epsonds.conf") == ["usb"]
    assert active(tmp_path / "epson2.conf") == ["usb"]
    assert "networking=no" in active(tmp_path / "pixma.conf")
    airscan = active(tmp_path / "airscan.conf")
    assert "discovery = disable" in airscan and "ws-discovery = off" in airscan
    assert '"IPP-USB scanner 1" = http://127.0.0.1:60000/eSCL, eSCL' in airscan


def test_sane_backend_uses_private_usb_only_config():
    b = SaneBackend()
    try:
        folder = b._env["SANE_CONFIG_DIR"]
        assert folder != "/etc/sane.d" and os.path.isdir(folder)
        assert "discovery = disable" in active(os.path.join(folder, "airscan.conf"))
    finally:
        b.close()
    assert not os.path.exists(folder)


def test_escl_usb_only_never_browses_or_leaves_loopback(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or None)
    b = EsclBackend(
        extra_urls=["http://192.168.1.20/eSCL", "http://127.0.0.1:60001/eSCL"],
        probe_ipp_usb=False,
        network=False,
    )
    assert b._candidate_urls() == ["http://127.0.0.1:60001/eSCL"]
    assert calls == []  # avahi-browse never run


def test_is_loopback_url():
    assert is_loopback_url("http://127.0.0.1:60000/eSCL")
    assert is_loopback_url("http://localhost:60000/eSCL")
    assert not is_loopback_url("http://192.168.1.20/eSCL")
    assert not is_loopback_url("https://scanner.example.com/eSCL")
