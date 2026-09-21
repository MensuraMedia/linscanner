# linscanner

A universal document scanner for Linux. Scan in **Color** or **Black &
White** at **High / Medium / Low** quality, preview and fix the pages, then
**Save As** PDF, PNG, JPEG or TIFF.

It works with **any scanner that has a SANE driver**, which covers most
scanners on Linux:

| Scanner type | SANE driver |
|---|---|
| Network / Wi-Fi scanners and multifunction printers (eSCL, WSD, AirScan) | `sane-airscan` (included) |
| Epson ES / DS / WF series (USB) | `epsonds` (e.g. Epson ES-400 II) |
| HP scanners and multifunction printers | `hpaio` (hplip) |
| Canon, Brother, Fujitsu, Plustek, … | built-in SANE backends |

Part of [linux-peripherals](../README.md). Version: see [`VERSION`](VERSION).

## Install and run

```bash
bash linscanner/install.sh      # as your normal user; installs missing packages (offline pool first)
```

Then open **linscanner** from the menu, or run `linscanner/run.sh`.

```bash
./run.sh --test-scanner         # try it without hardware (SANE's virtual scanner)
./run.sh --page devices         # open on a given page
./run.sh --version
bash install.sh --uninstall     # remove the menu entry
```

Works offline: all dependencies are in the repo's offline pool (Linux Mint 22 / Ubuntu 24.04).

## Using it

1. **Scan**: pick the scanner, the source (flatbed / feeder / both sides),
   **Color** or **Black & White**, **High** (600 dpi), **Medium** (300) or
   **Low** (150), and the paper size, then press **Scan**. The line under
   the options shows exactly what will be sent to the scanner. Quality snaps
   to the nearest resolution the scanner supports.
2. **Preview** opens when the scan finishes. Click a thumbnail to view a page,
   use **Rotate** or **Delete page**, then **Save As…**. PDF and TIFF save
   all pages in one file; PNG and JPEG save one file per page.
3. **Devices** lists every scanner and driver SANE found, with capabilities.
   **Settings** holds the theme, the default save folder, and what
   Black & White means.

**Black & White** is grayscale by default: readable, and safe for faint
text. Settings can switch it to pure black-and-white (lineart), which gives
smaller files and crisp text but can drop light marks.

When one scanner is offered by several drivers (for example the ES-400 II via
`epsonds` and Epson's own `epsonscan2`), only the most reliable one is shown.
Settings → Drivers shows them all.

## Development

| Task | Command (run in `linscanner/`) |
|---|---|
| Run | `./run.sh` |
| Test | `python3 -m pytest -q` (27 tests; UI-flow test needs a display) |
| Lint | `python3 -m black --check src tests && python3 -m pyflakes src tests` |
| Format | `python3 -m black src tests` |

Architecture: [`docs/architecture.md`](docs/architecture.md). Project rules:
[`CLAUDE.md`](CLAUDE.md). History: [`changelog.md`](changelog.md).

## Credits

- UI framework: [gtk-python-dashboard-starter](https://github.com/mikesdatawork/gtk-python-dashboard-starter) by mikesdatawork
- Build process and the Black Yellow Gray theme (`ui-kit-black-yellow-gray`): [MensuraMedia/universal-instruction-set](https://github.com/MensuraMedia/universal-instruction-set)
- Scanning: [SANE](http://www.sane-project.org/)
