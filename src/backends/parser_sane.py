"""
SANE Output Parser
Pure text parsing of `scanimage` output (no subprocesses) so it can be
unit-tested against captured fixtures.
"""

import re

from backends.backend_base import ScannerCapabilities, ScannerDevice
from config.config_scan import STANDARD_RESOLUTIONS

LIST_FORMAT = "%d|%v|%m|%t%n"  # scanimage -f: device|vendor|model|type
_SERIAL = re.compile(r"[0-9A-F]{12,}")
# "    --mode Lineart|Gray|Color [Color]"  /  "    -x 0..215.9mm [215.9]"
# "    --adf-skew[=(yes|no)] [no]"  (boolean: no value list)
_OPTION = re.compile(r"^\s+(--?[A-Za-z][\w-]*)(\[=\([^)]*\)\])?(?:\s+(.*?))?\s+\[(.*)\]\s*$")
_RANGE = re.compile(r"^(-?[\d.]+)\.\.(-?[\d.]+)")


def redact(text):
    """Hide long hex serial numbers some backends put in device names"""
    return _SERIAL.sub("…", text)


def parse_device_list(text):
    """Parse `scanimage -f '%d|%v|%m|%t%n'` output into ScannerDevice objects"""
    devices = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 4 or ":" not in parts[0]:
            continue
        dev_id, vendor, model, kind = (p.strip() for p in parts)
        devices.append(
            ScannerDevice(
                id=dev_id,
                vendor=vendor,
                model=redact(model).rstrip(":…").strip(),
                kind=kind,
                backend=dev_id.split(":", 1)[0],
            )
        )
    return devices


def model_key(device):
    """Normalised model name used to spot one scanner offered by two backends"""
    return re.sub(r"[^a-z0-9]", "", device.model.lower())


def parse_options(text):
    """Parse `scanimage -d DEV -A` output into {option: {values, default, unit}}"""
    options = {}
    for line in text.splitlines():
        m = _OPTION.match(line)
        if not m:
            continue
        name, boolean, spec, default = m.group(1).lstrip("-"), m.group(2), m.group(3), m.group(4)
        spec = boolean.strip("[=()]") if boolean else (spec or "")  # "(yes|no)" -> "yes|no"
        spec = re.sub(r"\s*\(in steps of [^)]*\)", "", spec).strip()
        unit = ""
        unit_m = re.search(r"(dpi|mm|%|us|bit)$", spec)
        if unit_m:
            unit = unit_m.group(1)
            spec = spec[: -len(unit)]
        rng = _RANGE.match(spec)
        if rng:
            values = {"min": float(rng.group(1)), "max": float(rng.group(2))}
        else:
            values = [v.strip() for v in spec.split("|") if v.strip()]
        options[name] = {"values": values, "default": default, "unit": unit}
    return options


def _resolutions(opt):
    if not opt:
        return []
    vals = opt["values"]
    if isinstance(vals, dict):
        lo, hi = vals["min"], vals["max"]
        return [r for r in STANDARD_RESOLUTIONS if lo <= r <= hi] or [int(lo)]
    out = []
    for v in vals:
        try:
            out.append(int(float(v)))
        except ValueError:
            pass
    return sorted(set(out))


def _max(opt):
    if opt and isinstance(opt["values"], dict):
        return opt["values"]["max"]
    return 0.0


def capabilities_from_options(options):
    """Normalise parsed options into ScannerCapabilities"""
    source = options.get("source", {})
    mode = options.get("mode", {})
    sources = source.get("values", []) if isinstance(source.get("values"), list) else []
    return ScannerCapabilities(
        sources=sources,
        modes=mode.get("values", []) if isinstance(mode.get("values"), list) else [],
        resolutions=_resolutions(options.get("resolution")),
        max_width_mm=_max(options.get("x")),
        max_height_mm=_max(options.get("y")),
        default_source=source.get("default", sources[0] if sources else ""),
        options=options,
    )


def parse_progress(text):
    """Return the last 'Progress: 42.3%' percentage in a chunk of stderr, or None"""
    found = re.findall(r"Progress:\s*([\d.]+)%", text)
    return float(found[-1]) if found else None
