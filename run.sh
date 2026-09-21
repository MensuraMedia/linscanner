#!/bin/bash
# run.sh - launch linscanner (system Python; dependencies are distro packages)
# Usage: ./run.sh [--test-scanner] [--page preview] [--version]
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
exec python3 src/main.py "$@"
