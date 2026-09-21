# linscanner technical document (v0.2.0)

How linscanner detects, connects to and drives scanners on Linux, what every
part does, and how the optional feature modules plug in. The user guide is
[`../README.md`](../README.md), the feature list [`FEATURES.md`](FEATURES.md),
and the code reference [`api-reference.md`](api-reference.md) (generated).
The research behind the connection design is in [`research/`](research/).

---

## 1. System overview

```
                 ┌────────────────────────────── GTK 3 UI (framework layout) ──────────────────────────────┐
                 │  Scan        Preview        Scan Device Information        Settings        About            │
                 └───────┬───────────┬──────────────────┬──────────────────────────┬────────────────────────┘
                         │           │                  │                          │
                 modules/manager_scan (ScanManager) ── modules/manager_device_info  features/FeatureRegistry
                         │                                                          (optional modules, isolated)
                 modules/manager_connection (ConnectionEngine: discovery, grouping, ranked fallback)
                         │
      ┌──────────────────┼──────────────────────────────┬───────────────────────────┐
 backends/backend_sane   backends/backend_escl           backends/usb_probe            (future backends)
 (scanimage: every SANE  (own eSCL client: IPP-over-USB  (sysfs + udev database:
  driver incl. airscan,   loopback ports, mDNS network)   identity, speed, classes,
  escl, hpaio, net)                                        access, SANE hwdb match)
```

Everything under `backends/` and most of `modules/` is GTK-free and fully
unit-tested. The UI only calls `ScanManager`, `manager_device_info` and the
`FeatureRegistry`.

---

## 2. USB interface processes

### 2.1 What happens when a scanner is plugged in

1. **Kernel enumeration.** The USB core reads the device and interface
   descriptors. They appear in `/sys/bus/usb/devices/<bus-port>/`, and a
   device node `/dev/bus/usb/BBB/DDD` is created. Scanners normally have
   **no kernel driver**, because SANE drives them from user space through
   libusb.
2. **udev rules.**
   - SANE's hardware database `/usr/lib/udev/hwdb.d/20-sane.hwdb` (1114
     entries on Mint 22) tags known scanners with `libsane_matched=yes`.
   - `60-libsane1.rules` then gives the logged-in user access (the `uaccess`
     tag, i.e. an ACL on the device node).
   - IPP-over-USB devices (interface `07/01/04`) trigger `ipp-usb`, which
     serves the device's eSCL/IPP over HTTP on `127.0.0.1:60000+`.
3. **User-space drivers.** When an app asks, SANE loads each enabled backend
   (`/etc/sane.d/dll.conf` and `dll.d/*`). Each backend probes libusb for the
   VID:PIDs it supports.

### 2.2 What linscanner reads (`backends/usb_probe.py`)

It reads everything without drivers, root or subprocesses:

| Fact | Source |
|---|---|
| Vendor/product ID, manufacturer, product | `idVendor`, `idProduct`, `manufacturer`, `product` in sysfs |
| Bus / device number, port path | `busnum`, `devnum`, directory name (e.g. `3-5`) |
| Link speed | `speed` (12 = USB 1.1, 480 = USB 2.0, 5000+ = USB 3.x) |
| Interfaces | per interface: `bInterfaceClass/SubClass/Protocol` + bound `driver` |
| Access | `os.access(/dev/bus/usb/BBB/DDD, R/W)` for the current user |
| SANE knows it | `libsane_matched` from `/run/udev/data/c<major:minor>` (key from sysfs `dev`) |
| Vendor name | `ID_VENDOR_FROM_DATABASE` from the same udev record |

### 2.3 "Is this a scanner?" heuristic (`UsbDevice.kinds`)

| Signal | Meaning |
|---|---|
| Interface `07/01/04` | **IPP-over-USB**: driverless eSCL through `ipp-usb` |
| Interface class `06` | Still-image / PTP (cameras, some portable scanners) |
| `libsane_matched=yes` | In SANE's hardware database |
| Class `ff` + a scanner vendor ID | Vendor protocol from a scanner maker (Epson `04b8`, Canon `04a9`, HP `03f0`, Brother `04f9`, Fujitsu `04c5`, …) |

Reference device: the Epson ES-400 II reports interfaces `ff/ff/ff` and
`ff/aa/01`, `libsane_matched=yes` and 480 Mbps, so it is
"sane-hwdb, vendor-protocol".

---

## 3. Universal, generic connection capabilities

