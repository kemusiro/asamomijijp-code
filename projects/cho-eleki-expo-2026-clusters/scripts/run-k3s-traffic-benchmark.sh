#!/usr/bin/env bash

set -Eeuo pipefail

readonly NAMESPACE="traffic-demo"
readonly WORKER_SELECTOR="app.kubernetes.io/name=traffic-worker"
readonly COORDINATOR_SELECTOR="app.kubernetes.io/name=traffic-coordinator"
readonly EXPECTED_WORKERS="${EXPECTED_WORKERS:-12}"
readonly CANDIDATES="${CANDIDATES:-120}"
readonly TIMEOUT_MS="${TIMEOUT_MS:-5000}"
readonly RETRIES="${RETRIES:-1}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || die "root privileges are required"
[[ $# -le 1 ]] || die "usage: sudo $0 [eastwest|balanced|all]"
scenario=${1:-all}
[[ ${scenario} == eastwest || ${scenario} == balanced || ${scenario} == all ]] \
  || die "scenario must be eastwest, balanced, or all"
[[ ${EXPECTED_WORKERS} =~ ^[0-9]+$ && ${EXPECTED_WORKERS} -ge 2 ]] \
  || die "EXPECTED_WORKERS must be an integer of at least 2"
[[ ${CANDIDATES} =~ ^[0-9]+$ && ${CANDIDATES} -ge 1 && ${CANDIDATES} -le 120 ]] \
  || die "CANDIDATES must be an integer from 1 to 120"
[[ ${TIMEOUT_MS} =~ ^[0-9]+$ && ${TIMEOUT_MS} -ge 100 ]] \
  || die "TIMEOUT_MS must be an integer of at least 100"
[[ ${RETRIES} =~ ^[0-9]+$ && ${RETRIES} -le 10 ]] \
  || die "RETRIES must be an integer from 0 to 10"
command -v k3s >/dev/null || die "k3s is not installed"
systemctl is-active --quiet k3s || die "k3s server is not active"

kubectl=(k3s kubectl)
"${kubectl[@]}" -n "${NAMESPACE}" wait --for=condition=Available \
  deployment/traffic-coordinator --timeout=120s >/dev/null

mapfile -t worker_rows < <(
  "${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${WORKER_SELECTOR}" \
    --sort-by=.spec.nodeName \
    -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.status.podIP}{" "}{.status.phase}{" "}{.status.containerStatuses[0].ready}{"\n"}{end}'
)
[[ ${#worker_rows[@]} -eq ${EXPECTED_WORKERS} ]] \
  || die "worker Pod count differs: ${#worker_rows[@]}/${EXPECTED_WORKERS}"

worker_urls=()
worker_nodes=()
for row in "${worker_rows[@]}"; do
  read -r node ip phase ready <<<"${row}"
  [[ -n ${node} && -n ${ip} && ${phase} == Running && ${ready} == true ]] \
    || die "worker is not ready: ${row}"
  worker_nodes+=("${node}")
  worker_urls+=("http://${ip}:8787")
done
[[ $(printf '%s\n' "${worker_nodes[@]}" | sort -u | wc -l | tr -d ' ') -eq ${EXPECTED_WORKERS} ]] \
  || die "worker Pods are not distributed to unique nodes"

coordinator=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${COORDINATOR_SELECTOR}" \
  -o jsonpath='{.items[0].metadata.name}')
[[ -n ${coordinator} ]] || die "coordinator Pod is missing"
workers_csv=$(IFS=,; printf '%s' "${worker_urls[*]}")
run_id=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}
run_dir="/results/${run_id}"
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- mkdir -p "${run_dir}"

if [[ ${scenario} == all ]]; then
  scenarios=(eastwest balanced)
else
  scenarios=("${scenario}")
fi

printf 'run=%s workers=%s nodes=%s\n' "${run_id}" "${EXPECTED_WORKERS}" "${worker_nodes[*]}"
for current in "${scenarios[@]}"; do
  final="${run_dir}/${current}.json"
  printf 'scenario=%s status=running output=%s\n' "${current}" "${final}"
  "${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- sh -c '
    set -eu
    final=$1
    shift
    tmp="${final}.tmp.$$"
    trap '\''rm -f "${tmp}"'\'' EXIT HUP INT TERM
    node /app/distributed-benchmark.mjs "$@" >"${tmp}"
    mv "${tmp}" "${final}"
    trap - EXIT HUP INT TERM
  ' sh "${final}" \
    --workers "${workers_csv}" \
    --scenario "${current}" \
    --candidates "${CANDIDATES}" \
    --timeout-ms "${TIMEOUT_MS}" \
    --retries "${RETRIES}"
  "${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- \
    node /app/validate-distributed-benchmark.mjs \
    "${final}" "${EXPECTED_WORKERS}" "${CANDIDATES}"
done

printf 'PASS: results=%s\n' "${run_dir}"
