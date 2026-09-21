---
date: 2026-09-21
session: afternoon
duration: ~1h
---

## What Was Done
- Diagnosed the Epson Scan 2 Flatpak: SIGABRT in libes2command on every scan (3 core dumps). The native .deb 6.7.80.0 scanned without crashing in a container.
- Installed native Epson Scan 2 on the host; added psmisc (killall) to its offline deps.
- Built linscanner 0.1.0 (plan approved by the user; colour scheme ui-kit-black-yellow-gray).

## Key Decisions
See decisions.md (SANE CLI backend, epsonds preferred, grayscale B&W, semver, black+pyflakes).

## Issues Encountered
- After each Epson Scan 2 crash the scanner stopped answering (epsonds: "write failed: Operation timed out") until it was power-cycled.
- Installing native Epson Scan 2 adds an `epsonscan2` SANE backend, so every SANE app sees the ES-400 II twice.

## What's Next
See pending.md: real-hardware GUI test, orientation, auto-crop.

## Files Changed
linscanner/ (new), bin/make-offline-bundle, offline pool + manifests, repo docs.

## Theme history (added 2026-09-21 16:30)
- 15:25: Black Yellow Gray (from universal-instruction-set ui-kit-black-yellow-gray.jpg) was the first default.
- 16:12: switched to Nord at the user's request.
- 16:30: **user correction**: default is the framework's Default Blue; Black Yellow Gray removed.
- Earlier commits (827defa, 4632aa3) and the append-only changelog entries still mention those defaults. That's history, not current state.