linscanner doesn't hard-code scanners. It uses **every standard way Linux
can reach a scanner**, from a MECE taxonomy
([`research/connection-methods.md`](research/connection-methods.md)):

| Code | Method | Transport | In linscanner |
|---|---|---|---|
| **A1** | Open-source SANE driver | USB (libusb) | `SaneBackend` (epsonds, pixma, genesys, fujitsu, avision, … 80+) |
| **A3** | Vendor SANE driver | USB / network | `SaneBackend` (epsonscan2, hpaio, brother*, …) |
| **B2** | Driverless eSCL over IPP-USB | USB → `ipp-usb` → HTTP | `SaneBackend` via `airscan`/`escl` on 127.0.0.1 |
| **D1** | linscanner's own eSCL client | HTTP (USB loopback or network) | `EsclBackend` (standard library only) |
| **B1** | Driverless network scanning | eSCL / WSD over the network | **Disabled** (USB only, see §3.0) |
| **C1** | Remote SANE | TCP 6566 (`saned`) | **Disabled** (USB only, see §3.0) |
| **D4** | Device-side scan-to-USB/folder | files | "Import images" feature module |
| T | SANE virtual test scanner | none | `--test-scanner`, tests |

### 3.0 USB only: network discovery disabled

Network / Wi-Fi scanning is **not supported at this time**.
`NETWORK_SCANNING = False` in `config/config_scan.py` is the single switch.

- **SANE.** `SaneBackend(network=False)`, the default, copies `/etc/sane.d`
  to a private temp folder, sets `SANE_CONFIG_DIR` to it, and runs
  `usb_only_config()`:
  - `dll.conf`: `net`, `escl` and `dell1600n_net` are commented out.
  - `epson2`, `epsonds`, `kodakaio`, `magicolor`: their `net …` lines
    (autodiscovery broadcasts, SNMP) are commented out.
  - `pixma.conf`: `networking=no` (BJNP / MFNP broadcasts).
  - `airscan.conf`: `discovery = disable` and `ws-discovery = off`. IPP-USB
    devices found on 127.0.0.1:60000–60015 are listed under `[devices]`, and
    that list is refreshed before every listing, so B2 still works.
  - The folder is removed by `close()`. The system configuration is never
    modified.
- **eSCL client.** `EsclBackend(network=False)` doesn't run `avahi-browse`,
  and drops any URL that isn't loopback (`is_loopback_url`).
- **UI.** Settings shows "Network scanning (Wi-Fi / Ethernet)" as a greyed-out
  check box marked "Not Supported". The start-up log records
  `network scanning: off`.
- **Verified with `strace` (2026-09-21, ES-400 II).** Before the change,
  discovery sent WS-Discovery multicast, broadcasts to UDP 8610/8612
  (pixma), 3289 and 161 (epson2 / magicolor, SNMP) and 1124
  (dell1600n_net). After it, discovery and `-A` option reads connect only to
  127.0.0.1, and both ES-400 II drivers (epsonds A1, epsonscan2 A3) are
  still found.
- **Tests:** `tests/test_usb_only.py`.
- **To add network support later:** set `NETWORK_SCANNING = True`, make the
  Settings check box active, and test B1 / C1 / D1-over-network on real
  hardware.

Out of scope (see research): IPP Scan (no devices yet), TWAIN (not on
Linux), removed kernel drivers, PTP/V4L2 capture (detected and hinted, not
driven).

### 3.1 Discovery and grouping (`ConnectionEngine.discover`)

1. Every backend lists what it sees:
   - SANE: `scanimage -f '%d|%v|%m|%t%n'`, about 10 s because it probes
     every backend.
   - eSCL client: probes loopback ports 60000–60015, then
     `GET /eSCL/ScannerCapabilities`. It runs `avahi-browse` for
     `_uscan._tcp` / `_uscans._tcp` only when network scanning is on (it's
     off).
2. Each entry gets a method code (`method_code`).
3. Entries are **grouped into physical scanners**:
   - They merge if they share a USB bus:device.
   - They also merge if they have the same normalised model **and different
     drivers**. For example, `epsonds:libusb:003:096` and `epsonscan2:ES-400II:…`
     become one scanner.
   - Two devices from the same driver stay separate.
4. Methods are ranked **A1 → A3 → B2 → D1 → B1 → C1**.
5. USB devices that look like scanners but that no backend claimed are added
   with **no methods and a hint**:
   - permission denied → replug or log out and in;
   - IPP-USB → start `ipp-usb`;
   - PTP → gphoto2 or import;
   - SANE-known → power-cycle, or vendor driver/firmware;
   - vendor protocol → the vendor's Linux driver.

