#!/usr/bin/env bash

set -Eeuo pipefail

SSH_USER=${SSH_USER:-ubuntu}
MNG_HOST=${MNG_HOST:-192.168.2.1}
STORAGE_HOST=${STORAGE_HOST:-192.168.2.2}
TIMEOUT_SECONDS=${TIMEOUT_SECONDS:-300}
SSH_KNOWN_HOSTS=${SSH_KNOWN_HOSTS:-}
REQUIRE_TRAFFIC_WORKERS=0

usage() {
  cat <<'EOF'
Usage: scripts/validate-pi4-cluster-recovery.sh [options]

Wait for the Pi 4 cluster after power-on and validate network boot, iSCSI,
K3s, NFS CSI, power state, and boot errors.

Options:
  --known-hosts PATH       Use PATH and require matching SSH host keys
  --timeout SECONDS        Recovery timeout (default: 300)
  --require-traffic-workers
                           Require 12 traffic-worker Pods and one coordinator
  -h, --help               Show this help

Environment overrides:
  SSH_USER, MNG_HOST, STORAGE_HOST, TIMEOUT_SECONDS, SSH_KNOWN_HOSTS
EOF
}

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'PASS: %s\n' "$*"
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --known-hosts)
      [[ $# -ge 2 ]] || die "--known-hosts requires PATH"
      SSH_KNOWN_HOSTS=$2
      shift 2
      ;;
    --timeout)
      [[ $# -ge 2 ]] || die "--timeout requires SECONDS"
      TIMEOUT_SECONDS=$2
      shift 2
      ;;
    --require-traffic-workers)
      REQUIRE_TRAFFIC_WORKERS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown option: $1"
      ;;
  esac
done

[[ ${TIMEOUT_SECONDS} =~ ^[0-9]+$ && ${TIMEOUT_SECONDS} -ge 30 ]] \
  || die "timeout must be an integer of at least 30 seconds"
command -v ssh >/dev/null || die "ssh is not installed"

ssh_options=(-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes)
if [[ -n ${SSH_KNOWN_HOSTS} ]]; then
  [[ -f ${SSH_KNOWN_HOSTS} ]] || die "known-hosts file not found: ${SSH_KNOWN_HOSTS}"
  ssh_options+=(-o "UserKnownHostsFile=${SSH_KNOWN_HOSTS}")
fi

remote() {
  local host=$1
  shift
  ssh "${ssh_options[@]}" "${SSH_USER}@${host}" "$@"
}

compute_hosts=()
for suffix in {10..21}; do
  compute_hosts+=("192.168.2.${suffix}")
done

all_hosts=("${MNG_HOST}" "${STORAGE_HOST}" "${compute_hosts[@]}")
deadline=$((SECONDS + TIMEOUT_SECONDS))

printf 'Waiting up to %ss for SSH on 14 Pi 4 nodes...\n' "${TIMEOUT_SECONDS}"
while :; do
  unavailable=()
  for host in "${all_hosts[@]}"; do
    remote "${host}" true >/dev/null 2>&1 || unavailable+=("${host}")
  done
  if [[ ${#unavailable[@]} -eq 0 ]]; then
    break
  fi
  ((SECONDS < deadline)) \
    || die "SSH timeout; unavailable: ${unavailable[*]}"
  printf 'WAIT: SSH unavailable: %s\n' "${unavailable[*]}"
  sleep 5
done
pass "SSH is available on management, storage, and 12 compute nodes"

printf 'Waiting for all 13 K3s nodes to become Ready...\n'
while :; do
  node_rows=$(remote "${MNG_HOST}" 'sudo -n k3s kubectl get nodes --no-headers' 2>/dev/null || true)
  node_count=$(printf '%s\n' "${node_rows}" | awk 'NF {n++} END {print n+0}')
  ready_count=$(printf '%s\n' "${node_rows}" | awk '$2 == "Ready" {n++} END {print n+0}')
  if [[ ${node_count} -eq 13 && ${ready_count} -eq 13 ]]; then
    break
  fi
  ((SECONDS < deadline)) \
    || die "K3s timeout; nodes=${node_count}, Ready=${ready_count}"
  printf 'WAIT: K3s nodes=%s, Ready=%s\n' "${node_count}" "${ready_count}"
  sleep 5
done
pass "13 K3s nodes are Ready"

for suffix in {10..21}; do
  node="node${suffix}"
  host="192.168.2.${suffix}"
  actual_node=$(remote "${host}" hostname)
  [[ ${actual_node} == "${node}" ]] \
    || die "${host} reports hostname ${actual_node}, expected ${node}"

  root=$(remote "${host}" 'findmnt -no SOURCE,FSTYPE /')
  [[ ${root} == '/dev/sda ext4' ]] \
    || die "${node} root is ${root}, expected /dev/sda ext4"

  transport=$(remote "${host}" "lsblk -dn -o NAME,TRAN | awk '\$1 == \"sda\" {print \$2}'")
  [[ ${transport} == iscsi ]] \
    || die "${node} /dev/sda transport is ${transport:-<empty>}, expected iscsi"

  if remote "${host}" 'lsblk -dn -o NAME | grep -q "^mmcblk"'; then
    die "${node} still has a detected microSD device"
  fi

  boot_order=$(remote "${host}" 'sudo -n vcgencmd bootloader_config | sed -n "s/^BOOT_ORDER=//p"')
  [[ ${boot_order} == 0xf12 ]] \
    || die "${node} BOOT_ORDER is ${boot_order:-<empty>}, expected 0xf12"

  remote "${host}" 'systemctl is-active --quiet k3s-agent' \
    || die "${node} k3s-agent is not active"
  failed_services=$(remote "${host}" 'systemctl --failed --no-legend | wc -l | tr -d " "')
  [[ ${failed_services} == 0 ]] \
    || die "${node} has ${failed_services} failed services"
  throttled=$(remote "${host}" 'sudo -n vcgencmd get_throttled')
  [[ ${throttled} == throttled=0x0 ]] \
    || die "${node} power status is ${throttled}"

  boot_errors=$(remote "${host}" \
    'sudo -n journalctl -k -b --no-pager | grep -Ei "under-voltage|voltage normalised|mmc.*(error|timeout)|USB disconnect|usb.*reset|I/O error|EXT4-fs error" || true')
  [[ -z ${boot_errors} ]] \
    || die "${node} has boot errors: ${boot_errors}"

  temperature=$(remote "${host}" 'sudo -n vcgencmd measure_temp')
  pass "${node}: iSCSI root, no microSD, ${throttled}, ${temperature}"
done

for host in "${MNG_HOST}" "${STORAGE_HOST}"; do
  failed_services=$(remote "${host}" 'systemctl --failed --no-legend | wc -l | tr -d " "')
  [[ ${failed_services} == 0 ]] \
    || die "${host} has ${failed_services} failed services"
  throttled=$(remote "${host}" 'sudo -n vcgencmd get_throttled')
  [[ ${throttled} == throttled=0x0 ]] \
    || die "${host} power status is ${throttled}"
  temperature=$(remote "${host}" 'sudo -n vcgencmd measure_temp')
  pass "${host}: no failed services, ${throttled}, ${temperature}"
done

iscsi_sessions=$(remote "${STORAGE_HOST}" \
  "sudo -n targetcli sessions list | awk '/^alias:/ {n++} END {print n+0}'")
[[ ${iscsi_sessions} == 12 ]] \
  || die "storage has ${iscsi_sessions} iSCSI sessions, expected 12"
pass "storage has 12 iSCSI sessions"

check_daemonset() {
  local namespace=$1
  local name=$2
  local expected=$3
  local ready
  ready=$(remote "${MNG_HOST}" \
    "sudo -n k3s kubectl -n ${namespace} get daemonset ${name} -o jsonpath='{.status.numberReady}'")
  [[ ${ready} == "${expected}" ]] \
    || die "${namespace}/${name} has ${ready:-0} Ready Pods, expected ${expected}"
  pass "${namespace}/${name} has ${ready} Ready Pods"
}

check_daemonset cluster-smoke node-smoke 12
check_daemonset kube-system csi-nfs-node 12
check_daemonset nfs-csi-smoke rwx-writer 12

if [[ ${REQUIRE_TRAFFIC_WORKERS} -eq 1 ]]; then
  check_daemonset traffic-demo traffic-worker 12
  coordinator=$(remote "${MNG_HOST}" \
    "sudo -n k3s kubectl -n traffic-demo get deployment traffic-coordinator -o jsonpath='{.status.availableReplicas}'")
  [[ ${coordinator} == 1 ]] \
    || die "traffic coordinator has ${coordinator:-0} available replicas, expected 1"
  pass "traffic coordinator has one available replica"
fi

pass "Pi 4 cluster recovery validation completed"
