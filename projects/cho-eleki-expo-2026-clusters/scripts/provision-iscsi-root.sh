#!/usr/bin/env bash

set -euo pipefail

original_args=("$@")

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/provision-iscsi-root.sh \
    --device /dev/disk/by-path/...-iscsi-...-lun-0 \
    --expected-model node11_boot \
    --hostname node11 \
    --initiator-iqn iqn.2026-09.mpi.test:node11 \
    --target-iqn iqn.2026-09.mpi.test:storage.node10 \
    --target-ip 192.168.2.2 \
    --source-root /mnt/ubuntu-image/root \
    --source-boot /mnt/ubuntu-image/boot \
    --tftp-dir /srv/tftp/node11-staging \
    --authorized-key /var/tmp/node11_authorized_key \
    --format

The target device is erased only when --format is present. The device must be
an iSCSI by-path device, exactly 32 GiB, unmounted, and match --expected-model.
EOF
}

device=
expected_model=
node_hostname=
initiator_iqn=
target_iqn=
target_ip=
source_root=
source_boot=
tftp_dir=
authorized_key=
format_device=false

while (($#)); do
  case "$1" in
    --device) device=${2:?}; shift 2 ;;
    --expected-model) expected_model=${2:?}; shift 2 ;;
    --hostname) node_hostname=${2:?}; shift 2 ;;
    --initiator-iqn) initiator_iqn=${2:?}; shift 2 ;;
    --target-iqn) target_iqn=${2:?}; shift 2 ;;
    --target-ip) target_ip=${2:?}; shift 2 ;;
    --source-root) source_root=${2:?}; shift 2 ;;
    --source-boot) source_boot=${2:?}; shift 2 ;;
    --tftp-dir) tftp_dir=${2:?}; shift 2 ;;
    --authorized-key) authorized_key=${2:?}; shift 2 ;;
    --format) format_device=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for value_name in device expected_model node_hostname initiator_iqn target_iqn target_ip source_root source_boot tftp_dir authorized_key; do
  if [[ -z ${!value_name} ]]; then
    echo "Missing required argument: $value_name" >&2
    usage >&2
    exit 2
  fi
done

