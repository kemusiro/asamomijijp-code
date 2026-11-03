#!/usr/bin/env bash

set -Eeuo pipefail

readonly NAMESPACE="nfs-csi-smoke"
readonly PVC_NAME="shared-data"
readonly WRITER_SELECTOR="app.kubernetes.io/name=rwx-writer"
readonly EXPECTED_COMPUTE_NODES="${EXPECTED_COMPUTE_NODES:-12}"

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
command -v k3s >/dev/null || die "k3s is not installed"
systemctl is-active --quiet k3s || die "k3s server is not active"

kubectl=(k3s kubectl)

"${kubectl[@]}" get csidriver nfs.csi.k8s.io >/dev/null \
  || die "CSIDriver nfs.csi.k8s.io is missing"
pass "CSIDriver nfs.csi.k8s.io exists"

expect_equal \
  "$("${kubectl[@]}" get storageclass nfs-rwx-retain -o jsonpath='{.provisioner}')" \
  "nfs.csi.k8s.io" \
  "StorageClass provisioner"
expect_equal \
  "$("${kubectl[@]}" get storageclass nfs-rwx-retain -o jsonpath='{.reclaimPolicy}')" \
  "Retain" \
  "StorageClass reclaim policy"
expect_equal \
  "$("${kubectl[@]}" get storageclass nfs-rwx-retain -o jsonpath='{.parameters.server}')" \
  "192.168.2.2" \
  "StorageClass NFS server"
expect_equal \
  "$("${kubectl[@]}" get storageclass nfs-rwx-retain -o jsonpath='{.parameters.share}')" \
  "/srv/storage-nfs/cluster/rwx" \
  "StorageClass NFS export"

expect_equal \
  "$("${kubectl[@]}" -n kube-system get deployment csi-nfs-controller -o jsonpath='{.status.availableReplicas}')" \
  "1" \
  "CSI controller available replicas"

for field in desiredNumberScheduled currentNumberScheduled numberReady numberAvailable; do
  expect_equal \
    "$("${kubectl[@]}" -n kube-system get daemonset csi-nfs-node -o "jsonpath={.status.${field}}")" \
    "${EXPECTED_COMPUTE_NODES}" \
    "CSI node DaemonSet ${field}"
done

expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get pvc "${PVC_NAME}" -o jsonpath='{.status.phase}')" \
  "Bound" \
  "RWX PVC phase"
expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" get pvc "${PVC_NAME}" -o jsonpath='{.spec.accessModes[0]}')" \
  "ReadWriteMany" \
  "RWX PVC access mode"

pv_name=$("${kubectl[@]}" -n "${NAMESPACE}" get pvc "${PVC_NAME}" \
  -o jsonpath='{.spec.volumeName}')
[[ -n ${pv_name} ]] || die "PVC has no bound PV"
expect_equal \
  "$("${kubectl[@]}" get pv "${pv_name}" -o jsonpath='{.spec.csi.driver}')" \
  "nfs.csi.k8s.io" \
  "PV CSI driver"
expect_equal \
  "$("${kubectl[@]}" get pv "${pv_name}" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')" \
  "Retain" \
  "PV reclaim policy"

for field in desiredNumberScheduled currentNumberScheduled numberReady numberAvailable; do
  expect_equal \
    "$("${kubectl[@]}" -n "${NAMESPACE}" get daemonset rwx-writer -o "jsonpath={.status.${field}}")" \
    "${EXPECTED_COMPUTE_NODES}" \
    "RWX writer DaemonSet ${field}"
done

mapfile -t writer_nodes < <(
  "${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${WRITER_SELECTOR}" \
    -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | sort -u
)
expect_equal "${#writer_nodes[@]}" "${EXPECTED_COMPUTE_NODES}" "unique writer nodes"

first_node=${writer_nodes[0]}
last_node=${writer_nodes[$((${#writer_nodes[@]} - 1))]}
first_pod=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${WRITER_SELECTOR}" \
  --field-selector "spec.nodeName=${first_node}" -o jsonpath='{.items[0].metadata.name}')
last_pod=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${WRITER_SELECTOR}" \
  --field-selector "spec.nodeName=${last_node}" -o jsonpath='{.items[0].metadata.name}')

node_file_count=$("${kubectl[@]}" -n "${NAMESPACE}" exec "${first_pod}" -- \
  sh -c 'find /data/nodes -maxdepth 1 -type f -name "node*.txt" | wc -l')
node_file_count=${node_file_count//[[:space:]]/}
expect_equal "${node_file_count}" "${EXPECTED_COMPUTE_NODES}" "shared per-node files"

marker="nfs-csi-validation-$(date -u +%Y%m%dT%H%M%SZ)-$$"
marker_path="/data/.${marker}"
cleanup_marker() {
  "${kubectl[@]}" -n "${NAMESPACE}" exec "${first_pod}" -- \
    rm -f "${marker_path}" >/dev/null 2>&1 || true
}
trap cleanup_marker EXIT

"${kubectl[@]}" -n "${NAMESPACE}" exec "${first_pod}" -- \
  sh -c 'printf "%s\n" "$1" > "$2"' sh "${marker}" "${marker_path}"
expect_equal \
  "$("${kubectl[@]}" -n "${NAMESPACE}" exec "${last_pod}" -- cat "${marker_path}")" \
  "${marker}" \
  "cross-node RWX read/write (${first_node} -> ${last_node})"
cleanup_marker
trap - EXIT

pass "NFS CSI RWX validation completed"
