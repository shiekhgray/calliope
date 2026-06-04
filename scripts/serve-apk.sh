#!/usr/bin/env bash
#
# serve-apk.sh — temporarily serve an APK over the LAN so you can install it
# on a phone by browsing to it. Phone must be on the same WiFi as this host.
#
# Usage:
#   ./scripts/serve-apk.sh [/path/to/app.apk] [port]
#
# Defaults: APK = ~/Downloads/app-debug.apk, port = 8090
#   (8000 is the API, 5173 is the web dev server — don't reuse those)
#
# Why a temp dir: python's http.server exposes the WHOLE directory it runs in.
# We copy just the APK into /tmp/apk-serve so we never expose all of Downloads.
# Ctrl-C stops the server and cleans up the temp dir automatically.

set -euo pipefail

APK="${1:-$HOME/Downloads/app-debug.apk}"
PORT="${2:-8090}"
SERVE_DIR="/tmp/apk-serve"

if [[ ! -f "$APK" ]]; then
    echo "APK not found: $APK" >&2
    exit 1
fi

# LAN IP (the 192.168.x.x address phones can reach — not docker/libvirt bridges)
LAN_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"

cleanup() { rm -rf "$SERVE_DIR"; echo; echo "Stopped, temp dir removed."; }
trap cleanup EXIT

mkdir -p "$SERVE_DIR"
cp "$APK" "$SERVE_DIR/calliope.apk"

echo "On your phone (same WiFi), open a browser and go to:"
echo
echo "    http://${LAN_IP}:${PORT}/calliope.apk"
echo
echo "Tap the downloaded file to install (allow 'unknown sources' if prompted)."
echo "Press Ctrl-C here to stop and clean up."
echo

cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 0.0.0.0
