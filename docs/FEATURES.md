# linscanner features and functions (v0.1.0)

> Theme note: the default is the framework's **Default Blue**. Black Yellow Gray was removed on 2026-09-21; see `README.md` §8 for the theme history.

Complete description of what linscanner does, page by page, plus
command-line options, files, settings and limits. The code-level reference
(every module, class and function) is generated in
[`api-reference.md`](api-reference.md). The design is described in
[`architecture.md`](architecture.md).

## 1. Scanner support

| Capability | How |
|---|---|
| Any scanner with a SANE driver | `backends/backend_sane.py` runs SANE's `scanimage` |
| USB scanners with open-source drivers | SANE backends (`epsonds`, `genesys`, `pixma`, `fujitsu`, `avision`, …; 80+ enabled on Mint 22) |
| Network / Wi-Fi scanners and MFPs | `sane-airscan` (eSCL/AirScan, WSD), which is a linscanner dependency |
| HP devices | `hpaio` from `hplip` when installed |
| Vendor SANE plugins | used automatically if installed (e.g. `epsonscan2`) |
| No hardware | SANE's virtual `test` scanner (`--test-scanner`); produces a colour test pattern |
| Duplicate drivers for one scanner | shown once, using the preferred driver (`PREFERRED_BACKENDS`: `epsonds` before `epsonscan2`) |
| Serial numbers | never shown (redacted in names and IDs) |

Verified hardware: Epson ES-400 II (USB `04b8:0181`, `epsonds`). The
initial GUI test passed on 2026-09-21.

## 2. Scan page

| Control | Function |
|---|---|
| Scanner list + **Refresh** | Lists scanners in the background (about 10 s; SANE probes every driver). Reselects the last-used scanner |
| Scanner details line | Device type and SANE driver in use |
| **Source** | The scanner's own sources (Flatbed, ADF Front, ADF Duplex, Automatic Document Feeder, …) |
| **Color** / **Black & White** | Color uses the device's colour mode. Black & White is grayscale by default, or pure black-and-white (lineart) if chosen in Settings, falling back to gray |
| **High** / **Medium** / **Low** | 600 / 300 / 150 dpi, snapped to the nearest resolution the scanner offers (ties go higher) |
| **Paper size** | Letter, Legal, A4, A5 or full scan area; clamped to the scanner's maximum |
| Summary line | Exactly what will be sent, e.g. `Gray · 300 dpi · 215.9×279.4 mm · ADF Duplex. Feeder: scans every loaded page.` |
| **Scan** | Starts the job. Feeder sources scan until the feeder is empty; flatbed scans one page |
| **Cancel** | Stops cleanly (SIGINT to scanimage) and keeps the pages already scanned |
| Progress bar + status | Per-page progress, a running page count, and plain-language errors (feeder empty, paper jam, busy, not responding → power-cycle) |
| Auto-navigation | Opens Preview when at least one page was scanned |

Every choice (color, quality, paper, last scanner) is remembered.

## 3. Preview page

| Control | Function |
|---|---|
| Large view | Fits the selected page to the window; decoded at display size (fast even for 600 dpi colour) |
| Thumbnail strip | Every page of the session; click to select (accent-colour outline) |
| **Rotate left / right / 180°** | Per page. Applied in the preview and on export; the scan files are never modified |
| **Delete page** | Removes the selected page |
| **Clear all** | Removes every page after a confirmation |
| Info line | `Page n of m · mode · dpi` |
| **Save As…** | GTK save dialog with PDF / PNG / JPEG / TIFF filters. The extension follows the chosen filter, it asks before overwriting, and it remembers the folder |

Export rules (`modules/manager_export.py`):

| Format | Output |
|---|---|
| PDF | One file with all pages; the page size comes from the scan resolution |
| TIFF | One multi-page file, deflate-compressed, with the dpi stored |
| PNG | One file per page (`name-001.png`, … when more than one) |
| JPEG | One file per page, quality 90, converted to RGB/gray as needed |

## 4. Devices page

One card per scanner SANE reports, including duplicates. It shows vendor,
model, driver, type and redacted device ID, and a ★ on the one the Scan page
uses. After a scanner has been selected on the Scan page, it also shows the
sources, modes, resolution range and maximum scan area.

## 5. Settings page

| Setting | Effect |
|---|---|
| Color scheme | The framework's 7 dark themes: **Default Blue (default**, as in the framework's example image), Adapta, Materia, Dracula, Nord, Gruvbox, Monokai. Applies instantly, with swatch preview. A saved theme that no longer exists falls back to Default Blue |
| Black & White | Grayscale (default) or Pure black & white (lineart) |
| Save folder | Default folder for Save As |
| Drivers | "Show every driver … and the virtual test scanner": off by default |

Settings are stored in `~/.config/linscanner/settings.json` (or under
`$XDG_CONFIG_HOME`). Writes are atomic, and invalid or unknown values are
ignored.

## 6. About page

Shows the version, a description, the SANE version (`scanimage --version`),
and credits.

## 7. Command line

| Command | Function |
|---|---|
| `./run.sh` | Start linscanner |
| `./run.sh --test-scanner` | Isolated session with only SANE's virtual scanner and a throwaway settings file |
| `./run.sh --page devices` | Open on a page (`scan`, `preview`, `devices`, `settings`, `about`) |
| `./run.sh --quit-after 20` | Close automatically (UI tests) |
| `./run.sh --version` | Print the version |
| `bash install.sh` | As your user: install missing deps (offline pool, then network) and add the menu entry |
| `bash install.sh --uninstall` | Remove the menu entry |

## 8. Files and data

| Path | Content |
|---|---|
| `/tmp/linscanner-*/scan-*/page-NNN.png` | This session's scans. Deleted when the app closes |
| `~/.config/linscanner/settings.json` | Settings |
| `~/.local/share/applications/linscanner.desktop` | Menu entry (created by `install.sh`) |

## 9. Offline and dependencies

The runtime uses only distro packages: `python3`, `python3-gi`,
`python3-gi-cairo`, `gir1.2-gtk-3.0`, `python3-pil`, `sane-utils`, `libsane1`
and `sane-airscan`. All of them, and their dependencies, are in
`../offline/noble-amd64/pool`. `install.sh` installs from there first, so no
network is needed on Linux Mint 22 / Ubuntu 24.04.

Development tools: `pytest`, `black` and `pyflakes`.

## 10. Quality gates

| Gate | Command | State at 0.1.0 |
|---|---|---|
| Build | `python3 -m compileall -q src` | passes |
| Lint | `python3 -m black --check src tests && python3 -m pyflakes src tests` | clean |
| Test | `python3 -m pytest -q` | 29 passed |
| Offline | `../bin/test-offline linscanner` | installs in a network-less container |
| Docs | `python3 tools/gen_api_docs.py` | every symbol documented |

## 11. Known limits (see `.claude/memory/pending.md`, `../docs/FOLLOW-UP.md`)

- Listing scanners takes about 10 s, because SANE probes every driver.
- The epsonds auto-crop doesn't shorten pages, so choose a paper size.
  ES-400 II pages may come out upside down; use Rotate 180°.
- There's no OCR, blank-page removal, Quick Edit (text/signatures) or scanner-button support yet (see the roadmap in `README.md`).
- Colours match the framework's Default Blue, but the shapes are still rounded cards and pills. The flat framework layout is planned.
- Settings stored inside the scanner (sleep timer, etc.) can't be changed from Linux.
