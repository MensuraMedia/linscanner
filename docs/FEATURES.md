# LinScanner features and functions (v0.3.4)

Every user-facing feature, page by page, plus command-line options, files and
limits.
- How it works: [`TECHNICAL.md`](TECHNICAL.md).
- Every code function: [`api-reference.md`](api-reference.md) (generated).

> Theme note: the default is the framework's **Default Blue**, with the flat
> framework layout. Black Yellow Gray was removed on 2026-09-21; see
> `README.md` §8 for the history.

## 1. Scanner support and connection

| Capability | How |
|---|---|
| Any scanner with a SANE driver | `backends/backend_sane.py` runs `scanimage` (80+ open-source drivers on Mint 22, plus vendor plugins) |
| Network / Wi-Fi scanners | **Not supported at this time**: USB cable only. `NETWORK_SCANNING = False` (`config/config_scan.py`) switches off all network discovery: SANE drivers get a private config (no `net`/`escl`/`dell1600n_net`, no Epson/Kodak/Magicolor `net` lines, pixma `networking=no`, airscan discovery disabled with IPP-USB devices listed on 127.0.0.1); the eSCL client doesn't use mDNS and only uses loopback URLs |
| Driverless USB MFPs (IPP-over-USB) | via `ipp-usb`; SANE airscan, or LinScanner's own eSCL client |
| LinScanner's own eSCL client | `backends/backend_escl.py`: loopback ports 60000+ (IPP-over-USB); mDNS browsing only when network scanning is on (it's off); capabilities, status, jobs, cancel |
| One scanner, several drivers | grouped as one physical scanner; methods ranked A1 open driver → A3 vendor → B2 IPP-USB → D1 own eSCL → B1 network → C1 saned |
| Fallback | on busy / I/O / timeout / access / unsupported / missing driver, it tries the next method. It never does on feeder empty, jam or cover open |
| USB scanners without a driver | detected from sysfs/udev and listed with advice (permissions, ipp-usb, vendor driver, firmware) |
| No hardware | `--test-scanner`: SANE's virtual scanner (colour test pattern) |
| Privacy | nothing leaves the computer; serial numbers redacted everywhere (README §7) |

Verified hardware: Epson ES-400 II (USB `04b8:0181`), reached via epsonds
(preferred) and epsonscan2 (fallback), firmware ADF 10L5.

## 2. Scan page

