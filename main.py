# SPDX-License-Identifier: GPL-3.0-only
"""Decky backend for JarnGrip: installs the pad's runtime and user service, starts and stops it, and keeps its config.

The pad itself runs as the armada user's systemd service (systemd/jarngrip.service), not inside Decky. Starting and
stopping it from here follows Ratatoskr's Decky backend (MIT); see driver/RATATOSKR-MIT-LICENSE.txt.

plugin.json asks for no "root" flag, so Decky runs this backend as the armada user, not as root. Keep it that way: as
root, every file written in the user's home below could be redirected by a link the user (or a game) planted there.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent
HOME = Path("/var/home/armada")
UID = GID = 1000
APP = HOME / ".local/share/jarngrip"
CFG = HOME / ".config/jarngrip/config.json"
# Which bottom-screen services the pad stopped to make room, so that stopping the pad can bring them back.
MARKER = HOME / ".local/state/jarngrip/restore.json"
UNIT = "jarngrip.service"
PAUSED_UNITS = (("ratatoskr", "touch-master.service"), ("bottom_screen", "armada-bottom-screen.service"))
THEMES = ("classic", "charcoal", "dark", "glass")
BACKGROUNDS = HOME / "Pictures/JarnGrip"
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
# Desktop Mode: the pad in the KDE app menu, and started with the desktop when "Start with Desktop Mode" is on.
APP_MENU = HOME / ".local/share/applications/jarngrip.desktop"
AUTOSTART = HOME / ".config/autostart/jarngrip.desktop"
DEFAULT = {
    "enabled": False, "page": "Interface", "sensitivity": 1.0, "theme": "classic", "haptics": True,
    "haptics_strength": 1.0, "burn_in": True, "clock_24h": False, "background_image": "", "glass_blur": 3, "desktop_mode": False,
    "bindings": {}, "profiles": {"Default": {"bindings": {}}}, "active_profile": "Default",
}


def _user_env() -> dict:
    return dict(os.environ, XDG_RUNTIME_DIR=f"/run/user/{UID}", DBUS_SESSION_BUS_ADDRESS=f"unix:path=/run/user/{UID}/bus")


def _user_systemctl(*args: str, timeout: int = 8) -> subprocess.CompletedProcess | None:
    """systemctl --user for the armada user: the user's manager named explicitly first, then the plain form."""
    for cmd in (["systemctl", "--machine=armada@.host", "--user", *args], ["systemctl", "--user", *args]):
        try:
            done = subprocess.run(cmd, env=_user_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode == 0:
            return done
    return None


def _systemctl(action: str, unit: str | None = None) -> bool:
    done = _user_systemctl(action, *([unit] if unit else []))
    return bool(done and done.returncode == 0)


def _active(unit: str) -> bool:
    done = _user_systemctl("is-active", unit, timeout=5)
    return bool(done and done.stdout.strip() == "active")


def _mkdir(path: Path) -> None:
    # Owned by the user even if this ever runs with more rights than the user's own.
    made = [p for p in (path, *path.parents) if not p.exists()]
    path.mkdir(parents=True, exist_ok=True)
    for p in made:
        try:
            os.chown(p, UID, GID)
        except OSError:
            pass


def _read() -> dict:
    cfg = json.loads(json.dumps(DEFAULT))
    try:
        saved = json.loads(CFG.read_text())
        if isinstance(saved, dict):
            cfg.update(saved)
    except (OSError, ValueError):
        pass
    if not isinstance(cfg.get("bindings"), dict):
        cfg["bindings"] = {}
    if not isinstance(cfg.get("profiles"), dict) or not cfg["profiles"]:
        cfg["profiles"] = json.loads(json.dumps(DEFAULT["profiles"]))
    return cfg


def _write(cfg: dict) -> None:
    """Written whole and renamed into place, so the pad, which reads this file once a second, never sees half of it."""
    _mkdir(CFG.parent)
    fd, tmp = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=str(CFG.parent))
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o644)
    os.chown(tmp, UID, GID)
    os.replace(tmp, CFG)


def _copy_if_changed(source: Path, target: Path, mode: int) -> bool:
    changed = not target.exists() or source.read_bytes() != target.read_bytes()
    if changed:
        shutil.copy2(source, target)
    os.chmod(target, mode)
    os.chown(target, UID, GID)
    return changed


def _install_runtime() -> bool:
    """Copy the driver and the user service into the user's home. Returns True if anything changed."""
    changed = False
    _mkdir(APP / "bin")
    for source in (PLUGIN / "driver/bin").glob("*.py"):
        changed |= _copy_if_changed(source, APP / "bin" / source.name, 0o755 if source.name == "jarngrip.py" else 0o644)
    for source in (PLUGIN / "driver").glob("*.py"):
        changed |= _copy_if_changed(source, APP / source.name, 0o644)
    _mkdir(APP / "fonts")
    for source in (PLUGIN / "driver/fonts").iterdir():
        changed |= _copy_if_changed(source, APP / "fonts" / source.name, 0o644)
    unit_dir = HOME / ".config/systemd/user"
    _mkdir(unit_dir)
    changed |= _copy_if_changed(PLUGIN / "systemd" / UNIT, unit_dir / UNIT, 0o644)
    if changed:
        _systemctl("daemon-reload")
    _install_desktop_entries(bool(_read().get("desktop_mode")))
    return changed