### 3.2 Heuristic fallback when scanning (`ConnectionEngine.scan`)

```
for method in physical.methods (ranked):
    caps    = method.backend.get_capabilities(device)
    request = the user's choices mapped onto THIS method's capabilities
              (equivalent source by type: flatbed / feeder / duplex; nearest dpi; paper clamp)
    try:    pages = method.backend.scan(request)  → success: record "ok", return pages
    except ScanError e:
        record (method, e)
        if e.code in {no_docs, jammed, cover_open}: raise   ← the user must act; never retry
        continue                                            ← busy, io, timeout, access,
                                                              unsupported, missing, no_device
all failed → ScanError("<last error> (tried: A, B, …)")
```

Error codes come from **scanimage's exit status, which equals the SANE
status** (`SANE_EXIT_CODES`):

| Exit | SANE status | Code |
|---|---|---|
| 3 | DEVICE_BUSY | busy |
| 6 | JAMMED | jammed |
| 7 | NO_DOCS | no_docs |
| 8 | COVER_OPEN | cover_open |
| 9 | IO_ERROR | io |
| 11 | ACCESS_DENIED | access |

Text matching is only a fallback. For eSCL, `AdfState` values map the same
way (Empty → no_docs, Jam → jammed, DoorOpen/HatchOpen → cover_open), and
HTTP 503 → busy.

### 3.3 Device access is serialised

A scanner is a single-user device. `backend_sane.DEVICE_LOCK` (re-entrant)
wraps every `scanimage` call: listing, options, status, firmware and scans.
The UI can therefore read status and firmware in the background without
"Device busy" collisions. This was found and fixed on the real ES-400 II.
Conflicts with **other** apps still surface as `busy`, and the engine then
falls through.

---

## 4. Capability and status interaction

| What | How |
|---|---|
| Options | `scanimage -d DEV -A` is parsed with groups (`standard`, `geometry`, `enhancement`, `advanced`, `sensors`) and flags (`inactive`, `advanced`, `read-only`, `hardware`) |
| Normalised capabilities | sources, modes, resolutions (lists, or ranges as standard steps), maximum area in mm |
| Device features | known option names → labels: skew correction, auto-crop, double-feed detection, blank skip, eject/load, paper-loaded and cover-open sensors, hardware buttons, counters |
| eSCL capabilities | make/model, serial (redacted), version, sources (Platen/Adf simplex/duplex), colour modes, resolutions, max size (1/300 in → mm), formats, feeder capacity, brightness/contrast/…, blank-page detection |
| Live status | eSCL `ScannerStatus` (`State`, `AdfState`), or an option read on SANE whose exit code is mapped to Ready / Busy / Not responding / Permission denied / Feeder empty / Jam / Cover open |
| Firmware | epsonds debug output (`SANE_DEBUG_EPSONDS`, "version: ADF 10L5"), eSCL `Version`, else "not reported by the driver" |

All of this appears on the **Scan Device Information** page (§5.3).

---

## 5. Application features and functions

### 5.1 Scan page

- **Scanner:** one entry per *physical* scanner, labelled with the preferred
  driver and "(+N more)" when there are fallbacks, plus **Refresh** and
  **Device info** buttons. Devices with no working driver are listed with
  their hint.
- **Options:**
  - **Profile** (feature);
  - **Source**;
  - **Sheets:** *All sheets* / *One sheet at a time*, shown for feeder sources;
  - **Color / Black & White**;
  - **High / Medium / Low**;
  - **Paper size**.
- **Summary line:** exactly what will be sent to the scanner.
- **Scan / Cancel / Done → Preview**, per-page progress, and status messages
  including how many blank pages were removed.

**Sheet-fed modes** (`sheet_limits`):

| Source | All sheets | One sheet at a time |
|---|---|---|
| Flatbed | 1 page | 1 page |
| Feeder, one side | until the feeder is empty | 1 page per press |
| Feeder, duplex | until the feeder is empty | 2 pages (front + back) per press |

In one-sheet mode each press adds to the same document. The button becomes
**Scan next sheet**, and **Done → Preview** finishes the document, which
triggers auto-save if that's enabled.

### 5.2 Preview page

- Large view and thumbnails (with Quick Edit layers shown).
- **Rotate left / right / 180°**, **Delete page**, **Clear all**,
  **Move ← / Move →**.
