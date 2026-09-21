---
name: linscanner-memory-index
description: Index of linscanner project memory (newest first)
type: project
---

# Memory Index

## Session Logs
- [2026-09-21 linscanner build](sessions/2026-09-21_1557_linscanner-build.md): v0.1.0 built; Epson Scan 2 Flatpak crash diagnosed

## Changes
- [2026-09-21 linscanner v0.1.0](changes/2026-09-21_linscanner-v0.1.0.md): initial feature set, 27 tests

## Decisions
- [decisions.md](decisions.md): SANE CLI backend, epsonds preferred, grayscale B&W, semver, theme, lint tools

## Project Context
- Part of MensuraMedia/linux-peripherals; must install offline from ../offline/ (Mint 22 / noble-amd64)
- Reference hardware: Epson ES-400 II (usb 04b8:0181) on Linux Mint 22.3

## Feedback & Preferences
- User wants universal and modular (generic drivers), a preview window, Save As, and B&W + Color at 3 quality levels
- Follow universal-instruction-set: plan first and wait for approval; changelog for every change
