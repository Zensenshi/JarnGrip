# SPDX-License-Identifier: MIT
# From Ratatoskr (https://github.com/venatrix-ritz/Ratatoskr), MIT License, Copyright (c) 2026 Ven (venatrix-ritz) and
# Thor Input Contributors; see driver/RATATOSKR-MIT-LICENSE.txt. Changed here: the log file (private, kept small) and the
# 8xx haptics codes.
"""Ratatoskr Diagnostic & Debug Code Registry."""
from __future__ import annotations

import glob
import os
import time
from enum import IntEnum

# In the user's own runtime folder (/run/user/<uid>, which only they can read), not the shared /tmp where Ratatoskr
# keeps /tmp/thor-input-debug.log.
LOG_PATH = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "jarngrip-debug.log")
LOG_MAX_BYTES = 1 << 20  # then the log starts over, keeping the previous one as .1


class DebugCode(IntEnum):
    # 0xx: Operational / Success
    OK = 0
    DAEMON_STARTING = 1
    DAEMON_READY = 2
    DAEMON_STOPPING = 3
    DAEMON_STOPPED = 4

    # 1xx: Virtual Input Subsystem (/dev/uinput)
    UINPUT_OK = 100
    ERR_UINPUT_OPEN = 101       # Cannot open /dev/uinput (permission or missing)
    ERR_UINPUT_SETUP = 102      # ioctl UI_DEV_SETUP failed
    ERR_UINPUT_CREATE = 103     # ioctl UI_DEV_CREATE failed
    ERR_UINPUT_WRITE = 104      # write() to uinput fd failed

    # 2xx: Physical Touch Digitizer (/dev/input/event*)
    TOUCH_OK = 200
    ERR_TOUCH_MISSING = 201     # bottom_touchscreen device not found in /sys/class/input
    ERR_TOUCH_OPEN = 202        # Cannot open /dev/input/event*
    ERR_TOUCH_GRAB = 203        # EVIOCGRAB failed (another process has exclusive grab)
    ERR_TOUCH_READ = 204        # read() failed or format error

    # 3xx: IPC Socket Subsystem (/run/user/1000/thor-input.sock)
    SOCKET_OK = 300
    ERR_SOCKET_BIND = 301       # Cannot bind to socket path
    ERR_SOCKET_CONNECT = 302    # Cannot connect to running daemon
    ERR_SOCKET_PROTOCOL = 303   # Bad JSON or unrecognized action
    ERR_SOCKET_TIMEOUT = 304    # Timeout waiting for response

    # 4xx: Display / Window Subsystem (Gamescope secondary display :2)
    DISPLAY_OK = 400
    ERR_DISPLAY_CONN = 401      # Gtk.init_check() failed on DISPLAY=:2
    ERR_CAIRO_RENDER = 402      # Cairo surface error

    # 5xx: Live Gesture & Keystroke Telemetry
    STATUS_TOUCH_DOWN = 501
    STATUS_TOUCH_MOVE = 502
    STATUS_TOUCH_UP = 503
    STATUS_CLICK_LEFT = 510
    STATUS_CLICK_RIGHT = 511
    STATUS_CLICK_MIDDLE = 512
    STATUS_SCROLL = 520
    STATUS_EDGE_SCROLL = 521
    STATUS_PINCH_ZOOM = 522
    STATUS_SWIPE_NAV = 523
    STATUS_DRAG_LOCK = 524
    STATUS_LONG_PRESS = 525
    STATUS_GLIDE_START = 530
    STATUS_KEY_PRESS = 540

    # 6xx: Settings & Quick Controls
    SETTINGS_UPDATED = 600
    BACKLIGHT_UPDATED = 601
    VOLUME_UPDATED = 602
    DIM_MIRROR = 610            # bottom screen follows Steam's idle-dim timer

    # 7xx: Hardware Controls Errors
    ERR_BACKLIGHT_SYSFS = 701
    ERR_PIPEWIRE_WPCTL = 702

    # 8xx: Haptics (force-feedback vibration motor)
    HAPTICS_OK = 800
    ERR_HAPTICS = 801           # no motor found, or it could not be opened or driven


