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
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import decky  # Decky Loader's backend module; emit() sends an event to the plugin's frontend
except ImportError:
    decky = None


def _log(text: str, error: bool = False) -> None:
    """Into the plugin's Decky log (~/homebrew/logs/jarngrip/)."""
    if decky:
        (decky.logger.error if error else decky.logger.info)(text)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ayn_button  # noqa: E402

PLUGIN = Path(__file__).resolve().parent
HOME = Path("/var/home/armada")
UID = GID = 1000
APP = HOME / ".local/share/jarngrip"
CFG = HOME / ".config/jarngrip/config.json"
# Which bottom-screen services the pad stopped to make room, so that stopping the pad can bring them back.
MARKER = HOME / ".local/state/jarngrip/restore.json"
UNIT = "jarngrip.service"
UNIT_FILE = HOME / ".config/systemd/user" / UNIT
LISTENER_FILE = UNIT_FILE.parent / "jarngrip-ayn.service"
PAUSED_UNITS = (("ratatoskr", "touch-master.service"), ("bottom_screen", "armada-bottom-screen.service"))
THEMES = ("classic", "charcoal", "dark", "glass")
BACKGROUNDS = HOME / "Pictures/JarnGrip"
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
# Desktop Mode: the pad in the KDE app menu, and started with the desktop when "Start with Desktop Mode" is on.
APP_MENU = HOME / ".local/share/applications/jarngrip.desktop"
AUTOSTART = HOME / ".config/autostart/jarngrip.desktop"
# The AYN button below the screen (see ayn_button.py): looked for every few seconds, as InputPlumber's virtual devices
# come and go, and the profile change that stops its screenshot, kept here so that turning it off can undo it.
WATCH_RETRY_S = 5
AYN_STATE = HOME / ".local/state/jarngrip/inputplumber.json"
# The backend cannot read /dev/input: Decky runs it as the user but without the user's groups. A user service has them,
# so jarngrip-ayn.service (driver/bin/ayn_listen.py) listens and writes a byte per press into this FIFO.
LISTENER = "jarngrip-ayn.service"
AYN_FIFO = Path(f"/run/user/{UID}/jarngrip-ayn")
# The installer's marker: the polkit rule lets the user load InputPlumber profiles only while it exists.
INSTALLED_MARKER = Path("/var/lib/jarngrip/installed")
DEFAULT = {
    "enabled": False, "page": "Interface", "sensitivity": 1.0, "theme": "classic", "haptics": True,
    "haptics_strength": 1.0, "burn_in": True, "clock_24h": False, "background_image": "", "glass_blur": 3, "desktop_mode": False,
    "shortcut": True, "shortcut_buttons": [1 << 13 | 1 << 14, 0], "ayn_button": False,
    "ayn_no_screenshot": False,
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
    _mkdir(UNIT_FILE.parent)
    changed |= _copy_if_changed(PLUGIN / "systemd" / UNIT, UNIT_FILE, 0o644)
    changed |= _copy_if_changed(PLUGIN / "systemd" / LISTENER_FILE.name, LISTENER_FILE, 0o644)
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


def _open_fifo(path: Path) -> int:
    """The FIFO the AYN button listener writes presses into, made if missing and opened for reading. Opened read-write,
    so that it always has a writer: with none, a FIFO reads as ended and would wake the reader over and over."""
    try:
        if path.exists() and not stat.S_ISFIFO(path.stat().st_mode):
            path.unlink()
        if not path.exists():
            os.mkfifo(path, 0o600)
    except OSError as err:
        _log(f"AYN button: cannot make {path}: {err.strerror}", error=True)
    return os.open(path, os.O_RDWR | os.O_NONBLOCK)


def _number(value, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


class Plugin:
    _ignore_until = 0.0  # AYN button presses before this (time.monotonic()) queued up during a toggle
    _ayn_error = ""      # what went wrong the last time the AYN button's screenshot was changed
    _ayn_lock = None

    async def _main(self):
        changed = _install_runtime()
        # Apply updates to a running pad, but never auto-start after a Decky reload. A stale enabled flag must not
        # grab the digitizer during a Game Mode -> Desktop Mode transition (Ratatoskr issue #34).
        if changed and _active(UNIT):
            _systemctl("restart", UNIT)
        if changed and _active(LISTENER):
            _systemctl("restart", LISTENER)
        self._fifo = _open_fifo(AYN_FIFO)
        loop = asyncio.get_running_loop()
        self._tasks = [loop.create_task(self._read_presses(self._fifo)), loop.create_task(self._watch_ayn_button())]

    async def _unload(self):
        for task in getattr(self, "_tasks", []):
            task.cancel()
        if getattr(self, "_fifo", -1) >= 0:
            os.close(self._fifo)
            self._fifo = -1
        _systemctl("stop", LISTENER)
        # Only while JarnGrip runs: without it, a button that no longer takes screenshots would do nothing at all.
        await self._sync_screenshot(False)

    async def _uninstall(self):
        """Decky is removing the plugin (from its settings, or "Uninstall JarnGrip" in the panel): put back what JarnGrip
        changed and remove what it put in the user's home, as the uninstall script does. The settings stay. Root's files
        cannot go from here: the installer's backups and the polkit rule stay, but deleting the user's own marker makes
        the rule stop applying (see polkit/49-jarngrip-inputplumber.rules)."""
        await self._sync_screenshot(False)
        for unit in (UNIT, LISTENER):
            _systemctl("stop", unit)
        _restore_paused()
        for path in (UNIT_FILE, LISTENER_FILE, APP_MENU, AUTOSTART, AYN_STATE, INSTALLED_MARKER, AYN_FIFO):
            path.unlink(missing_ok=True)
        shutil.rmtree(APP, ignore_errors=True)
        _systemctl("daemon-reload")

    async def _sync_screenshot(self, wanted: bool | None = None) -> str:
        """Stop or bring back the AYN button's screenshot to match the settings (or wanted). InputPlumber is asked
        from a thread: each call can take a moment."""
        if wanted is None:
            cfg = _read()
            wanted = bool(cfg.get("ayn_button") and cfg.get("ayn_no_screenshot"))
        if self._ayn_lock is None:
            self._ayn_lock = asyncio.Lock()
        async with self._ayn_lock:
            self._ayn_error = await asyncio.to_thread(ayn_button.sync, wanted, AYN_STATE)
        return self._ayn_error

    async def _watch_ayn_button(self):
        """For as long as the plugin runs, every few seconds: keep the listener running while "AYN button" is on, and
        the screenshot setting applied, since InputPlumber forgets it when it restarts."""
        _log("AYN button: watching")
        while True:
            # Nothing that goes wrong in one round may end the watching: the button would go dead until Decky restarts.
            try:
                await self._watch_round()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _log(f"AYN button: {type(err).__name__}: {err}", error=True)
            await asyncio.sleep(WATCH_RETRY_S)

    async def _watch_round(self):
        wanted = bool(_read().get("ayn_button"))
        if wanted != await asyncio.to_thread(_active, LISTENER):
            started = await asyncio.to_thread(_systemctl, "start" if wanted else "stop", LISTENER)
            _log(f"AYN button: listener {'started' if wanted else 'stopped'}" if started
                 else f"AYN button: could not {'start' if wanted else 'stop'} {LISTENER}", error=not started)
        before = self._ayn_error
        if await self._sync_screenshot() != before:
            _log(f"AYN button: {self._ayn_error or 'screenshot setting applied'}", error=bool(self._ayn_error))

    async def _read_presses(self, fd: int):
        """Toggle the pad on each press the listener reports (a byte each) while "AYN button" is on."""
        loop = asyncio.get_running_loop()
        ready = asyncio.Event()
        loop.add_reader(fd, ready.set)
        try:
            while True:
                await ready.wait()
                ready.clear()
                try:
                    data = os.read(fd, 64)
                except BlockingIOError:
                    continue
                if not data:
                    return  # only in tests: the backend holds the FIFO's write end itself, so it never ends
                # Presses that queued up while the pad was starting or stopping are not a new request.
                if time.monotonic() >= self._ignore_until and _read().get("ayn_button"):
                    _log("AYN button: pressed, toggling the pad")
                    result = await self.set_enabled(not _active(UNIT))
                    self._ignore_until = time.monotonic() + 0.5
                    if decky:
                        await decky.emit("jarngrip_toggled", result)
        finally:
            loop.remove_reader(fd)

    async def get_status(self):
        return {"enabled": _active(UNIT), "profile": _read().get("active_profile", "Default"),
                "ayn_error": self._ayn_error}

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
        ayn_before = (current.get("ayn_button"), current.get("ayn_no_screenshot"))
        if isinstance(cfg.get("bindings"), dict):
            current["bindings"] = cfg["bindings"]
        current["sensitivity"] = _number(cfg.get("sensitivity"), 0.2, 3.0, current["sensitivity"])
        current["haptics_strength"] = _number(cfg.get("haptics_strength"), 0.05, 1.0, current["haptics_strength"])
        current["glass_blur"] = int(_number(cfg.get("glass_blur"), 1, 5, current["glass_blur"]))
        for key in ("haptics", "burn_in", "clock_24h", "desktop_mode", "shortcut", "ayn_button", "ayn_no_screenshot"):
            if key in cfg:
                current[key] = bool(cfg[key])
        if "desktop_mode" in cfg:
            _install_desktop_entries(current["desktop_mode"])
        buttons = cfg.get("shortcut_buttons")  # [ulButtons, ulUpperButtons] masks from Steam, as the panel records them
        if (isinstance(buttons, list) and len(buttons) == 2 and all(type(m) is int and 0 <= m < 1 << 32 for m in buttons)
                and any(buttons)):
            current["shortcut_buttons"] = buttons
        if cfg.get("theme") in THEMES:
            current["theme"] = cfg["theme"]
        if cfg.get("background_image") == "" or cfg.get("background_image") in _backgrounds():
            current["background_image"] = cfg["background_image"]
        _write(current)
        if (current.get("ayn_button"), current.get("ayn_no_screenshot")) != ayn_before:
            await self._watch_round()  # now, rather than within the next few seconds
            if self._ayn_error:
                return {"ok": True, "config": current, "error": self._ayn_error}
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
