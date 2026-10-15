#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
HOST="${1:-${THOR_HOST:-}}"
[[ -n "$HOST" ]] || { echo "Usage: $0 armada@<thor-ip>" >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ssh -tt "$HOST" 'sudo bash -s' < "$SCRIPT_DIR/uninstall-on-device.sh"
