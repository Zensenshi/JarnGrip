# SPDX-License-Identifier: GPL-3.0-only
"""A short buzz for each button press, through the kernel's force-feedback interface (EV_FF).

Anything that can play force-feedback effects is an input device, picked from sysfs by what it can play. A gamepad
comes first, then a bare vibration motor. On the Thor, the gamepad itself belongs to InputPlumber (root only), but its
virtual "Microsoft X-Box 360 pad" passes rumble on to the controller's motor: the same buzz as Steam's on-screen
keyboard, and much stronger than the separate "qcom-hv-haptics" motor, which is the fallback. Nothing is grabbed: one
effect is uploaded and each buzz is a single write, so the game's and Steam's own rumble keep working.

A device that another program has grabbed (EVIOCGRAB) is skipped: the kernel accepts the effect upload on it but
silently drops every play request written to it, so it would look fine and never buzz.
"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import struct
import threading
import time

from touch_frames import EVENT_STRUCT

EV_FF = 0x15
FF_RUMBLE, FF_PERIODIC, FF_CONSTANT, FF_SINE = 0x50, 0x51, 0x52, 0x5A
EFFECT_NAMES = {"rumble": FF_RUMBLE, "periodic": FF_PERIODIC, "constant": FF_CONSTANT}
# What a device is driven with, in order of preference. A haptics motor gets a constant effect first: that is the
# timed buzz Qualcomm's haptics driver is built for (Android's vibrator uses it), while a gamepad is made to rumble.
MOTOR_EFFECTS = (FF_CONSTANT, FF_RUMBLE, FF_PERIODIC)
GAMEPAD_EFFECTS = (FF_RUMBLE, FF_PERIODIC, FF_CONSTANT)
RETRY_S = 10.0  # while no motor is found (or it went away), look again this often
# Buzz patterns: (start, length) of each buzz, in units of the configured pulse length.
PATTERNS = {
    "press": ((0.0, 1.0),),               # a button or key
    "tick": ((0.0, 0.6),),                # a lighter one: switching page or view, a swipe changing direction
    "lock": ((0.0, 1.0), (2.5, 1.0)),     # two: a modifier or click button locked on
}

# struct ff_effect: type, id, direction, trigger {button, interval}, replay {length, delay}, then a union whose largest
# member (ff_periodic_effect) ends in a pointer, so the union is pointer-aligned. Native struct alignment matches C.
_HEAD = struct.Struct("@HhHHHHH")
_UNION_AT = struct.calcsize("@HhHHHHH0P")
_UNION_SIZE = struct.calcsize("@HHhhH4HIP")
EFFECT_SIZE = _UNION_AT + _UNION_SIZE
_IOC_WRITE = 1
EVIOCSFF = (_IOC_WRITE << 30) | (EFFECT_SIZE << 16) | (ord("E") << 8) | 0x80
EVIOCRMFF = (_IOC_WRITE << 30) | (struct.calcsize("i") << 16) | (ord("E") << 8) | 0x81
EVIOCGRAB = (_IOC_WRITE << 30) | (struct.calcsize("i") << 16) | (ord("E") << 8) | 0x90
_LONG_BITS = struct.calcsize("L") * 8


def ff_bits(text: str) -> int:
    """sysfs prints a capability bitmap as hex words, the most significant first, each one unsigned long wide."""
    value = 0
    for word in text.split():
        value = (value << _LONG_BITS) | int(word, 16)
    return value


def find_motors(dev_dir: str = "/dev/input", sys_dir: str = "/sys/class/input") -> list:
    """[(node, name, effect types)] of every input device that can buzz, gamepads before bare motors. The effect
    types are the ones the device supports, best first."""
    found = []
    for node in sorted(glob.glob(os.path.join(dev_dir, "event*"))):
        device = os.path.join(sys_dir, os.path.basename(node), "device")
        try:
            with open(os.path.join(device, "name"), encoding="utf-8") as f:
                name = f.read().strip()
            with open(os.path.join(device, "capabilities", "ff"), encoding="utf-8") as f:
                bits = ff_bits(f.read())
        except (OSError, ValueError):
            continue
        motor = any(word in name.lower() for word in ("vibra", "haptic", "rumble"))
        kinds = tuple(e for e in (MOTOR_EFFECTS if motor else GAMEPAD_EFFECTS) if bits >> e & 1)
        if kinds:
            found.append((motor, node, name, kinds))
    return [(node, name, kinds) for _, node, name, kinds in sorted(found)]


def held_elsewhere(fd: int) -> bool:
    """True if another program has grabbed the device. Found by grabbing it and letting go at once: a device nobody
    holds is ours for only that instant."""
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except OSError as err:
        return err.errno == errno.EBUSY
    fcntl.ioctl(fd, EVIOCGRAB, 0)
    return False


def pack_effect(kind: int, effect_id: int, length_ms: int, strength: float) -> bytearray:
    buf = bytearray(EFFECT_SIZE)
    _HEAD.pack_into(buf, 0, kind, effect_id, 0, 0, 0, length_ms, 0)
    if kind == FF_RUMBLE:  # strong (low-frequency) and weak motor magnitudes
        level = int(strength * 0xFFFF)
        struct.pack_into("@HH", buf, _UNION_AT, level, level)
    elif kind == FF_PERIODIC:  # waveform, period (ms), magnitude, offset, phase
        struct.pack_into("@HHhhH", buf, _UNION_AT, FF_SINE, 10, int(strength * 0x7FFF), 0, 0)
    else:  # constant level
        struct.pack_into("@h", buf, _UNION_AT, int(strength * 0x7FFF))
    return buf


def _upload(fd: int, kind: int, effect: int, length_ms: int, strength: float) -> int:
    """Upload an effect and return its id. With an id of -1 the kernel assigns one and writes it back; with an existing
    id it replaces that effect."""
    buf = pack_effect(kind, effect, length_ms, strength)
    fcntl.ioctl(fd, EVIOCSFF, buf)
    return struct.unpack_from("@h", buf, 2)[0]


class Haptics:
    """Buzzes from the touch thread; configured once a second from the GTK thread.

    Uploading an effect to a virtual pad waits for the daemon behind it (InputPlumber) to answer, so the slow device
    calls never run under the lock that pulses take: a stalled daemon must not stall touch input."""

    def __init__(self, find=find_motors, clock=time.monotonic, held=held_elsewhere, upload=None) -> None:
        self._find = find
        self._held = held
        self._upload = upload or _upload
        self._clock = clock
        self.fd = -1
        self.kind = 0
        self.effect = -1
        self.enabled = False
        self.strength = 1.0
        self.length_ms = 40
        self.effect_kind = None  # force one effect type ("haptics_effect" in the config); None picks per device
        self._pulses = 0         # counts patterns, so that the steps of an older one leave a newer one alone
        self._io = threading.RLock()  # guards fd and effect: pulses, their timers and configure all use them
        self.status = "off"
        self._last_try = -RETRY_S

    def configure(self, enabled: bool, strength: float, length_ms: int, effect: str = "") -> None:
        """Apply the settings; cheap to call every second. Also looks for a motor again while none is open."""
        strength = max(0.05, min(1.0, strength))
        length_ms = max(5, min(100, int(length_ms)))
        kind = EFFECT_NAMES.get(effect)
        changed = (strength, length_ms) != (self.strength, self.length_ms)
        if kind != self.effect_kind:
            self.close()  # a different effect type may mean a different device
            self._last_try = -RETRY_S
        self.enabled, self.strength, self.length_ms, self.effect_kind = enabled, strength, length_ms, kind
        if not enabled:
            self.close()
            self.status = "off"
        elif self.fd < 0:
            if self._clock() - self._last_try >= RETRY_S:
                self._open()
        elif changed:
            fd, effect = self.fd, self.effect
            try:
                self._upload(fd, self.kind, effect, length_ms, strength)  # replaces the effect in place: same id
            except OSError as err:
                with self._io:
                    if self.fd == fd:
                        self._lost(err)

    def _open(self) -> None:
        self._last_try = self._clock()
        self.status = "no vibration motor found"
        names = {v: k for k, v in EFFECT_NAMES.items()}
        skipped = []
        for node, name, kinds in self._find():
            if self.effect_kind is not None:
                kinds = tuple(k for k in kinds if k == self.effect_kind)
            for kind in kinds:  # a driver may list an effect type and still refuse it: try the next one
                try:
                    fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
                except OSError as err:
                    self.status = f"cannot open {name} ({node}): {err.strerror}"
                    break
                if self._held(fd):
                    os.close(fd)
                    skipped.append(name)
                    break
                try:
                    effect = self._upload(fd, kind, -1, self.length_ms, self.strength)
                except OSError as err:
                    os.close(fd)
                    self.status = f"{name} ({node}) refused a {names[kind]} effect: {err.strerror}"
                    continue
                with self._io:
                    self.fd, self.kind, self.effect = fd, kind, effect
                self.status = f"{name} ({node}), {names[kind]} effect"
                return
        if skipped and self.status == "no vibration motor found":
            self.status = f"every vibration device is held by another program ({', '.join(skipped)})"

    def pulse(self, pattern: str = "press") -> None:
        """Play a pattern from PATTERNS. Every buzz is started and also stopped explicitly: the kernel ends an effect
        after its length only on real hardware, and on a virtual pad that is up to the daemon behind it (InputPlumber)."""
        if self.fd < 0:
            return
        self._pulses += 1
        for start, length in PATTERNS.get(pattern, PATTERNS["press"]):
            self._at(start * self.length_ms, 1)
            self._at((start + length) * self.length_ms, 0)

    def _at(self, ms: float, value: int) -> None:
        if ms <= 0:
            self._send(self._pulses, value)
            return
        timer = threading.Timer(ms / 1000.0, self._send, (self._pulses, value))
        timer.daemon = True
        timer.start()

    def _send(self, pulse: int, value: int) -> None:
        with self._io:
            if pulse != self._pulses or self.fd < 0:
                return  # a newer pattern has started, or the device was closed
            try:
                os.write(self.fd, EVENT_STRUCT.pack(0, 0, EV_FF, self.effect, value))
            except OSError as err:
                self._lost(err)

    def _lost(self, err: OSError) -> None:
        self.close()
        self.status = f"motor lost ({err.strerror}); looking for it again"
        self._last_try = self._clock()

    def close(self) -> None:
        with self._io:
            self._close()

    def _close(self) -> None:
        if self.fd < 0:
            return
        if self.effect >= 0:
            try:
                fcntl.ioctl(self.fd, EVIOCRMFF, self.effect)
            except OSError:
                pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd, self.effect = -1, -1
