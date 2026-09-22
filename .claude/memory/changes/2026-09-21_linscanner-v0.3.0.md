---
date: 2026-09-21
type: feature
files_changed: [linscanner/src/**, linscanner/tests/**, linscanner/docs/**, linscanner/resources/fonts/**, linscanner/resources/icons/**, linscanner/app.json, linscanner/install.sh, linscanner/VERSION]
---

## Change: linscanner 0.3.0
- Round 1 (commit 2a513b0):
  - Preview speed, zoom and 1/2-row thumbnails;
  - Save; Recent; the remembered scanner;
  - Quick Edit Add Text with guides; signatures and fonts;
  - About.
- Round 2 (this commit):
  - Heroicons; Scan Type; paper sizes and Auto-Detect;
  - Apply Signature with the chooser and Create Signature;
  - pointer zones; the Recent table with clear-by-age;
  - compact buttons; About → Compatibility.

## Why
User requests after live testing (2026-09-21). The design was written first:
docs/design/0.3.0-ui-refinements.md.

## Root causes of fixes
- **Empty Sheets row:** `show_all()` on a widget marked no-show-all doesn't
  show its children.
- **Recent icons:** a ListStore column of type `object` can't feed
  CellRendererPixbuf.
- **Test hang:** an idle callback that returned a truthy value repeated
  forever. `_in_thread` now wraps callbacks one-shot.

## Testing
- 103 tests; black and pyflakes clean.
- A scripted UI walkthrough with SANE's test scanner, with screenshots.
- The user's live session on the ES-400 II (round 1) had no errors: scan,
  signature, Save, Recent.
