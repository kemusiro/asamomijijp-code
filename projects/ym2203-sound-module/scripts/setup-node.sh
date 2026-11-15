#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
NODE_VERSION=$(tr -d '[:space:]' < "$REPOSITORY_ROOT/.node-version")

if [ "$NODE_VERSION" != "22.23.2" ]; then
  echo "Node.js $NODE_VERSION has no pinned archive checksum in scripts/setup-node.sh." >&2
  exit 1
fi

case "$(uname -s):$(uname -m)" in
  Darwin:arm64)
    PLATFORM="darwin-arm64"
    ARCHIVE_SHA256="61130f394c1630d211dd50aecc4353d379480f36d3ac913cd85dbba1aed585c6"
    ;;
  Darwin:x86_64)
    PLATFORM="darwin-x64"
    ARCHIVE_SHA256="58e99022c2ff89395576cc7fd4d98cea24bb68081475d5f88b801ee8729fb026"
    ;;
  Linux:aarch64 | Linux:arm64)
    PLATFORM="linux-arm64"
    ARCHIVE_SHA256="013b59cfd2819703a6f4a14ab891fc46fc2a4e3f5bcd92de3fb4929b43e35b30"
    ;;
  Linux:x86_64)
    PLATFORM="linux-x64"
    ARCHIVE_SHA256="b294a556e639d64338823920e5866c21c02741742d2e1529ee1a225c1ec9252a"
    ;;
  *)
    echo "Unsupported Node.js development platform: $(uname -s) $(uname -m)" >&2
    exit 1
    ;;
esac

ARCHIVE_NAME="node-v${NODE_VERSION}-${PLATFORM}.tar.gz"
NODE_CACHE_ROOT="$REPOSITORY_ROOT/.cache/node"
NODE_INSTALLATION="$NODE_CACHE_ROOT/node-v${NODE_VERSION}-${PLATFORM}"
NODE_EXECUTABLE="$NODE_INSTALLATION/bin/node"

if [ -x "$NODE_EXECUTABLE" ] && [ "$($NODE_EXECUTABLE --version)" = "v$NODE_VERSION" ]; then
  printf '%s\n' "$NODE_INSTALLATION"
  exit 0
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command was not found: $1" >&2
    exit 1
  fi
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

require_command curl
require_command tar

DOWNLOAD_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/micropython-web-lab-node.XXXXXX")
ARCHIVE_PATH="$DOWNLOAD_ROOT/$ARCHIVE_NAME"
EXTRACTED_PATH="$DOWNLOAD_ROOT/node-v${NODE_VERSION}-${PLATFORM}"

cleanup() {
  rm -rf "$DOWNLOAD_ROOT"
}
trap cleanup EXIT HUP INT TERM

echo "Downloading Node.js v$NODE_VERSION for $PLATFORM" >&2
curl --fail --location --silent --show-error \
  "https://nodejs.org/dist/v${NODE_VERSION}/${ARCHIVE_NAME}" \
  --output "$ARCHIVE_PATH"

ACTUAL_SHA256=$(sha256_file "$ARCHIVE_PATH")
if [ "$ACTUAL_SHA256" != "$ARCHIVE_SHA256" ]; then
  echo "Node.js archive checksum did not match." >&2
  echo "Expected: $ARCHIVE_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  exit 1
fi

tar -xzf "$ARCHIVE_PATH" -C "$DOWNLOAD_ROOT"
mkdir -p "$NODE_CACHE_ROOT"
if [ -e "$NODE_INSTALLATION" ]; then
  rm -rf "$NODE_INSTALLATION"
fi
mv "$EXTRACTED_PATH" "$NODE_INSTALLATION"

if [ "$($NODE_EXECUTABLE --version)" != "v$NODE_VERSION" ]; then
  echo "Installed Node.js version did not match v$NODE_VERSION." >&2
  exit 1
fi

printf '%s\n' "$NODE_INSTALLATION"
