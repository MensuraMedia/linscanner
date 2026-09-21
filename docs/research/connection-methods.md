# Research: scanner connection methods (MECE) and the fallback chain

Collected 2026-09-21 as input for linscanner's heuristic connection engine.
The host checks were read-only, on Linux Mint 22.3. "(?)" = unverified.

## Findings on the reference host
- **Device:** Epson ES-400 II `04b8:0181`, interfaces `ff/ff/ff` and `ff/aa/01`, `libsane_matched=yes`.
  `scanimage -L` lists it twice: `epsonds:libusb:…` and `epsonscan2:ES-400II:…`.
- **Installed:** `libsane1`/`sane-utils` 1.2.1, `sane-airscan` 0.99.29, `ipp-usb` 0.9.24, `hplip` + `libsane-hpaio` 3.23.12, `simple-scan`, `avahi-daemon`, `libgphoto2`.
  Vendor packages: `epsonscan2` 6.7.80 + non-free plugin (firmware blobs in `/usr/share/epsonscan2/esfw*.bin`).
- **In the archive, not installed:** `gphoto2`, `xsane`, `libinsane1`/`gir1.2-libinsane-1.0` 1.0.10, `v4l-utils`.
  **Not in the archive:** `utsushi`, `imagescan`, `brscan*`, `hplip-plugin`.
- **SANE config:**
  - Both `escl` and `airscan` are enabled, so a driverless device appears twice.
  - `gphoto2` is commented out in `dll.conf`.
  - `v4l` is listed but `libsane-v4l.so` is absent, so it's silently skipped.
  - `dll.d/` holds `airscan`, `epsonscan2`, `hplip`.
- **ipp-usb** is inactive: no `07/01/04` device is attached. Its udev rule matches `*:070104:*` and HP `ff0901`. Loopback ports are 60000–65535, with DNS-SD on.
- **Backend lookup:** `/usr/share/sane/*.desc` isn't installed, and `20-sane.hwdb` (1114 entries) doesn't name the backend.
  To map a VID:PID to a backend, grep `/etc/sane.d/*.conf` for `usb 0xVVVV 0xPPPP`, check the SANE supported-devices list, or use `scanimage -L`.

## Taxonomy (two axes: who speaks the protocol × which protocol/transport)

| # | Method | Protocol / transport | Detect | Packages (24.04) | Notes |
|---|---|---|---|---|---|
| A1 | Open SANE backend, USB | libusb + vendor command set (ESC/I, ESC/I-2, PIXMA, genesys…) | USB `ff/*/*`, `libsane_matched`, `sane-find-scanner` | `libsane1` | epsonds, epson2, pixma, genesys, plustek, gt68xx, fujitsu, canon_dr, avision, kodak*, hp5590, xerox_mfp, kvs*, ricoh*, lexmark. `epjitsu` needs firmware the user extracts |
| A2 | Open SANE backend, vendor network protocol | TCP/UDP (pixma BJNP, epson2 net, kodakaio, magicolor, xerox_mfp, dell1600n_net) | backend probe / `.conf` line | `libsane1` | older networked MFPs; often manual config |
| A3 | Vendor proprietary SANE backend | via `dll.d` | vendor ID + `dll.d` file | vendor: `epsonscan2`(+non-free), `brscan2-5`(+`brscan-skey`), Canon `scangearmp2`; archive: `libsane-hpaio` (+ `hp-plugin` for some LaserJet MFPs) | best quality for the brand; proprietary, x86-only |
| B1 | Driverless eSCL, network | HTTP(S)+XML | mDNS `_uscan._tcp` / `_uscans._tcp`, TXT `rs=` | `sane-airscan`; `escl` in `libsane1` | most AirPrint/Mopria MFPs from about 2015 on; airscan has better ADF and cancel than escl |
| B2 | Driverless eSCL over USB (IPP-over-USB) | USB `07/01/04` → `ipp-usb` → `localhost:60000+` → eSCL | `070104` in `ID_USB_INTERFACES`; `ipp-usb status` | `ipp-usb`, `avahi-daemon` | most eSCL MFPs with IPP-USB; quirk files |
| B3 | WSD / WS-Scan | SOAP/HTTP, WS-Discovery | WS-Discovery probe | `sane-airscan` | devices without eSCL; network only |
| B4 | IPP Scan (PWG 5100.17) | IPP | — | none | not on the market yet (OpenPrinting). **Skip** |
| C1 | Remote SANE (`net` + `saned`) | TCP 6566 | `net.conf`, `SANE_NET_HOSTS` | `sane-utils`, `libsane1` | scanner on another Linux machine; needs the saned ACL |
| D1 | App's own eSCL client | as B1/B2 via urllib | mDNS or known host/port | none | bypasses SANE when airscan/escl misbehave |
| D2 | PTP / MTP | USB class `06` | interface class | `libgphoto2` (+ `gphoto2` CLI) | cameras, some portable scanners |
| D3 | UVC document cameras | V4L2, USB class `0e` | `/dev/video*` | `v4l-utils` | visualizers; low resolution |
| D4 | Device-initiated push / import | scan-to-USB/SD (class 08), SMB/FTP/email, buttons | mounted storage, watched folder | `udisks2`, `gvfs` | works whenever the front panel works; last resort |

