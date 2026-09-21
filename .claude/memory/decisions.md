---
name: linscanner-decisions
description: Architecture and product decisions for linscanner, newest first
type: project
---

# Decisions

### 2026-09-21: Plan approved with recommended defaults
- Reason: user approval ("approve, use your recommended defaults").
- Impact:
  - OCR in English only.
  - Auto-crop, deskew and blank-page removal on by default; the other roadmap modules off.
  - Quick Edit on, with 20 system fonts from distro font packages (DejaVu, Liberation, Noto, Ubuntu, URW base35 incl. Z003 script).
  - Signatures in `~/.local/share/linscanner/signatures/`.
  - Sheet-fed "All sheets" / "One sheet at a time" added at the user's request.

### 2026-09-21: Default theme is the framework's "Default Blue"; Black Yellow Gray removed
- Reason: user correction. The app should follow the original framework styling (gtk-python-dashboard-starter dashboard.png); the black/yellow scheme wasn't needed.
- Impact:
  - Default is `default` (Default Blue: #2d2d2d window, #353535 sidebar, #0078D7 accent), completed from the framework's config_theme.py.
  - Themes are exactly the framework's seven.
  - Saved ids of removed themes fall back to the default.
  - Logo scan line recoloured to #0078D7.
- Supersedes: "Default theme is Nord" and "Default theme Black Yellow Gray" below (kept for history).
- Still open: layout shapes (rounded cards/pills) → the flat square framework layout is planned (awaiting approval).

### 2026-09-21: Default theme is Nord (superseded: Default Blue is default)
- Reason: user request (supersedes Black Yellow Gray as default; that theme stays selectable).
- Impact: Nord completed from the official palette (nord0-nord14); existing users keep their saved theme.

### 2026-09-21: Lint with black + pyflakes instead of ruff
- Reason: ruff is not packaged in Ubuntu 24.04; installing it via pip breaks the distro-packages-only / offline rule.
- Impact: `python3 -m black --check` + `python3 -m pyflakes`; revisit when ruff is packaged.

### 2026-09-21: Prefer epsonds over Epson's epsonscan2 SANE backend
- Reason: the Epson Scan 2 Flatpak crashed (SIGABRT in libes2command) on every scan on the reference host; epsonds scanned reliably.
- Impact: `PREFERRED_BACKENDS` orders epsonds first; duplicates hidden unless Settings → Drivers shows all.

### 2026-09-21: Black & White means grayscale by default
- Reason: grayscale keeps faint text and signatures; pure black-and-white can drop them.
- Impact: Settings offers "Pure black & white (lineart)", which falls back to gray if the device has no lineart.

### 2026-09-21: Semantic versioning, starting at 0.1.0
- Reason: universal-instruction-set defines no app version scheme.
- Impact: `VERSION` file; changelog records every change.

### 2026-09-21: Default theme "Black Yellow Gray" (superseded; theme removed)
- Reason: user chose universal-themes/image-reference/ui-kit-black-yellow-gray.jpg.
- Impact: colours sampled from the image (#111111, #181818, #212121, #fbd700, #b3b3b3, #82828e, #3fd059, #e8555d); the framework's 7 themes stay selectable.

### 2026-09-21: SANE via the scanimage CLI, behind a backend interface
- Reason: SANE unifies USB, network (sane-airscan: eSCL/WSD) and HP scanners; the CLI needs no Python binding (python3-sane isn't installed) and is in the offline pool.
- Impact: `backends/backend_base.ScannerBackend`; other backends can be added without UI changes.

### 2026-09-21: Build on gtk-python-dashboard-starter structure
- Reason: user requirement; gives modular config/ui/pages/modules layout.
- Impact: pages get an AppContext (settings, scan manager, event hub) because they share state, which the template's pages don't need.