| Control | Function |
|---|---|
| **Detect Scanner**: **Find**, scanner list, spinner / green ✓, **Devices** | **Find** (before the list) searches again. Physical scanners ("Epson ES-400II (epsonds (+1 more))"). The spinner turns while looking. The scanner in use is **remembered** and reached directly at the next start; if it doesn't answer, a full search runs |
| Power icon (after the scanner list) | Green `power` when the scanner answered; red, with "Device may be off. Check power settings." under the list, when it can't be found or reached (the details go in its tooltip and the log). The status line at the bottom is only for scanning. Previously: "Unable to detect scanner. Check that it's connected and powered on, then press Refresh."; the technical detail goes to the log |
| **Profile** (feature) | One-click presets and "Save as profile…" |
| **Scan Type** | **Front Page** (one side), **Front & Back** (duplex, when the scanner can), **Flatbed** (only on scanners with both a glass and a feeder). Mapped to the driver's sources by `scan_types()`; remembered |
| **Sheets** (feeder) | **Multi-Page**: every sheet into one document. **Single Page**: every sheet too (feeders pull the whole stack through), but each sheet becomes its own document (front + back together); Preview labels them Doc 1, Doc 2, … with ✓ when saved. After everything is saved the next Scan starts afresh; unsaved pages are kept (1 page, or 2 for Front & Back, per press; same document) |
| **Color** / **Black & White** | Color, or B&W: grayscale by default, pure lineart via Settings |
| **High / Medium / Low** | 600 / 300 / 150 dpi, snapped to the nearest supported resolution |
| **Blank Pages** | **Keep** / **Remove**: switches the Blank-page removal module (kept in sync with Settings → Features) |
| **Document Size** (half width) | **Auto-Detect** (default: scans the whole area, then fits each page to the paper; the scanner's own auto-size option, e.g. epsonds `--adf-crp`, is switched on too). Documents: Letter, Legal, Executive, Half Letter, A4, A5, A6, B5. Receipts: 80 / 58 mm wide. Cards: business, ID / credit, index. Photos: 4×6, 5×7. Other: check, full scan area. Receipts, cards and checks are fitted to the paper, falling back to their nominal size |
| Summary line | Exactly what will be sent, and how sheets are handled |
| **Scan**, **Cancel** | Start, or stop (keeping the pages scanned) |
| Progress + status | Per-page progress, page count, blank pages removed, plain-language errors |

## 3. Document and Saved pages

**Document** (toolbar groups, by what the tools do; every tool is a Phosphor icon with a caption on hover)

| Group / control | Function |
|---|---|
| History: Undo (`arrow-u-up-left`), Redo (`arrow-u-up-right`) | Ctrl+Z, Ctrl+Shift+Z / Ctrl+Y; up to 30 steps; a new scan or opened document starts a fresh history |
| Pages: Add Page (`file-plus`) | Insert the pages of PDFs (rendered at 300 dpi) or images after the current page |
| Pages: Add Image (`arrow-square-in`, feature) | Add PNG / JPEG / TIFF files as new pages |
| Pages: Duplicate (`copy`) | Copy the page (with its rotation and edits) after itself |
| Pages: Delete page (`file-x`), Clear all (`trash-simple`) | Remove one page, or all (after confirming; Undo brings them back) |
| Arrange: rotate left / right / 180° (`arrow-counter-clockwise`, `arrow-clockwise`, `arrows-clockwise`) | Per page, non-destructive |
| Arrange: move left / right (`arrow-left`, `arrow-right`), reverse order (`arrows-left-right`) | Reorder pages |
| Edit: Crop (`crop`) | Drag a rectangle over the page; what falls outside dims while you drag. Esc cancels, Ctrl+Z undoes. The kept part becomes a **new page** named *crop 1*, *crop 2*, … inserted after the source page and its earlier crops; the source page is never replaced |
| Edit: Add Text (`text-t`), Signature (`user-list`) (Quick Edit feature) | Open the editor with Add Text active, or with Apply Signature armed (§6) |
| Export: Save page as… (`export`) | Save only this page to its own file |
| Thumbnail captions | Double-click a caption (or F2) to name a page. The name replaces *Page n*, and is what Save calls the file and Save As offers. Empty restores *Page n*; Ctrl+Z undoes a rename |
| View bar: first / previous / next / last (`caret-double-left`, `caret-left`, `caret-right`, `caret-double-right`) | Home, Page Up, Page Down, End |
| View bar: zoom out / in, fit page (`arrows-in`), fit width (`arrows-out-line-horizontal`) | 25–1600 % of fit; Ctrl + wheel; drag to pan. Pages are drawn from display copies, so switching takes about 25 ms |
| Thumbnails | Left-aligned, scroll bar always shown, **1 row / 2 rows** (remembered) |
| **Save All** (only with several documents) | Saves each document as its own PDF in the default save location (`scan-<date>-<time>-001.pdf`, …) |
| **Save** / **Save As…** | With several documents they act on the selected one. Save writes to the document's file; a new document goes to the Save folder as a PDF, named after its thumbnails when they agree on one name and automatically otherwise. Save As chooses the name (pre-filled the same way) and format (PDF, TIFF, PNG, JPEG) |

The groups wrap onto a second row in narrow windows, and the page scrolls when
the window is smaller than it. The window can be snapped to half or a quarter
of the screen.

**Saved** (sidebar)

| Part | Function |
|---|---|
| Table | Date saved · 📂 · Folder · File name · 📄 · Pages · Format · 🗑; uniform rows, fixed columns, newest first, scrollable |
| Search box | Filters the list as you type, over the file name and the folder |
| File name cell | Editable: click it and type to **rename the file on disk** (same folder, extension kept). A name already taken is refused with a message, and the list entry follows the file |
| Preview pane | Under the list, in a `Gtk.Paned` (drag the divider) inside a collapsible expander (remembered as `saved_preview_open`). One click on a row renders the selected document's first page, with ← → for the other pages |
| 📂 folder icon (Phosphor `folder-open`) | Opens the system file manager at the folder, highlighting the file (freedesktop FileManager1), else just the folder |
| 📄 document icon (`file-text`), double-click, Enter | Opens the document (PDF rendered at 300 dpi with Ghostscript; images frame by frame) in Document and starts Quick Edit; **Save** then writes back to it |
| 🗑 trash icon | Removes the entry from the list (the file is never touched) |
| **Clear** + *All / Older than 5, 10, 20, 30, 60, 90 days* | Clears entries after confirming (files untouched) |

## 4. Scan Devices Found page (sidebar: Devices)

Populates automatically; **Check for devices again** re-runs discovery.

| Section | Content |
|---|---|
| Identity | vendor, model, USB ID, vendor name from the USB database |
| Connection | USB port / bus / device, link speed, interface classes, why it's a scanner, your access, SANE udev match, eSCL address |
| Connection methods | ranked list (★ preferred), with each method's result at the last scan |
| Capabilities | sources, colour modes, resolutions, maximum area, duplex, device features (skew, crop, double-feed, sensors, buttons…), eSCL formats and feeder capacity |
| Status | **Check status**: Ready / Busy / Feeder empty / Jam / Cover open / Not responding / Permission denied |
| Firmware | from the driver, when it reports one |

## 5. Settings page

| Setting | Effect |
|---|---|
| Color scheme | The framework's 7 themes (Default Blue default); a removed theme falls back to Default Blue |
| Black & White | Grayscale or Pure black & white |
| Default save location (**Choose…**) | Where Save puts new documents and Save As starts; saving elsewhere doesn't change it |
| Network scanning (Wi-Fi / Ethernet) | Shown greyed out, marked **Not Supported** |
| **Features** | On/off for each module, with its options; load or run errors are listed |
| Drivers | Show every driver per scanner, and the virtual test scanner |

## 6. Feature modules (switch in Settings → Features; delete the file to remove)

| Module | Default | What it does |
|---|---|---|
| Auto-crop | on | Removes the feeder overrun at the end of a sheet (never cuts page margins) |
| Auto-straighten (deskew) | on | Straightens pages tilted up to ±5° |
| Blank-page removal | on | Removes empty pages; sensitivity slider; colour content is never "blank" |
| Quick Edit | on | **Add Text** tool (click anywhere and type; Enter adds a line below) in 20 basic fonts plus the signature fonts; **styled runs**: highlight words (drag, Shift + arrows, double-click, Ctrl+A) and change their font, size or colour (with nothing highlighted, the whole text changes); text has no resize handle, only signatures do; soft **alignment guides** (edges, centre, equal spacing, mirror; Alt = free); **Apply Signature** + edit icon (signature chooser: up to 4 saved, delete, **Create Signature** by typed name in a signature font or PNG upload); pointer zones (hand on the frame = move, text cursor inside = edit, corner = resize); delete and apply to all pages (icons) |
| Import images | on | Adds image files as pages (the last-resort method: scan-to-USB on the device) |
| Auto-rotate | off | Turns upside-down or sideways pages upright (Tesseract orientation detection) |
| Batch splitting | off | Blank separator sheets split the stack into files `name-001.pdf`, … |
| Image enhancement | off | Brightness, contrast, sharpen, despeckle, whiter background |
| Searchable PDF (OCR) | off | Invisible text layer (Tesseract, English) |
| PDF options | off | PDF/A-2b and/or smaller files (Ghostscript) |
| Auto-save | off | Saves finished documents as PDF with a name template `{date} {time} {n} {pages} {mode}` |
| Scan profiles | off | Document (B&W), Color document, Photo, Receipt, Archive, plus your own |

## 7. Command line

| Command | Function |
|---|---|
| `./run.sh` | Start LinScanner |
| `./run.sh --test-scanner` | Only SANE's virtual scanner, with throwaway settings |
| `./run.sh --page devices` | Open on a page (`scan`, `preview`, `devices`, `settings`, `about`) |
| `./run.sh --quit-after N` | Close after N seconds (tests) |
| `./run.sh --version` | Print the version |
| `./run.sh --debug` | Verbose log, also on the terminal |
| `bash install.sh` / `--uninstall` | Install dependencies (offline pool first) and the menu entry / remove the menu entry |

## 8. Files and data

| Path | Content |
|---|---|
| `/tmp/linscanner-*/` | This session's scans (processed in place); deleted on exit |
| `~/.config/linscanner/settings.json` | Settings, feature on/off, feature options, profiles |
| `~/.local/share/linscanner/signatures/` | Saved signatures (max 4) |
| `~/.local/share/linscanner/fonts/` | Signature fonts the user added (never bundled) |
| `~/.local/share/linscanner/recent.json` | Recent list |
| `resources/fonts/signature/` | 2 bundled SIL OFL signature fonts (Great Vibes, Sacramento) + `fonts.json` |
| `resources/icons/phosphor/` | The Phosphor Icons used (MIT) |
| `~/.local/share/applications/linscanner.desktop` | Menu entry |

## 9. Logging and diagnostics

| Item | Detail |
|---|---|
| Log files | `~/.local/state/linscanner/logs/linscanner-YYYY-MM-DD.log`; 14 days kept; 5 MB × 3 rotations per day |
| Recorded | start-up environment; features; settings; discovery (devices, methods, USB facts, timing); scan requests (choices → exact request); scanimage commands, exit codes and messages; eSCL requests; each page (size, crop, deskew angle, blank score, rotation, dropped by …); fallback attempts; exports (documents, files, sizes, timing); Quick Edit counts (never the text); status messages; feature errors with tracebacks; uncaught exceptions |
| Redaction | serial numbers → `…`, home folder → `~` |
| Settings → Diagnostics | log path, **Open log folder**, **Save diagnostics…** (zip: 3 days of logs, system info, device info, feature states, settings) |
| `--debug` | DEBUG level (timings, every SANE/eSCL call, option lists, settings changes), also printed to the terminal; `SANE_DEBUG_DLL=1` |
| Safety | logging failures never affect scanning (tested) |

## 10. Quality gates

| Gate | Command | State at 0.2.0 |
|---|---|---|
| Build | `python3 -m compileall -q src` | passes |
| Lint | `python3 -m black --check src tests && python3 -m pyflakes src tests` | clean |
| Test | `python3 -m pytest -q` | 114 passed |
| Offline | `../bin/test-offline linscanner` | 304 packages install; feature pipeline verified offline |
| Docs | `python3 tools/gen_api_docs.py` | every symbol documented |

## 11. Known limits

- Discovery takes about 10–20 s: SANE probes every driver over USB.
- USB only: network / Wi-Fi scanning is not supported at this time.
- Auto-crop can't tell an overrun from the paper when both are the same
  colour; use Document Size then.
- Cameras / PTP devices are detected and explained, not captured.
- OCR is English only.
- Settings stored inside the scanner can't be changed from Linux.
- Auto-Detect needs the paper to differ from the scanner's background; white paper on a white backing is kept whole (or the nominal receipt / card size is used).

## 12. About page

Version and description; **Compatibility** (scanners, multifunction printers, verified devices, systems, paper, formats, what's not supported yet, and a note that compatibility keeps evolving); **Privacy**; **Licence**; **Your files**; **Handy shortcuts**; **System** (LinScanner, SANE, Python, GTK); **Credits** (including Phosphor Icons); (signature-font credits are kept in the backlog, `../docs/FOLLOW-UP.md` #33).
