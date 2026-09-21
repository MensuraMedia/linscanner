# linscanner

**A universal document scanner for Linux.** Scan in **Color** or **Black &
White** at **High, Medium or Low** quality, check the pages in a preview,
rotate or remove pages, then **Save As** PDF, PNG, JPEG or TIFF. It works
with any scanner that Linux's standard scanning system (SANE) can drive: USB
scanners, network and Wi-Fi scanners, and multifunction printers.

| | |
|---|---|
| Version | 0.1.0 (see [`VERSION`](VERSION), [`changelog.md`](changelog.md)) |
| Platform | Linux desktop, GTK 3 |
| Tested on | Linux Mint 22.3 (Ubuntu 24.04 base), kernel 7.0, amd64, with an Epson WorkForce ES-400 II |
| Part of | [linux-peripherals](../README.md), which has offline installers and device references |

![Scan page](docs/images/screenshot-scan.png)

---

## Contents

1. [Features](#1-features)
2. [Compatibility](#2-compatibility)
3. [Installation](#3-installation)
4. [Using linscanner](#4-using-linscanner)
5. [Settings, files and command line](#5-settings-files-and-command-line)
6. [Troubleshooting](#6-troubleshooting)
7. [Privacy and security](#7-privacy-and-security)
8. [Themes and appearance](#8-themes-and-appearance)
9. [Known limits and roadmap](#9-known-limits-and-roadmap)
10. [Development](#10-development)
11. [Credits](#11-credits)

---

## 1. Features

| Area | What you get |
|---|---|
| **Scanning** | Any SANE scanner. Flatbed, document feeder (scans every loaded page) and duplex (both sides in one pass) |
| **Color / Black & White** | Color, or Black & White. B&W is grayscale by default (keeps faint text); Settings can switch it to pure black-and-white |
| **Quality** | High 600 dpi, Medium 300 dpi, Low 150 dpi, automatically matched to the nearest resolution your scanner supports |
| **Paper size** | Letter, Legal, A4, A5 or the full scan area, limited to your scanner's maximum |
| **Clear feedback** | A summary line shows exactly what will be scanned; per-page progress; page count; plain-language errors (feeder empty, paper jam, scanner busy, not responding) |
| **Cancel** | Stops the scan and keeps the pages already scanned |
| **Preview** | Large fit-to-window view and a thumbnail strip; opens automatically after scanning |
| **Page tools** | Rotate left, right or 180° per page; delete a page; clear all |
| **Save As** | PDF (all pages in one file), TIFF (multi-page), PNG or JPEG (one file per page). Remembers your folder and asks before overwriting |
| **Devices page** | Every scanner and driver found, with sources, modes, resolutions and scan area |
| **Smart driver choice** | If one scanner is offered by several drivers, only the most reliable one is shown |
| **Remembers your choices** | Scanner, color, quality, paper, save folder and theme |
| **Themes** | The framework's seven dark themes; **Default Blue** is the default |
| **Works offline** | Every dependency is in the repo's offline package pool |
| **Try without hardware** | `--test-scanner` uses SANE's built-in virtual scanner |

The complete feature and function list is in
[`docs/FEATURES.md`](docs/FEATURES.md), and every code function is in
[`docs/api-reference.md`](docs/api-reference.md).

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

linscanner uses **SANE**, so it supports every scanner that has a SANE
driver on your system:

| Scanner type | How Linux talks to it | Driver (package) |
|---|---|---|
| **Network / Wi-Fi scanners and multifunction printers** (AirScan, eSCL, Mopria, WSD), most models from about 2015 on | Driverless over the network | `airscan` (**sane-airscan**, installed with linscanner), `escl` (libsane1) |
| **USB multifunction printers with IPP-over-USB** | Driverless over USB via the `ipp-usb` service | `airscan` + **ipp-usb** |
| **Epson** ES / DS / WF / Perfection series | USB, or network for some | `epsonds`, `epson2` (libsane1); optional Epson `epsonscan2` |
| **HP** scanners and all-in-ones | USB / network | `hpaio` (**libsane-hpaio** / hplip) |
| **Canon** PIXMA / LiDE / imageFORMULA | USB / network | `pixma`, `genesys`, `canon_dr` (libsane1) |
| **Brother** | USB / network | driverless (`airscan`) for most; Brother's `brscan` for older models |
| **Fujitsu / Ricoh** fi-series, ScanSnap | USB | `fujitsu`, `epjitsu` (some need a firmware file) |
| **Plustek, Avision, Kodak, Panasonic, Visioneer, Xerox, Samsung, …** | USB | `plustek`, `avision`, `kodak*`, `kvs*`, `xerox_mfp`, … (80+ drivers in libsane1) |
| Scanner attached to another Linux computer | Network (`saned`) | `net` (libsane1) |

**Verified hardware:** Epson WorkForce ES-400 II (USB `04b8:0181`, driver
`epsonds`). The initial hardware test passed on 2026-09-21.

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
- SANE (`sane-utils`, `libsane1`), plus `sane-airscan` for network scanners

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
4. **Color:** *Color* or *Black & White*.
5. **Quality:** *High* for small print, photos or archiving; *Medium* for
   everyday documents; *Low* for quick copies and small files.
6. **Paper size:** match your document. This avoids blank space below the page.
7. Check the grey **"Will scan: …"** line, then press **Scan**.

Pages appear as they are scanned, and **Preview** opens when the scan finishes.

![Preview page](docs/images/screenshot-preview.png)

### Fix and save
- Click a thumbnail to view that page.
- **Rotate left / right / 180°** to correct orientation, for example if your
  feeder delivers pages upside down.
- **Delete page** removes a blank or bad page. **Clear all** starts over.
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
| Drivers | Show every driver per scanner, and SANE's virtual test scanner (off by default) |

**Files:**

| Path | Content |
|---|---|
| `~/.config/linscanner/settings.json` | Your settings |
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

---

## 6. Troubleshooting

| Problem | What to do |
|---|---|
| "No scanners found" | Check the cable and power, press **Refresh**, and run `scanimage -L`. If that lists nothing, your scanner needs a SANE driver (see [Compatibility](#scanners)) |
| Scanner listed but "not responding" / timed out | Power-cycle the scanner and press Refresh. On the ES-400 II this happens after the Epson Scan 2 Flatpak crashes |
| "Document feeder is empty" | Load pages **face down**, top edge first, until the feeder grips them |
| "Scanner is busy" | Close other scanning apps (Document Scanner, Epson Scan 2, gscan2pdf) |
| Pages come out upside down | Use **Rotate 180°**. Auto-rotate is on the roadmap |
| Image is longer than the page | Choose the matching **Paper size** instead of Full scan area |
| Scanning is slow at High quality | Use a USB 3 port and cable if the scanner supports it (`../bin/device-finder` shows the link speed) |
| Scanner appears twice in other apps | A vendor driver (e.g. Epson's `epsonscan2`) adds a second entry; linscanner hides it automatically |
| Only works with sudo | Permissions: log out and in, or re-run the device installer (for the ES-400 II: `devices/scanner/epson-es-400-ii/install.sh`) |
| Network scanner not found | Same network/subnet? Is eSCL/AirScan enabled in the printer's web page? Run `airscan-discover` |

**Scanner-specific notes** are in the device references, e.g.
[`../devices/scanner/epson-es-400-ii/README.md`](../devices/scanner/epson-es-400-ii/README.md).

---

## 7. Privacy and security

- Everything runs locally. There's no network access, except to talk to a
  network scanner you choose.
- Scans stay in a private temp folder until you save them, and are deleted on exit.
- Scanner serial numbers are hidden in the interface.
- linscanner runs as your normal user. The installer asks for your password
  only to install missing distro packages.

---

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

**Known styling gap:**
- The colours match the framework, but the widget shapes don't yet. The
  current version has rounded cards and pill buttons; the framework is flat
  and square, with full-width sidebar rows and a filled active row.
- The flat framework layout is the first item of the next approved release
  (see [roadmap](#9-known-limits-and-roadmap)).

---

## 9. Known limits and roadmap

**Current limits:**
- Finding scanners takes about 10 seconds, because SANE checks every driver.
- There's no OCR, blank-page removal, auto-deskew, auto-crop or auto-rotate yet.
- Settings stored inside the scanner (sleep timer, etc.) can't be changed from Linux.

**Planned (awaiting approval, see [`../docs/HANDOFF.md`](../docs/HANDOFF.md)):**
- **0.2.0:**
  - Flat framework styling.
  - A **Scan Device Information** section with a "Check for devices again" button.
  - A connection engine that falls back through every method (SANE → vendor driver → driverless USB → direct eSCL → network eSCL/WSD → remote SANE → camera → import).
  - A full technical document.
- **0.3.0:** top-10 modern scanner features as **switchable modules**:
  - searchable PDF (OCR)
  - blank-page removal
  - auto-deskew
  - auto-crop
  - auto-rotate
  - scan profiles
  - image enhancement
  - auto-save with file-name templates
  - batch splitting / page reordering
  - PDF/A and compression options
- **Quick Edit** (requested 2026-09-21, also a switchable module), in Preview:
  - add basic **text** (about 20 common fonts, size, colour);
  - add **signatures** from transparent PNG files, kept in a small signature library;
  - drag, resize and remove placed items, and re-apply them to other pages, like mainstream PDF editors;
  - edits are stored as layers and flattened only on Save As.

---

## 10. Development

| Task | Command (in `linscanner/`) |
|---|---|
| Run | `./run.sh` (or `./run.sh --test-scanner`) |
| Test | `python3 -m pytest -q` (29 tests: parser against real scanner output, choice mapping, export, settings/themes, real scans via SANE's virtual scanner, and a full UI flow) |
| Lint | `python3 -m black --check src tests && python3 -m pyflakes src tests` |
| Format | `python3 -m black src tests` |
| API docs | `python3 tools/gen_api_docs.py` → `docs/api-reference.md` |
| Offline proof | `../bin/test-offline linscanner` |

**Layout**, following the framework:

```
src/main.py          entry point
src/config/          themes, layout, scan presets (all tunables)
src/backends/        scanner interface + SANE backend + parser (no GTK)
src/modules/         scan manager, export, settings, theme, navigation, app context
src/ui/              window, sidebar, content area, components (segmented control, preview)
src/pages/           scan, preview, devices, settings, about
src/utils/           paths, version
tests/               pytest suite + captured scanner output fixtures
docs/                FEATURES, api-reference, architecture, research, images
```

- **Add a page:** subclass `pages/page_base.BasePage`, then add it to
  `ui/content_area.PAGES` and `ui/sidebar.NAV_ITEMS`.
- **Add a scanner backend:** implement `backends/backend_base.ScannerBackend`.

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
