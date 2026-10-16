#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
PLUGIN_DIR=/home/armada/homebrew/plugins/jarngrip
APP_DIR=/var/home/armada/.local/share/jarngrip
UNIT=/var/home/armada/.config/systemd/user/jarngrip.service
if [[ $(id -u) -ne 0 ]]; then
  if ! sudo -n true 2>/dev/null; then [[ -t 0 ]] || { echo "Run from a terminal: sudo $0" >&2; exit 2; }; sudo -v; fi
  exec sudo "$0" "$@"
fi
# Files in the user's home are removed as the user, never as root: root would follow links the user can plant there.
as_user() { if command -v runuser >/dev/null; then runuser -u armada -- "$@"; else sudo -u armada -- "$@"; fi; }
systemctl --machine=armada@.host --user stop jarngrip.service jarngrip-ayn.service 2>/dev/null || systemctl --user stop jarngrip.service jarngrip-ayn.service 2>/dev/null || true
MARKER=/var/home/armada/.local/state/jarngrip/restore.json
if [[ -f "$MARKER" ]]; then
  python3 - "$MARKER" <<'PY'
import json,sys,subprocess
try:
 d=json.load(open(sys.argv[1]))
 for key,unit in [('ratatoskr','touch-master.service'),('bottom_screen','armada-bottom-screen.service')]:
  if d.get(key):subprocess.run(['systemctl','--machine=armada@.host','--user','start',unit],check=False)
except Exception:pass
PY
  as_user rm -f "$MARKER"
fi
# Give the AYN button its screenshot back if "Stop the screenshot" changed InputPlumber's profile, then remove the
# polkit rule that let the plugin do that.
B=org.shadowblip.InputPlumber
for d in $(busctl --system --list tree $B 2>/dev/null | grep -E '/CompositeDevice[0-9]+$'); do
  if busctl --system get-property $B "$d" org.shadowblip.Input.CompositeDevice ProfileName 2>/dev/null | grep -q ' + JarnGrip"$'; then
    busctl --system call $B "$d" org.shadowblip.Input.CompositeDevice LoadProfilePath s /usr/share/inputplumber/profiles/default.yaml || true
  fi
done
as_user rm -f /var/home/armada/.local/state/jarngrip/inputplumber.json
rm -f /etc/polkit-1/rules.d/49-jarngrip-inputplumber.rules
rm -rf /var/lib/jarngrip
if [[ -f "$PLUGIN_DIR/plugin.json" ]] && grep -q 'JarnGrip' "$PLUGIN_DIR/plugin.json"; then rm -rf "$PLUGIN_DIR"; fi
as_user rm -f "$UNIT" /var/home/armada/.config/systemd/user/jarngrip-ayn.service /run/user/1000/jarngrip-ayn /var/home/armada/.local/share/applications/jarngrip.desktop /var/home/armada/.config/autostart/jarngrip.desktop
as_user rm -rf "$APP_DIR"
rm -rf /home/armada/homebrew/jarngrip-backups
su -s /bin/sh armada -c 'XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user daemon-reload' 2>/dev/null || true
systemctl restart plugin_loader.service
echo "JarnGrip removed. Configuration remains under /var/home/armada/.config/jarngrip/."