def _install_desktop_entries(autostart: bool) -> None:
    """The Desktop Mode app-menu entry always; the autostart entry only while "Start with Desktop Mode" is on. Neither
    touches the Game Mode service."""
    for target, source, wanted in ((APP_MENU, "jarngrip.desktop", True),
                                   (AUTOSTART, "jarngrip-autostart.desktop", autostart)):
        if wanted:
            _mkdir(target.parent)
            _copy_if_changed(PLUGIN / "desktop" / source, target, 0o644)
        else:
            target.unlink(missing_ok=True)


def _backgrounds() -> list:
    try:
        return sorted(p.name for p in BACKGROUNDS.iterdir() if p.is_file() and p.suffix.lower() in PICTURE_TYPES)
    except OSError:
        return []


def _restore_paused() -> None:
    try:
        paused = json.loads(MARKER.read_text())
    except (OSError, ValueError):
        paused = {}
    MARKER.unlink(missing_ok=True)
    for key, unit in PAUSED_UNITS:
        if isinstance(paused, dict) and paused.get(key):
            _systemctl("start", unit)


def _number(value, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


class Plugin:
    async def _main(self):
        changed = _install_runtime()
        # Apply updates to a running pad, but never auto-start after a Decky reload. A stale enabled flag must not
        # grab the digitizer during a Game Mode -> Desktop Mode transition (Ratatoskr issue #34).
        if changed and _active(UNIT):
            _systemctl("restart", UNIT)

    async def get_status(self):
        return {"enabled": _active(UNIT), "profile": _read().get("active_profile", "Default")}

    async def get_config(self):
        return _read()

    async def set_enabled(self, enabled):
        _install_runtime()
        if enabled:
            paused = {key: _active(unit) for key, unit in PAUSED_UNITS}
            _mkdir(MARKER.parent)
            MARKER.write_text(json.dumps(paused))
            os.chown(MARKER, UID, GID)
            for key, unit in PAUSED_UNITS:
                if paused[key]:
                    _systemctl("stop", unit)
            started = _systemctl("start", UNIT)
            # A simple service counts as started the moment its process exists. Give the pad time to fail (no uinput,
            # no bottom display) before believing it, so a pad that dies at once does not leave the bottom screen dead.
            if started:
                await asyncio.sleep(1.5)
            if not started or not _active(UNIT):
                _restore_paused()
                return {"enabled": False, "error": "The pad did not start; the bottom screen was given back."}
        else:
            _systemctl("stop", UNIT)
            if _active(UNIT):
                return {"enabled": True, "error": "The pad did not stop; the bottom screen was left as it is."}
            _restore_paused()
        return await self.get_status()

    async def save_config(self, cfg):
        """Save the settings the Decky panel changes. Anything missing keeps its saved value; anything invalid is
        ignored."""
        if not isinstance(cfg, dict):
            return {"ok": False, "error": "expected a configuration object"}
        current = _read()
        if isinstance(cfg.get("bindings"), dict):
            current["bindings"] = cfg["bindings"]
        current["sensitivity"] = _number(cfg.get("sensitivity"), 0.2, 3.0, current["sensitivity"])
        current["haptics_strength"] = _number(cfg.get("haptics_strength"), 0.05, 1.0, current["haptics_strength"])
        current["glass_blur"] = int(_number(cfg.get("glass_blur"), 1, 5, current["glass_blur"]))
        for key in ("haptics", "burn_in", "clock_24h", "desktop_mode"):
            if key in cfg:
                current[key] = bool(cfg[key])
        if "desktop_mode" in cfg:
            _install_desktop_entries(current["desktop_mode"])
        if cfg.get("theme") in THEMES:
            current["theme"] = cfg["theme"]
        if cfg.get("background_image") == "" or cfg.get("background_image") in _backgrounds():
            current["background_image"] = cfg["background_image"]
        _write(current)
        return {"ok": True, "config": current}

    async def list_backgrounds(self):
        _mkdir(BACKGROUNDS)
        return {"folder": str(BACKGROUNDS), "pictures": _backgrounds()}

    async def select_profile(self, name):
        cfg = _read()
        profile = cfg["profiles"].get(name)
        if not isinstance(profile, dict):
            return {"ok": False, "error": "unknown profile"}
        cfg["bindings"] = dict(profile.get("bindings") or {})
        cfg["active_profile"] = name
        _write(cfg)
        return {"ok": True, "config": cfg}

    async def save_profile(self, name):
        """Save the current bindings as a profile, new or existing, and make it the active one."""
        name = name.strip() if isinstance(name, str) else ""
        if not 0 < len(name) <= 24:
            return {"ok": False, "error": "A profile name is 1 to 24 characters."}
        cfg = _read()
        cfg["profiles"][name] = {"bindings": dict(cfg["bindings"])}
        cfg["active_profile"] = name
        _write(cfg)
        return {"ok": True, "config": cfg}

    async def delete_profile(self, name):
        cfg = _read()
        if name not in cfg["profiles"] or len(cfg["profiles"]) == 1:
            return {"ok": False, "error": "The last profile cannot be deleted."}
        del cfg["profiles"][name]
        if cfg["active_profile"] == name:
            cfg["active_profile"] = next(iter(cfg["profiles"]))
            cfg["bindings"] = dict(cfg["profiles"][cfg["active_profile"]].get("bindings") or {})
        _write(cfg)
        return {"ok": True, "config": cfg}

    async def stop(self):
        return await self.set_enabled(False)
