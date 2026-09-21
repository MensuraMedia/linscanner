# Research: richer interaction with scanner capabilities and status

Collected 2026-09-21 as input for the "Scan Device Information" panel and the
connection engine. "(verified)" = checked on the reference host (Epson
ES-400 II, SANE 1.2.1, sane-airscan 0.99.29, ipp-usb 0.9.24, epsonscan2
6.7.80, hplip 3.23.12). "(?)" = not confirmed. Serial numbers are redacted.

## 1. SANE option model
- Types: BOOL, INT, FIXED, STRING, BUTTON (action, no value), GROUP.
- Constraints: NONE, RANGE (min/max/quant), WORD_LIST, STRING_LIST.
- Capability flags: SOFT_SELECT, HARD_SELECT, SOFT_DETECT, EMULATED, AUTOMATIC, INACTIVE, ADVANCED.
- Groups: `standard`, `geometry`, `enhancement`, `advanced`, `sensors`.
- Well-known sensors and buttons: `scan`, `email`, `fax`, `copy`, `pdf`, `cancel`, `page-loaded`, `cover-open`.
- `scanimage -A` format: each option prints as `--name constraint [value]`, with at most one suffix:
  - ` [inactive]`
  - ` [hardware]`: HARD_SELECT
  - ` [read-only]`: SOFT_DETECT without SOFT_SELECT
  - ` [advanced]`
  - An `auto|` prefix means AUTOMATIC. Re-running `-A` re-reads the sensor values.
- Sensors by backend:
  - **fujitsu:** `double-feed`, `error-code`, `skew-angle`, `page-loaded`, `cover-open`, and double-feed controls (`df-*`).
  - **canon_dr:** `start`, `stop`, `counter`, `roller-counter`, `adf-loaded`.
  - **avision:** `message`, `adf-installed`, `button%d`.
  - **epsonds:** a `scan` button sensor, inactive when absent; the ES-400 II exposes none (verified).
- Buttons:
  - `scanbd` 1.5.1 is in Ubuntu 24.04 universe (verified). It holds the device while polling, so apps must use its `scanbm` hand-off (?).
  - `insaned` is not packaged (verified).

## 2. eSCL (AirScan / Mopria)
- Endpoints: `GET /eSCL/ScannerCapabilities`, `GET /eSCL/ScannerStatus`, `POST /eSCL/ScanJobs` (201 + `Location`), `GET <Location>/NextDocument`, `DELETE <Location>`.
- Capabilities:
  - Identity: `pwg:MakeAndModel`, `pwg:SerialNumber`, `scan:UUID`, `scan:AdminURI`.
  - Sources: `scan:Platen`; `scan:Adf` with `AdfSimplexInputCaps`, `AdfDuplexInputCaps`, `FeederCapacity`, `AdfOptions` (`DetectPaperLoaded`, `Duplex`).
  - Per source: min/max width and height, `MaxOpticalXResolution`.
  - `SettingProfiles`: `ColorModes` (`BlackAndWhite1`, `Grayscale8`, `RGB24`), `DocumentFormats`, `SupportedResolutions`.
  - `SupportedIntents`.
  - `*Support` ranges for Brightness, Contrast, Gamma, Sharpen, Threshold, NoiseRemoval, CompressionFactor.
  - `BlankPageDetection` / `BlankPageDetectionAndRemoval`.
- Status:
  - `pwg:State`: `Idle|Processing|Testing|Stopped|Down`.
  - `scan:AdfState`: `ScannerAdfLoaded|Empty|Jam|DoorOpen|HatchOpen|Mispick|MultipickDetected|…`.
  - `Jobs/JobInfo` with `JobState` and `ImagesToTransfer`.
  - The escl backend maps them as: Processing→DEVICE_BUSY, Jam→JAMMED, DoorOpen→COVER_OPEN, Empty→NO_DOCS.
- ScanSettings: `Intent`; `ScanRegion` in 1/300 inch (A4 = 2480×3508); `InputSource` (`Platen|Feeder|Camera`); `ColorMode`; resolution; `DocumentFormat`; `Duplex`; brightness and contrast; `BlankPageDetection`.
- Over USB: ipp-usb binds each device to a loopback port in 60000–65535, stable for a given VID/PID/serial (verified: `/etc/ipp-usb/ipp-usb.conf`). Example: `curl -s http://localhost:60000/eSCL/ScannerStatus`.
- Over the network: find devices with DNS-SD `_uscan._tcp` / `_uscans._tcp`; the TXT `rs=` gives the path prefix (?).

## 3. WS-Scan (WSD)
`GetScannerElements` returns `ScannerDescription`, `ScannerConfiguration`
(Platen, ADF, duplex) and `ScannerStatus` (`ScannerState`,
`ActiveConditions`). Use it through sane-airscan; don't implement it directly.

## 4. IPP (multifunction devices)
- `Get-Printer-Attributes` on `/ipp/print`: `printer-make-and-model`, `printer-device-id`, `printer-uuid`, `printer-state(-reasons)`, `printer-more-info`, firmware (?).
- IPP Scan (PWG 5100.17, `/ipp/scan`) is rarely implemented; eSCL is the practical route.
- ipp-usb: `ipp-usb status` (daemon control socket), logs in `/var/log/ipp-usb/`, and the device web UI at `http://localhost:<port>/`.

