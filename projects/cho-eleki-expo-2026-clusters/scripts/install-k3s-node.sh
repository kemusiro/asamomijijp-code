#!/usr/bin/env bash

set -Eeuo pipefail

readonly K3S_VERSION="v1.36.3+k3s1"
readonly K3S_SHA256="c9a209103f480f163b7c6a56f00862b4481927b284dc29a3716bb70d886691a8"
readonly AIRGAP_SHA256="856feb047453cd697c2bc4dcf20127448554c8366be992a211558a13d830a038"
readonly INSTALLER_SHA256="46177d4c99440b4c0311b67233823a8e8a2fc09693f6c89af1a7161e152fbfad"
readonly MANAGED_MARKER="# Managed by scripts/install-k3s-node.sh"

usage() {
  cat <<'EOF'
Usage:
  sudo ./install-k3s-node.sh server NODE_NAME NODE_IP ASSET_DIR
  sudo ./install-k3s-node.sh agent NODE_NAME NODE_IP ASSET_DIR TOKEN_FILE

ASSET_DIR must contain the following files from the official K3s release:
  k3s-arm64
  k3s-airgap-images-arm64.tar.zst
  install.sh

The agent token is copied to a root-only local file. Its contents are never
printed. Existing K3s configuration not created by this script is preserved and
causes the script to stop.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || die "root privileges are required"
[[ $# -ge 4 ]] || {
  usage >&2
  exit 2
}

role=$1
node_name=$2
node_ip=$3
asset_dir=$4
token_file=${5:-}

[[ ${role} == server || ${role} == agent ]] || die "role must be server or agent"
[[ ${node_name} =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || die "invalid node name: ${node_name}"
[[ ${node_ip} =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "invalid IPv4 address: ${node_ip}"
[[ $(uname -m) == aarch64 ]] || die "this installer requires aarch64"
[[ $(stat -fc %T /sys/fs/cgroup) == cgroup2fs ]] || die "cgroup v2 is not active"
[[ -z $(swapon --show --noheadings) ]] || die "swap must be disabled"
[[ $(hostname) == "${node_name}" ]] || die "hostname is $(hostname), expected ${node_name}"
ip -4 -o addr show dev eth0 | grep -Fq " ${node_ip}/" || die "${node_ip} is not configured on eth0"

for file in k3s-arm64 k3s-airgap-images-arm64.tar.zst install.sh; do
  [[ -f ${asset_dir}/${file} ]] || die "missing asset: ${asset_dir}/${file}"
done

printf '%s  %s\n' "${K3S_SHA256}" "${asset_dir}/k3s-arm64" | sha256sum --check --status \
  || die "k3s-arm64 checksum mismatch"
printf '%s  %s\n' "${AIRGAP_SHA256}" "${asset_dir}/k3s-airgap-images-arm64.tar.zst" | sha256sum --check --status \
  || die "air-gap image checksum mismatch"
printf '%s  %s\n' "${INSTALLER_SHA256}" "${asset_dir}/install.sh" | sha256sum --check --status \
  || die "install.sh checksum mismatch"

if [[ ${role} == agent ]]; then
  [[ -n ${token_file} && -f ${token_file} ]] || die "agent installation requires TOKEN_FILE"
  [[ -s ${token_file} ]] || die "TOKEN_FILE is empty"
fi

config_dir=/etc/rancher/k3s
config_file=${config_dir}/config.yaml
if [[ -e ${config_file} ]] && ! grep -Fqx "${MANAGED_MARKER}" "${config_file}"; then
  die "existing unmanaged configuration found at ${config_file}"
fi

install -d -m 0755 /usr/local/bin /usr/local/lib/k3s
install -d -m 0700 "${config_dir}"
install -d -m 0755 /var/lib/rancher/k3s/agent/images
install -m 0755 "${asset_dir}/k3s-arm64" /usr/local/bin/k3s
install -m 0755 "${asset_dir}/install.sh" "/usr/local/lib/k3s/install-${K3S_VERSION}.sh"
install -m 0644 "${asset_dir}/k3s-airgap-images-arm64.tar.zst" \
  /var/lib/rancher/k3s/agent/images/k3s-airgap-images-arm64.tar.zst

tmp_config=$(mktemp)
trap 'rm -f "${tmp_config}"' EXIT

if [[ ${role} == server ]]; then
  cat >"${tmp_config}" <<EOF
${MANAGED_MARKER}
node-name: ${node_name}
node-ip: ${node_ip}
advertise-address: ${node_ip}
tls-san:
  - ${node_ip}
flannel-iface: eth0
disable:
  - traefik
  - servicelb
write-kubeconfig-mode: "0640"
node-taint:
  - node-role.kubernetes.io/control-plane=true:NoSchedule
node-label:
  - exhibition.asamomiji.jp/role=control-plane
EOF
else
  install -m 0600 "${token_file}" "${config_dir}/agent-token"
  cat >"${tmp_config}" <<EOF
${MANAGED_MARKER}
server: https://192.168.2.1:6443
token-file: ${config_dir}/agent-token
node-name: ${node_name}
node-ip: ${node_ip}
flannel-iface: eth0
node-label:
  - exhibition.asamomiji.jp/role=compute
EOF
fi

install -m 0600 "${tmp_config}" "${config_file}"

INSTALL_K3S_SKIP_DOWNLOAD=true \
INSTALL_K3S_EXEC="${role}" \
  sh "/usr/local/lib/k3s/install-${K3S_VERSION}.sh"

installed_version=$(/usr/local/bin/k3s --version)
case ${installed_version} in
  *"${K3S_VERSION}"*) ;;
  *) die "installed version is unexpected: ${installed_version}" ;;
esac

printf 'Installed K3s %s as %s on %s (%s).\n' \
  "${K3S_VERSION}" "${role}" "${node_name}" "${node_ip}"