- Feature buttons (**Quick Edit…**, **Import images…**).
- **Save As…** (PDF / TIFF / PNG / JPEG).

Export flattens rotation and Quick Edit layers. Features may split the
pages into several documents, write the PDF themselves (OCR) and
post-process it (PDF/A, size).

### 5.3 Scan Device Information page

This page populates automatically, and **Check for devices again** re-runs
full discovery (SANE + eSCL + USB) for this page and the Scan page. For each
scanner it shows:
- Identity
- Connection (USB port / bus / device, link speed, interfaces, why it's a scanner, your access, SANE udev match, eSCL address)
- **Connection methods in fallback order** (★ preferred), and the result of each method at the last scan
- Capabilities and device features
- **Check status**
- Firmware

### 5.4 Settings and About

- **Settings:**
  - Theme: the framework's seven; **Default Blue** is the default.
  - Black & White style.
  - Save folder.
  - **Features:** on/off switches, each with its options.
  - Drivers: show all, and the test scanner.
- **About:** version, SANE version, credits.

---

## 6. Feature modules (switchable, removable)

`src/features/feature_<name>.py`. The **core never imports a feature.**
`FeatureRegistry` loads every file in the folder, each from exactly its file
path, and calls hooks only on enabled features. **Every hook call is
isolated**: an exception is logged in `registry.errors`, shown in Settings,
and skipped. A deleted file means the feature is absent. A file that fails to
load is reported and the rest load normally. All of this is tested.

| Hook | When | Used by |
|---|---|---|
| `process_page(image, page)` → image / None | each scanned page, in the scan thread | autocrop, deskew, autorotate, batch_split, blank_removal, enhance |
| `split_documents(pages)` | before export | batch_split |
| `export_pdf(pages, path)` → bool | PDF export | ocr |
| `postprocess_pdf(path)` | after a PDF is written | pdf_options |
| `after_scan(ctx, pages, final)` | a scan ended / document done | autosave |
| `extend_scan_page`, `extend_preview` | page construction | profiles; quick_edit, import_images |
| `settings_widget(ctx)` | Settings page | blank_removal, enhance, pdf_options, autosave |

| Module | Default | What it does | Built with |
|---|---|---|---|
| autocrop | **on** | Trims the feeder overrun: a uniform band at the end of the sheet that differs from the paper. Never cuts page margins, and never guesses when the overrun matches the paper | numpy |
| deskew | **on** | Projection-profile search over ±5° in 0.25° steps; straightens pages when the angle is ≥ 0.3° | Pillow, numpy |
| autorotate | off | Tesseract OSD (`--psm 0`); rotates when confidence ≥ 2 | tesseract, osd data |
| batch_split | off | Blank pages become separators; Save As writes `name-001.pdf`, `name-002.pdf`, … | core blank detection |
| blank_removal | **on** | Drops pages whose content ratio is below 0.2% (adjustable). Content = pixels that differ from the per-channel paper colour, so colour pages are kept and blank coloured paper is removed | numpy |
| enhance | off | Despeckle, brightness, contrast, whiter background, unsharp mask | Pillow |
| ocr | off | Searchable PDF: `tesseract <list> out -l eng pdf` | tesseract, eng data |
| pdf_options | off | PDF/A-2b and/or smaller files (`gs -dPDFA=2`, `-dPDFSETTINGS`) | ghostscript |
| autosave | off | Saves finished documents as PDF, named from `{date} {time} {n} {pages} {mode}` | core export |
| profiles | off | Built-in presets (Document, Color document, Photo, Receipt, Archive) plus your own | settings |
| quick_edit | **on** | Text (20 fonts) and PNG signatures; move, resize, delete, apply to all pages; non-destructive layers flattened on export | Cairo (editor), Pillow (export), fontconfig |
| import_images | **on** | Adds PNG/JPEG/TIFF (multi-page) files as pages; the D4 fallback | Pillow |

### 6.1 Quick Edit details

- **Fonts:** DejaVu Sans / Serif / Sans Mono, Liberation Sans / Serif / Mono,
  Noto Sans / Serif / Sans Mono, Ubuntu, Ubuntu Mono, URW Gothic, Nimbus
  Sans, Nimbus Sans Narrow, Nimbus Roman, Nimbus Mono PS, C059, P052, URW
  Bookman, Z003 (script).
  - They're resolved with `fc-match`, and only installed families are offered.
  - They come from the distro packages `fonts-dejavu-core`, `fonts-liberation`,
    `fonts-noto-core`, `fonts-ubuntu` and `fonts-urw-base35`, which are in
    the offline pool.
- **Signatures:**
  - Library: `~/.local/share/linscanner/signatures/` (honours `$XDG_DATA_HOME`).
  - PNG transparency is kept. If an import has none, linscanner offers to
    make the near-white background transparent and trims the border.
- **Editing:**
  - Click to select (blue frame); drag to move; drag the corner square to
    resize (signatures: width; text: font size).
  - Delete / Backspace removes the item. Double-click text to load it for
    editing, then use **Update selected text**.
  - **Apply to all pages** copies the selected item to the same place on every page.
- **Model:** `page["overlays"]`. Positions and sizes are page fractions, and
  text size is in points (pixels = pt × dpi / 72). Cairo draws the editor and
  Pillow draws the export, both anchored at the ascender, so they match.

---

## 7. Data, privacy, performance

| Item | Detail |
|---|---|
| Session scans | `/tmp/linscanner-*/`, deleted on exit; processed pages overwrite the scan file in place |
| Settings | `~/.config/linscanner/settings.json`: atomic writes, type-checked keys; `features` and `feature_settings` hold module state |
| Serial numbers | redacted in names, IDs and eSCL info |
| Threads | discovery, options, scans, status and firmware run off the GTK thread (`GLib.idle_add` back) |
| Page processing | a few tens of ms per page (autocrop/deskew/blank at 300 dpi); OCR only at export |
| Discovery | about 10–20 s (SANE probes every backend); the result is cached until "Check for devices again" |

---

## 7b. Logging

`utils/util_logging.py` configures the `linscanner.*` loggers:
- **Files:** a daily file in `$XDG_STATE_HOME/linscanner/logs/` (default
  `~/.local/state/…`), rotated at 5 MB, kept 14 days.
- **Redaction:** `RedactingFormatter` applies `parser_sane.redact` and
  replaces the home folder with `~` on every line, tracebacks included.
- **Uncaught exceptions:** `install_excepthook` logs them from the main
  thread and from worker threads.

| Logger | Records |
|---|---|
| `app` | start/exit, environment (`system_info`), settings |
| `sane` | every scanimage call (args, exit code, time; stderr on failure), scan start/end, pages, messages |
| `escl` | every HTTP request (method, URL, status, bytes, time), job lifecycle, status before a scan |
| `engine` | discovery summary per physical scanner (USB facts, ranked methods, hints); each fallback attempt and outcome |
| `scan` | request mapping (choices → device request), per-page processing notes, drops, cancel |
| `features` | modules loaded/enabled, on/off changes, each hook's time (debug), failures with traceback |
| `export` | documents, Quick Edit item count, files and sizes, time, failures |
| `quick_edit` | item counts per page (never the text) |
| `ui`, `settings`, `crash` | status and error messages, setting changes (debug), uncaught exceptions |

**Settings → Diagnostics → Save diagnostics…** writes a zip with the last 3
days of logs, `system-info.txt`, device information, feature states and
settings, all redacted. Logging never raises: an unwritable location falls
back to a null handler.

## 8. Dependencies (all distro packages; all in the offline pool)

`python3`, `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`,
`python3-pil`, `python3-numpy`, `sane-utils`, `libsane1`, `sane-airscan`,
`tesseract-ocr`, `tesseract-ocr-eng`, `tesseract-ocr-osd`, `ghostscript`,
`fontconfig`, `fonts-dejavu-core`, `fonts-liberation`, `fonts-noto-core`,
`fonts-urw-base35`, `fonts-ubuntu`.

On a clean Ubuntu 24.04 that's 304 packages with dependencies. It was
verified in a `--network none` container: the app runs, 12 features load,
20 fonts, deskew, and PDF/A.

---

## 9. Verification (v0.2.0)

| Check | Result |
|---|---|
| Unit + integration tests | 62 passed. Covers: parser on real ES-400 II output; engine grouping and fallback; direct eSCL against a fake eSCL server; SANE virtual scanner (flatbed, feeder, one-sheet, cancel, serialisation); every feature module; registry isolation; UI flows (scan → preview, one-sheet, features, Quick Edit, profiles) |
| Lint | black + pyflakes clean |
| Real hardware | ES-400 II: discovery merges epsonds + epsonscan2, Device Info complete, firmware ADF 10L5, status Ready; initial GUI scan user-confirmed (0.1.0) |
| Offline | `bin/test-offline linscanner` OK; feature pipeline run in a network-less container |
