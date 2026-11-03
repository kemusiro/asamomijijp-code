#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
run_user="${SUDO_USER:-$(id -un)}"
output_dir="/var/lib/pico-raytracing"
display_port="8080"

usage() {
  cat <<'EOF'
usage: sudo scripts/install-pico-raytracing-exhibition.sh [options]
  --repo-dir PATH    Pi 5上のリポジトリ絶対パス
  --run-user USER    展示プロセスとデスクトップを使うユーザ
  --output-dir PATH  PNGとログの保存先
  --display-port N   ローカル表示サーバのポート
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir) repo_dir="$2"; shift 2 ;;
    --run-user) run_user="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --display-port) display_port="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "不明な引数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "systemd設定のためsudoで実行してください。" >&2
  exit 1
fi
if [[ "$repo_dir" != /* || "$output_dir" != /* ]]; then
  echo "--repo-dirと--output-dirには絶対パスを指定してください。" >&2
  exit 2
fi
if [[ "$repo_dir$output_dir$run_user" =~ [[:space:]] ]]; then
  echo "パスとユーザ名に空白または改行は使用できません。" >&2
  exit 2
fi
if ! [[ "$display_port" =~ ^[0-9]+$ ]] || ((display_port < 1 || display_port > 65535)); then
  echo "display portは1..65535で指定してください。" >&2
  exit 2
fi
if ! id "$run_user" >/dev/null 2>&1; then
  echo "ユーザが存在しません: $run_user" >&2
  exit 2
fi
for relative in \
  scripts/run-pico-raytracing-exhibition.py \
  scripts/serve-pico-raytracing-display.py \
  scripts/start-pico-raytracing-kiosk.sh \
  projects/raspberry-pi-pico-cluster/raytracing/display/index.html; do
  if [[ ! -e "$repo_dir/$relative" ]]; then
    echo "必要なファイルがありません: $repo_dir/$relative" >&2
    exit 2
  fi
done

if ! command -v fc-match >/dev/null 2>&1 || [[ "$(fc-match -f '%{family}' 'Noto Sans CJK JP:lang=ja')" != *"Noto Sans CJK JP"* ]]; then
  echo '日本語フォントがありません。sudo apt-get install fonts-noto-cjk fontconfig を実行してください。' >&2
  exit 2
fi

run_group="$(id -gn "$run_user")"
install -d -o "$run_user" -g "$run_group" -m 0755 "$output_dir"

browser_command=""
for candidate in chromium chromium-browser google-chrome; do
  if command -v "$candidate" >/dev/null 2>&1; then
    browser_command="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$browser_command" ]]; then
  echo "Chromiumが見つかりません。先にインストールしてください。" >&2
  exit 2
fi
if [[ "$(basename "$browser_command")" == google-chrome* ]]; then
  policy_dir="/etc/opt/chrome/policies/managed"
else
  policy_dir="/etc/chromium/policies/managed"
fi
install -d -m 0755 "$policy_dir"
cat > "$policy_dir/pico-raytracing-kiosk.json" <<'EOF'
{"TranslateEnabled": false}
EOF
chmod 0644 "$policy_dir/pico-raytracing-kiosk.json"

cat > /etc/systemd/system/pico-raytracing-display.service <<EOF
[Unit]
Description=Pico ray-tracing visitor display server
After=local-fs.target

[Service]
Type=simple
User=$run_user
Group=$run_group
WorkingDirectory=$repo_dir
ExecStart=/usr/bin/python3 -B $repo_dir/scripts/serve-pico-raytracing-display.py --host 127.0.0.1 --port $display_port --output-dir $output_dir
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$output_dir

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/pico-raytracing-runner.service <<EOF
[Unit]
Description=Pico 2 W 16-node ray-tracing exhibition runner
After=network-online.target pico-raytracing-display.service
Wants=network-online.target pico-raytracing-display.service

[Service]
Type=simple
User=$run_user
Group=$run_group
WorkingDirectory=$repo_dir
ExecStart=/usr/bin/python3 -u -B $repo_dir/scripts/run-pico-raytracing-exhibition.py --cycles 0 --output-dir $output_dir --display-state $output_dir/display-state.json --live-image $output_dir/live-progress.png
Restart=on-failure
RestartPreventExitStatus=78
RestartSec=5
TimeoutStopSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$output_dir

[Install]
WantedBy=multi-user.target
EOF

autostart_dir="$(getent passwd "$run_user" | cut -d: -f6)/.config/autostart"
install -d -o "$run_user" -g "$run_group" -m 0755 "$autostart_dir"
cat > "$autostart_dir/pico-raytracing-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Pico Ray-Tracing Exhibition
Exec=$repo_dir/scripts/start-pico-raytracing-kiosk.sh http://127.0.0.1:$display_port/
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
chown "$run_user:$run_group" "$autostart_dir/pico-raytracing-kiosk.desktop"
chmod 0755 \
  "$repo_dir/scripts/start-pico-raytracing-kiosk.sh" \
  "$repo_dir/scripts/run-pico-raytracing-exhibition.py" \
  "$repo_dir/scripts/serve-pico-raytracing-display.py" \
  "$repo_dir/scripts/check-pico-raytracing-exhibition.py"

systemctl daemon-reload
systemctl enable --now pico-raytracing-display.service pico-raytracing-runner.service

echo "インストール完了: http://127.0.0.1:$display_port/"
echo "Chromiumのページ翻訳候補を表示しない管理ポリシーを設定しました。"
echo "画面の自動起動は、$run_user の次回デスクトップログイン時から有効です。"
echo "確認: python3 $repo_dir/scripts/check-pico-raytracing-exhibition.py"
