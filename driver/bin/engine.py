# SPDX-License-Identifier: MIT
# Copied unchanged from Ratatoskr (https://github.com/venatrix-ritz/Ratatoskr), MIT License,
# Copyright (c) 2026 Ven (venatrix-ritz) and Thor Input Contributors. See driver/RATATOSKR-MIT-LICENSE.txt.
"""Thor Input Virtual Input Engine: UInput bridge & multi-touch gesture processor.

Gesture mathematics, coordinate transforms, and physics calculations credit to:
- Project Barry (https://github.com/project-barry/barry-launcher) by lavachemist.
"""
from __future__ import annotations

import math
import os
import struct
import threading
import time
from typing import Any

try:
    import fcntl
except ImportError:  # not Linux: the gesture engine still imports; only UInputBridge needs it
    fcntl = None

from debug_codes import DebugCode, DebugLogger

# Linux input subsystem constants from <linux/uinput.h> & <linux/input-event-codes.h>
UINPUT = "/dev/uinput"
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_DEV_SETUP = 0x405C5503

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

SYN_REPORT = 0
REL_X = 0x00
REL_Y = 0x01
REL_HWHEEL = 0x06
REL_WHEEL = 0x08
REL_WHEEL_HI_RES = 11
REL_HWHEEL_HI_RES = 12

BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112

# Standard event keycodes
KEY_ESC = 1
KEY_TAB = 15
KEY_LEFTCTRL = 29
KEY_LEFTALT = 56
KEY_LEFTMETA = 125  # Super / Windows key
KEY_F24 = 194  # no default binding anywhere: used for the harmless 'wake' tap

ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39

BUS_VIRTUAL = 0x06
EVENT_STRUCT = struct.Struct("llHHi")
SETUP_STRUCT = struct.Struct("HHHH80sI")

# Screen dimensions (bottom screen)
SCREEN_WIDTH = 1240
SCREEN_HEIGHT = 1080

# Gesture thresholds
TAP_MAX_TIME_S = 0.25
TAP_MAX_DISTANCE_PX = 12.0  # per finger; a tap with more travel than this is a move, not a click
LONG_PRESS_TIME_S = 0.45
LONG_PRESS_MAX_DIST_PX = 24.0
SCROLL_DIVISOR = 10.0
SWIPE_THRESHOLD_PX = 85.0
HI_RES_NOTCH = 120
# Game Mode's gamescope hides the pointer once it has not moved for --hide-cursor-delay (3000 ms on the Thor,
# refs/upstream/gamescope steamcompmgr.cpp checkSuspension). Pointer motion and buttons un-hide it, wheel events
# neither un-hide it nor restart the timer (wlserver.cpp wlserver_mousemotion / wlserver_mousewheel), and a hidden
# pointer's wheel does not reach Steam. A button press un-hides it only until the next check, because it does not
# restart the timer either (wlserver_mousebutton), so rapid tapping in one place loses the pointer after 3 s.
# So a scroll or a button press after the pointer has been still for this long is preceded by a net-zero
# one-pixel nudge, the same fix barry-launcher's inputd uses for scrolling (WAKE_POINTER_S = 2.0).
POINTER_WAKE_S = 2.0
# The Thor's touch controller sometimes loses a finger-lift: the kernel keeps reporting that contact as down
# (observed: a contact still held 57 s later, with every finger off the glass). A contact that has reported
# nothing for this long is treated as lifted. Just above the longest long-press delay (1.2 s) so a deliberate
# press-and-hold is not cut short; real fingers on this panel jitter, a stationary ghost reports nothing.
STALE_CONTACT_S = 1.5
# A flick glides only if the finger was still moving when it lifted: the speed is that of the last move, and a finger
# that stopped and then lifted must not glide at the speed it had before it stopped.
GLIDE_MAX_IDLE_S = 0.1
# The controller reports at most five fingers and loses lifts when several are down at once, so this many
# simultaneous fingers is treated as misuse: no output until every finger has left the glass (or expired).
MISUSE_FINGERS = 4
# Stylus mode has no two-finger scroll, so a touch that starts in the right-hand strip scrolls vertically and one
# that starts in the bottom strip scrolls horizontally.
STRIP_RIGHT_W = 110.0
STRIP_BOTTOM_H = 100.0
STRIP_START_PX = 4.0       # a strip touch scrolls nothing until it has travelled this far (landing wiggle)
STRIP_REVERSE_PX = 1.5     # a step against the current direction smaller than this is pen jitter, not a reversal
STRIP_ACCEL_SPEED = 600.0  # px/s that adds one extra unit of gain...
STRIP_ACCEL_MAX = 2.0      # ...up to this much extra
# A pen lands, lifts and lands again to reposition (like lifting a mouse), and the landing often registers as a
# short tap. Pen mode therefore clicks only on a double tap: two taps close together within this time and distance.
PEN_DOUBLE_TAP_S = 0.45
PEN_DOUBLE_TAP_DIST_PX = 60.0


