---
date: 2026-09-21
type: feature
files_changed: [linscanner/**, bin/make-offline-bundle, offline/noble-amd64/manifests/app-linscanner.txt, offline/noble-amd64/pool/*]
---

## Change: linscanner 0.1.0, universal document scanner

GTK 3 app on the gtk-python-dashboard-starter structure, with scanning through SANE:
- Scan page: scanner, source, Color / Black & White, High / Medium / Low, paper size
- Preview: thumbnails and a large view, rotate and delete, Save As PDF/PNG/JPEG/TIFF
- Devices, Settings (theme, save folder, B&W style, driver visibility), About

## Why
The Epson Scan 2 Flatpak crashed on every scan and never produced a file. The
user wanted their own universal, modular scanner app that works with most
scanners through widely adopted drivers.

## Impact
- New folder `linscanner/`, and a menu entry via `install.sh`.
- `bin/make-offline-bundle` now also reads `*/app.json`.
- The offline pool gains linscanner's dependencies (270 with deps, 565 packages total).
- No change to existing device installers.

## Testing
- `python3 -m pytest -q`: 27 passed. Covers:
  - the parser against real ES-400 II and SANE test-backend output;
  - choice mapping, export, settings;
  - real scans via the SANE virtual scanner (flatbed, 10-page feeder, cancel);
  - an in-process UI flow (scan → preview → rotate/delete → PDF).
- black --check and pyflakes: clean. compileall: clean.
- Launched on the desktop (`--test-scanner`); screenshot matches the reference palette.
- `bin/test-offline linscanner`: deps install with --network none. The app scanned 10 pages and wrote a PDF inside that container.
- `install.sh` on the host: dependencies present, menu entry valid (desktop-file-validate), re-run is idempotent.
- Not yet: GUI scan on the real ES-400 II (pending, needs paper loaded).
