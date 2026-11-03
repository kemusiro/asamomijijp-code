#!/usr/bin/env bash
# firstはcoordinator停止のまま適用する。対象ノードラベルは操作前に別途確認する。
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo 'sudoで実行してください' >&2; exit 1; }
[[ $# -eq 1 && ($1 == first || $1 == all || $1 == display) ]] || { echo 'usage: sudo deploy-k3s.sh first|all|display' >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $1 == first ]]; then
  stage=$(mktemp -d)
  trap 'rm -rf -- "$stage"' EXIT
  cp -a -- "$root" "$stage/base"
  python3 - "$root" "$stage/kustomization.yaml" <<'PY'
import json,sys
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps({'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':['base'],'patches':[{'target':{'kind':'Deployment','name':'vehicle-coordinator'},'patch':'- op: replace\n  path: /spec/replicas\n  value: 0'}]}))
PY
else
  stage=$root
fi
apply=(k3s kubectl apply --server-side --field-manager=vehicle-deploy -k "$stage")
if [[ $1 == display ]]; then
  apply+=(--selector='app.kubernetes.io/name!=vehicle-worker')
fi
"${apply[@]}"
if [[ $1 != display ]]; then
  k3s kubectl -n vehicle-evolution rollout status daemonset/vehicle-worker --timeout=180s
fi
if [[ $1 != first ]]; then
  k3s kubectl -n vehicle-evolution rollout status deployment/vehicle-coordinator --timeout=180s
fi