def raw_to_screen(raw_x: int, raw_y: int) -> tuple[float, float]:
    """Convert raw 1080x1240 sensor coords (rotated 90 deg) to 1240x1080 screen space."""
    return float(raw_y), float(SCREEN_HEIGHT - 1 - raw_x)


class UInputBridge:
    """Manages virtual mouse and keyboard via /dev/uinput with diagnostics."""

    def __init__(self, logger: DebugLogger | None = None) -> None:
        self.logger = logger or DebugLogger("uinput")
        self.lock = threading.RLock()  # release_all() holds it while calling mouse_button() and key(), which take it again
        self.mouse_fd = -1
        self.kb_fd = -1
        self.held_buttons: set[int] = set()
        self.held_keys: set[int] = set()

        # Telemetry counters
        self.count_mouse_moves = 0
        self.count_clicks_left = 0
        self.count_clicks_right = 0
        self.count_scrolls = 0
        self.count_keystrokes = 0
        self.count_pointer_wakes = 0
        self.moved_at = 0.0  # monotonic time of the last pointer motion we sent
        self.wake_pointer = True  # False once the running Game Mode no longer hides the pointer (Pen +)

        # Scroll accumulators for high-res wheel to notch conversion
        self.scroll_accum_y = 0.0
        self.scroll_accum_x = 0.0

        self._init_devices()

    def _init_devices(self) -> None:
        try:
            self.mouse_fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as err:
            self.logger.log(DebugCode.ERR_UINPUT_OPEN, f"Mouse open failed: {err}")
            raise

        try:
            fcntl.ioctl(self.mouse_fd, UI_SET_EVBIT, EV_KEY)
            for b in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE):
                fcntl.ioctl(self.mouse_fd, UI_SET_KEYBIT, b)
            fcntl.ioctl(self.mouse_fd, UI_SET_EVBIT, EV_REL)
            for r in (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL, REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES):
                fcntl.ioctl(self.mouse_fd, UI_SET_RELBIT, r)
            fcntl.ioctl(
                self.mouse_fd,
                UI_DEV_SETUP,
                SETUP_STRUCT.pack(BUS_VIRTUAL, 0x1234, 0x5678, 1, b"Thor Virtual Trackpad", 0),
            )
            fcntl.ioctl(self.mouse_fd, UI_DEV_CREATE)
            self.logger.log(DebugCode.UINPUT_OK, "Virtual Trackpad device registered")
        except OSError as err:
            self.logger.log(DebugCode.ERR_UINPUT_SETUP, f"Mouse setup failed: {err}")
            raise

        # 2. Virtual Keyboard
        try:
            self.kb_fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
            fcntl.ioctl(self.kb_fd, UI_SET_EVBIT, EV_KEY)
            for k in range(1, 248):
                try:
                    fcntl.ioctl(self.kb_fd, UI_SET_KEYBIT, k)
                except OSError:
                    pass
            fcntl.ioctl(
                self.kb_fd,
                UI_DEV_SETUP,
                SETUP_STRUCT.pack(BUS_VIRTUAL, 0x1234, 0x5679, 1, b"Thor Virtual Keyboard", 0),
            )
            fcntl.ioctl(self.kb_fd, UI_DEV_CREATE)
            self.logger.log(DebugCode.UINPUT_OK, "Virtual Keyboard device registered")
        except OSError as err:
            self.logger.log(DebugCode.ERR_UINPUT_SETUP, f"Keyboard setup failed: {err}")
            raise

    def emit_mouse_rel(self, dx: int, dy: int) -> None:
        if not dx and not dy:
            return
        now = time.time()
        sec, usec = int(now), int((now % 1) * 1e6)
        evs = [
            EVENT_STRUCT.pack(sec, usec, EV_REL, REL_X, dx),
            EVENT_STRUCT.pack(sec, usec, EV_REL, REL_Y, dy),
            EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0),
        ]
        with self.lock:
            if self.mouse_fd >= 0:
                try:
                    os.write(self.mouse_fd, b"".join(evs))
                    self.count_mouse_moves += 1
                    self.moved_at = time.monotonic()
                except OSError as err:
                    self.logger.log(DebugCode.ERR_UINPUT_WRITE, f"emit_mouse_rel: {err}")

    def _wake_pointer_locked(self, sec: int, usec: int) -> None:
        """Nudge the pointer out and back if it has been still long enough for gamescope to hide it.
        The caller holds self.lock and has checked that the mouse device is open."""
        if not self.wake_pointer or time.monotonic() - self.moved_at <= POINTER_WAKE_S:
            return
        for step in (1, -1):  # out and back: the pointer ends where it started
            os.write(self.mouse_fd, EVENT_STRUCT.pack(sec, usec, EV_REL, REL_X, step) + EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0))
        self.moved_at = time.monotonic()
        self.count_pointer_wakes += 1

    def emit_scroll(self, dx_units: int, dy_units: int) -> None:
        if not dx_units and not dy_units:
            return
        now = time.time()
        sec, usec = int(now), int((now % 1) * 1e6)
        evs = []
        if dy_units:
            evs.append(EVENT_STRUCT.pack(sec, usec, EV_REL, REL_WHEEL_HI_RES, int(dy_units)))
            self.scroll_accum_y += dy_units
            notches = int(self.scroll_accum_y / HI_RES_NOTCH)
            if notches:
                self.scroll_accum_y -= notches * HI_RES_NOTCH
                evs.append(EVENT_STRUCT.pack(sec, usec, EV_REL, REL_WHEEL, notches))
        if dx_units:
            evs.append(EVENT_STRUCT.pack(sec, usec, EV_REL, REL_HWHEEL_HI_RES, int(dx_units)))
            self.scroll_accum_x += dx_units
            notches = int(self.scroll_accum_x / HI_RES_NOTCH)
            if notches:
                self.scroll_accum_x -= notches * HI_RES_NOTCH
                evs.append(EVENT_STRUCT.pack(sec, usec, EV_REL, REL_HWHEEL, notches))
        evs.append(EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0))
        with self.lock:
            if self.mouse_fd >= 0:
                try:
                    self._wake_pointer_locked(sec, usec)
                    os.write(self.mouse_fd, b"".join(evs))
                    self.count_scrolls += 1
                except OSError as err:
                    self.logger.log(DebugCode.ERR_UINPUT_WRITE, f"emit_scroll: {err}")

    def mouse_button(self, button_code: int, down: bool) -> None:
        now = time.time()
        sec, usec = int(now), int((now % 1) * 1e6)
        val = 1 if down else 0
        evs = [
            EVENT_STRUCT.pack(sec, usec, EV_KEY, button_code, val),
            EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0),
        ]
        with self.lock:
            if down:
                self.held_buttons.add(button_code)
                if button_code == BTN_LEFT:
                    self.count_clicks_left += 1
                    self.logger.log(DebugCode.STATUS_CLICK_LEFT)
                elif button_code == BTN_RIGHT:
                    self.count_clicks_right += 1
                    self.logger.log(DebugCode.STATUS_CLICK_RIGHT)
                elif button_code == BTN_MIDDLE:
                    self.logger.log(DebugCode.STATUS_CLICK_MIDDLE)
            if self.mouse_fd >= 0:
                try:
                    if down:
                        self._wake_pointer_locked(sec, usec)
                    os.write(self.mouse_fd, b"".join(evs))
                    if not down:
                        self.held_buttons.discard(button_code)  # only once the release really went out
                except OSError as err:
                    self.logger.log(DebugCode.ERR_UINPUT_WRITE, f"mouse_button: {err}")

    def key(self, key_code: int, down: bool) -> None:
        now = time.time()
        sec, usec = int(now), int((now % 1) * 1e6)
        val = 1 if down else 0
        evs = [
            EVENT_STRUCT.pack(sec, usec, EV_KEY, key_code, val),
            EVENT_STRUCT.pack(sec, usec, EV_SYN, SYN_REPORT, 0),
        ]
        with self.lock:
            if down:
                self.held_keys.add(key_code)
                self.count_keystrokes += 1
                self.logger.log(DebugCode.STATUS_KEY_PRESS, f"Key {key_code} DOWN")
            if self.kb_fd >= 0:
                try:
                    os.write(self.kb_fd, b"".join(evs))
                    if not down:
                        self.held_keys.discard(key_code)  # a failed key-up stays held, so release_all() retries it
                except OSError as err:
                    self.logger.log(DebugCode.ERR_UINPUT_WRITE, f"key: {err}")

    def tap_key(self, key_code: int, delay_s: float = 0.02) -> None:
        self.key(key_code, True)
        if delay_s > 0:
            time.sleep(delay_s)
        self.key(key_code, False)

    def tap_button(self, button_code: int, delay_s: float = 0.02) -> None:
        """Asynchronously emit a button click without blocking the caller."""
        def _do_click():
            self.mouse_button(button_code, True)
            time.sleep(delay_s)
            self.mouse_button(button_code, False)

        threading.Thread(target=_do_click, daemon=True).start()

    def release_all(self) -> None:
        with self.lock:
            for b in list(self.held_buttons):
                self.mouse_button(b, False)
            for k in list(self.held_keys):
                self.key(k, False)

    def get_telemetry(self) -> dict[str, Any]:
        with self.lock:
            return {
                "mouse_moves": self.count_mouse_moves,
                "clicks_left": self.count_clicks_left,
                "clicks_right": self.count_clicks_right,
                "scrolls": self.count_scrolls,
                "pointer_wakes": self.count_pointer_wakes,
                "keystrokes": self.count_keystrokes,
                "held_buttons": list(self.held_buttons),
                "held_keys": list(self.held_keys),
            }

    def close(self) -> None:
        self.release_all()
        with self.lock:
            if self.mouse_fd >= 0:
                try:
                    fcntl.ioctl(self.mouse_fd, UI_DEV_DESTROY)
                except OSError:
                    pass
                os.close(self.mouse_fd)
                self.mouse_fd = -1
            if self.kb_fd >= 0:
                try:
                    fcntl.ioctl(self.kb_fd, UI_DEV_DESTROY)
                except OSError:
                    pass
                os.close(self.kb_fd)
                self.kb_fd = -1


