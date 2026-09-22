"""
Device Information
Builds the "Scan Devices Found" content for a physical scanner:
identity, connection path, connection methods (fallback order), permissions,
capabilities, live status and firmware. No GTK: returns plain data.
See docs/research/device-capabilities.md §8.
"""

import os
import re
import subprocess

from backends.backend_base import ScanError
from backends.backend_escl import EsclBackend
from backends.backend_sane import SaneBackend
from backends.parser_sane import device_features, redact
from backends.usb_probe import speed_label

STATUS_TEXT = {
    "ok": ("ok", "Ready: the scanner is responding"),
    "busy": ("busy", "Busy: another program is using the scanner"),
    "io": ("error", "Not responding: power-cycle the scanner, then check again"),
    "timeout": ("error", "Not responding: power-cycle the scanner, then check again"),
    "access": ("error", "Permission denied: replug the scanner or log out and in"),
    "no_docs": ("warn", "Ready, but the feeder is empty"),
    "jammed": ("error", "Paper jam: clear the feeder"),
    "cover_open": ("error", "Cover open: close the scanner cover"),
    "no_device": ("error", "Not found: check the cable and power"),
    "missing": ("error", "Scanning software missing: install sane-utils"),
}


def sections(physical, caps=None):
    """[(section title, [(label, value), ...])] describing a physical scanner"""
    out = []
    ident = [("Vendor", physical.vendor or "unknown"), ("Model", physical.model or "unknown")]
    u = physical.usb
    if u:
        ident.append(("USB ID", u.usb_id))
        if u.vendor_db:
            ident.append(("Vendor (USB database)", u.vendor_db))
    out.append(("Identity", ident))

    conn = []
    if u:
        conn += [
            ("Connection", f"USB · port {u.port_path} · bus {u.bus:03d} device {u.dev:03d}"),
            ("Link speed", speed_label(u.speed_mbps)),
            (
                "USB interfaces",
                ", ".join(
                    f"{c:02x}/{s:02x}/{p:02x}" + (f" ({d})" if d else "") for c, s, p, d in u.interfaces
                ),
            ),
            ("Why it's a scanner", ", ".join(u.kinds) or "listed by a driver"),
            ("Your access", "yes" if u.accessible else "NO: permission denied"),
            ("Known to SANE (udev)", "yes" if u.libsane_matched else "no"),
        ]
    for m in physical.methods:
        if m.device.id.startswith("escl-direct:"):
            conn.append(("eSCL address", m.device.id.split(":", 1)[1]))
    if not conn:
        conn.append(("Connection", physical.kind))
    out.append(("Connection", conn))

    methods = [
        (f"{i}. {'★ ' if i == 1 else ''}{m.label}", redact(m.device.id))
        for i, m in enumerate(physical.methods, 1)
    ]
    if not methods:
        methods = [("No working method", physical.hint or "No driver answered for this device.")]
    for label, result in physical.attempts:
        methods.append((f"Last scan · {label}", "worked" if result == "ok" else result))
    out.append(("Connection methods (tried in this order)", methods))

    if caps:
        res = (
            f"{caps.resolutions[0]}–{caps.resolutions[-1]} dpi ({len(caps.resolutions)} steps)"
            if caps.resolutions
            else "?"
        )
        cap = [
            ("Sources", ", ".join(caps.sources) or "default"),
            ("Color modes", ", ".join(caps.modes) or "?"),
            ("Resolutions", res),
            (
                "Maximum scan area",
                f"{caps.max_width_mm:g} × {caps.max_height_mm:g} mm" if caps.max_width_mm else "?",
            ),
            ("Duplex", "yes" if any("duplex" in s.lower() for s in caps.sources) else "no"),
        ]
        feats = device_features(caps.options) if caps.options and "escl" not in caps.options else []
        escl = caps.options.get("escl") if caps.options else None
        if escl:
            if escl.get("feeder_capacity"):
                cap.append(("Feeder capacity", f"{escl['feeder_capacity']} sheets"))
            if escl.get("adjustments"):
                feats += [f"{a} adjustment" for a in escl["adjustments"]]
            if escl.get("blank_page_detection"):
                feats.append("Blank-page detection")
            cap.append(("File formats", ", ".join(escl.get("formats", [])) or "?"))
        cap.append(("Device features", ", ".join(feats) or "none reported"))
        out.append(("Capabilities", cap))
    return out


def check_status(physical):
    """(level, text) for the scanner's current state: ok / warn / busy / error"""
    if not physical.methods:
        return "error", physical.hint or "No working connection method"
    method = physical.methods[0]
    backend = method.backend
    try:
        if isinstance(backend, EsclBackend):
            state, adf = backend.get_status(method.device.id)
            if adf == "ScannerAdfEmpty":
                return STATUS_TEXT["no_docs"]
            if adf in ("ScannerAdfJam", "ScannerAdfMispick", "ScannerAdfMultipickDetected"):
                return STATUS_TEXT["jammed"]
            if adf in ("ScannerAdfDoorOpen", "ScannerAdfHatchOpen"):
                return STATUS_TEXT["cover_open"]
            if state in ("Processing", "Testing"):
                return STATUS_TEXT["busy"]
            loaded = " · paper loaded" if adf == "ScannerAdfLoaded" else ""
            return "ok", f"Ready ({state}){loaded}"
        caps_reader = getattr(backend, "_run", None)
        if caps_reader is None:  # generic backend: re-reading capabilities proves it responds
            backend.get_capabilities(method.device.id)
            return STATUS_TEXT["ok"]
        r = caps_reader(["-d", method.device.id, "-A"], 60)
        if r.returncode == 0:
            return STATUS_TEXT["ok"]
        return STATUS_TEXT.get(
            SaneBackend.classify(r.returncode, r.stderr), ("error", r.stderr.strip()[-200:])
        )
    except ScanError as e:
        return STATUS_TEXT.get(e.code, ("error", str(e)))


def firmware(physical):
    """Firmware / version string if a driver reports one, else a short explanation"""
    for m in physical.methods:
        if m.device.backend == "epsonds" and hasattr(m.backend, "_env"):
            try:
                with m.backend.lock:  # never open the scanner while another call has it
                    r = subprocess.run(
                        ["scanimage", "-d", m.device.id, "-A"],
                        capture_output=True,
                        text=True,
                        errors="replace",  # debug output contains raw protocol bytes
                        timeout=60,
                        env=dict(m.backend._env, SANE_DEBUG_EPSONDS="16"),
                    )
            except (OSError, subprocess.SubprocessError):
                continue
            found = re.search(r"\[epsonds\]\s+version:\s*(.+)", r.stderr)
            if found:
                return found.group(1).strip()
        if m.device.id.startswith("escl-direct:"):
            caps = m.backend.get_capabilities(m.device.id)
            version = caps.options.get("escl", {}).get("version")
            if version:
                return f"eSCL protocol {version} (device firmware not reported)"
    if physical.usb:
        return "not reported by the driver"
    return "unknown"


def usb_node_hint(physical):
    """Extra advice when the USB device node isn't accessible"""
    u = physical.usb
    if u and not u.accessible and os.path.exists(u.node):
        return f"{u.node} isn't writable for your user. The device's udev rule may be missing."
    return ""
