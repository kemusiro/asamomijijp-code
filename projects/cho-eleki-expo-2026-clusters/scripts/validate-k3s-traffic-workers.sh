#!/usr/bin/env bash

set -Eeuo pipefail

readonly NAMESPACE="traffic-demo"
readonly EXPECTED_WORKERS="${EXPECTED_WORKERS:-12}"

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$*"
}

expect_equal() {
  local actual=$1
  local expected=$2
  local description=$3
  [[ ${actual} == "${expected}" ]] \
    || die "${description}: expected=${expected}, actual=${actual:-<empty>}"
  pass "${description}: ${actual}"
}

[[ ${EUID} -eq 0 ]] || die "root privileges are required"
[[ ${EXPECTED_WORKERS} =~ ^[0-9]+$ && ${EXPECTED_WORKERS} -ge 1 ]] \
  || die "EXPECTED_WORKERS must be a positive integer"
command -v k3s >/dev/null || die "k3s is not installed"
systemctl is-active --quiet k3s || die "k3s server is not active"
kubectl=(k3s kubectl)

expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get pvc traffic-results -o jsonpath='{.status.phase}')" \
  "Bound" \
  "results PVC phase"
expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get pvc traffic-results -o jsonpath='{.spec.accessModes[0]}')" \
  "ReadWriteMany" \
  "results PVC access mode"
expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get deployment traffic-coordinator -o jsonpath='{.status.availableReplicas}')" \
  "1" \
  "coordinator available replicas"
expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get service traffic-dashboard -o jsonpath='{.spec.ports[0].nodePort}')" \
  "30095" \
  "dashboard NodePort"

for field in desiredNumberScheduled currentNumberScheduled numberReady numberAvailable; do
  expect_equal \
    "$("${kubectl[@]}" -n "${NAMESPACE}" get daemonset traffic-worker -o "jsonpath={.status.${field}}")" \
    "${EXPECTED_WORKERS}" \
    "worker DaemonSet ${field}"
done

mapfile -t pods < <(
  "${kubectl[@]}" -n "${NAMESPACE}" get pod -l app.kubernetes.io/name=traffic-worker \
    --sort-by=.spec.nodeName \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{" "}{.status.podIP}{"\n"}{end}'
)
expect_equal "${#pods[@]}" "${EXPECTED_WORKERS}" "worker Pod count"

declare -A nodes=()
for row in "${pods[@]}"; do
  read -r pod node ip <<<"${row}"
  [[ -n ${pod} && -n ${node} && -n ${ip} ]] || die "invalid worker Pod row: ${row}"
  [[ -z ${nodes[${node}]:-} ]] || die "multiple worker Pods are on ${node}"
  nodes[${node}]=1
  health=$("${kubectl[@]}" -n "${NAMESPACE}" exec "${pod}" -- \
    node -e 'fetch("http://127.0.0.1:8787/health").then(r=>r.json()).then(x=>{if(x.status!=="ok"||x.workerId!==process.argv[1])process.exit(1);console.log(x.version)})' "${node}")
  [[ -n ${health} ]] || die "health check failed: ${node}"
done
expect_equal "${#nodes[@]}" "${EXPECTED_WORKERS}" "unique worker nodes"
pass "all worker health endpoints report their node names"

coordinator=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l app.kubernetes.io/name=traffic-coordinator \
  -o jsonpath='{.items[0].metadata.name}')
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- node --input-type=module -e '
  const expected = Number(process.argv[1]);
  const response = await fetch("http://127.0.0.1:8080/api/dashboard");
  if (!response.ok) process.exit(1);
  const data = await response.json();
  if (data.expectedWorkers !== expected || data.readyWorkers !== expected || data.workers.length !== expected) process.exit(1);
' "${EXPECTED_WORKERS}" || die "dashboard API validation failed"
pass "dashboard API reports ${EXPECTED_WORKERS} ready workers"
mount_line=$("${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- \
  sh -c 'grep " /results " /proc/mounts')
[[ ${mount_line} == *"nfs4"* && ${mount_line} == *"vers=4.2"* ]] \
  || die "results volume is not mounted with NFSv4.2: ${mount_line}"
pass "coordinator results volume uses NFSv4.2"
pass "K3s traffic worker validation completed"
