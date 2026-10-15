#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""JarnGrip: the bottom-screen window, the touchscreen reader and the pad's lifecycle, in Game Mode (the systemd
service, in the bottom gamescope session) or in Desktop Mode (--desktop, an app on the KDE desktop).

What is on the screen and what a touch does is in pad_model.py, how it looks is in pad_draw.py, and finding the
digitizer is in touch_device.py. The virtual mouse and keyboard, the gesture engine, the touch-frame parser and the
burn-in protection come from Ratatoskr (engine.py, touch_frames.py, burn_in.py).
"""
from __future__ import annotations

import ctypes
import fcntl
import json
import os
import select
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # debug_codes.py sits one level up

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

import haptics  # noqa: E402
import pad_draw  # noqa: E402
import system_status  # noqa: E402
import touch_device  # noqa: E402
from burn_in import BurnInProtector  # noqa: E402
from debug_codes import DebugCode, DebugLogger  # noqa: E402
from engine import SCREEN_HEIGHT, SCREEN_WIDTH, TouchGestureProcessor, UInputBridge  # noqa: E402
from pad_model import FLASH_S, PadController  # noqa: E402
from touch_frames import EVENT_STRUCT, TouchFrameParser  # noqa: E402

CONFIG = Path.home() / ".config/jarngrip/config.json"
# Written by the Decky backend when it starts the pad: which bottom-screen services it stopped to make room.
MARKER = Path.home() / ".local/state/jarngrip/restore.json"
# Pictures for the Game Glass theme; the Decky panel lists this folder.
BACKGROUNDS = Path.home() / "Pictures/JarnGrip"
# Held for the pad's lifetime, so that the Game Mode service and a Desktop Mode launch never run two pads at once.
LOCK = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "jarngrip.lock"
RESTORE_UNITS = (("ratatoskr", "touch-master.service"), ("bottom_screen", "armada-bottom-screen.service"))
TOUCH_RETRY_S = 3


def load_config() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def save_config_value(key: str, value) -> None:
    """Change one setting in the config file, keeping the rest. Written whole and renamed into place, like the Decky
    panel does, so neither ever reads half a file."""
    cfg = load_config()
    cfg[key] = value
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=str(CONFIG.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(cfg, f, indent=2)
        os.chmod(tmp, 0o644)
        os.replace(tmp, CONFIG)
    except BaseException:
        os.unlink(tmp)
        raise


class PrivateLogger(DebugLogger):
    """The debug log without a line per key press: together those would be a record of everything typed."""

    def log(self, code: DebugCode, details: str = "") -> None:
        if code != DebugCode.STATUS_KEY_PRESS:
            super().log(code, details)


def load_fonts(folder: Path) -> set:
    """Make the bundled fonts (Cinzel for Classic, Nunito for Game Glass) available to this process alone, through
    fontconfig, which cairo finds fonts with. Returns the families loaded; a theme whose font is missing falls back."""
    try:
        fontconfig = ctypes.CDLL("libfontconfig.so.1")
        fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    except (OSError, AttributeError):
        return set()
    return {path.stem.split("-")[0] for path in sorted(folder.glob("*.ttf"))  # Cinzel-Bold.ttf is Cinzel
            if fontconfig.FcConfigAppFontAddFile(None, str(path).encode())}


def _number(cfg: dict, key: str, default: float) -> float:
    try:
        return float(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def take_lock() -> int | None:
    """The single-pad lock, or None if another pad holds it. Released when the process ends, however it ends."""
    try:
        fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return fd


class PadApp:
    def __init__(self, desktop: bool = False) -> None:
        # In Desktop Mode the pad is an ordinary app on the KDE desktop's bottom screen, not the Game Mode service in
        # the bottom gamescope session.
        self.desktop = desktop
        self.logger = DebugLogger("jarngrip")
        self.logger.log(DebugCode.DAEMON_STARTING, "Desktop Mode" if desktop else "Game Mode")
        pad_draw.LOADED_FONTS = load_fonts(Path(__file__).resolve().parent.parent / "fonts")
        if pad_draw.LOADED_FONTS != {"Cinzel", "Nunito"}:
            self.logger.log(DebugCode.ERR_CAIRO_RENDER, f"bundled fonts loaded: {sorted(pad_draw.LOADED_FONTS)}")
        self.exit_code = 0
        self.stop = threading.Event()
        # Touch frames arrive on the reader thread; config changes and shutdown happen on the GTK thread.
        self.lock = threading.RLock()
        self.touch_fd = -1
        self.touch_status = "looking for the bottom touchscreen"
        self.reader: threading.Thread | None = None
        self.parser: TouchFrameParser | None = None
        self._config_mtime: int | None = -1
        self._cleaned = False
        self._last_error_log = 0.0

        # Created before anything is grabbed: if /dev/uinput is not usable, the pad exits without touching the digitizer.
        self.bridge = UInputBridge(PrivateLogger("uinput"))
        self.gesture = TouchGestureProcessor(self.bridge)
        self.haptics = haptics.Haptics()
        self.haptic_settings = (True, 1.0, 40, "")  # enabled, strength, pulse length in ms, forced effect type
        # Burn-in protection (from Ratatoskr): a slow 1.5 px drift, trackpad hints that fade, and dimming when idle.
        self.burn_in = BurnInProtector(shift_radius=1.5, cycle_seconds=90.0, idle_timeout=60.0, idle_floor=0.4,
                                       hint_duration=5.0)
        self.burn_in_on = True
        self._burn_state: tuple = ()
        self._last_view = ""
        self.clock_24h = False
        self._backdrop_key: tuple | None = None  # (picture, blur) the backdrop was made from
        self._logged_size: tuple = ()
        self.pad = PadController(self.bridge, self.gesture, on_change=self._changed,
                                 on_close=lambda: GLib.idle_add(self._close_pad), haptic=self.haptics.pulse,
                                 on_theme=lambda theme: GLib.idle_add(self._save_theme, theme), later=self._later)
        self.pad.set_page_by_title(str(load_config().get("page", "")))

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("JarnGrip")
        self.window.set_decorated(False)
        if desktop:
            # Never take the keyboard focus from the game: the pad's keys go to whichever window has it.
            self.window.set_accept_focus(False)
            self.window.set_focus_on_map(False)
            self._fullscreen_on_bottom_screen()
        else:
            # The bottom gamescope session is the bottom screen alone, at 1240 by 1080.
            self.window.set_resizable(False)
            self.window.set_default_size(SCREEN_WIDTH, SCREEN_HEIGHT)
            self.window.fullscreen()
        self.window.connect("destroy", lambda *_: Gtk.main_quit())
        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.on_draw)
        self.window.add(self.area)

    def _later(self, delay: float, job) -> None:
        """For the pad: run job after delay seconds, under the touch lock, without the touch thread waiting for it."""
        def run() -> None:
            with self.lock:
                job()

        timer = threading.Timer(delay, run)
        timer.daemon = True
        timer.start()

    def _fullscreen_on_bottom_screen(self) -> None:
        """Desktop Mode: fullscreen on the bottom screen. The window is sized in the desktop's units, which KDE scales
        (443 by 386 at 2.8 for the Thor's bottom screen), and must stay resizable: on Wayland a fixed-size window keeps
        its size even when made fullscreen. The painter scales the pad to whatever size the window gets."""
        display = Gdk.Display.get_default()
        sizes = [(m.get_geometry().width, m.get_geometry().height)
                 for m in (display.get_monitor(i) for i in range(display.get_n_monitors()))]
        index = system_status.bottom_screen(sizes)
        self.logger.log(DebugCode.DISPLAY_OK, f"screens {sizes}, the pad takes screen {index}")
        if index is None:
            self.window.fullscreen()
            return
        self.window.set_default_size(*sizes[index])
        self.window.fullscreen_on_monitor(self.window.get_screen(), index)

    def start(self) -> None:
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)
        GLib.timeout_add(250, self._burn_in_tick)
        if self._start_touch():
            GLib.timeout_add_seconds(TOUCH_RETRY_S, self._start_touch)
        self.window.show_all()
        self.logger.log(DebugCode.DAEMON_READY, self.touch_status)

    # ------------------------------------------------------------------ drawing

    def _changed(self) -> None:
        """Called by the pad (on either thread) when something visible changed."""
        GLib.idle_add(self._redraw)
        GLib.timeout_add(int(FLASH_S * 1000) + 20, self._redraw)  # and once more when a tapped button stops being lit

    def _redraw(self) -> bool:
        self.area.queue_draw()
        return False

    def on_draw(self, area, cr) -> bool:
        width, height = area.get_allocated_width(), area.get_allocated_height()
        if self.desktop and (width, height) != self._logged_size:
            self._logged_size = (width, height)
            self.logger.log(DebugCode.DISPLAY_OK, f"the pad's window is {width} by {height}")
        if (width, height) != (SCREEN_WIDTH, SCREEN_HEIGHT) and width > 0 and height > 0:
            cr.scale(width / SCREEN_WIDTH, height / SCREEN_HEIGHT)
        try:
            # Not under the lock: painting only reads the pad's state, and a touch must never wait for a repaint.
            pad_draw.paint(cr, self.pad)
        except Exception as err:
            self._log_error(DebugCode.ERR_CAIRO_RENDER, f"{type(err).__name__}: {err}")
        return False

    def _log_error(self, code: DebugCode, text: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log > 5.0:
            self._last_error_log = now
            self.logger.log(code, text)

    # ------------------------------------------------------------------ configuration

    def _tick(self) -> bool:
        """Once a second: pick up a changed config file (the Decky panel writes it) and refresh the settings view."""
        try:
            mtime = CONFIG.stat().st_mtime_ns
        except OSError:
            mtime = None
        if mtime != self._config_mtime:
            self._config_mtime = mtime
            cfg = load_config()
            with self.lock:
                self.pad.apply_config(cfg)
            self.haptic_settings = (bool(cfg.get("haptics", True)), _number(cfg, "haptics_strength", 1.0),
                                    int(_number(cfg, "haptics_ms", 40)), str(cfg.get("haptics_effect", "")))
            self.burn_in_on = bool(cfg.get("burn_in", True))
            self.burn_in.idle_timeout = max(5.0, _number(cfg, "dim_after_s", 60.0))
            self.burn_in.idle_floor = max(0.1, min(1.0, _number(cfg, "dim_level", 0.4)))
            self.clock_24h = bool(cfg.get("clock_24h", False))
            self._update_backdrop(cfg)
            self.area.queue_draw()  # the theme may have changed
        status = self.haptics.status
        self.haptics.configure(*self.haptic_settings)  # not under self.lock: it can wait on InputPlumber
        if self.haptics.status != status:
            self.logger.log(DebugCode.HAPTICS_OK if self.haptics.fd >= 0 else DebugCode.ERR_HAPTICS,
                            self.haptics.status)
        self._refresh_info()
        percent, charging = system_status.read_battery()
        status_info = (system_status.clock_text(self.clock_24h), percent, charging)
        if status_info != self.pad.status_info:
            self.pad.status_info = status_info
            self.area.queue_draw()
        return True

    def _update_backdrop(self, cfg: dict) -> None:
        """Make the Game Glass backdrop when that theme is on and its picture or blur changed; drop it otherwise."""
        if self.pad.theme != "glass":
            self.pad.backdrop, self._backdrop_key = None, None
            return
        name = Path(str(cfg.get("background_image") or "")).name  # a file in BACKGROUNDS, never a path elsewhere
        halvings = int(max(1, min(5, _number(cfg, "glass_blur", 3))))
        if (name, halvings) == self._backdrop_key:
            return
        self._backdrop_key = (name, halvings)
        backdrop = None
        if name:
            try:
                # Loaded at no more than twice the screen size: a camera photo would otherwise take a lot of memory.
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(BACKGROUNDS / name), 2 * SCREEN_WIDTH,
                                                                 2 * SCREEN_HEIGHT, True)
                pixbuf = pixbuf.apply_embedded_orientation() or pixbuf
                surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, 1, None)
                backdrop = pad_draw.make_backdrop(surface, pixbuf.get_width(), pixbuf.get_height(), halvings)
            except GLib.Error as err:
                self.logger.log(DebugCode.ERR_CAIRO_RENDER, f"could not load the background {name}: {err.message}")
        self.pad.backdrop = backdrop or pad_draw.default_backdrop(halvings)

    def _burn_in_tick(self) -> bool:
        """Four times a second: move the drift along and fade the dimming and hints, redrawing only when that shows."""
        pad, burn = self.pad, self.burn_in
        if pad.view != self._last_view:
            self._last_view = pad.view
            burn.notify_mode_change()  # a new view shows its hints again
        if self.burn_in_on:
            pad.shift, pad.brightness, pad.hint_alpha = (burn.get_orbital_offset(), burn.get_luminance_scale(),
                                                         burn.get_hint_alpha())
        else:
            pad.shift, pad.brightness, pad.hint_alpha = (0.0, 0.0), 1.0, 1.0
        state = (round(pad.shift[0] * 4), round(pad.shift[1] * 4), round(pad.brightness * 50), round(pad.hint_alpha * 20))
        if state != self._burn_state:
            self._burn_state = state
            self.area.queue_draw()
        return True

    def _save_theme(self, theme: str) -> bool:
        self.area.queue_draw()
        try:
            save_config_value("theme", theme)
        except (OSError, ValueError) as err:
            self.logger.log(DebugCode.SETTINGS_UPDATED, f"could not save the theme: {err}")
        self._update_backdrop(load_config())
        return False

    def _refresh_info(self) -> None:
        info = [
            f"Touch: {self.touch_status}",
            f"Trackpad sensitivity: {self.gesture.sensitivity:.1f}",
            f"Haptics: {self.haptics.status}",
            "Swipe a number up for Shift, down for Ctrl, or left to cancel it.",
        ]
        if info != self.pad.info_lines:
            self.pad.info_lines = info
            if self.pad.view == "settings":
                self.area.queue_draw()

    # ------------------------------------------------------------------ touchscreen

    def _start_touch(self) -> bool:
        """Find and grab the bottom touchscreen. Returns True while it is still missing, so that a GLib timeout
        calling this keeps trying."""
        if self.stop.is_set() or self.touch_fd >= 0:
            return False
        node = touch_device.find_bottom_touchscreen()
        if not node:
            self._set_touch_status("no bottom touchscreen found", DebugCode.ERR_TOUCH_MISSING)
            return True
        try:
            fd = touch_device.open_and_grab(node)
        except OSError as err:
            self._set_touch_status(f"cannot take {node}: {err}", DebugCode.ERR_TOUCH_GRAB)
            return True
        self.touch_fd = fd
        self.parser = TouchFrameParser(touch_device.to_screen_for(fd))
        self._set_touch_status(f"{node} ({touch_device.device_name(fd)})", DebugCode.TOUCH_OK)
        self.reader = threading.Thread(target=self._read_touch, args=(fd, self.parser), daemon=True)
        self.reader.start()
        return False

    def _set_touch_status(self, status: str, code: DebugCode) -> None:
        if status != self.touch_status:  # the retry runs every few seconds: say each thing once
            self.touch_status = status
            self.logger.log(code, status)
            self._refresh_info()

    def _read_touch(self, fd: int, parser: TouchFrameParser) -> None:
        while not self.stop.is_set():
            try:
                ready, _, _ = select.select([fd], [], [], 0.1)
                if not ready:
                    with self.lock:
                        self.pad.expire(time.time())  # kernel event timestamps are wall-clock
                    continue
                data = os.read(fd, EVENT_STRUCT.size * 256)
            except BlockingIOError:
                continue
            except (OSError, ValueError) as err:
                if not self.stop.is_set():
                    # The digitizer went away (resume, re-enumeration). Give it up cleanly and look for it again:
                    # ending this thread silently would leave the grab held and the bottom screen dead.
                    self.logger.log(DebugCode.ERR_TOUCH_READ, f"touch device lost ({err}); looking for it again")
                    GLib.idle_add(self._touch_lost)
                return
            if not data:
                time.sleep(0.05)
                continue
            try:
                with self.lock:
                    for frame in parser.feed(data):
                        self._dispatch(frame)
            except Exception as err:  # one bad frame must not end touch input while the grab is still held
                self._log_error(DebugCode.ERR_TOUCH_READ, f"touch handler error: {type(err).__name__}: {err}")

    def _dispatch(self, frame) -> None:
        pad = self.pad
        if frame.downs or frame.moves:
            self.burn_in.record_touch()  # wakes a dimmed pad
        pad.expire(frame.ts)
        if frame.dropped:
            # The kernel's buffer overflowed and the contact state is gone: let go of everything, then read back
            # the fingers that are still down.
            self.logger.log(DebugCode.ERR_TOUCH_READ, "SYN_DROPPED: contact state discarded")
            pad.release_everything()
            try:
                slots = touch_device.read_mt_slots(self.touch_fd)
            except (OSError, struct.error) as err:
                self.logger.log(DebugCode.ERR_TOUCH_READ, f"could not read the touch slots after SYN_DROPPED: {err}")
                return
            for tid, x, y in self.parser.resync(slots, time.time()).downs:
                pad.touch_down(tid, x, y, frame.ts)
            return
        for tid in frame.ups:
            pad.touch_up(tid, frame.ts)
        for tid, x, y in frame.downs:
            pad.touch_down(tid, x, y, frame.ts)
            where = pad.last_touch[2] or "nothing"
            # A keyboard touch is logged without its key or position: the log must not spell out what was typed.
            self.logger.log(DebugCode.STATUS_TOUCH_DOWN, "on the keyboard" if where.startswith("key:")
                            else f"({x:.0f}, {y:.0f}) on {where}")
        for tid, x, y in frame.moves:
            pad.touch_move(tid, x, y, frame.ts)
        if frame.live == 0 and not frame.downs:
            pad.all_lifted(frame.ts)

    def _touch_lost(self) -> bool:
        if self.touch_fd >= 0:
            touch_device.release(self.touch_fd)
            self.touch_fd = -1
        with self.lock:
            self.pad.release_everything()
        if not self.stop.is_set() and self._start_touch():
            GLib.timeout_add_seconds(TOUCH_RETRY_S, self._start_touch)
        return False

    # ------------------------------------------------------------------ shutdown

    def _close_pad(self) -> bool:
        """"Close pad" on the settings view: give the bottom screen back without needing the Decky panel. The services
        the pad displaced conflict with its unit, so starting them makes systemd stop the pad; with none to start,
        the pad just quits. In Desktop Mode it just quits: the bottom screen goes back to the desktop."""
        if self.desktop:
            Gtk.main_quit()
            return False
        try:
            previous = json.loads(MARKER.read_text())
        except (OSError, ValueError):
            previous = {}
        # armada-run-bottom loads the bottom session's environment: point systemctl at the user manager explicitly.
        runtime = f"/run/user/{os.getuid()}"
        env = dict(os.environ, XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS=f"unix:path={runtime}/bus")
        for key, unit in RESTORE_UNITS:
            if isinstance(previous, dict) and previous.get(key):
                try:
                    subprocess.run(["systemctl", "--user", "start", "--no-block", unit], env=env, timeout=5, check=False)
                except (OSError, subprocess.SubprocessError) as err:
                    self.logger.log(DebugCode.DAEMON_STOPPING, f"could not start {unit}: {err}")
        try:
            MARKER.unlink()
        except OSError:
            pass
        Gtk.main_quit()
        return False

    def request_quit(self, signum: int = 0) -> bool:
        """Leave the main loop so that cleanup() runs. systemd stops the service with SIGTERM."""
        self.logger.log(DebugCode.DAEMON_STOPPING, signal.Signals(signum).name if signum else "quit request")
        Gtk.main_quit()
        return False

    def cleanup(self) -> None:
        """Give the hardware back: every held key and button, the touchscreen grab, the virtual devices. Safe to call
        more than once, and each step is guarded so that one failure cannot skip the rest."""
        if self._cleaned:
            return
        self._cleaned = True
        self.stop.set()
        if self.reader is not None:
            self.reader.join(timeout=0.5)

        def release_touch() -> None:
            if self.touch_fd >= 0:
                touch_device.release(self.touch_fd)
                self.touch_fd = -1

        for name, step in (("held keys", self.pad.release_everything), ("touchscreen grab", release_touch),
                           ("vibration motor", self.haptics.close), ("virtual devices", self.bridge.close)):
            try:
                step()
            except Exception as err:
                self.logger.log(DebugCode.DAEMON_STOPPING, f"cleanup step '{name}' failed: {type(err).__name__}: {err}")
        self.logger.log(DebugCode.DAEMON_STOPPED)


def main() -> None:
    desktop, autostart = "--desktop" in sys.argv, "--autostart" in sys.argv
    if autostart and not load_config().get("desktop_mode"):
        return  # the Desktop Mode autostart entry outlived its setting
    if take_lock() is None:
        DebugLogger("jarngrip").log(DebugCode.DAEMON_STOPPING, "another pad is already running")
        return
    app = PadApp(desktop)
    # The default action for SIGTERM ends the process on the spot and skips cleanup(). Leave the main loop instead.
    try:
        from gi.repository import GLibUnix  # GLib.unix_signal_add is deprecated in favour of this

        signal_add = GLibUnix.signal_add
    except (ImportError, AttributeError):
        signal_add = GLib.unix_signal_add
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal_add(GLib.PRIORITY_HIGH, sig, app.request_quit, sig)
    app.start()
    try:
        Gtk.main()
    finally:
        app.cleanup()
    sys.exit(app.exit_code)


if __name__ == "__main__":
    main()
