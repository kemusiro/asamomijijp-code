#!/usr/bin/env bash

set -Eeuo pipefail

readonly NAMESPACE="traffic-demo"
readonly WORKER_SELECTOR="app.kubernetes.io/name=traffic-worker"
readonly COORDINATOR_SELECTOR="app.kubernetes.io/name=traffic-coordinator"
readonly EXPECTED_WORKERS="${EXPECTED_WORKERS:-12}"
readonly OUTER_POPULATION="${OUTER_POPULATION:-12}"
readonly OUTER_GENERATIONS="${OUTER_GENERATIONS:-5}"
readonly BUDGET_MS="${BUDGET_MS:-15000}"
readonly SIGNAL_POPULATION="${SIGNAL_POPULATION:-12}"
readonly TIMEOUT_MS="${TIMEOUT_MS:-60000}"
readonly OUTER_RESULT="${OUTER_RESULT:-}"

die(){ printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]]||die "root privileges are required"
[[ $# -eq 0 ]]||die "usage: sudo $0"
for value in EXPECTED_WORKERS OUTER_POPULATION OUTER_GENERATIONS BUDGET_MS SIGNAL_POPULATION TIMEOUT_MS; do
  current=${!value}; [[ ${current} =~ ^[0-9]+$ ]]||die "${value} must be an integer"
done
[[ ${EXPECTED_WORKERS} -ge 2 ]]||die "EXPECTED_WORKERS must be at least 2"
[[ ${BUDGET_MS} -ge 1000 ]]||die "BUDGET_MS must be at least 1000"
command -v k3s >/dev/null||die "k3s is not installed"
systemctl is-active --quiet k3s||die "k3s server is not active"

kubectl=(k3s kubectl)
"${kubectl[@]}" -n "${NAMESPACE}" wait --for=condition=Available deployment/traffic-coordinator --timeout=120s >/dev/null
mapfile -t worker_rows < <("${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${WORKER_SELECTOR}" --sort-by=.spec.nodeName -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.status.podIP}{" "}{.status.phase}{" "}{.status.containerStatuses[0].ready}{"\n"}{end}')
[[ ${#worker_rows[@]} -eq ${EXPECTED_WORKERS} ]]||die "worker Pod count differs: ${#worker_rows[@]}/${EXPECTED_WORKERS}"
worker_urls=(); worker_nodes=()
for row in "${worker_rows[@]}"; do
  read -r node ip phase ready <<<"${row}"
  [[ -n ${node} && -n ${ip} && ${phase} == Running && ${ready} == true ]]||die "worker is not ready: ${row}"
  worker_nodes+=("${node}"); worker_urls+=("http://${ip}:8787")
done
coordinator=$("${kubectl[@]}" -n "${NAMESPACE}" get pod -l "${COORDINATOR_SELECTOR}" -o jsonpath='{.items[0].metadata.name}')
[[ -n ${coordinator} ]]||die "coordinator Pod is missing"
workers_csv=$(IFS=,; printf '%s' "${worker_urls[*]}")
run_id=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}
run_dir="/results/${run_id}"
outer=${OUTER_RESULT:-${run_dir}/outer-search.json}; final="${run_dir}/time-budget.json"
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- mkdir -p "${run_dir}"

run_atomic(){
  local output=$1; shift
  "${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- sh -c '
    set -eu; final=$1; shift; tmp="${final}.tmp.$$"; trap '\''rm -f "${tmp}"'\'' EXIT HUP INT TERM
    "$@" >"${tmp}"; mv "${tmp}" "${final}"; trap - EXIT HUP INT TERM
  ' sh "${output}" "$@"
}

if [[ -z ${OUTER_RESULT} ]]; then
  printf 'run=%s phase=outer-search workers=%s output=%s\n' "${run_id}" "${EXPECTED_WORKERS}" "${outer}"
  run_atomic "${outer}" node /app/outer-search.mjs --workers "${workers_csv}" --population "${OUTER_POPULATION}" --generations "${OUTER_GENERATIONS}" --timeout-ms "${TIMEOUT_MS}"
else
  printf 'run=%s phase=outer-search status=reuse input=%s\n' "${run_id}" "${outer}"
fi
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- node /app/validate-outer-search.mjs "${outer}" "${OUTER_POPULATION}" "${OUTER_GENERATIONS}"
printf 'run=%s phase=time-budget budget_ms=%s output=%s\n' "${run_id}" "${BUDGET_MS}" "${final}"
run_atomic "${final}" node /app/time-budget-benchmark.mjs --workers "${workers_csv}" --outer-result "${outer}" --budget-ms "${BUDGET_MS}" --population "${SIGNAL_POPULATION}" --timeout-ms "${TIMEOUT_MS}"
"${kubectl[@]}" -n "${NAMESPACE}" exec "${coordinator}" -- node /app/validate-time-budget.mjs "${final}" "${EXPECTED_WORKERS}" "${BUDGET_MS}"
printf 'PASS: outer=%s benchmark=%s nodes=%s\n' "${outer}" "${final}" "${worker_nodes[*]}"
