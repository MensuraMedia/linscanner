---
date: 2026-09-21
type: feature
files_changed: [linscanner/src/backends/backend_sane.py, linscanner/src/backends/backend_escl.py, linscanner/src/config/config_scan.py, linscanner/src/main.py, linscanner/src/pages/page_settings.py, linscanner/tests/test_usb_only.py, linscanner/README.md, linscanner/LICENSE, linscanner/docs/**]
---

## Change: privacy statement, USB only, license
- README §7 "Safety, security and privacy": no data leaves the machine; storage table; network section.
- USB only: network discovery disabled (private SANE config, loopback-only eSCL); Settings shows "Network scanning (Wi-Fi / Ethernet)" greyed out, "Not Supported".
- LICENSE: linscanner Community License (Noncommercial) 1.0; README §12.

## Why
User requests (2026-09-21): privacy language; Wi-Fi not supported, cable only; a noncommercial license; then disable network discovery but keep the option visible as "Not Supported".

## Testing
- strace before and after:
  - before: WS-Discovery multicast and broadcasts to UDP 8610/8612/3289/161/1124;
  - after: 127.0.0.1 only;
  - the ES-400 II is still found via epsonds and epsonscan2.
- 74 tests pass; black and pyflakes are clean; the app starts, and the Settings row was checked by screenshot.
