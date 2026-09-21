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
