#!/usr/bin/env bash

set -Eeuo pipefail

readonly ARCHIVE_NAME="node-22.22.0-bookworm-slim-arm64.tar"
readonly ARCHIVE_SHA256="b01ec05c31ead915d83e5ed27d1a5c4dae44e9bcfbc91520d223172d6d4366fa"
readonly IMAGE="docker.io/library/node:22.22.0-bookworm-slim"
readonly IMAGE_INDEX="sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94"
readonly IMAGE_DIR="/var/lib/rancher/k3s/agent/images"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || die "root privileges are required"
[[ $# -eq 1 ]] || die "usage: sudo $0 /path/to/${ARCHIVE_NAME}"
[[ $(uname -m) == aarch64 ]] || die "this archive requires aarch64"
command -v k3s >/dev/null || die "k3s is not installed"
systemctl is-active --quiet k3s || systemctl is-active --quiet k3s-agent \
  || die "k3s or k3s-agent must be active"

source_archive=$1
[[ -f ${source_archive} ]] || die "archive not found: ${source_archive}"
printf '%s  %s\n' "${ARCHIVE_SHA256}" "${source_archive}" | sha256sum --check --status \
  || die "archive checksum mismatch"

install -d -m 0755 "${IMAGE_DIR}"
install -m 0644 "${source_archive}" "${IMAGE_DIR}/${ARCHIVE_NAME}"
k3s ctr images import --platform linux/arm64 "${IMAGE_DIR}/${ARCHIVE_NAME}" >/dev/null

k3s ctr images list | awk -v image="${IMAGE}" -v digest="${IMAGE_INDEX}" \
  '$1 == image && $3 == digest {found = 1} END {exit !found}' \
  || die "image or index digest was not imported: ${IMAGE}@${IMAGE_INDEX}"

printf 'Installed and imported %s.\n' "${ARCHIVE_NAME}"
