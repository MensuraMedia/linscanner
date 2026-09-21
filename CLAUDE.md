# CLAUDE.md — linscanner

## Overview
Universal Linux document scanner (GTK 3 + SANE). Must run from distro packages
only (no pip) and install offline from `../offline/`. This file extends the
parent `../CLAUDE.md` / `../AGENTS.md`; where they conflict, this file wins for
`linscanner/`.

## Architecture
- Python 3.10+, GTK 3 via PyGObject, Pillow for export, SANE via `scanimage`
- Structure from gtk-python-dashboard-starter: `src/{config,ui,pages,modules,utils}` + `src/backends`
- Details: @docs/architecture.md

## Build & Runtime Standards (Enforced)
```bash
# Build
python3 -m compileall -q src
# Test
python3 -m pytest -q
# Lint
python3 -m black --check src tests && python3 -m pyflakes src tests
# Run
./run.sh            # ./run.sh --test-scanner for no hardware
```

## Project Conventions
- File prefixes as in the framework: `config_*`, `manager_*`, `page_*`, `component_*`, `backend_*`, `util_*`.
- UI never talks to a scanner directly: pages → `modules/manager_scan.py` → `backends/backend_*.py`.
- Scanner-specific knowledge lives in `config/config_scan.py` (mode names, preferred backends), not in code paths.
- Anything blocking (listing, options, scanning) runs off the GTK thread; results return via `GLib.idle_add`.
- Colours only come from `config/config_themes.py` → generated CSS; no hard-coded colours in widgets.
- New pages: subclass `pages/page_base.BasePage`, add one line to `ui/content_area.PAGES` and `ui/sidebar.NAV_ITEMS`.
- Never show or log scanner serial numbers (`parser_sane.redact`).
- Optional functionality goes in `src/features/feature_<name>.py` (a `Feature(BaseFeature)`); the core only calls `FeatureRegistry` hooks. A feature must never be imported by the core or by another feature (shared helpers go in `utils/`).
- Every `scanimage` call goes through `backend_sane.DEVICE_LOCK` (a scanner is single-user).
- New connection methods: implement `ScannerBackend`, give it a method code in `manager_connection.method_code`, add it to the engine in `main.py`.
- Dependencies: distro packages only; add new ones to `app.json` → `offline`, then `../bin/make-offline-bundle linscanner && ../bin/test-offline linscanner`.

## Memory & Workflow (universal-instruction-set)
- Plan first for changes touching 3+ files; wait for approval.
- Every change: an entry in `changelog.md` **and** `changelog.json` (append-only, ISO time, < 120 chars), before committing.
- Features and fixes: a change manifest in `.claude/memory/changes/YYYY-MM-DD_*.md` (root cause for fixes).
- Decisions: `.claude/memory/decisions.md`. Open items: `.claude/memory/pending.md`. Session logs: `.claude/memory/sessions/`.
- Build → Lint → Test must pass before a commit; report failures, don't auto-fix silently.
- Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`). Semantic versioning in `VERSION`.

## References
- @docs/architecture.md
- @.claude/memory/decisions.md
- @.claude/memory/MEMORY.md
