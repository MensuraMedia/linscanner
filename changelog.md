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
