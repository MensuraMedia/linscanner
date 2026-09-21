# linscanner

**A universal document scanner for Linux.** Scan in **Color** or **Black &
White** at **High, Medium or Low** quality, check the pages in a preview,
rotate or remove pages, then **Save As** PDF, PNG, JPEG or TIFF. It works
with any **cable-connected (USB)** scanner or multifunction printer that
Linux's standard scanning system (SANE) can drive.

> **Supported connection:** linscanner currently supports scanners
> **connected by cable (USB) only**. Scanning over **Wi-Fi or a network
> (Ethernet) connection is not supported at this time.**

| | |
|---|---|
| Version | 0.2.0 (see [`VERSION`](VERSION), [`changelog.md`](changelog.md)) |
| Platform | Linux desktop, GTK 3 |
| Tested on | Linux Mint 22.3 (Ubuntu 24.04 base), kernel 7.0, amd64, with an Epson WorkForce ES-400 II |
| Part of | [linux-peripherals](../README.md), which has offline installers and device references |
| Connection | USB cable only (Wi-Fi / network scanning not supported at this time) |
| License | [linscanner Community License (Noncommercial)](LICENSE): free to use, copy, modify and share; commercial use by permission |

![Scan page](docs/images/screenshot-scan.png)

---

## Contents

1. [Features](#1-features)
2. [Compatibility](#2-compatibility)
3. [Installation](#3-installation)
4. [Using linscanner](#4-using-linscanner)
5. [Settings, files and command line](#5-settings-files-and-command-line)
6. [Troubleshooting](#6-troubleshooting)
7. [Safety, security and privacy](#7-safety-security-and-privacy)
8. [Themes and appearance](#8-themes-and-appearance)
9. [Known limits and roadmap](#9-known-limits-and-roadmap)
10. [Development](#10-development)
11. [Credits](#11-credits)
12. [License](#12-license)

---

## 1. Features

| Area | What you get |
|---|---|
| **Scanning** | Any cable-connected (USB) SANE scanner, plus linscanner's own driverless eSCL client. Flatbed, document feeder and duplex |
| **Sheet-fed modes** | **All sheets** (the whole stack in one go) or **One sheet at a time** (each press adds a sheet to the same document; a duplex sheet gives front + back) |
| **Connection fallback** | Tries every way to reach the scanner in order over the USB cable (open-source driver → vendor driver → driverless IPP-over-USB → own eSCL client), until one scans. Never retries when you need to act (feeder empty, jam, cover open) |
| **Scan Device Information** | Every detected scanner with identity, USB connection details, connection methods, permissions, capabilities, live status and firmware, plus **Check for devices again** |
| **Color / Black & White** | Color, or Black & White. B&W is grayscale by default (keeps faint text); Settings can switch it to pure black-and-white |
| **Quality** | High 600 dpi, Medium 300 dpi, Low 150 dpi, automatically matched to the nearest resolution your scanner supports |
| **Paper size** | Letter, Legal, A4, A5 or the full scan area, limited to your scanner's maximum |
| **Clear feedback** | A summary line shows exactly what will be scanned; per-page progress; page count; plain-language errors (feeder empty, paper jam, scanner busy, not responding) |
| **Cancel** | Stops the scan and keeps the pages already scanned |
| **Preview** | Large fit-to-window view and a thumbnail strip; opens automatically after scanning |
| **Page tools** | Rotate left, right or 180°; move pages earlier or later; delete a page; clear all |
| **Quick Edit** | Add text (20 basic fonts, size, colour) and signatures from transparent PNGs; drag, resize, delete and apply to all pages. Non-destructive until Save As |
| **Automatic clean-up** | Auto-crop (feeder overrun), deskew and blank-page removal, on by default |
| **More modules** | Searchable PDF (OCR), auto-rotate, image enhancement, scan profiles, auto-save with file-name templates, batch splitting, PDF/A and smaller PDFs, import images. Each can be switched on or off in Settings |
| **Save As** | PDF (all pages in one file), TIFF (multi-page), PNG or JPEG (one file per page). Remembers your folder and asks before overwriting |
| **Smart driver choice** | One scanner offered by several drivers is shown once, with the most reliable driver first and the others kept as fallbacks |
| **Remembers your choices** | Scanner, color, quality, paper, save folder and theme |
| **Look** | Flat, square gtk-python-dashboard-starter layout; the framework's seven themes, **Default Blue** by default |
| **Works offline** | Every dependency is in the repo's offline package pool |
| **Try without hardware** | `--test-scanner` uses SANE's built-in virtual scanner |

The complete feature and function list is in
[`docs/FEATURES.md`](docs/FEATURES.md). How it works (USB processes, connection
methods, fallback, modules) is in [`docs/TECHNICAL.md`](docs/TECHNICAL.md), and
every code function is in [`docs/api-reference.md`](docs/api-reference.md).

---

## 2. Compatibility

### Operating systems

| System | Status |
|---|---|
| **Linux Mint 22.x** / Ubuntu 24.04 (amd64) | **Tested.** Offline install supported |
| Ubuntu 22.04, Linux Mint 21, Debian 12/13 | Expected to work (needs Python 3.10+, GTK 3, SANE); installs from the internet, since there's no offline bundle for these yet |
| Other distributions (Fedora, Arch, openSUSE, …) | Should run from `run.sh` with the equivalent packages; `install.sh` is Debian-family only |
| arm64 (Raspberry Pi 64-bit etc.) | Should work with distro packages (untested) (?) |
| Desktop sessions | Any X11 or Wayland desktop that runs GTK 3 apps (Cinnamon, GNOME, MATE, Xfce, KDE, …) |

### Scanners

linscanner uses **SANE**, so it supports every **cable-connected (USB)**
scanner that has a SANE driver on your system.

> **Wi-Fi and network scanning is not supported at this time.** Please
> connect your scanner with a USB cable. Many Wi-Fi models also have a USB
> port and work well that way. Network support may be added in a future
> version; until then, network connections are neither tested nor supported.


| Scanner type | How Linux talks to it | Driver (package) |
|---|---|---|
| **USB multifunction printers with IPP-over-USB** | Driverless over USB via the `ipp-usb` service | `airscan` + **ipp-usb** |
| **Epson** ES / DS / WF / Perfection series | USB | `epsonds`, `epson2` (libsane1); optional Epson `epsonscan2` |
| **HP** scanners and all-in-ones | USB | `hpaio` (**libsane-hpaio** / hplip) |
| **Canon** PIXMA / LiDE / imageFORMULA | USB | `pixma`, `genesys`, `canon_dr` (libsane1) |
| **Brother** | USB | driverless over IPP-over-USB (`airscan`) for most; Brother's `brscan` for older models |
| **Fujitsu / Ricoh** fi-series, ScanSnap | USB | `fujitsu`, `epjitsu` (some need a firmware file) |
| **Plustek, Avision, Kodak, Panasonic, Visioneer, Xerox, Samsung, …** | USB | `plustek`, `avision`, `kodak*`, `kvs*`, `xerox_mfp`, … (80+ drivers in libsane1) |
| Network / Wi-Fi scanners, and scanners shared from another computer (`saned`) | **Not supported at this time** | — |

**Verified hardware:** Epson WorkForce ES-400 II (USB `04b8:0181`, driver
`epsonds`). The initial hardware test passed on 2026-09-21.

![Scan Device Information](docs/images/screenshot-device-info.png)

**Check your scanner** before or after installing:
```bash
scanimage -L                                 # lists every scanner SANE can use
sane-find-scanner -q                         # "found possible USB scanner" = recognised on USB
../bin/device-finder --scanners              # full inventory, marks scanners and their driver
```
If `scanimage -L` lists your scanner, linscanner can use it. If not, see
[Troubleshooting](#6-troubleshooting). For the full research on every
connection method, see
[`docs/research/connection-methods.md`](docs/research/connection-methods.md).

### Requirements

- Python 3.10+
- GTK 3.24 with PyGObject (`python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`)
- Pillow (`python3-pil`)
- SANE (`sane-utils`, `libsane1`), plus `sane-airscan` for IPP-over-USB multifunction printers

No pip packages and no internet at runtime.

---

## 3. Installation

### Recommended (as your normal user, not sudo)
```bash
cd linux-peripherals
bash linscanner/install.sh
```
It installs any missing packages, **from the repo's offline pool first**, so
no internet is needed on Mint 22 / Ubuntu 24.04. It asks for your password
only if packages are missing. It then adds **linscanner** to your
applications menu and checks that the app starts and that SANE sees scanners.
It's safe to run again.

### Offline machine
Clone the repo with Git LFS on any connected machine (`git lfs pull`), copy
it over (for example on a USB stick), then run the installer as above.
Details: [`../offline/README.md`](../offline/README.md).

### Manual
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil sane-utils libsane1 sane-airscan
linscanner/run.sh
```

### Uninstall
```bash
bash linscanner/install.sh --uninstall     # removes the menu entry
rm -rf ~/.config/linscanner                # removes your settings (optional)
```

---

## 4. Using linscanner

### Scan a document
1. Open **linscanner** from the menu (or run `linscanner/run.sh`).
2. **Scanner:** it's found automatically. Finding scanners takes about 10
   seconds; press **Refresh** after plugging one in.
3. **Source:** *Flatbed* for one page on the glass; a *Feeder* / *ADF*
   source for a stack; *Duplex* for both sides.
   - **Sheets** (feeder sources): *All sheets* scans the whole stack. *One
     sheet at a time* scans one sheet per press, so you can feed sheets one
     by one. The button becomes **Scan next sheet**, and **Done → Preview**
     finishes the document.
4. **Color:** *Color* or *Black & White*.
5. **Quality:** *High* for small print, photos or archiving; *Medium* for
   everyday documents; *Low* for quick copies and small files.
6. **Paper size:** match your document. This avoids blank space below the page.
7. Check the grey **"Will scan: …"** line, then press **Scan**.

Pages appear as they are scanned, and **Preview** opens when the scan finishes.

![Preview page](docs/images/screenshot-preview.png)

![Quick Edit](docs/images/screenshot-quick-edit.png)

### Fix and save
- Click a thumbnail to view that page.
- **Rotate left / right / 180°** to correct orientation, for example if your
  feeder delivers pages upside down.
- **Delete page** removes a bad page, and **Move ← / →** reorders pages.
  **Clear all** starts over.
- **Quick Edit…** opens the page editor:
  - **Text:** type it, choose one of 20 fonts, a size and a colour, then **Add text**.
  - **Signatures:** **Import PNG…** adds a signature image to your library
    (`~/.local/share/linscanner/signatures/`). Transparent PNGs work best. If
    yours has a white background, linscanner offers to make it transparent.
    Select it, then **Place signature**.
  - **Editing:** drag items to move them, and drag the blue corner square to
    resize. **Delete** removes an item, double-click text to edit it, and
    **Apply to all pages** repeats an item (e.g. a signature or date) on
    every page.
  - Edits show in the preview and are added to the file when you **Save As**.
- **Import images…** adds PNG/JPEG/TIFF files as pages (e.g. scans your
  scanner saved to a USB stick).
- **Save As…** asks for a file name and format:

| Format | Best for | Pages |
|---|---|---|
| **PDF** | Sharing, printing, archiving | All pages in one file |
| **TIFF** | Archiving at full quality | All pages in one file |
| **PNG** | Lossless images, text | One file per page (`name-001.png`, …) |
| **JPEG** | Small photo-like images | One file per page |

### Quality and file size (Letter page, typical)

| Quality | dpi | Use |
|---|---|---|
| High | 600 | Fine print, photos, archiving (largest files) |
| Medium | 300 | Everyday documents; the standard for OCR and PDFs |
| Low | 150 | Quick copies, email, screen reading |

---

## 5. Settings, files and command line

**Settings page:**

| Setting | Effect |
|---|---|
| Color scheme | The framework's seven themes (Default Blue by default) |
| Black & White | Grayscale (default) or Pure black & white |
| Save folder | Where Save As starts |
| Features | Switch each module on or off, with its options (blank-page sensitivity, enhancement sliders, PDF/A and size, auto-save folder and name template) |
| Drivers | Show every driver per scanner, and SANE's virtual test scanner (off by default) |

**Files:**

| Path | Content |
|---|---|
| `~/.config/linscanner/settings.json` | Your settings (including feature on/off and options) |
| `~/.local/share/linscanner/signatures/` | Your signature library (Quick Edit) |
| `~/.local/state/linscanner/logs/` | Daily logs (14 days), redacted |
| `/tmp/linscanner-*/` | This session's scans (deleted when you close linscanner, so save first) |
| `~/.local/share/applications/linscanner.desktop` | Menu entry |

**Command line:**

| Command | Effect |
|---|---|
| `run.sh` | Start linscanner |
| `run.sh --test-scanner` | Use only SANE's virtual scanner, with separate throwaway settings (no hardware needed) |
| `run.sh --page devices` | Open on a page: `scan`, `preview`, `devices`, `settings`, `about` |
| `run.sh --version` | Show the version |
| `run.sh --quit-after N` | Close after N seconds (automated tests) |
| `run.sh --debug` | Verbose log (also printed to the terminal) plus SANE driver-loading details |

---

## 6. Troubleshooting

**Logs:** linscanner keeps a log of every session in
`~/.local/state/linscanner/logs/` (one file per day, kept 14 days).
It records:
- detection: scanners, connection methods, timing;
- every scan: your choices, the exact scanner command, each page, and what
  auto-crop, deskew and blank removal did to it;
- fallback attempts, and errors with the scanner's full message;
- every save.

Serial numbers and your home folder path are removed. **Settings →
Diagnostics** has **Open log folder** and **Save diagnostics…** (one zip to
send for help). Start with `run.sh --debug` for extra detail.


| Problem | What to do |
|---|---|
| "No scanners found" | Check the cable and power, then **Device Info → Check for devices again**. A scanner found on USB but with no working driver is listed there with what to do |
| Scanner listed but "not responding" / timed out | Power-cycle the scanner and press Refresh. On the ES-400 II this happens after the Epson Scan 2 Flatpak crashes |
| "Document feeder is empty" | Load pages **face down**, top edge first, until the feeder grips them |
| "Scanner is busy" | Close other scanning apps (Document Scanner, Epson Scan 2, gscan2pdf) |
| Pages come out upside down | Turn on **Auto-rotate** in Settings → Features (needs text on the page), or use **Rotate 180°** |
| Image is longer than the page | Auto-crop (on by default) trims the feeder overrun when it's distinguishable from the paper; otherwise choose the matching **Paper size** |
| A page with content was removed as blank | Lower the blank-page sensitivity in Settings → Features, or turn blank-page removal off |
| Can't find the text in a saved PDF | Turn on **Searchable PDF (OCR)** in Settings → Features |
| Scanning is slow at High quality | Use a USB 3 port and cable if the scanner supports it (`../bin/device-finder` shows the link speed) |
| Scanner appears twice in other apps | A vendor driver (e.g. Epson's `epsonscan2`) adds a second entry; linscanner hides it automatically |
| Only works with sudo | Permissions: log out and in, or re-run the device installer (for the ES-400 II: `devices/scanner/epson-es-400-ii/install.sh`) |
| My Wi-Fi / network scanner isn't listed, or doesn't scan | Wi-Fi and network scanning isn't supported at this time. Connect the scanner with a USB cable |

**Scanner-specific notes** are in the device references, e.g.
[`../devices/scanner/epson-es-400-ii/README.md`](../devices/scanner/epson-es-400-ii/README.md).

---

## 7. Safety, security and privacy

### Our commitment

**Your scans and information never leave your computer.** linscanner does not
send documents, scan images, text, signatures, settings, logs, device details
or any other data to anyone else. That includes the linscanner developers,
cloud services, analytics or advertising companies, AI or OCR services, and
any other second or third party.

- **No cloud.** Every step runs on the computer that did the scan: scanning,
  page processing, OCR, PDF creation, Quick Edit and saving.
- **No accounts, sign-in, telemetry, analytics, crash reporting, ads or
  update checks.** linscanner never contacts the internet.
- **OCR is local.** Searchable PDFs use Tesseract, installed on your
  computer. Your text is never uploaded for recognition.
- **You decide what leaves.** A file leaves your computer only if you copy,
  email or upload it yourself.

### Where your data is kept

| Data | Location | Lifetime |
|---|---|---|
| Scans in progress | `/tmp/linscanner-*/`, a folder only your user can read | Deleted when linscanner closes |
| Saved documents | The folder you choose in **Save As** or Auto-save | Until you delete them |
| Settings and profiles | `~/.config/linscanner/settings.json` | Until you delete them |
| Signatures | `~/.local/share/linscanner/signatures/` | Until you delete them (Quick Edit → delete) |
| Logs | `~/.local/state/linscanner/logs/` | 14 days, then deleted automatically |

- **Logs don't contain your content.** They record technical events only: no
  page images and no Quick Edit text.
  - Scanner serial numbers are replaced with `…`.
  - Your home folder path is shown as `~`.
- **Settings → Diagnostics → Save diagnostics…** writes a zip file to the
  place you pick on this computer. It is never sent anywhere automatically;
  sharing it (for example, to get help) is your choice. It contains the same
  redacted logs and system details, and no scans.

### What linscanner does on your network, and why

For full transparency, here is the only network activity. None of it carries
your scans or personal information to anyone.

1. **USB scanners that use IPP-over-USB.** linscanner talks to `127.0.0.1`
   ports 60000–60015. That address is *this computer*: the `ipp-usb` service
   passes the traffic down the USB cable. It never reaches a network.
2. **Finding scanners on your local network.** When linscanner looks for
   scanners (at start-up and on **Refresh** / **Check for devices again**),
   the SANE drivers and linscanner's detection send short "is there a scanner here?" queries to
   your local network (mDNS, WS-Discovery and vendor discovery broadcasts).
   - The queries contain no scans, files or personal data.
   - Routers don't forward them to the internet.
3. **No scanning over the network.** Wi-Fi and network scanning isn't
   supported at this time, so your pages travel only along the USB cable,
   from the scanner into your computer.

Verified on 2026-09-21: every connection made during device discovery was
traced (`strace`). They went only to this computer (`127.0.0.1` and local
system services) and to local-network discovery addresses. There were **no
connections to any internet address**. A USB-only scanner, such as the
Epson ES-400 II, never uses the network at all.

### Security

- **No elevated rights.** linscanner runs as your normal user and never asks
  for administrator access. Access to USB scanners comes from standard
  desktop permissions (udev `uaccess`).
- **The installer** asks for your password only to install missing distro
  packages. It takes them from the repository's offline package pool first,
  and only falls back to your system's configured Debian/Ubuntu/Mint
  package sources if that pool isn't available.
- **Trusted components only.** linscanner uses Python, GTK and the
  distribution's SANE, Tesseract and Ghostscript packages, plus Epson's own
  driver for Epson scanners. No code is downloaded at run time.
- **Private temporary files.** Scans in progress are kept in a folder only
  your user can open, and are removed on exit.

## 8. Themes and appearance

linscanner's structure comes from **gtk-python-dashboard-starter**, and so
do its seven dark themes:

| Theme | Accent |
|---|---|
| **Default Blue** (default) | `#0078D7` on `#2d2d2d` / `#353535`, as in the framework's example image |
| Adapta | `#00bcd4` |
| Materia | `#8ab4f8` |
| Dracula | `#bd93f9` |
| Nord | `#88c0d0` |
| Gruvbox | `#fe8019` |
| Monokai | `#f92672` |

**Theme history (so older notes make sense):**
- Version 0.1.0 first shipped a "Black Yellow Gray" default (from a
  universal-instruction-set reference image).
- The default then briefly became Nord.
- On 2026-09-21 the user corrected this. The default is the **framework's
  Default Blue**, and Black Yellow Gray was **removed**.
- If your saved settings name a removed theme, linscanner falls back to
  Default Blue.
- Older commits and the append-only change log still mention the earlier
  defaults.

**Styling:** since 0.2.0 linscanner uses the framework's flat, square layout (full-width sidebar rows, active row filled with the accent colour, flat buttons).

---

## 9. Known limits and roadmap

**Current limits:**
- Only cable-connected (USB) scanners are supported. Wi-Fi and network scanning is not supported at this time.
- Finding scanners takes about 10–20 seconds, because SANE checks every driver, including the drivers' own network discovery.
- Cameras (PTP) and document cameras are detected and explained, but not captured.
- Settings stored inside the scanner (sleep timer, etc.) can't be changed from Linux.
- OCR is English only.

**Done in 0.2.0:**
- the framework styling;
- sheet-fed modes;
- Scan Device Information;
- the connection engine with fallback and the own eSCL client;
- all ten roadmap modules;
- Quick Edit.

The technical details are in [`docs/TECHNICAL.md`](docs/TECHNICAL.md), and open items in [`../docs/FOLLOW-UP.md`](../docs/FOLLOW-UP.md).

---

## 10. Development

| Task | Command (in `linscanner/`) |
|---|---|
| Run | `./run.sh` (or `./run.sh --test-scanner`) |
| Test | `python3 -m pytest -q` (62 tests: parser, engine and fallback, fake eSCL server, SANE virtual scanner, every feature module, registry isolation, UI flows) |
| Lint | `python3 -m black --check src tests && python3 -m pyflakes src tests` |
| Format | `python3 -m black src tests` |
| API docs | `python3 tools/gen_api_docs.py` → `docs/api-reference.md` |
| Offline proof | `../bin/test-offline linscanner` |

**Layout**, following the framework:

```
src/main.py          entry point
src/config/          themes, layout, scan presets (all tunables)
src/backends/        scanner interface, SANE backend, own eSCL client, USB probe, parser (no GTK)
src/features/        optional modules (feature_*.py), loaded by the FeatureRegistry
src/modules/         scan manager, connection engine, device info, export, settings, theme, navigation, context
src/ui/              window, sidebar, content area, components (segmented control, preview)
src/pages/           scan, preview, device info, settings, about
src/utils/           paths, version
tests/               pytest suite + captured scanner output fixtures
docs/                FEATURES, api-reference, architecture, research, images
```

- **Add a page:** subclass `pages/page_base.BasePage`, then add it to
  `ui/content_area.PAGES` and `ui/sidebar.NAV_ITEMS`.
- **Add a scanner backend:** implement `backends/backend_base.ScannerBackend` and add it to the engine in `main.py`.
- **Add a feature:** create `src/features/feature_<name>.py` with a `Feature(BaseFeature)` class. It's loaded automatically, can be switched off in Settings, and deleting the file removes it.

Project rules, from the universal instruction set, are in
[`CLAUDE.md`](CLAUDE.md):
- plan first, and wait for approval;
- every change goes in `changelog.md` + `changelog.json`;
- decisions go in `.claude/memory/decisions.md`;
- conventional commits;
- semantic versioning.

The design is in [`docs/architecture.md`](docs/architecture.md).

---

## 11. Credits

- UI structure and themes: [gtk-python-dashboard-starter](https://github.com/mikesdatawork/gtk-python-dashboard-starter) by mikesdatawork (free for personal and educational use)
- Build process: [MensuraMedia/universal-instruction-set](https://github.com/MensuraMedia/universal-instruction-set)
- Scanning: [SANE](http://www.sane-project.org/), [sane-airscan](https://github.com/alexpevzner/sane-airscan), [ipp-usb](https://github.com/OpenPrinting/ipp-usb)
- Images and PDF: [Pillow](https://python-pillow.org/)

---

## 12. License

linscanner is shared under the
[**linscanner Community License (Noncommercial)**](LICENSE).

- **You're welcome to** use it free of charge, and to copy, modify and share
  it for any noncommercial purpose. This includes personal and household
  use, education, research, and not-for-profit community work. Please keep
  the license with every copy.
- **Commercial use** needs our written permission first. This covers
  selling it, bundling it into a paid product or service, or using it in the
  operations of a business. We're happy to talk; please contact
  [MensuraMedia](https://github.com/MensuraMedia).
- The components linscanner builds on (SANE, GTK, Tesseract, Ghostscript,
  Pillow, vendor drivers, the dashboard framework, …) keep their own
  licenses.

This is a summary; the [`LICENSE`](LICENSE) file is the authoritative text.
