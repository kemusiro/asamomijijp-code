#!/usr/bin/env bash
# 既存の球体展示サービスへ専用drop-inを追加する。ブラウザ・Wi-Fi設定には触れない。
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
vehicle_api=''
output_dir=/var/lib/pico-raytracing
backup_dir=''
workers=16
vehicle_preset=smooth
sphere_preset=detailed
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir) repo_dir=$2; shift 2;;
    --vehicle-api) vehicle_api=$2; shift 2;;
    --output-dir) output_dir=$2; shift 2;;
    --backup-dir) backup_dir=$2; shift 2;;
    --workers) workers=$2; shift 2;;
    --vehicle-preset) vehicle_preset=$2; shift 2;;
    --sphere-preset) sphere_preset=$2; shift 2;;
    -h|--help) echo 'sudo install-pico-scene-cycle.sh --repo-dir PATH --vehicle-api http://PI4:30096/api/state --backup-dir PATH [--output-dir PATH] [--workers 16] [--vehicle-preset smooth] [--sphere-preset detailed]'; exit 0;;
    *) echo "不明な引数: $1" >&2;exit 2;;
  esac
done
[[ $vehicle_preset == preview || $vehicle_preset == exhibition || $vehicle_preset == smooth ]] || { echo 'vehicle-presetはpreview/exhibition/smoothです' >&2;exit 2; }
[[ $sphere_preset == exhibition || $sphere_preset == detailed ]] || { echo 'sphere-presetはexhibition/detailedです' >&2;exit 2; }
[[ $EUID -eq 0 ]] || { echo 'systemd更新にはsudoが必要です' >&2;exit 1; }
for path in "$repo_dir" "$output_dir" "$backup_dir"; do
  [[ $path == /* && $path =~ ^[a-zA-Z0-9_./-]+$ ]] || { echo '絶対パスを指定してください。空白・制御文字は使えません' >&2;exit 2; }
done
[[ $workers =~ ^[0-9]+$ ]] && ((workers>=1&&workers<=16)) || { echo 'workersは1〜16です' >&2;exit 2; }
python3 - "$repo_dir" "$vehicle_api" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]);sys.path.insert(0,str(r/'projects/raspberry-pi-pico-cluster/raytracing/host'))
from live_vehicle import validate_api_url
validate_api_url(sys.argv[2])
for f in ['scripts/run-pico-raytracing-exhibition.py','scripts/serve-pico-raytracing-display.py','projects/raspberry-pi-pico-cluster/raytracing/pico/scene_raytracer.py','projects/raspberry-pi-pico-cluster/raytracing/network/scene_manager.py']:
 if not (r/f).is_file():raise SystemExit('必要なソースがありません: '+f)
PY
for unit in pico-raytracing-runner pico-raytracing-display; do
  [[ $(systemctl show "$unit.service" --property=LoadState --value) == loaded ]] || { echo "既存の$unit.serviceを導入してください" >&2;exit 2; }
done
mkdir -p -- "$backup_dir"
for unit in pico-raytracing-runner pico-raytracing-display; do
  if [[ ! -f $backup_dir/$unit.service.txt ]]; then systemctl cat "$unit.service" > "$backup_dir/$unit.service.txt"; fi
done
run_user=$(systemctl show pico-raytracing-runner.service --property=User --value)
[[ -n $run_user && $run_user != root ]] || { echo '既存runnerの実行ユーザを確認してください' >&2;exit 2; }
systemctl stop pico-raytracing-runner.service
install -d -o "$run_user" -g "$(id -gn "$run_user")" -m 0755 "$output_dir"
for unit in pico-raytracing-runner pico-raytracing-display; do
  install -d -m 0755 "/etc/systemd/system/$unit.service.d"
  if [[ -f /etc/systemd/system/$unit.service.d/scene-cycle.conf && ! -f $backup_dir/$unit.scene-cycle.conf ]]; then
    cp -a "/etc/systemd/system/$unit.service.d/scene-cycle.conf" "$backup_dir/$unit.scene-cycle.conf"
  fi
done
cat > /etc/systemd/system/pico-raytracing-runner.service.d/scene-cycle.conf.tmp <<EOF
[Service]
WorkingDirectory=$repo_dir
ExecStart=
ExecStart=/usr/bin/python3 -u -B $repo_dir/scripts/run-pico-raytracing-exhibition.py --scene-mode alternating --vehicle-api $vehicle_api --vehicle-preset $vehicle_preset --sphere-preset $sphere_preset --workers $workers --worker-timeout 7 --manager-timeout 120 --minimum-display-seconds 4 --cycles 0 --output-dir $output_dir --display-state $output_dir/display-state.json --live-image $output_dir/live-progress.png
ReadWritePaths=
ReadWritePaths=$output_dir
EOF
cat > /etc/systemd/system/pico-raytracing-display.service.d/scene-cycle.conf.tmp <<EOF
[Service]
WorkingDirectory=$repo_dir
ExecStart=
ExecStart=/usr/bin/python3 -B $repo_dir/scripts/serve-pico-raytracing-display.py --host 127.0.0.1 --port 8080 --output-dir $output_dir
ReadWritePaths=
ReadWritePaths=$output_dir
EOF
for unit in pico-raytracing-runner pico-raytracing-display; do mv "/etc/systemd/system/$unit.service.d/scene-cycle.conf.tmp" "/etc/systemd/system/$unit.service.d/scene-cycle.conf"; done
systemctl daemon-reload
systemctl restart pico-raytracing-display.service
systemctl restart pico-raytracing-runner.service
echo '交互展示を開始しました。全Picoにalternating-raytracer-v2が必要です。'
echo 'Pico側を旧コアへ復旧する際はrunnerを止め、今回のscene-cycle.confだけを退避してdaemon-reloadしてください。'
