#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${1:-${THOR_HOST:-}}"
[[ -n "$HOST" ]] || { echo "Usage: $0 armada@<thor-ip>" >&2; exit 2; }
ARCHIVE="$(mktemp -t jarngrip.XXXXXX.tar.gz)"
trap 'rm -f "$ARCHIVE"' EXIT
# COPYFILE_DISABLE keeps macOS tar from adding ._* companion files, which the Thor would unpack as real files, and
# on macOS (bsdtar) --no-xattrs --no-mac-metadata leave out the Mac's own file tags (where a file came from, its
# access lists), which mean nothing on the Thor. The project folder is packed by its contents, so it can have any name
# on this computer.
MAC_ONLY=()
if tar --version 2>/dev/null | grep -q bsdtar; then MAC_ONLY=(--no-xattrs --no-mac-metadata); fi
COPYFILE_DISABLE=1 tar ${MAC_ONLY[@]+"${MAC_ONLY[@]}"} -C "$ROOT" --exclude .git --exclude __pycache__ \
  --exclude .DS_Store -czf "$ARCHIVE" .
# The installer runs as root, so it is unpacked into a fresh private folder (mktemp -d), never a fixed path in /tmp that
# another program could have created first and filled with a script of its own.
REMOTE="$(ssh "$HOST" 'dir="$(mktemp -d /tmp/jarngrip.XXXXXX)" && cat > "$dir/jarngrip.tar.gz" && echo "$dir"' < "$ARCHIVE")"
[[ "$REMOTE" =~ ^/tmp/jarngrip\.[A-Za-z0-9]+$ ]] || { echo "Could not copy JarnGrip to $HOST." >&2; exit 1; }
ssh -tt "$HOST" "trap 'rm -rf $REMOTE' EXIT; mkdir $REMOTE/JarnGrip && tar -xzf $REMOTE/jarngrip.tar.gz -C $REMOTE/JarnGrip && sudo $REMOTE/JarnGrip/scripts/install-on-device.sh"
