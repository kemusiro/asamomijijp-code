#!/usr/bin/env bash

set -Eeuo pipefail

readonly ARCHIVE_NAME="nfs-csi-v4.13.4-arm64.tar"
readonly ARCHIVE_SHA256="f84e56850b7a038cdaab8ab769293e62df9fc9b80cdb88873e1fddf5b20e6487"
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

for image in \
  registry.k8s.io/sig-storage/csi-provisioner:v6.3.0 \
  registry.k8s.io/sig-storage/csi-resizer:v2.2.0 \
  registry.k8s.io/sig-storage/csi-snapshotter:v8.6.0 \
  registry.k8s.io/sig-storage/livenessprobe:v2.19.0 \
  registry.k8s.io/sig-storage/csi-node-driver-registrar:v2.17.0 \
  registry.k8s.io/sig-storage/nfsplugin:v4.13.4; do
  k3s ctr images list -q | grep -Fqx "${image}" || die "image was not imported: ${image}"
done

printf 'Installed and imported %s.\n' "${ARCHIVE_NAME}"
