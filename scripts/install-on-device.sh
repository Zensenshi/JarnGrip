#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGINS=/home/armada/homebrew/plugins
PLUGIN_DIR="$PLUGINS/jarngrip"
# Staging, backups and failed installs live outside the plugins folder: Decky loads every folder in it as a plugin.
WORK=/home/armada/homebrew/jarngrip-backups
STAGE="$WORK/stage.$$"
BACKUP="$WORK/jarngrip.$(date +%Y%m%d%H%M%S)"
USER_HOME=/var/home/armada
if [[ $(id -u) -ne 0 ]]; then
  if ! sudo -n true 2>/dev/null; then
    [[ -t 0 ]] || { echo "Run from a terminal: sudo $0" >&2; exit 2; }
    sudo -v
  fi
  exec sudo "$0" "$@"
fi
[[ -f "$ROOT/plugin.json" && -f "$ROOT/main.py" ]] || { echo "Run this from the unpacked JarnGrip directory." >&2; exit 2; }
# Copying as root follows symbolic links: one planted in this folder could copy any file on the system into the plugin.
if [[ -n "$(find "$ROOT" -type l -print -quit)" ]]; then
  echo "Refusing to install: $ROOT contains symbolic links." >&2; exit 2
fi

plugin_name() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("name",""))' "$1/plugin.json" 2>/dev/null || true; }
# Files in the user's home are changed as the user, never as root: root would follow links the user can plant there.
as_user() { if command -v runuser >/dev/null; then runuser -u armada -- "$@"; else sudo -u armada -- "$@"; fi; }
user_systemctl() {
  systemctl --machine=armada@.host --user "$@" 2>/dev/null \
    || su -s /bin/sh armada -c "XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user $*" 2>/dev/null
}

# Before 0.4.0 this plugin was Thor WoW Pad (id thor-wow-pad). Stop and remove that install, give back the screen
# services it paused, and carry its settings and profiles over.
OLD_PLUGIN="$PLUGINS/thor-wow-pad"
if [[ -e "$OLD_PLUGIN" && "$(plugin_name "$OLD_PLUGIN")" == "Thor WoW Pad" ]]; then
  echo "Replacing Thor WoW Pad, the old name of JarnGrip."
  user_systemctl stop thor-wow-pad.service || true
  OLD_MARKER="$USER_HOME/.local/state/thor-wow-pad/restore.json"
  if [[ -f "$OLD_MARKER" ]]; then
    python3 - "$OLD_MARKER" <<'PY'
import json,sys,subprocess
try:
 d=json.load(open(sys.argv[1]))
 for key,unit in [('ratatoskr','touch-master.service'),('bottom_screen','armada-bottom-screen.service')]:
  if d.get(key):subprocess.run(['systemctl','--machine=armada@.host','--user','start',unit],check=False)
except Exception:pass
PY
  fi
  as_user rm -rf "$USER_HOME/.local/state/thor-wow-pad"
  if [[ -d "$USER_HOME/.config/thor-wow-pad" && ! -e "$USER_HOME/.config/jarngrip" ]]; then
    as_user mv "$USER_HOME/.config/thor-wow-pad" "$USER_HOME/.config/jarngrip"
    echo "Moved settings and profiles to $USER_HOME/.config/jarngrip/."
  fi
  as_user rm -f "$USER_HOME/.config/systemd/user/thor-wow-pad.service"
  as_user rm -rf "$USER_HOME/.local/share/thor-wow-pad"
  rm -rf "$OLD_PLUGIN"
  user_systemctl daemon-reload || true
fi
# Old installers left their backups in the plugins folder, where Decky could load them as duplicate plugins.
for leftover in "$PLUGINS"/thor-wow-pad.backup.* "$PLUGINS"/thor-wow-pad.failed.* "$PLUGINS"/thor-wow-pad.stage.*; do
  if [[ -d "$leftover" && "$(plugin_name "$leftover")" == "Thor WoW Pad" ]]; then rm -rf "$leftover"; fi
done

mkdir -p "$PLUGINS" "$WORK"
if [[ -e "$PLUGIN_DIR" ]]; then
  [[ -f "$PLUGIN_DIR/plugin.json" ]] || { echo "Refusing to replace unrelated files at $PLUGIN_DIR" >&2; exit 3; }
  [[ "$(plugin_name "$PLUGIN_DIR")" == "JarnGrip" ]] || { echo "Refusing to replace a different plugin at $PLUGIN_DIR" >&2; exit 3; }
fi
python3 - "$ROOT" "$STAGE" <<'PY'
import shutil,sys
shutil.copytree(sys.argv[1],sys.argv[2],symlinks=True,dirs_exist_ok=True)
PY
chown -R root:root "$STAGE"; chmod -R a+rX,u+w "$STAGE"
if [[ -e "$PLUGIN_DIR" ]]; then mv "$PLUGIN_DIR" "$BACKUP"; fi
if ! mv "$STAGE" "$PLUGIN_DIR"; then [[ ! -e "$BACKUP" ]] || mv "$BACKUP" "$PLUGIN_DIR"; exit 4; fi
if ! systemctl restart plugin_loader.service; then
  FAILED="$WORK/failed.$(date +%Y%m%d%H%M%S)"
  mv "$PLUGIN_DIR" "$FAILED"
  if [[ -e "$BACKUP" ]]; then mv "$BACKUP" "$PLUGIN_DIR"; fi
  echo "Decky restart failed; new files kept at $FAILED and previous version restored when available." >&2
  exit 5
fi
# The AYN button's "Stop the screenshot" loads InputPlumber profiles, which InputPlumber's policy keeps to admins.
install -d -m 0755 /etc/polkit-1/rules.d
install -m 0644 -o root -g root "$PLUGIN_DIR/polkit/49-jarngrip-inputplumber.rules" /etc/polkit-1/rules.d/
# The rule applies only while this marker exists. The user owns it, so that uninstalling from Decky, which runs as the
# user, can delete it.
install -d -m 0755 -o armada -g armada /var/lib/jarngrip
install -m 0644 -o armada -g armada /dev/null /var/lib/jarngrip/installed
# Keep the three newest backups.
ls -1dt "$WORK"/jarngrip.* 2>/dev/null | tail -n +4 | while read -r old; do rm -rf "$old"; done
echo "Installed JarnGrip. Open Steam > Decky > JarnGrip to enable it."
if [[ -e "$BACKUP" ]]; then echo "Previous version kept at $BACKUP"; fi