**Out of scope:**
- Kernel `scanner.ko` (removed).
- TWAIN bridges (not on Linux).
- `_privet._tcp` (Cloud Print, dead).
- `_scanner._tcp` (legacy, hint only (?)).
- libinsane (a SANE wrapper, not a transport; optional).
- Direct ESC/I-2 (duplicates epsonds).
- utsushi/iscan (superseded).
- AirSane and go-mfp (they export or simulate scanners rather than drive them).

## Recommended fallback order
Detect first, then walk down the list. Cheapest and most local first, then zero-config driverless, then methods needing manual setup, then non-scanner capture.

1. **A1** open SANE backend over USB, when the device has `libsane_matched` and is listed by a non-vendor backend.
2. **A3** vendor SANE backend for the same device. Put it first for brands where A1 is weak (newer Canon, Brother).
3. **B2** eSCL over IPP-USB via airscan, only if `070104` is present. Start `ipp-usb` if it's inactive.
4. **D1** direct eSCL against the ipp-usb localhost port.
5. **B1** network eSCL via airscan, then `escl` as a secondary.
6. **D1** direct eSCL against the network host (mDNS, or an IP the user enters).
7. **B3** WSD via airscan.
8. **A2/A3 network modes** (BJNP, brsaneconfig-registered Brother, epsonscan2 network).
9. **C1** `net`/saned remote.
10. **D2** gphoto2 PTP, then **D3** V4L2.
11. **D4** import from mounted USB/SD or a watched folder.

Dedupe the list: one MFP can appear as `airscan:e*`, `escl:` and a native backend. Prefer the order above.

## Fall through to the next method on
- "No scanners were identified", or the backend `.so` / `dll.d` entry missing.
- `DEVICE_BUSY`: retry once, then move on (a claim is held by another backend, ipp-usb or hplip).
- `IO_ERROR` or a timeout: try `SANE_USB_WORKAROUND=1` once. Also libusb TIMEOUT/PIPE, network refused or timeout, and `net`'s `connect_timeout`.
- `ACCESS_DENIED`: udev/uaccess.
- `UNSUPPORTED` / `INVAL`.
- eSCL: 503 (retry with backoff, then move on), 4xx/5xx on POST `ScanJobs`, capabilities that won't parse, TLS failure on `_uscans`.
- ipp-usb inactive or no ports in `ipp-usb status`.
- Firmware or plugin missing: epjitsu `firmware` line; HP "plugin required"; epsonscan2 non-free plugin.

**Do NOT fall through** on `NO_DOCS`, `JAMMED` or `COVER_OPEN`. These need the user to act, and retrying another backend on the same device would fail or double-feed.

## Sources
- sane-airscan: https://github.com/alexpevzner/sane-airscan, plus the `sane-airscan(5)` and `airscan-discover(1)` man pages
- ipp-usb: https://github.com/OpenPrinting/ipp-usb, https://openprinting.github.io/projects/03-ipp-usb
- SANE man pages: `sane-escl(5)`, `sane-net(5)`, `sane-usb(5)`, `saned(8)`, `sane-epjitsu(5)`, `sane-find-scanner(1)`, `sane-gphoto2(5)` (Debian/Ubuntu manpages)
- hwdb format: sane-backends `tools/sane-desc.c`
- Ubuntu noble package pages: sane-airscan, ipp-usb, libsane1, libsane-hpaio
- OpenPrinting GSoC 2026 ideas (IPP Scan status), OpenPrinting go-mfp
- printerarchive.net eSCL notes
- Only search-result summaries were seen (pages not opened) for: sane-backends 1.0.29 notes, Brother brsaneconfig FAQ, HP plugin page, scangearmp2, libinsane docs.
