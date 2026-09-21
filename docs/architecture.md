# linscanner architecture

> Full technical description (USB processes, connection methods, fallback,
> capability/status interaction, feature modules): [`TECHNICAL.md`](TECHNICAL.md).
> This page covers the original layering; 0.2.0 adds `modules/manager_connection`
> (engine), `modules/manager_device_info`, `backends/backend_escl`,
> `backends/usb_probe` and the `features/` registry.

```
main.py ─ builds AppContext(settings, scan manager, navigation, theme) ─ AppWindow
                                    │
      ┌─────────────────────────────┼──────────────────────────────┐
   ui/sidebar          ui/content_area (Gtk.Stack, one page per id)     modules/app_context
                        │   scan · preview · devices · settings · about   (event hub: pages-changed,
                        ▼                                                  devices-changed, settings-changed)
   pages/page_*  ──uses──►  modules/manager_scan  ──►  backends/backend_base.ScannerBackend
                            (choices → ScanRequest,       └─ backends/backend_sane (scanimage)
                             threads, page list)               └─ backends/parser_sane (pure parsing)
                            modules/manager_export (Pillow: PDF/TIFF/PNG/JPEG)
                            modules/manager_settings (~/.config/linscanner/settings.json)
                            modules/manager_theme_applicator (theme → CSS)
```

## Layers

| Layer | Files | Rule |
|---|---|---|
| Config | `config/config_scan.py`, `config_themes.py`, `config_layout.py` | Data only; all tunables live here |
| Backends | `backends/backend_base.py` (interface), `backend_sane.py`, `parser_sane.py` | No GTK imports; testable without a display |
| Modules | `manager_scan`, `manager_export`, `manager_settings`, `manager_navigation`, `manager_theme_applicator`, `app_context` | Business logic; GTK only for `GLib.idle_add` and CSS |
| UI | `ui/app_window`, `sidebar`, `content_area`, `components/*`, `pages/*` | Widgets and user events only |

## Scanner abstraction

`ScannerBackend` defines `available()`, `list_devices()`, `get_capabilities(id)`
and `scan(request, on_page, on_progress, cancel_event)`. SANE is the one
implementation because it already unifies most drivers (USB backends,
`sane-airscan` for eSCL/WSD network scanners, `hpaio`). Another backend (for
example direct eSCL over HTTP) can be added without touching the UI.

`SaneBackend` runs `scanimage`:
- list: `scanimage -f '%d|%v|%m|%t%n'` (about 10 s: probes every SANE backend)
- options: `scanimage -d DEV -A`, parsed into `ScannerCapabilities`
- scan: `--format=png --progress --batch=DIR/page-%03d.png --batch-print`
  - Each finished page's path arrives on stdout, so the Preview fills live.
  - Progress percentages arrive on stderr.
  - Flatbed jobs add `--batch-count=1`, so a flatbed never loops.
  - Cancel sends SIGINT; pages already scanned are kept.
- `only_backends=[...]` runs SANE with a private `SANE_CONFIG_DIR`. Used for
  the virtual `test` scanner (tests, `--test-scanner`).

## Mapping user choices to a device

| Choice | Mapping (`manager_scan.py`) |
|---|---|
| Color | first device mode matching `color`, `colour`, `24bit color`, `rgb` |
| Black & White | `gray…` names. With Settings → "Pure", `lineart`/`binary` first, gray as the fallback |
| High / Medium / Low | 600 / 300 / 150 dpi, snapped to the nearest supported resolution (ties go higher) |
| Paper | mm size clamped to the device's `-x/-y` maximum; "Full scan area" sends none |
| Feeder | a source containing `adf`/`feeder`/`duplex` scans until empty |
| Duplicate drivers | one entry per model, preferring `PREFERRED_BACKENDS` (epsonds before epsonscan2) |

## Threading

Listing, option reads and scans run in worker threads (`ScanManager._in_thread`).
Every UI update goes through `GLib.idle_add`. `ScanManager.busy` blocks
concurrent jobs.

## Data and privacy

- Scanned pages go to a per-session temp dir, which is deleted on exit.
- Settings are stored in `~/.config/linscanner/settings.json`. Writes are
  atomic, and unknown keys or wrong types are ignored.
- Scanner serial numbers are redacted before display.

## Tests (`tests/`)

| Test | Needs |
|---|---|
| `test_parser_sane.py` | fixtures captured from a real ES-400 II and the SANE test backend |
| `test_manager_scan.py`, `test_export.py`, `test_settings.py` | nothing |
| `test_backend_sane_integration.py` | `sane-utils` (virtual test scanner) |
| `test_ui_flow.py` | display + `sane-utils`: drives the real window, scan → preview → PDF |
