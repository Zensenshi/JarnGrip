# SPDX-License-Identifier: GPL-3.0-only
"""Finds, opens and grabs the Thor's bottom touchscreen, and nothing else.

The pad takes the digitizer exclusively (EVIOCGRAB), so picking the wrong node is not harmless: the top panel is
"top_touchscreen", and grabbing that one takes touch away from Game Mode while the pad itself hears nothing.
The node is therefore chosen by name only, with no fallback, and the name is checked again on the open descriptor
before the grab.

Finding, grabbing and reading the digitizer follow thor_app.py in Ratatoskr (https://github.com/venatrix-ritz/Ratatoskr,
MIT License, Copyright (c) 2026 Ven (venatrix-ritz) and Thor Input Contributors).
"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import struct
from typing import Callable

from engine import SCREEN_HEIGHT, SCREEN_WIDTH, raw_to_screen
from touch_frames import ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_SLOT, ABS_MT_TRACKING_ID

# <linux/input.h>: EVIOCGNAME(len) = _IOC(_IOC_READ, 'E', 0x06, len); EVIOCGABS(abs) = _IOR('E', 0x40 + abs,
# struct input_absinfo), 24 bytes; EVIOCGMTSLOTS(len) = _IOC(_IOC_READ, 'E', 0x0a, len); EVIOCGRAB = _IOW('E', 0x90, int).
_IOC_READ = 2
EVIOCGRAB = (1 << 30) | (struct.calcsize("i") << 16) | (ord("E") << 8) | 0x90


def _ioc_read(nr: int, length: int) -> int:
    return (_IOC_READ << 30) | (length << 16) | (ord("E") << 8) | nr


def is_bottom_touchscreen(name: str) -> bool:
    name = name.strip().lower()
    return "bottom" in name and "touchscreen" in name


def find_bottom_touchscreen(dev_dir: str = "/dev/input", sys_dir: str = "/sys/class/input") -> str | None:
    for node in sorted(glob.glob(os.path.join(dev_dir, "event*"))):
        try:
            with open(os.path.join(sys_dir, os.path.basename(node), "device", "name"), encoding="utf-8") as f:
                if is_bottom_touchscreen(f.read()):
                    return node
        except OSError:
            pass
    return None


def device_name(fd: int) -> str:
    buf = bytearray(256)
    fcntl.ioctl(fd, _ioc_read(0x06, len(buf)), buf)
    return bytes(buf).split(b"\0", 1)[0].decode("utf-8", "replace")


def open_and_grab(node: str) -> int:
    """Open the node and take it exclusively. Raises OSError, with nothing left open or grabbed, if it cannot be
    opened or grabbed, or if it is not the bottom touchscreen after all (nodes are renumbered on resume)."""
    fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
    try:
        name = device_name(fd)
        if not is_bottom_touchscreen(name):
            raise OSError(errno.ENODEV, f"{node} is '{name}', not the bottom touchscreen")
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except BaseException:
        os.close(fd)
        raise
    return fd


def release(fd: int) -> None:
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 0)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def axis_max(fd: int, code: int) -> int:
    """The largest value the device reports on an absolute axis, or 0 if it cannot be read."""
    info = bytearray(24)
    try:
        fcntl.ioctl(fd, _ioc_read(0x40 + code, len(info)), info)
    except OSError:
        return 0
    return struct.unpack("6i", info)[2]


def to_screen_for(fd: int) -> Callable:
    """The raw-to-screen mapping for this digitizer. The panel is mounted rotated (engine.raw_to_screen); if it
    reports a different range than the 1080 by 1240 that mapping assumes, the same mapping is scaled to fit."""
    max_x, max_y = axis_max(fd, ABS_MT_POSITION_X), axis_max(fd, ABS_MT_POSITION_Y)
    if max_x <= 0 or max_y <= 0 or (max_x, max_y) == (SCREEN_HEIGHT - 1, SCREEN_WIDTH - 1):
        return raw_to_screen
    return lambda raw_x, raw_y: (raw_y * (SCREEN_WIDTH - 1) / max_y, (SCREEN_HEIGHT - 1) * (1 - raw_x / max_x))


def read_mt_slots(fd: int) -> dict:
    """Current kernel state of every touch slot: {slot: (tracking id, raw x, raw y)}, live slots only."""
    count = axis_max(fd, ABS_MT_SLOT) + 1
    values = {}
    for code in (ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
        buf = bytearray(struct.pack("I", code) + bytes(4 * count))
        fcntl.ioctl(fd, _ioc_read(0x0A, len(buf)), buf)
        values[code] = struct.unpack(f"{count}i", bytes(buf[4:]))
    return {
        slot: (values[ABS_MT_TRACKING_ID][slot], values[ABS_MT_POSITION_X][slot], values[ABS_MT_POSITION_Y][slot])
        for slot in range(count) if values[ABS_MT_TRACKING_ID][slot] >= 0
    }
