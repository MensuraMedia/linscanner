---
name: linscanner-pending
description: Open items for linscanner
type: project
---

# Pending

- [x] Initial real-hardware GUI test with the Epson ES-400 II: successful (user-confirmed 2026-09-21)
- [ ] Full test matrix on hardware: Color + B&W × High/Medium/Low, duplex, each Save As format
- [ ] Confirm page orientation on the ES-400 II; consider an "auto-rotate 180°" option if pages always come out upside down
- [ ] Check whether `--adf-crp` (auto-crop) can replace fixed paper sizes on epsonds
- [ ] Optional: scanner-specific extra options (skew correction, eject) from `ScannerCapabilities.options`
- [ ] Optional: OCR / searchable PDF (tesseract is already in the offline pool for gscan2pdf)
- [ ] Quick Edit module (requested 2026-09-21): text with ~20 basic fonts; signature library from transparent PNGs; place/drag/resize/re-apply; flatten on Save As. Awaiting plan approval (docs/HANDOFF.md item 7)
- [ ] Flat, square framework layout (Default Blue palette already applied). Awaiting plan approval (item 1)
