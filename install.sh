#!/usr/bin/env bash
# linscanner installer for Debian-based systems (Debian, Ubuntu, Linux Mint).
#
#   - installs missing dependencies (GTK 3 Python bindings, Pillow, SANE, sane-airscan)
#     from the repo's offline pool first, network otherwise (asks for sudo only then)
#   - adds "linscanner" to the desktop menu (~/.local/share/applications)
#   - verifies the app starts and SANE can list scanners
# Safe to re-run: it only changes what is missing or wrong.
#
# Run as your NORMAL user (the menu entry is per-user).
# Usage: bash install.sh [--uninstall]

set -u
export LC_ALL=C

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
REPO_ROOT="$(cd "$APP_DIR/.." && pwd)"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/linscanner.desktop"
PACKAGES=(python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil python3-numpy sane-utils libsane1 sane-airscan tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd ghostscript fontconfig fonts-dejavu-core fonts-liberation fonts-noto-core fonts-urw-base35 fonts-ubuntu)

if [[ $EUID -eq 0 ]]; then
    echo "Run this as your normal user (without sudo) - the menu entry is per-user."; exit 1
fi

if [[ -t 1 ]]; then G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; B=$'\e[1m'; N=$'\e[0m'; else G= Y= R= B= N=; fi
SUMMARY=(); FAILED=0
step()  { echo; echo "${B}==> $*${N}"; }
ok()    { echo "    ${G}OK${N}    $*"; SUMMARY+=("${G}OK${N}    $*"); }
fixed() { echo "    ${Y}FIXED${N} $*"; SUMMARY+=("${Y}FIXED${N} $*"); }
fail()  { echo "    ${R}FAIL${N}  $*"; SUMMARY+=("${R}FAIL${N}  $*"); FAILED=1; }
info()  { echo "          $*"; }
report() {
    echo; echo "${B}================ linscanner install summary ================${N}"
    printf '  %s\n' "${SUMMARY[@]}"
    [[ $FAILED -eq 0 ]] && echo "  ${G}${B}Result: linscanner ready - find it in the menu or run $APP_DIR/run.sh${N}" \
                        || echo "  ${R}${B}Result: setup incomplete - see FAIL lines above${N}"
    exit $FAILED
}

if [[ "${1:-}" == "--uninstall" ]]; then
    step "Uninstalling"
    rm -f "$DESKTOP" && ok "Removed menu entry (dependencies and settings left in place)"
    report
fi

step "Checking dependencies"
MISSING=()
for p in "${PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || MISSING+=("$p")
done
if [[ ${#MISSING[@]} -eq 0 ]]; then
    ok "Dependencies present: ${PACKAGES[*]}"
elif sudo "$REPO_ROOT/bin/offline-install" "${MISSING[@]}" >/dev/null 2>&1; then
    fixed "Installed from offline pool: ${MISSING[*]}"
elif sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${MISSING[@]}" >/dev/null; then
    fixed "Installed from network: ${MISSING[*]}"
else
    fail "Could not install: ${MISSING[*]}"; report
fi

step "Desktop menu entry"
mkdir -p "$(dirname "$DESKTOP")"
ENTRY="[Desktop Entry]
Type=Application
Name=linscanner
GenericName=Document Scanner
Comment=Scan documents in color or black & white and save as PDF or images
Exec=$APP_DIR/run.sh
Icon=$APP_DIR/resources/images/logo.png
Terminal=false
Categories=Graphics;Scanning;
Keywords=scan;scanner;pdf;document;sane;"
if [[ -f "$DESKTOP" ]] && [[ "$(cat "$DESKTOP")" == "$ENTRY" ]]; then
    ok "Menu entry present ($DESKTOP)"
else
    printf '%s\n' "$ENTRY" > "$DESKTOP" && chmod 644 "$DESKTOP"
    command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$DESKTOP")" 2>/dev/null
    fixed "Added menu entry ($DESKTOP)"
fi

step "Verifying"
VER=$("$APP_DIR/run.sh" --version 2>/dev/null)
[[ "$VER" == linscanner* ]] && ok "App starts: $VER" || fail "App did not start: run $APP_DIR/run.sh to see the error"
if python3 -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; import PIL' 2>/dev/null; then
    ok "GTK 3 and Pillow importable"
else
    fail "GTK 3 or Pillow missing from Python"
fi
COUNT=$(timeout 60 scanimage -f '%d%n' 2>/dev/null | grep -vc '^test:')
if [[ "$COUNT" -gt 0 ]]; then ok "SANE sees $COUNT scanner device(s)"
else info "No scanner connected right now - linscanner will find it when plugged in"; ok "SANE available"; fi

report
