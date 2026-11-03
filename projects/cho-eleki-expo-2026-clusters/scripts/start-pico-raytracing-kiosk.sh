#!/usr/bin/env bash
set -euo pipefail

url="${PICO_DISPLAY_URL:-http://127.0.0.1:8080/}"
if [[ $# -gt 1 ]]; then
  echo "usage: $0 [display-url]" >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then
  url="$1"
fi

browser=""
for candidate in chromium chromium-browser google-chrome; do
  if command -v "$candidate" >/dev/null 2>&1; then
    browser="$candidate"
    break
  fi
done
if [[ -z "$browser" ]]; then
  echo "Chromiumが見つかりません。chromium-browserをインストールしてください。" >&2
  exit 1
fi

profile_dir="${XDG_CACHE_HOME:-$HOME/.cache}/pico-raytracing-kiosk"
mkdir -p "$profile_dir"

if command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset s noblank || true
  xset -dpms || true
fi

while true; do
  "$browser" \
    --kiosk \
    --app="$url" \
    --user-data-dir="$profile_dir" \
    --password-store=basic \
    --no-first-run \
    --lang=ja \
    --accept-lang=ja \
    --disable-extensions \
    --disable-component-extensions-with-background-pages \
    --disable-translate \
    --disable-features=Translate,TranslateUI \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required || true
  echo "Chromiumが終了しました。5秒後に展示画面を再起動します。" >&2
  sleep 5
done