class TouchGestureProcessor:
    """Interprets raw multi-touch contacts into pointer, scroll, and click actions."""

    def __init__(self, bridge: UInputBridge, logger: DebugLogger | None = None) -> None:
        self.bridge = bridge
        self.logger = logger or DebugLogger("gesture")
        self.sensitivity = 1.5
        self.glide_enabled = True
        self.friction = 5  # 1 (slickest) to 10 (most friction)
        self.scroll_speed = 3  # 1 (precision) to 5 (fast)
        self.tap_to_click = True
        self.long_press_right_click = False  # Ven: press to hold or 2-finger, not both (default: 2-finger)
        self.long_press_delay_ms = 450  # 250 to 900 ms
        self.two_finger_right_click = True
        self.three_finger_middle_click = False
        self.three_finger_swipe_enabled = False  # Disabled to eliminate accidental gesture triggers
        self.stylus_mode = False  # one pointer, no gestures, long press right-clicks, edge strips scroll

        # Touch tracking state
        self.active_contacts: dict[int, dict] = {}  # tid -> info
        self.start_time: float = 0.0
        self.last_move_time: float = 0.0
        self.accum_dist: float = 0.0
        self.max_fingers: int = 0
        self.is_dragging: bool = False
        self.pointer_active: bool = False  # False while a one-finger touch could still turn out to be a tap
        self.misuse_lock: bool = False  # True from the MISUSE_FINGERS-th finger until no contact is left
        self._expired_tids: set[int] = set()  # contacts dropped as stale: the kernel may reuse their slot
        self.strip: str | None = None  # 'v' / 'h' while the current stylus touch is a strip scroll
        self._last_up_t: float = 0.0  # when the previous touch ended, for the touch summary log
        self.strip_rest: float = 0.0
        self.strip_live: bool = False  # past the landing dead zone
        self.strip_moved: float = 0.0
        self.strip_dir: int = 0
        self._pen_tap_prev: tuple[float, float, float] | None = None  # (time, x, y) of the last pen tap
        self._pen_note = ""  # why the last pen tap did or did not click, for the touch summary log
        self.last_tap_time: float = 0.0

        # Long-press right click timer
        self.long_press_timer: threading.Timer | None = None
        self.long_press_triggered: bool = False

        # Multi-finger gesture tracking
        self.start_centroid: tuple[float, float] = (0.0, 0.0)
        self.swipe_triggered: bool = False

        # Fractional accumulator for high-res subpixel delta
        self.rest_x: float = 0.0
        self.rest_y: float = 0.0

        # Glide velocity
        self.vel_x: float = 0.0
        self.vel_y: float = 0.0
        self.vel_time: float = 0.0  # when vel_x / vel_y were last measured (kernel clock)
        self.glide_thread: threading.Thread | None = None
        self.glide_stop = threading.Event()

        # Telemetry / HUD
        self.last_state_label = "IDLE"
        self.last_coords = (0.0, 0.0)

    def set_settings(
        self,
        sensitivity: float | None = None,
        glide: bool | None = None,
        friction: int | float | None = None,
        scroll_speed: int | float | None = None,
        tap_to_click: bool | None = None,
        long_press_right_click: bool | None = None,
        long_press_delay_ms: int | float | None = None,
        two_finger_right_click: bool | None = None,
        three_finger_middle_click: bool | None = None,
        three_finger_swipe_enabled: bool | None = None,
        stylus_mode: bool | None = None,
        **kwargs: Any,
    ) -> None:
        if sensitivity is not None:
            self.sensitivity = max(0.2, min(5.0, float(sensitivity)))
        if glide is not None:
            self.glide_enabled = bool(glide)
        if friction is not None:
            self.friction = max(1, min(10, int(round(float(friction)))))
        if scroll_speed is not None:
            self.scroll_speed = max(1, min(5, int(round(float(scroll_speed)))))
        if tap_to_click is not None:
            self.tap_to_click = bool(tap_to_click)
        # Ven's rule: Press to hold OR two finger right click, not both
        if two_finger_right_click is not None:
            self.two_finger_right_click = bool(two_finger_right_click)
            if self.two_finger_right_click:
                self.long_press_right_click = False
        if long_press_right_click is not None:
            self.long_press_right_click = bool(long_press_right_click)
            if self.long_press_right_click:
                self.two_finger_right_click = False
        if long_press_delay_ms is not None:
            self.long_press_delay_ms = max(200, min(1200, int(round(float(long_press_delay_ms)))))
        if three_finger_middle_click is not None:
            self.three_finger_middle_click = bool(three_finger_middle_click)
        if three_finger_swipe_enabled is not None:
            self.three_finger_swipe_enabled = bool(three_finger_swipe_enabled)
        if stylus_mode is not None and bool(stylus_mode) != self.stylus_mode:
            self.stylus_mode = bool(stylus_mode)
            self._pen_tap_prev = None
            self.reset_all()  # fingers down under the old mode must not carry over
        self.logger.log(
            DebugCode.SETTINGS_UPDATED,
            f"sens={self.sensitivity}, friction={self.friction}, 2f_right={self.two_finger_right_click}",
        )

    def get_settings(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity,
            "glide": self.glide_enabled,
            "friction": self.friction,
            "scroll_speed": self.scroll_speed,
            "tap_to_click": self.tap_to_click,
            "long_press_right_click": self.long_press_right_click,
            "long_press_delay_ms": self.long_press_delay_ms,
            "two_finger_right_click": self.two_finger_right_click,
            "three_finger_middle_click": self.three_finger_middle_click,
            "three_finger_swipe_enabled": self.three_finger_swipe_enabled,
            "stylus_mode": self.stylus_mode,
        }

    def reset_all(self) -> None:
        """Reset all active tracking state and cancel timers cleanly."""
        self._cancel_long_press()
        self.active_contacts.clear()
        self.max_fingers = 0
        self.is_dragging = False
        self.swipe_triggered = False
        self.accum_dist = 0.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.long_press_triggered = False
        self.misuse_lock = False
        self.strip = None
        self._expired_tids.clear()
        self.last_state_label = "IDLE"

    def expire_stale(self, now: float) -> None:
        """Forget contacts that have been silent for STALE_CONTACT_S: a lost lift would otherwise make every later
        single-finger touch look like a two-finger scroll, and nothing resets until the controller lets go.
        Called with the kernel timestamp of every frame, and from the reader's idle ticks."""
        self._drop_stale_contacts(now)

    def _drop_stale_contacts(self, now: float) -> None:
        stale = [tid for tid, c in self.active_contacts.items() if now - c.get("seen_t", now) > STALE_CONTACT_S]
        for tid in stale:
            c = self.active_contacts.pop(tid)
            self._expired_tids.add(tid)
            self.logger.log(DebugCode.STATUS_TOUCH_UP, f"dropped stale contact {tid} at ({c['last_x']:.0f}, {c['last_y']:.0f}): silent for {now - c['seen_t']:.1f}s")
        if stale and not self.active_contacts:
            self.max_fingers = 0
            self.accum_dist = 0.0
            self.vel_x = 0.0
            self.vel_y = 0.0
            self.pointer_active = False
            self.misuse_lock = False
            self.strip = None
            self._cancel_long_press()

    def _strip_at(self, x: float, y: float) -> str | None:
        if x >= SCREEN_WIDTH - STRIP_RIGHT_W:
            return "v"
        if y >= SCREEN_HEIGHT - STRIP_BOTTOM_H:
            return "h"
        return None

    def _pen_tap(self, now: float) -> None:
        """Pen mode: a tap clicks only as the second of two close taps. A lone tap is usually the pen landing."""
        x, y = self.last_coords
        prev = self._pen_tap_prev
        gap = now - prev[0] if prev else None
        dist = math.hypot(x - prev[1], y - prev[2]) if prev else None
        if prev and gap < PEN_DOUBLE_TAP_S and dist < PEN_DOUBLE_TAP_DIST_PX:
            self.last_state_label = "TAP LEFT (PEN)"
            self._pen_note = f"second tap {gap * 1000:.0f} ms and {dist:.0f} px after the first"
            self.bridge.tap_button(BTN_LEFT)
            self.last_tap_time = now
        else:
            self.last_state_label = "PEN TAP 1 OF 2"
            self._pen_note = "first tap" if not prev else f"first tap (previous one was {gap * 1000:.0f} ms and {dist:.0f} px away)"
        self._pen_tap_prev = (now, x, y)

    def _strip_scroll(self, dx: float, dy: float, dt: float) -> None:
        along = dy if self.strip == "v" else dx
        if not self.strip_live:
            self.strip_moved += along
            if abs(self.strip_moved) < STRIP_START_PX:
                return
            self.strip_live = True
            self.strip_dir = 1 if self.strip_moved > 0 else -1
            return
        direction = 1 if along > 0 else -1 if along < 0 else 0
        if direction and self.strip_dir and direction != self.strip_dir and abs(along) < STRIP_REVERSE_PX:
            return  # jitter
        if direction:
            self.strip_dir = direction
        boost = 1.0 + min(STRIP_ACCEL_MAX, (abs(along) / dt) / STRIP_ACCEL_SPEED)
        divisor = max(4.0, 22.0 - (self.scroll_speed * 4.0))
        gain = HI_RES_NOTCH / divisor
        self.strip_rest += (-along if self.strip == "v" else along) * gain * boost
        step = int(self.strip_rest)
        if step:
            self.strip_rest -= step
            if self.strip == "v":
                self.bridge.emit_scroll(0, step)
            else:
                self.bridge.emit_scroll(step, 0)
            self.last_state_label = "PEN SCROLL"

    def _cancel_long_press(self) -> None:
        if self.long_press_timer and self.long_press_timer.is_alive():
            self.long_press_timer.cancel()
        self.long_press_timer = None

    def _on_long_press(self) -> None:
        if len(self.active_contacts) == 1 and not self.is_dragging and self.accum_dist < LONG_PRESS_MAX_DIST_PX:
            self.long_press_triggered = True
            self.last_state_label = "LONG PRESS RIGHT"
            self.logger.log(DebugCode.STATUS_LONG_PRESS)
            self.bridge.tap_button(BTN_RIGHT)


    def touch_down(self, tid: int, x: float, y: float, now: float) -> None:
        self.glide_stop.set()
        self._drop_stale_contacts(now)
        if self.stylus_mode and self.active_contacts:
            return  # one pointer only: a resting palm or a second hand is ignored for as long as the first touch lasts
        contact = {"id": tid, "start_x": x, "start_y": y, "last_x": x, "last_y": y, "start_t": now, "seen_t": now}
        self.active_contacts[tid] = contact
        count = len(self.active_contacts)
        self.max_fingers = max(self.max_fingers, count)
        self.last_coords = (x, y)
        self.last_state_label = f"DOWN ({count} finger{'s' if count > 1 else ''})"
        self._expired_tids.discard(tid)

        if count >= MISUSE_FINGERS:
            if not self.misuse_lock:
                self.logger.log(DebugCode.STATUS_TOUCH_DOWN, f"{count} fingers down: ignoring touch until all lift")
            self.misuse_lock = True
            self._cancel_long_press()
            self.vel_x = 0.0
            self.vel_y = 0.0
            self.last_state_label = "TOO MANY FINGERS"
            return

        if count == 1:
            self.start_time = now
            self.last_move_time = now
            self.accum_dist = 0.0
            self.vel_x = 0.0
            self.vel_y = 0.0
            self.long_press_triggered = False
            self.pointer_active = False
            self.strip = self._strip_at(x, y) if self.stylus_mode else None
            self.strip_rest = 0.0
            self.strip_live = False
            self.strip_moved = 0.0
            self.strip_dir = 0
            if self.strip:
                self.last_state_label = "PEN SCROLL"

            if (self.long_press_right_click or self.stylus_mode) and not self.strip:
                self._cancel_long_press()
                delay_s = self.long_press_delay_ms / 1000.0
                self.long_press_timer = threading.Timer(delay_s, self._on_long_press)
                self.long_press_timer.start()

        elif count >= 2:
            self._cancel_long_press()

        if count == 3:
            pts = list(self.active_contacts.values())
            self.start_centroid = (sum(p["last_x"] for p in pts) / 3.0, sum(p["last_y"] for p in pts) / 3.0)
            self.swipe_triggered = False

    def touch_move(self, tid: int, x: float, y: float, now: float) -> None:
        contact = self.active_contacts.get(tid)
        if not contact:
            if tid not in self._expired_tids:
                return
            # A new finger landed in the slot of a ghost we already dropped: the kernel keeps the old tracking
            # id and reports it as movement. It is moving, so it is a real finger.
            self.logger.log(DebugCode.STATUS_TOUCH_DOWN, f"contact {tid} moved after being dropped as stale: treating it as a new touch")
            self.touch_down(tid, x, y, now)
            return

        dx = x - contact["last_x"]
        dy = y - contact["last_y"]
        contact["last_x"] = x
        contact["last_y"] = y
        contact["seen_t"] = now

        if self.misuse_lock:
            return

        self.accum_dist += math.hypot(dx, dy)
        self.last_coords = (x, y)

        count = len(self.active_contacts)
        dt = max(0.001, now - self.last_move_time)
        self.last_move_time = now

        if count == 1:
            if self.strip:
                self._strip_scroll(dx, dy, dt)
                return

            if self.accum_dist > LONG_PRESS_MAX_DIST_PX:
                self._cancel_long_press()

            if not self.pointer_active:
                # Hold the cursor still while this could be a tap: otherwise every tap nudges the cursor and
                # every quick nudge ends in a click. Movement starts once the finger has travelled past the
                # tap distance or stayed down past the tap time; the travel before that is not replayed.
                if self.accum_dist < TAP_MAX_DISTANCE_PX and (now - self.start_time) < TAP_MAX_TIME_S:
                    self.last_state_label = "HOLD"
                    return
                self.pointer_active = True

            self.last_state_label = "MOVE"
            speed = self.sensitivity
            mag = math.hypot(dx, dy)
            accel = 1.0 + min(1.6, mag / 25.0)
            target_dx = dx * speed * accel + self.rest_x
            target_dy = dy * speed * accel + self.rest_y

            ix = int(target_dx)
            iy = int(target_dy)
            self.rest_x = target_dx - ix
            self.rest_y = target_dy - iy

            if ix or iy:
                self.bridge.emit_mouse_rel(ix, iy)
            # measured on every step, also the sub-pixel ones: a finger that is slowing down must slow the glide too
            self.vel_x = (dx * speed * accel) / dt
            self.vel_y = (dy * speed * accel) / dt
            self.vel_time = now

        elif count == 2:
            self._cancel_long_press()
            scroll_divisor = max(4.0, 22.0 - (self.scroll_speed * 4.0))
            scroll_dy = int(-dy * (HI_RES_NOTCH / scroll_divisor))
            scroll_dx = int(dx * (HI_RES_NOTCH / scroll_divisor))
            if scroll_dx or scroll_dy:
                self.bridge.emit_scroll(scroll_dx, scroll_dy)
                self.last_state_label = "SCROLL 2-FINGER"

        elif count >= 3:
            self._cancel_long_press()
            if self.three_finger_swipe_enabled:
                pts = list(self.active_contacts.values())
                cur_cx = sum(p["last_x"] for p in pts) / count
                cur_cy = sum(p["last_y"] for p in pts) / count
                delta_x = cur_cx - self.start_centroid[0]
                delta_y = cur_cy - self.start_centroid[1]

                if not self.swipe_triggered:
                    if delta_y < -SWIPE_THRESHOLD_PX:
                        self.swipe_triggered = True
                        self.last_state_label = "SWIPE UP"
                        self.bridge.tap_key(KEY_LEFTMETA)
                    elif delta_y > SWIPE_THRESHOLD_PX:
                        self.swipe_triggered = True
                        self.last_state_label = "SWIPE DOWN"
                        self.bridge.tap_key(KEY_ESC)
                    elif abs(delta_x) > SWIPE_THRESHOLD_PX:
                        self.swipe_triggered = True
                        self.last_state_label = "SWIPE TAB"
                        self.bridge.key(KEY_LEFTALT, True)
                        self.bridge.tap_key(KEY_TAB)
                        self.bridge.key(KEY_LEFTALT, False)

    def touch_up(self, tid: int, now: float) -> None:
        last_of_touch = len(self.active_contacts) == 1 and tid in self.active_contacts
        started, travelled, fingers = self.start_time, self.accum_dist, self.max_fingers
        down = self.active_contacts.get(tid)
        where = f"({down['start_x']:.0f}, {down['start_y']:.0f})" if down else "?"
        self._pen_note = ""
        self._touch_up(tid, now)
        if last_of_touch:
            if self.last_tap_time == now:
                outcome = "left click"
            elif self.long_press_triggered:
                outcome = "long-press right click"
            else:
                outcome = "no click"
            gap = f"{(started - self._last_up_t) * 1000:.0f} ms" if self._last_up_t else "n/a"
            self.logger.log(
                DebugCode.STATUS_TOUCH_UP,
                f"touch ended: {(now - started) * 1000:.0f} ms down, {travelled:.0f} px travelled, {fingers} finger(s), "
                f"{gap} since the previous touch ended, at {where} -> {outcome}"
                f"{' (pen: ' + self._pen_note + ')' if self.stylus_mode and self._pen_note else ' (pen)' if self.stylus_mode else ''}",
            )
            self._last_up_t = now

    def _touch_up(self, tid: int, now: float) -> None:
        self._cancel_long_press()
        self._expired_tids.discard(tid)
        contact = self.active_contacts.pop(tid, None)
        if not contact:
            return

        if self.misuse_lock:
            if not self.active_contacts:
                self.misuse_lock = False
                self.max_fingers = 0
                self.accum_dist = 0.0
                self.vel_x = 0.0
                self.vel_y = 0.0
                self.pointer_active = False
                self.swipe_triggered = False
                self.last_state_label = "IDLE"
            return

        if len(self.active_contacts) < 3:
            self.swipe_triggered = False  # a new three-finger swipe can start once a finger has lifted

        if len(self.active_contacts) == 0:

            if self.strip:
                self.strip = None
                self.max_fingers = 0
                self.last_state_label = "IDLE"
                return

            duration = now - self.start_time
            if now - self.vel_time > GLIDE_MAX_IDLE_S:
                self.vel_x = 0.0
                self.vel_y = 0.0  # the finger had stopped before it lifted: that speed is old

            if self.long_press_triggered:
                self.last_state_label = "LONG PRESS DONE"
            elif not self.pointer_active and self.accum_dist < TAP_MAX_DISTANCE_PX * max(1, self.max_fingers) and duration < TAP_MAX_TIME_S:
                if self.max_fingers == 1 and self.tap_to_click and self.stylus_mode:
                    self._pen_tap(now)
                elif self.max_fingers == 1 and self.tap_to_click:
                    # 1-finger Tap: Crisp Left Click (non-blocking)
                    self.last_state_label = "TAP LEFT"
                    self.bridge.tap_button(BTN_LEFT)
                    self.last_tap_time = now
                elif self.max_fingers == 2 and self.two_finger_right_click:
                    # 2-finger Tap: Crisp Right Click (non-blocking)
                    self.last_state_label = "TAP RIGHT (2-FINGER)"
                    self.bridge.tap_button(BTN_RIGHT)
                elif self.max_fingers == 3 and self.three_finger_middle_click:
                    # 3-finger Tap: Crisp Middle Click (non-blocking)
                    self.last_state_label = "TAP MIDDLE (3-FINGER)"
                    self.bridge.tap_button(BTN_MIDDLE)
            elif self.glide_enabled and self.max_fingers == 1 and not self.stylus_mode:
                speed = math.hypot(self.vel_x, self.vel_y)
                if speed > 140.0:
                    self.last_state_label = "GLIDE"
                    self.logger.log(DebugCode.STATUS_GLIDE_START, f"velocity={speed:.1f}")
                    self._start_glide(self.vel_x, self.vel_y)

            self.max_fingers = 0
            if not self.glide_enabled or math.hypot(self.vel_x, self.vel_y) <= 140.0:
                self.last_state_label = "IDLE"


    def _start_glide(self, vx: float, vy: float) -> None:
        # A fresh event per glide: clearing a shared one could revive an older glide that had not yet seen its stop.
        self.glide_stop.set()
        stop = threading.Event()
        self.glide_stop = stop

        # Decay based on friction setting (1 = 0.97 slick, 5 = 0.88, 10 = 0.74 high friction)
        decay = 0.97 - ((self.friction - 1) / 9.0) * 0.23

        def _glide_loop():
            cur_vx, cur_vy = vx, vy
            dt = 0.016
            accum_x, accum_y = 0.0, 0.0
            while not stop.is_set():
                cur_vx *= decay
                cur_vy *= decay
                if math.hypot(cur_vx, cur_vy) < 12.0:
                    break
                accum_x += cur_vx * dt
                accum_y += cur_vy * dt
                ix = int(accum_x)
                iy = int(accum_y)
                accum_x -= ix
                accum_y -= iy
                if ix or iy:
                    self.bridge.emit_mouse_rel(ix, iy)
                time.sleep(dt)
            self.last_state_label = "IDLE"

        self.glide_thread = threading.Thread(target=_glide_loop, daemon=True)
        self.glide_thread.start()
