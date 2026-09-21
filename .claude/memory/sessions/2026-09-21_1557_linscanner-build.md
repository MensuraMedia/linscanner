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
