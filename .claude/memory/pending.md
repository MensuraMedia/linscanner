---
name: linscanner-pending
description: Open items for linscanner
type: project
---

# Pending

- [ ] Real-hardware test in the GUI with the Epson ES-400 II: Color + B&W, High/Medium/Low, feeder duplex, Save As PDF (user test)
- [ ] Confirm page orientation on the ES-400 II; consider an "auto-rotate 180°" option if pages always come out upside down
- [ ] Check whether `--adf-crp` (auto-crop) can replace fixed paper sizes on epsonds
- [ ] Optional: scanner-specific extra options (skew correction, eject) from `ScannerCapabilities.options`
- [ ] Optional: OCR / searchable PDF (tesseract is already in the offline pool for gscan2pdf)
