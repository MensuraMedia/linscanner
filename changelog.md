# Project Change Log

> Local record of all changes. Does NOT depend on git.

| Date-Time | Change Description |
|---|---|
| 2026-09-21T15:20:00 | Plan approved: universal SANE scanner app on gtk-python-dashboard-starter |
| 2026-09-21T15:25:00 | Scaffold from framework; Black Yellow Gray theme sampled from UIS reference |
| 2026-09-21T15:30:00 | Scanner layer: backend interface, SANE backend (scanimage), output parser |
| 2026-09-21T15:38:00 | Scan manager: color/quality/paper mapping, duplicate-driver filter, threads |
| 2026-09-21T15:42:00 | Pages: Scan, Preview (rotate/delete/Save As), Devices, Settings, About |
| 2026-09-21T15:47:00 | Export PDF/TIFF/PNG/JPEG via Pillow; settings JSON with session overrides |
| 2026-09-21T15:50:00 | Tests: 27 (parser fixtures, mapping, export, settings, SANE, UI flow) |
| 2026-09-21T15:53:00 | Lint toolchain black + pyflakes (ruff not packaged for Ubuntu 24.04) |
| 2026-09-21T15:55:00 | install.sh (offline pool first) + desktop entry; deps added to offline bundle |
| 2026-09-21T15:57:00 | Docs: README, CLAUDE.md, architecture, decisions, manifest; v0.1.0 |
| 2026-09-21T16:12:00 | Default theme changed to Nord (full official palette: cards, pills, status colours) |
| 2026-09-21T16:20:00 | Initial real-hardware test on Epson ES-400 II passed (user-confirmed) |
| 2026-09-21T16:15:00 | Docstrings for every class, method and function (documentation only) |
| 2026-09-21T16:16:00 | docs/FEATURES.md and generated docs/api-reference.md (tools/gen_api_docs.py) |
| 2026-09-21T16:18:00 | Research saved: docs/research connection-methods.md, device-capabilities.md |
| 2026-09-21T16:30:00 | Default theme = framework Default Blue (full framework palette); logo line blue |
| 2026-09-21T16:31:00 | Removed Black Yellow Gray theme; themes = framework's 7; removed ids fall back |
| 2026-09-21T16:40:00 | Comprehensive README (usage, compatibility, troubleshooting); docs updated |
| 2026-09-21T16:45:00 | Plan approved (7 items + sheet-fed modes); recommended defaults accepted |
| 2026-09-21T16:55:00 | Flat, square framework styling (sidebar rows, active fill, flat buttons, sections) |
| 2026-09-21T17:05:00 | Sheet modes: All sheets / One sheet at a time (duplex sheet = 2 pages) |
| 2026-09-21T17:20:00 | Error codes from scanimage exit status; user-action vs fall-through classes |
| 2026-09-21T17:30:00 | USB probe (sysfs + udev db), direct eSCL backend (IPP-USB/network), fake-eSCL tests |
| 2026-09-21T17:45:00 | Connection engine: grouped devices, ranked methods, fallback scan, driverless hints |
| 2026-09-21T17:55:00 | Scan Device Information page + Check for devices again; firmware; live status |
| 2026-09-21T18:00:00 | Fix: serialise SANE device access (Device busy between pages); option flags/groups |
| 2026-09-21T18:20:00 | Feature registry: feature_*.py modules, isolated hooks, Settings on/off + options |
| 2026-09-21T18:35:00 | Modules: autocrop, deskew, blank removal, autorotate, enhance, OCR, PDF options |
| 2026-09-21T18:45:00 | Modules: batch split, autosave, profiles, import images; Move page left/right |
| 2026-09-21T18:55:00 | Quick Edit: 20 fonts, PNG signature library, move/resize/apply to all, flatten |
| 2026-09-21T19:00:00 | Fix: blank detection kept colour pages (per-channel paper colour); autocrop safe |
| 2026-09-21T19:10:00 | Offline deps (tesseract, gs, numpy, fonts); docs/TECHNICAL.md; version 0.2.0 |
| 2026-09-21T17:05:00 | Logging: daily redacted logs, scan/page/feature/export/engine records, --debug |
| 2026-09-21T17:06:00 | Settings > Diagnostics: open log folder, save diagnostics zip; 7 logging tests |
| 2026-09-21T19:30:00 | README: full Safety, security and privacy section (no data leaves the machine; network activity disclosed; strace-verified) |
| 2026-09-21T19:30:00 | README: supported connection is USB cable only; Wi-Fi / network scanning not supported at this time |
| 2026-09-21T19:30:00 | LICENSE: linscanner Community License (Noncommercial) 1.0; README section 12 |
| 2026-09-21T20:10:00 | USB only: network discovery disabled (private SANE config: no net/escl/dell1600n_net, no Epson/Kodak/Magicolor net lines, pixma networking=no, airscan discovery off with IPP-USB on 127.0.0.1; eSCL client loopback only); strace-verified |
| 2026-09-21T20:10:00 | Settings: 'Network scanning (Wi-Fi / Ethernet)' shown greyed out, marked Not Supported; tests/test_usb_only.py (5 tests, 74 total) |
| 2026-09-21T20:10:00 | Docs: README privacy section updated (linscanner doesn't use your network), FEATURES, TECHNICAL §3.0 |
| 2026-09-21T21:00:00 | Docs: handoff (0.3.0 request list), follow-ups #31/#32, reference, architecture, CLAUDE.md, memory; backup |
| 2026-09-21T20:05:00 | Preview: fast page switching (display copies, cached thumbnails), zoom + pan, scrollable 1/2-row thumbnails |
| 2026-09-21T20:05:00 | Save button above Save As (overwrites the document's file; new documents go to the Save folder as PDF) |
| 2026-09-21T20:05:00 | Recent page: saved documents with folder / document icons; open a PDF or image back into Quick Edit |
| 2026-09-21T20:05:00 | Quick Edit: Add Text tool (click and type), soft alignment guides, 4 persistent signature slots |
| 2026-09-21T20:05:00 | Signatures from 9 bundled SIL OFL fonts (font browser); Add fonts... imports personal fonts locally |
| 2026-09-21T20:05:00 | Scan page: spinner, 'Scanner Found', remembered scanner reached directly at start, plain problem messages |
| 2026-09-21T20:05:00 | About: privacy, licence, your files, shortcuts, system, credits, signature-font attributions |
| 2026-09-21T20:05:00 | Fix: background callbacks are one-shot; display-copy writes are atomic; tests use a private data dir |
