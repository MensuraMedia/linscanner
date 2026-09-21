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
- [x] Quick Edit module: done in 0.2.0
- [x] Flat, square framework layout: done in 0.2.0
- [ ] Real-hardware GUI pass of 0.2.0 on the ES-400 II: one-sheet mode, duplex, blank removal, deskew/crop on real paper, Quick Edit + Save As, OCR
- [ ] Test the eSCL client and B2 path with a real IPP-over-USB / network scanner (none available here)