## 5. USB identification without drivers
- sysfs: `idVendor`, `idProduct`, `manufacturer`, `product`, `bcdDevice`, `speed`, `busnum`/`devnum`, and per interface the class/subclass/protocol plus the bound driver.
- udev properties:
  - `ID_VENDOR_FROM_DATABASE`, `ID_USB_INTERFACES`, `ID_PATH`.
  - `libsane_matched=yes` comes from `20-sane.hwdb` (1114 entries); `60-libsane1.rules` then grants access.
  - ES-400 II values: `ID_USB_INTERFACES=:ffffff:ffaa01:`, `libsane_matched=yes`, 480 Mbps (verified).
- Class heuristic:
  - `07/01/04` = IPP-over-USB (ipp-usb; HP also uses `ff/09/01`).
  - `07/01/0x` = printer.
  - `06` = still-image / PTP.
  - `ff` plus a scanner vendor ID (04b8 Epson, 04a9 Canon, 03f0 HP, 04f9 Brother, 04c5 Fujitsu, 0638 Avision, 1083 Canon DR) or `libsane_matched` = likely scanner.
- `sane-find-scanner -q`: "found possible USB scanner … at libusb:BBB:DDD" is a heuristic. "Access denied" lines are non-scanner devices (verified).

## 6. Vendor-specific sources
- epsonds, with `SANE_DEBUG_EPSONDS=1 scanimage -d <dev> -A` (verified):
  - product, firmware (`ADF 10L5`), serial;
  - ADF: sheet feed, single-pass duplex, pre-feed, area/max, paper-end detection, skew correction, cropping.
- Epson Scan 2 (verified):
  - `epsonscan2 --list` returns the device ID and ModelID.
  - `epsonscan2 --get-status` returns live feeder status, e.g. "Load the originals in the ADF."
  - `-c` writes SF2 settings: `DoubleFeedDetection`, `BlankPageSkip`, `PaperDeskew`, `AutoSize`, `PaperEndDetection`, …
- HPLIP: `hp-info -i -d <uri>` (model, dynamic status), `hp-check`.
- Brother: `brscan-skey` handles scan buttons (?).

## 7. Status and health
- scanimage exit code = SANE status:

| Exit code | Status | Message |
|---|---|---|
| 3 | DEVICE_BUSY | "Device busy" |
| 6 | JAMMED | "Document feeder jammed" |
| 7 | NO_DOCS | "Document feeder out of documents" |
| 8 | COVER_OPEN | "Scanner cover is open" |
| 9 | IO_ERROR | "Error during device I/O" |
| 11 | ACCESS_DENIED | "Access to resource denied" |

- In `--batch`, NO_DOCS after at least one page counts as success ("Batch terminated, N pages scanned").
- Double feed usually surfaces as JAMMED or IO_ERROR.
- Status without scanning: eSCL `ScannerStatus`, SANE sensor options, `epsonscan2 --get-status`.

## 8. Recommended "Scan Device Information" panel (priority order)
1. Identity: vendor/model, serial (redacted), SANE device names. Merge duplicates by serial or USB path.
2. Connection path: USB bus:dev, port, speed; or ipp-usb port; or network host and protocol. Also the backend.
3. Driver and permissions: claiming backends, `libsane_matched`, ACL, advice when access is denied.
4. Capabilities: sources, modes, resolutions, area, duplex, advanced features (skew, crop, double-feed, blank-skip); eSCL XML fields.
5. Live status: a "Check status" button mapping eSCL / sensors / exit codes to Ready, Busy, Feeder empty, Jam, Cover open.
6. Firmware (best effort): eSCL, IPP, vendor debug.
7. Hardware buttons: document scanbd; don't poll from the app.

## Sources
- https://sane-project.gitlab.io/standard/api.html
- https://gitlab.com/sane-project/backends/-/raw/master/include/sane/saneopts.h
- https://gitlab.com/sane-project/backends/-/raw/master/frontend/scanimage.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/fujitsu.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/canon_dr.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/avision.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/epsonds.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/epsonds-cmd.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/escl/escl_capabilities.c
- https://gitlab.com/sane-project/backends/-/raw/master/backend/escl/escl_status.c
- https://raw.githubusercontent.com/alexpevzner/sane-airscan/master/airscan-escl.c
- https://pkg.go.dev/github.com/OpenPrinting/go-mfp/proto/escl
- https://github.com/OpenPrinting/ipp-usb
- https://learn.microsoft.com/en-us/windows-hardware/drivers/image/scannerstatus
- https://ftp.pwg.org/pub/pwg/candidates/cs-ippscan10-20140918-5100.17.pdf
- Local (verified): `/etc/ipp-usb/ipp-usb.conf`, `/lib/udev/rules.d/71-ipp-usb.rules`, `/lib/udev/hwdb.d/20-sane.hwdb`
