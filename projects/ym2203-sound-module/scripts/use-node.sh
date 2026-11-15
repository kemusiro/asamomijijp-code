#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
NODE_INSTALLATION=$("$SCRIPT_DIR/setup-node.sh")

PATH="$NODE_INSTALLATION/bin:$PATH"
COREPACK_HOME="$REPOSITORY_ROOT/.cache/corepack"
COREPACK_ENABLE_STRICT=1
export PATH COREPACK_HOME COREPACK_ENABLE_STRICT

if [ ! -x "$NODE_INSTALLATION/bin/pnpm" ]; then
  "$NODE_INSTALLATION/bin/corepack" enable pnpm --install-directory "$NODE_INSTALLATION/bin"
fi

if [ "$#" -eq 0 ]; then
  echo "Node.js $(node --version) development shell" >&2
  DEVELOPMENT_SHELL=${SHELL:-/bin/sh}
  case "${DEVELOPMENT_SHELL##*/}" in
    bash)
      exec "$DEVELOPMENT_SHELL" --noprofile --norc
      ;;
    zsh)
      exec "$DEVELOPMENT_SHELL" -f
      ;;
    *)
      exec "$DEVELOPMENT_SHELL"
      ;;
  esac
fi

case "$1" in
  pnpm)
    shift
    exec "$NODE_INSTALLATION/bin/pnpm" "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
