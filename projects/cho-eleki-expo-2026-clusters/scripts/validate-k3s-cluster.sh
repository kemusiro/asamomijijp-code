#!/usr/bin/env bash

set -Eeuo pipefail

readonly EXPECTED_VERSION="v1.36.3+k3s1"
readonly SMOKE_NAMESPACE="cluster-smoke"
readonly SMOKE_LABEL="app.kubernetes.io/name=node-smoke"
readonly COMPUTE_LABEL="exhibition.asamomiji.jp/role=compute"
readonly EXPECTED_COMPUTE_NODES=12

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || die "run this script with sudo on mng"
command -v k3s >/dev/null || die "k3s is not installed"

expected_nodes=(mng)
for number in $(seq 10 21); do
  expected_nodes+=("node${number}")
done

for node in "${expected_nodes[@]}"; do
  ready=$(k3s kubectl get node "${node}" \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
  [[ ${ready} == True ]] || die "${node} is not Ready"

  version=$(k3s kubectl get node "${node}" -o jsonpath='{.status.nodeInfo.kubeletVersion}')
  [[ ${version} == "${EXPECTED_VERSION}" ]] \
    || die "${node} uses ${version}, expected ${EXPECTED_VERSION}"
done

control_role=$(k3s kubectl get node mng \
  -o jsonpath='{.metadata.labels.exhibition\.asamomiji\.jp/role}')
[[ ${control_role} == control-plane ]] || die "mng control-plane label is missing"

taints=$(k3s kubectl get node mng -o jsonpath='{range .spec.taints[*]}{.key}={.value}:{.effect}{"\n"}{end}')
grep -Fqx 'node-role.kubernetes.io/control-plane=true:NoSchedule' <<<"${taints}" \
  || die "mng NoSchedule taint is missing"

compute_nodes=$(k3s kubectl get nodes -l "${COMPUTE_LABEL}" --no-headers | wc -l | tr -d ' ')
[[ ${compute_nodes} -eq ${EXPECTED_COMPUTE_NODES} ]] \
  || die "found ${compute_nodes} compute nodes, expected ${EXPECTED_COMPUTE_NODES}"

k3s kubectl wait --for=condition=Available \
  deployment/coredns deployment/local-path-provisioner deployment/metrics-server \
  -n kube-system --timeout=60s >/dev/null
k3s kubectl rollout status daemonset/node-smoke -n "${SMOKE_NAMESPACE}" --timeout=60s >/dev/null

ready_smoke_pods=$(k3s kubectl get pods -n "${SMOKE_NAMESPACE}" -l "${SMOKE_LABEL}" \
  --field-selector=status.phase=Running --no-headers | wc -l | tr -d ' ')
[[ ${ready_smoke_pods} -eq ${EXPECTED_COMPUTE_NODES} ]] \
  || die "found ${ready_smoke_pods} running smoke Pods, expected ${EXPECTED_COMPUTE_NODES}"

unique_nodes=$(k3s kubectl get pods -n "${SMOKE_NAMESPACE}" -l "${SMOKE_LABEL}" \
  -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | sort -u | wc -l | tr -d ' ')
[[ ${unique_nodes} -eq ${EXPECTED_COMPUTE_NODES} ]] \
  || die "smoke Pods use ${unique_nodes} unique nodes, expected ${EXPECTED_COMPUTE_NODES}"

source_pod=$(k3s kubectl get pod -n "${SMOKE_NAMESPACE}" \
  --field-selector=spec.nodeName=node10 -l "${SMOKE_LABEL}" \
  -o jsonpath='{.items[0].metadata.name}')
[[ -n ${source_pod} ]] || die "node10 smoke Pod was not found"

k3s kubectl exec -n "${SMOKE_NAMESPACE}" "${source_pod}" -- \
  nslookup kubernetes.default.svc.cluster.local >/dev/null

while read -r node pod_ip; do
  reply=$(k3s kubectl exec -n "${SMOKE_NAMESPACE}" "${source_pod}" -- \
    wget -T 5 -qO- "http://${pod_ip}:8080/")
  [[ ${reply} == node-smoke-* ]] || die "unexpected response from ${node} (${pod_ip}): ${reply}"
done < <(k3s kubectl get pods -n "${SMOKE_NAMESPACE}" -l "${SMOKE_LABEL}" \
  -o custom-columns=NODE:.spec.nodeName,IP:.status.podIP --no-headers | sort -V)

printf 'PASS: %s nodes are Ready, %s compute Pods are distributed one per node, and DNS/Pod communication works.\n' \
  "${#expected_nodes[@]}" "${EXPECTED_COMPUTE_NODES}"
