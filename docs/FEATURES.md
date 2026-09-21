# linscanner features and functions (v0.2.0)

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
| Driverless USB MFPs (IPP-over-USB) | via `ipp-usb`; SANE airscan, or linscanner's own eSCL client |
| linscanner's own eSCL client | `backends/backend_escl.py`: loopback ports 60000+ (IPP-over-USB); mDNS browsing only when network scanning is on (it's off); capabilities, status, jobs, cancel |
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
| Scanner list, **Refresh**, **Device info** | Physical scanners ("Epson ES-400II (epsonds (+1 more))"); the details line lists its connection methods |
| **Profile** (feature) | One-click presets and "Save as profile…" |
| **Source** | The scanner's own sources |
| **Sheets** (feeder sources) | **All sheets** (until the feeder is empty) or **One sheet at a time** (1 page, or 2 for duplex, per press; same document) |
| **Color** / **Black & White** | Color, or B&W: grayscale by default, pure lineart via Settings |
| **High / Medium / Low** | 600 / 300 / 150 dpi, snapped to the nearest supported resolution |
| **Paper size** | Letter, Legal, A4, A5, full area; clamped to the scanner maximum |
| Summary line | Exactly what will be sent, and how sheets are handled |
| **Scan** / **Scan next sheet**, **Cancel**, **Done → Preview** | Start, stop (keeping pages), finish a one-sheet document |
| Progress + status | Per-page progress, page count, blank pages removed, plain-language errors |

## 3. Preview page

| Control | Function |
|---|---|
| Large view + thumbnails | Fit-to-window; Quick Edit layers shown on both |
| **Rotate left / right / 180°** | Per page, non-destructive |
| **Move ← / Move →** | Reorder pages |
| **Delete page**, **Clear all** | Remove one page, or all after confirmation |
| **Quick Edit…** (feature) | Text and signature editor (§6) |
| **Import images…** (feature) | Add PNG/JPEG/TIFF (multi-page) files as pages |
| **Save As…** | PDF, TIFF (multi-page), PNG, JPEG (one file per page). Applies rotation and layers, and runs the export features (split, OCR, PDF/A) |

## 4. Scan Device Information page

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
| Save folder | Where Save As starts |
| Network scanning (Wi-Fi / Ethernet) | Shown greyed out, marked **Not Supported** |
| **Features** | On/off for each module, with its options; load or run errors are listed |
| Drivers | Show every driver per scanner, and the virtual test scanner |

## 6. Feature modules (switch in Settings → Features; delete the file to remove)

| Module | Default | What it does |
|---|---|---|
| Auto-crop | on | Removes the feeder overrun at the end of a sheet (never cuts page margins) |
| Auto-straighten (deskew) | on | Straightens pages tilted up to ±5° |
| Blank-page removal | on | Removes empty pages; sensitivity slider; colour content is never "blank" |
| Quick Edit | on | Text in 20 fonts (DejaVu, Liberation, Noto, Ubuntu, URW families, Z003 script); signatures from transparent PNGs (library in `~/.local/share/linscanner/signatures/`; offers to clear a white background); select, drag, resize, delete, double-click to edit, **Apply to all pages** |
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
| `./run.sh` | Start linscanner |
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
| `~/.local/share/linscanner/signatures/` | Signature library |
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
| Test | `python3 -m pytest -q` | 74 passed |
| Offline | `../bin/test-offline linscanner` | 304 packages install; feature pipeline verified offline |
| Docs | `python3 tools/gen_api_docs.py` | every symbol documented |

## 11. Known limits

- Discovery takes about 10–20 s: SANE probes every driver over USB.
- USB only: network / Wi-Fi scanning is not supported at this time.
- Auto-crop can't tell an overrun from the paper when both are the same
  colour; use Paper size then.
- Cameras / PTP devices are detected and explained, not captured.
- OCR is English only.
- Settings stored inside the scanner can't be changed from Linux.