if [[ $EUID -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi
if [[ $format_device != true ]]; then
  echo "Refusing to continue without --format." >&2
  exit 1
fi
if [[ $device != /dev/disk/by-path/*-iscsi-*-lun-* ]]; then
  echo "Device is not an iSCSI by-path device: $device" >&2
  exit 1
fi
if [[ ! -b $device ]]; then
  echo "Block device not found: $device" >&2
  exit 1
fi
if [[ ! -d $source_root || ! -d $source_boot ]]; then
  echo "Ubuntu source root or boot directory is missing." >&2
  exit 1
fi
if [[ ! -s $authorized_key ]] || ! ssh-keygen -l -f "$authorized_key" >/dev/null; then
  echo "Authorized key is missing or invalid: $authorized_key" >&2
  exit 1
fi
if [[ ! $node_hostname =~ ^node[0-9]+$ ]]; then
  echo "Unexpected hostname: $node_hostname" >&2
  exit 1
fi
if [[ ! $initiator_iqn =~ ^iqn\..+:${node_hostname}$ ]]; then
  echo "Initiator IQN does not match hostname: $initiator_iqn" >&2
  exit 1
fi
if [[ $tftp_dir != "/srv/tftp/$node_hostname-staging" ]]; then
  echo "TFTP staging directory must be /srv/tftp/$node_hostname-staging: $tftp_dir" >&2
  exit 1
fi

resolved_device=$(readlink -f "$device")
device_name=$(basename "$resolved_device")
actual_size=$(blockdev --getsize64 "$resolved_device")
expected_size=$((32 * 1024 * 1024 * 1024))
actual_model=$(tr -d ' ' < "/sys/class/block/$device_name/device/model")

if [[ $actual_size -ne $expected_size ]]; then
  echo "Unexpected device size: $actual_size bytes" >&2
  exit 1
fi
if [[ $actual_model != "$expected_model" ]]; then
  echo "Unexpected device model: $actual_model (expected $expected_model)" >&2
  exit 1
fi
if findmnt -rn -S "$resolved_device" >/dev/null; then
  echo "Device is already mounted: $resolved_device" >&2
  exit 1
fi

# Keep all provisioning mounts in a private namespace. Without this, mounts
# created below a shared / can propagate into systemd services that have their
# own mount namespaces and survive cleanup in the calling namespace.
if [[ ${ISCSI_PROVISION_MOUNT_NS:-} != 1 ]]; then
  exec unshare --mount --propagation private \
    env ISCSI_PROVISION_MOUNT_NS=1 "$0" "${original_args[@]}"
fi

mount_dir="/mnt/iscsi-provision-$node_hostname"
kernel_version=

cleanup() {
  umount -R "$mount_dir/boot/firmware" 2>/dev/null || true
  umount -R "$mount_dir/run" 2>/dev/null || true
  umount -R "$mount_dir/sys" 2>/dev/null || true
  umount -R "$mount_dir/proc" 2>/dev/null || true
  umount -R "$mount_dir/dev" 2>/dev/null || true
  umount "$mount_dir" 2>/dev/null || true
}
trap cleanup EXIT

echo "Formatting $device ($actual_model, 32 GiB) for $node_hostname"
mkfs.ext4 -F -E nodiscard -L "$node_hostname-root" -m 0 "$device"
root_uuid=$(blkid -s UUID -o value "$device")

install -d -m 0755 "$mount_dir" "$tftp_dir"
mount "$device" "$mount_dir"
rsync -aHAX --numeric-ids "$source_root/" "$mount_dir/"
rsync -aH --delete "$source_boot/" "$tftp_dir/"
rm -f "$tftp_dir/user-data" "$tftp_dir/meta-data" "$tftp_dir/network-config"

install -d -m 0755 \
  "$mount_dir/boot/firmware" \
  "$mount_dir/etc/netplan" \
  "$mount_dir/etc/ssh/sshd_config.d" \
  "$mount_dir/etc/sudoers.d" \
  "$mount_dir/etc/iscsi"

cat > "$mount_dir/etc/fstab" <<EOF
UUID=$root_uuid / ext4 defaults,_netdev 0 1
# /boot/firmware is provided by TFTP from the management node.
EOF
cat > "$mount_dir/etc/hostname" <<EOF
$node_hostname
EOF
cat > "$mount_dir/etc/hosts" <<EOF
127.0.0.1 localhost
127.0.1.1 $node_hostname

::1 localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
EOF
cat > "$mount_dir/etc/netplan/01-cluster.yaml" <<'EOF'
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: false
      critical: true
EOF
chmod 0600 "$mount_dir/etc/netplan/01-cluster.yaml"
cat > "$mount_dir/etc/iscsi/initiatorname.iscsi" <<EOF
InitiatorName=$initiator_iqn
EOF
cat > "$mount_dir/etc/iscsi/iscsi.initramfs" <<EOF
ISCSI_INITIATOR=$initiator_iqn
ISCSI_TARGET_NAME=$target_iqn
ISCSI_TARGET_IP=$target_ip
ISCSI_TARGET_PORT=3260
ISCSI_TARGET_GROUP=1
EOF
chmod 0600 "$mount_dir/etc/iscsi/iscsi.initramfs"
cat > "$mount_dir/etc/ssh/sshd_config.d/99-cluster.conf" <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
cat > "$mount_dir/etc/sudoers.d/90-cluster" <<'EOF'
ubuntu ALL=(ALL) NOPASSWD:ALL
EOF
chmod 0440 "$mount_dir/etc/sudoers.d/90-cluster"
touch "$mount_dir/etc/cloud/cloud-init.disabled"
ln -snf /usr/share/zoneinfo/Asia/Tokyo "$mount_dir/etc/localtime"
echo Asia/Tokyo > "$mount_dir/etc/timezone"
: > "$mount_dir/etc/machine-id"
rm -f "$mount_dir/var/lib/dbus/machine-id"

mount --rbind /dev "$mount_dir/dev"
mount --make-rslave "$mount_dir/dev"
mount -t proc proc "$mount_dir/proc"
mount --rbind /sys "$mount_dir/sys"
mount --make-rslave "$mount_dir/sys"
mount --rbind /run "$mount_dir/run"
mount --make-rslave "$mount_dir/run"
mount --bind "$tftp_dir" "$mount_dir/boot/firmware"

if ! chroot "$mount_dir" getent passwd ubuntu >/dev/null; then
  chroot "$mount_dir" useradd -m -s /bin/bash -G adm,sudo,plugdev,netdev,lxd ubuntu
fi
chroot "$mount_dir" passwd -l ubuntu
ubuntu_uid=$(chroot "$mount_dir" id -u ubuntu)
ubuntu_gid=$(chroot "$mount_dir" id -g ubuntu)
install -d -m 0700 -o "$ubuntu_uid" -g "$ubuntu_gid" "$mount_dir/home/ubuntu/.ssh"
install -m 0600 -o "$ubuntu_uid" -g "$ubuntu_gid" "$authorized_key" "$mount_dir/home/ubuntu/.ssh/authorized_keys"
rm -f "$mount_dir"/etc/ssh/ssh_host_*
chroot "$mount_dir" ssh-keygen -A
chroot "$mount_dir" systemctl enable ssh
# Firmware metadata refresh is unnecessary on these fixed-purpose Pi nodes and
# would make their health depend on Internet access during an exhibition.
chroot "$mount_dir" systemctl disable fwupd-refresh.timer
chroot "$mount_dir" update-initramfs -u -k all

kernel_version=$(find "$mount_dir/boot" -maxdepth 1 -name 'vmlinuz-*' -printf '%f\n' | sed 's/^vmlinuz-//' | sort -V | tail -1)
if [[ -z $kernel_version ]]; then
  echo "Generated kernel was not found." >&2
  exit 1
fi
install -m 0644 "$mount_dir/boot/initrd.img-$kernel_version" "$tftp_dir/initrd.img"
install -m 0644 "$mount_dir/boot/vmlinuz-$kernel_version" "$tftp_dir/vmlinuz"
cat > "$tftp_dir/cmdline.txt" <<EOF
console=serial0,115200 multipath=off dwc_otg.lpm_enable=0 console=tty1 ip=dhcp root=UUID=$root_uuid rootfstype=ext4 rootwait rw fixrtc
EOF
chmod 0644 "$tftp_dir/cmdline.txt"

sync
echo "Provisioned $node_hostname"
echo "ROOT_UUID=$root_uuid"
echo "KERNEL_VERSION=$kernel_version"
echo "TFTP_DIR=$tftp_dir"
