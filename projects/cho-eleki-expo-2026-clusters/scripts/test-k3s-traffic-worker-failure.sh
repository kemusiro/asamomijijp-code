#!/usr/bin/env bash

set -Eeuo pipefail

readonly NAMESPACE="traffic-demo"
readonly EXPECTED_WORKERS="${EXPECTED_WORKERS:-12}"
readonly CANDIDATES="${CANDIDATES:-120}"
readonly TIMEOUT_MS="${TIMEOUT_MS:-5000}"
readonly RETRIES="${RETRIES:-1}"
readonly FAULT_DELAY_SECONDS="${FAULT_DELAY_SECONDS:-2}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || die "root privileges are required"
[[ $# -le 1 ]] || die "usage: sudo $0 [VICTIM_NODE]"
readonly VICTIM_NODE="${1:-${VICTIM_NODE:-node10}}"
[[ ${EXPECTED_WORKERS} =~ ^[0-9]+$ && ${EXPECTED_WORKERS} -ge 2 ]] \
  || die "EXPECTED_WORKERS must be an integer of at least 2"
[[ ${CANDIDATES} =~ ^[0-9]+$ && ${CANDIDATES} -ge 1 && ${CANDIDATES} -le 120 ]] \
  || die "CANDIDATES must be an integer from 1 to 120"
[[ ${TIMEOUT_MS} =~ ^[0-9]+$ && ${TIMEOUT_MS} -ge 100 ]] \
  || die "TIMEOUT_MS must be an integer of at least 100"
[[ ${RETRIES} =~ ^[0-9]+$ && ${RETRIES} -ge 1 && ${RETRIES} -le 10 ]] \
  || die "RETRIES must be an integer from 1 to 10"
[[ ${FAULT_DELAY_SECONDS} =~ ^[0-9]+$ && ${FAULT_DELAY_SECONDS} -ge 1 ]] \
  || die "FAULT_DELAY_SECONDS must be a positive integer"
command -v k3s >/dev/null || die "k3s is not installed"
systemctl is-active --quiet k3s || die "k3s server is not active"
kubectl=(k3s kubectl)

mapfile -t worker_rows < <(
  "${kubectl[@]}" -n "${NAMESPACE}" get pod -l app.kubernetes.io/name=traffic-worker \
    --sort-by=.spec.nodeName \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{" "}{.status.podIP}{" "}{.status.containerStatuses[0].ready}{"\n"}{end}'
)
[[ ${#worker_rows[@]} -eq ${EXPECTED_WORKERS} ]] \
  || die "worker Pod count differs: ${#worker_rows[@]}/${EXPECTED_WORKERS}"

worker_urls=()
victim_pod=
for row in "${worker_rows[@]}"; do
  read -r pod node ip ready <<<"${row}"
  [[ -n ${pod} && -n ${node} && -n ${ip} && ${ready} == true ]] \
    || die "worker is not ready: ${row}"
  worker_urls+=("http://${ip}:8787")
  [[ ${node} == "${VICTIM_NODE}" ]] && victim_pod=${pod}
done
[[ -n ${victim_pod} ]] || die "victim Pod was not found on ${VICTIM_NODE}"

coordinator=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l app.kubernetes.io/name=traffic-coordinator \
  -o jsonpath='{.items[0].metadata.name}')
workers_csv=$(IFS=,; printf '%s' "${worker_urls[*]}")
run_id=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-fault-$$}
run_dir="/results/${run_id}"
final="${run_dir}/eastwest.json"
log_file=$(mktemp /tmp/traffic-worker-fault.XXXXXX)
cleanup() {
  rm -f "${log_file}"
}
trap cleanup EXIT

"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- mkdir -p "${run_dir}"
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- sh -c '
  set -eu
  final=$1
  shift
  tmp="${final}.tmp.$$"
  trap '\''rm -f "${tmp}"'\'' EXIT HUP INT TERM
  node /app/distributed-run.mjs "$@" >"${tmp}"
  mv "${tmp}" "${final}"
  trap - EXIT HUP INT TERM
' sh "${final}" \
  --workers "${workers_csv}" \
  --scenario eastwest \
  --candidates "${CANDIDATES}" \
  --timeout-ms "${TIMEOUT_MS}" \
  --retries "${RETRIES}" >"${log_file}" 2>&1 &
runner_pid=$!

sleep "${FAULT_DELAY_SECONDS}"
printf 'fault: deleting pod=%s node=%s\n' "${victim_pod}" "${VICTIM_NODE}"
"${kubectl[@]}" -n "${NAMESPACE}" delete pod "${victim_pod}" \
  --grace-period=0 --force --wait=false

if ! wait "${runner_pid}"; then
  cat "${log_file}" >&2
  die "distributed run did not recover"
fi
cat "${log_file}" >&2

"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- \
  node /app/validate-distributed-fault.mjs \
  "${final}" "${VICTIM_NODE}" "${EXPECTED_WORKERS}" "${CANDIDATES}"
"${kubectl[@]}" -n "${NAMESPACE}" rollout status daemonset/traffic-worker --timeout=180s
printf 'PASS: results=%s\n' "${final}"