CODE_DESCRIPTIONS: dict[DebugCode, str] = {
    DebugCode.OK: "Healthy",
    DebugCode.DAEMON_STARTING: "Daemon starting up",
    DebugCode.DAEMON_READY: "Daemon ready and listening",
    DebugCode.DAEMON_STOPPING: "Daemon stopping",
    DebugCode.DAEMON_STOPPED: "Daemon stopped",
    DebugCode.UINPUT_OK: "UInput devices operational",
    DebugCode.ERR_UINPUT_OPEN: "Failed to open /dev/uinput",
    DebugCode.ERR_UINPUT_SETUP: "Failed UI_DEV_SETUP ioctl",
    DebugCode.ERR_UINPUT_CREATE: "Failed UI_DEV_CREATE ioctl",
    DebugCode.ERR_UINPUT_WRITE: "Failed to write event to uinput",
    DebugCode.TOUCH_OK: "Bottom touchscreen grabbed",
    DebugCode.ERR_TOUCH_MISSING: "bottom_touchscreen device not found",
    DebugCode.ERR_TOUCH_OPEN: "Cannot open touchscreen device",
    DebugCode.ERR_TOUCH_GRAB: "EVIOCGRAB failed (exclusive lock held)",
    DebugCode.ERR_TOUCH_READ: "Error reading touch events",
    DebugCode.SOCKET_OK: "UNIX IPC socket ready",
    DebugCode.ERR_SOCKET_BIND: "Cannot bind IPC socket",
    DebugCode.ERR_SOCKET_CONNECT: "Cannot connect to IPC socket",
    DebugCode.ERR_SOCKET_PROTOCOL: "IPC protocol parsing error",
    DebugCode.ERR_SOCKET_TIMEOUT: "IPC communication timed out",
    DebugCode.DISPLAY_OK: "Display pipeline connected",
    DebugCode.ERR_DISPLAY_CONN: "Cannot connect to secondary display :2",
    DebugCode.ERR_CAIRO_RENDER: "Rendering engine failure",
    DebugCode.STATUS_TOUCH_DOWN: "Touch contact detected",
    DebugCode.STATUS_TOUCH_MOVE: "Pointer motion processed",
    DebugCode.STATUS_TOUCH_UP: "Touch contact released",
    DebugCode.STATUS_CLICK_LEFT: "Left click emitted",
    DebugCode.STATUS_CLICK_RIGHT: "Right click emitted",
    DebugCode.STATUS_CLICK_MIDDLE: "Middle click emitted",
    DebugCode.STATUS_SCROLL: "Scroll wheel emitted",
    DebugCode.STATUS_EDGE_SCROLL: "Edge scrollbar active",
    DebugCode.STATUS_PINCH_ZOOM: "Pinch zoom gesture emitted",
    DebugCode.STATUS_SWIPE_NAV: "Multi-finger navigation swipe emitted",
    DebugCode.STATUS_DRAG_LOCK: "Drag lock engaged",
    DebugCode.STATUS_LONG_PRESS: "Long press right click emitted",
    DebugCode.STATUS_GLIDE_START: "Momentum glide active",
    DebugCode.STATUS_KEY_PRESS: "Hardware keystroke emitted",
    DebugCode.SETTINGS_UPDATED: "Settings successfully updated",
    DebugCode.BACKLIGHT_UPDATED: "Display backlight brightness adjusted",
    DebugCode.VOLUME_UPDATED: "System volume level adjusted",
    DebugCode.DIM_MIRROR: "Bottom screen idle-dim mirror event",
    DebugCode.ERR_BACKLIGHT_SYSFS: "Backlight sysfs write failure",
    DebugCode.ERR_PIPEWIRE_WPCTL: "PipeWire wpctl execution failure",
    DebugCode.HAPTICS_OK: "Vibration motor in use",
    DebugCode.ERR_HAPTICS: "Haptics unavailable",
}


class DebugLogger:
    """Structured diagnostic logger writing to LOG_PATH and stdout."""

    def __init__(self, context: str = "core") -> None:
        self.context = context

    def log(self, code: DebugCode, details: str = "") -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        desc = CODE_DESCRIPTIONS.get(code, "Unknown")
        msg = f"[{ts}] [DBG-{int(code):03d}] [{self.context}] {desc}"
        if details:
            msg += f" - {details}"
        print(msg, flush=True)
        try:
            if os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
                os.replace(LOG_PATH, LOG_PATH + ".1")
        except OSError:
            pass
        try:
            # Readable by the user alone, and never written through a symbolic link.
            fd = os.open(LOG_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError:
            pass


def run_self_diagnostics() -> dict:
    """Runs a full hardware and OS level self-test."""
    report = {
        "timestamp": time.time(),
        "all_passed": True,
        "checks": {},
    }

    # 1. Check /dev/uinput
    uinput_ok = os.path.exists("/dev/uinput") and os.access("/dev/uinput", os.W_OK)
    report["checks"]["uinput"] = {
        "passed": uinput_ok,
        "code": int(DebugCode.UINPUT_OK if uinput_ok else DebugCode.ERR_UINPUT_OPEN),
        "detail": "/dev/uinput is writable" if uinput_ok else "No write access to /dev/uinput",
    }
    if not uinput_ok:
        report["all_passed"] = False

    # 2. Check bottom_touchscreen
    touch_node = None
    for p in glob.glob("/sys/class/input/event*/device/name"):
        try:
            with open(p, encoding="utf-8") as f:
                if f.read().strip() == "bottom_touchscreen":
                    touch_node = "/dev/input/" + p.split("/")[4]
                    break
        except OSError:
            pass

    touch_ok = touch_node is not None and os.access(touch_node, os.R_OK)
    report["checks"]["touchscreen"] = {
        "passed": touch_ok,
        "node": touch_node,
        "code": int(DebugCode.TOUCH_OK if touch_ok else DebugCode.ERR_TOUCH_MISSING),
        "detail": f"Found {touch_node} with read access" if touch_ok else "bottom_touchscreen not accessible",
    }
    if not touch_ok:
        report["all_passed"] = False

    # 3. Check IPC socket
    sock_path = f"/run/user/{os.getuid()}/thor-input.sock"
    sock_exists = os.path.exists(sock_path)
    report["checks"]["ipc_socket"] = {
        "path": sock_path,
        "active": sock_exists,
        "code": int(DebugCode.SOCKET_OK if sock_exists else DebugCode.ERR_SOCKET_CONNECT),
    }

    # 4. Check secondary display environment
    env_file = f"/run/user/{os.getuid()}/armada-bottom-env"
    env_ok = os.path.exists(env_file)
    report["checks"]["secondary_gamescope"] = {
        "passed": env_ok,
        "code": int(DebugCode.DISPLAY_OK if env_ok else DebugCode.ERR_DISPLAY_CONN),
        "detail": "Bottom display environment active" if env_ok else "Bottom display env missing",
    }

    return report
