---
date: 2026-09-21
type: feature
files_changed: [linscanner/src/**, linscanner/tests/**, linscanner/docs/**, linscanner/app.json, linscanner/install.sh, offline/noble-amd64/**]
---

## Change: linscanner 0.2.0
- Flat framework styling (gtk-python-dashboard-starter layout), Default Blue.
- Sheet-fed modes: All sheets / One sheet at a time (duplex sheet = 2 pages).
- Connection engine:
  - USB probe (sysfs + udev);
  - own eSCL client (IPP-over-USB + mDNS);
  - grouping and ranked methods;
  - fallback that never retries on user-action errors;
  - SANE exit-code classification;
  - device access serialised.
- Scan Device Information page with Check for devices again, status, firmware.
- Feature registry and 12 modules: autocrop, deskew, blank removal, autorotate, enhance, OCR, PDF options, batch split, autosave, profiles, import images, Quick Edit.
- docs/TECHNICAL.md, FEATURES.md, README and api-reference updated.

## Why
User-approved plan (7 items + sheet-fed modes), using the recommended defaults.

## Impact
- New modules under backends/, modules/, features/, utils/.
- The Devices page became Device Info.
- The offline bundle gains tesseract, ghostscript, numpy and font packages (578 packages, 358 MB).

## Testing
- 62 tests pass:
  - parser, engine grouping and fallback;
  - fake eSCL server;
  - SANE virtual scanner (feeder, one-sheet, cancel, serialisation);
  - every feature on synthetic pages with known answers;
  - registry isolation;
  - UI flows incl. Quick Edit and profiles.
- black + pyflakes clean.
- Real ES-400 II: discovery merges epsonds + epsonscan2, Device Info complete, firmware ADF 10L5, status Ready.
- Offline container: 304 packages, 12 features load, 20 fonts, deskew and PDF/A work.

Root causes fixed during testing:
- "Device busy" between pages → DEVICE_LOCK;
- colour pages dropped as blank → per-channel detection;
- auto-crop cutting margins → trailing-band-only;
- registry importing by name → load by path.

Not yet: a real-hardware GUI pass of the 0.2.0 features; real IPP-USB / network eSCL devices (none available).
