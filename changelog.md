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
| 2026-09-21T20:45:00 | Design doc docs/design/0.3.0-ui-refinements.md (written before the build; outcome recorded) |
| 2026-09-21T20:45:00 | Heroicons (MIT) for Recent, Quick Edit and zoom; util_icons recolours SVGs to the theme; librsvg2-common dep |
| 2026-09-21T20:45:00 | Scan Type (Front Page / Front & Back / Flatbed) replaces Source; remembered |
| 2026-09-21T20:45:00 | Paper sizes: Auto-Detect (default), documents, receipts, cards, photos, checks; driver auto-size option |
| 2026-09-21T20:45:00 | Auto-Detect crop (util_autodetect): paper found against the scanner background; nominal-size fallback |
| 2026-09-21T20:45:00 | Quick Edit: Apply Signature + edit icon (chooser popover, Create Signature dialog); icon tools |
| 2026-09-21T20:45:00 | Quick Edit pointer zones: hand on frame (move), text cursor inside (edit), resize corner |
| 2026-09-21T20:45:00 | Recent as a table (date, folder, file, icons), newest first; clear all / older than 5-90 days; trash per row |
| 2026-09-21T20:45:00 | About: Compatibility section (ever evolving); Heroicons credit |
| 2026-09-21T20:45:00 | Buttons sized to their labels, 28 px like the sidebar rows |
| 2026-09-21T20:45:00 | Fix: Sheets row empty after choosing a feeder; Recent icon column type |
| 2026-09-21T20:45:00 | Docs: README, FEATURES, TECHNICAL (6b), screenshots, api-reference; 103 tests; v0.3.0 |
| 2026-09-21T21:55:00 | Design doc docs/design/0.3.1-ui-polish.md (before the build; outcome recorded) |
| 2026-09-21T21:55:00 | Phosphor Icons (MIT) replace Heroicons; Preview page tools are icons with hover captions |
| 2026-09-21T21:55:00 | Scan page: Detect Scanner, Find before the list, green check when connected, Devices button |
| 2026-09-21T21:55:00 | Options: uniform 150 px buttons; Blank Pages Keep/Remove (synced with Settings); Document Size half width |
| 2026-09-21T21:55:00 | Button text 10 pt (sidebar size); sidebar Devices; page title Scan Devices Found |
| 2026-09-21T21:55:00 | App icon in Alt+Tab/panel: WM_CLASS linscanner, icon list, hicolor icon, StartupWMClass |
| 2026-09-21T21:55:00 | Signature fonts: 9 OFL + 4 licence-checked freeware (Arkipelago, Julia Lauren, Paul Signature, Sandra Belhock) |
| 2026-09-21T21:55:00 | Follow-up #33 rewritten for the bundled fonts only; v0.3.1; 105 tests |
| 2026-09-21T22:30:00 | Preview: PDF-editor toolbar groups (history, pages, arrange, content) with Phosphor icons and hover captions |
| 2026-09-21T22:30:00 | Add Text (text-t) and Signature (user-list) replace Quick Edit...; Add Image (arrow-square-in) replaces Import images |
| 2026-09-21T22:30:00 | Add Page (file-plus): insert PDF / image pages after the current page |
| 2026-09-21T22:30:00 | Duplicate page, Save page as (extract), Reverse order, Undo / Redo (Ctrl+Z / Ctrl+Shift+Z) |
| 2026-09-21T22:30:00 | Page navigation (first / previous / next / last), Fit width |
| 2026-09-21T22:30:00 | Window resizable and snappable: non-homogeneous page stack, scrolled pages, min ~200x400 |
| 2026-09-21T22:30:00 | Fix: feature buttons shown without their icons (show_all skips no-show-all widgets) |
| 2026-09-21T22:30:00 | v0.3.2; 106 tests |
| 2026-09-21T23:10:00 | Scan page: power icon (green ready / red 'Device may be off. Check power settings.'); detection off the status line |
| 2026-09-21T23:10:00 | Scan Options title; Scan Type row without label; Sheets: Multi-Page / Single Page |
| 2026-09-21T23:10:00 | Single Page: one page then Preview; after Save the next Scan starts a new document (unsaved pages kept) |
| 2026-09-21T23:10:00 | Quick Edit: styled text runs; highlight words and change font / size / colour; resize handle for signatures only |
| 2026-09-21T23:10:00 | Signature fonts reduced to Great Vibes and Sacramento (OFL); About no longer lists fonts; backlog #33 has the credits |
| 2026-09-21T23:10:00 | Settings: Default save location with Choose...; saving elsewhere no longer overwrites it |
| 2026-09-21T23:10:00 | v0.3.3; 113 tests |
| 2026-09-22T00:30:00 | Fix: Single Page stopped after one page while the ES-400 II fed the rest of the stack out unscanned |
| 2026-09-22T00:30:00 | Single Page now scans the whole tray with each sheet as its own document (front + back together) |
| 2026-09-22T00:30:00 | Preview: Doc n labels with a saved mark, per-document Save / Save As, Save All (one PDF per document) |
| 2026-09-22T00:30:00 | Auto-save writes one file per document; undo remembers documents; v0.3.4; 114 tests |
| 2026-09-22T01:10:00 | Program name is LinScanner (window title, sidebar, About, menu entry, messages, docs, LICENSE); technical names stay lowercase |
| 2026-09-22T01:10:00 | Scan page: scanner list, power mark and Devices take half the width |
| 2026-09-22T01:10:00 | v0.3.5 |
| 2026-09-22T01:40:00 | Own repository: MensuraMedia/linscanner (history kept; test serial replaced by a placeholder); linux-peripherals includes it as a submodule |
| 2026-09-22T01:40:00 | Fix: installer start check accepts the name LinScanner |
| 2026-09-23T15:36:50 | 0.3.6: Open with LinScanner. `run.sh FILE…` (and the menu entry's `Exec=… %F` + `MimeType=` for PDF/PNG/JPEG/TIFF/BMP) opens documents as pages in Preview, so the file manager's Open With lists LinScanner. Verified: right-click handler registration (`gio mime`), a 2-page PDF opened from the command line. |
| 2026-09-23T18:40:07 | 0.3.7: Zoom further into pages - maximum 8x to 16x (same steps), and zooming past a page's own resolution now keeps enlarging the view (Image.thumbnail never enlarged, so zoom used to stop silently). One zoomed page is capped at 40 megapixels. |
| 2026-09-23T21:51:16 | 0.3.8: Preview reworked - crop tool (drag a rectangle; dims what it removes; Esc cancels, Ctrl+Z undoes), page navigation moved to the top in place of the title and subtitle (more room for the page), Save / Save All / Save As as icon buttons, thumbnail-row selector now one icon button beside the thumbnails. Devices page: each section in its own card with Capabilities under Identity. Printers are no longer listed as scanners (a printer-class USB device that SANE does not know and that offers no eSCL scanner service is skipped - the Canon TR150 used to appear with a misleading permission hint). |
| 2026-09-23T23:00:46 | 0.4.0: Preview is now **Document** and Recent is now **Saved** (routes unchanged). |
| 2026-09-23T23:00:46 | 0.4.0: Crops become new pages - a crop is inserted after the page it came from, named “crop 1”, “crop 2”, … per source page; the original page is never replaced, and nothing is written outside the session folder until you save. |
| 2026-09-23T23:00:46 | 0.4.0: Name a page by double-clicking its thumbnail caption (F2 also works). The name replaces “Page n”, is what Save calls the file, and is offered by Save As. Undo restores the old name. |
| 2026-09-23T23:00:46 | 0.4.0: Document toolbar regrouped by function: History, Pages, Arrange, Edit (crop, text, signature), Export (save this page as…, Save, Save All, Save As). |
| 2026-09-23T23:00:46 | 0.4.0: Saved page: search box (file name and folder), a preview of the selected document in the lower half (collapsible, draggable divider, page by page), click a row to preview it and double-click to open it in Document, and the file name cell renames the file on disk (an existing name is refused; the list entry follows the file). |
| 2026-09-23T23:00:46 | 0.4.0: Fix: Save As did nothing - the icon button calls its action without arguments, so every click raised TypeError before the dialog opened. |
| 2026-09-23T23:00:46 | 0.4.0: Fix: Save All had no icon - the hidden button was revealed with show(), which never showed its child image. |
| 2026-09-23T23:00:46 | 0.4.0: 142 tests (6 new for names, crops, search, rename and the preview pane); README, FEATURES, TECHNICAL, api-reference and the screenshots updated; docs/design/0.4.0-document-and-saved.md records the concept. |
| 2026-09-24T01:50:45 | 0.4.1: Licence changed to Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0), replacing the bespoke LinScanner Community License (Noncommercial) 1.0. LICENSE carries a plain-language summary followed by the full official legal code; README, the About page and the docs updated. Free to use, share and adapt for any noncommercial purpose with credit and a link; commercial use still needs written permission. Not retroactive: copies released earlier keep the terms they came with. |
