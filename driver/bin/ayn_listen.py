#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""JarnGrip's AYN button listener: jarngrip-ayn.service, run while "AYN button" is on in Decky.

The Decky backend cannot read input devices itself: Decky switches it to the user without the user's groups, and
/dev/input belongs to the input group. A user service has them. This one reads the key an AYN button press arrives as,
without grabbing it, and writes one byte per press into a FIFO that the backend reads and toggles the pad on.

A press arrives as KEY_RECORD on InputPlumber's virtual pad while the button takes screenshots (InputPlumber's
Screenshot, on a pad that has none), and as KEY_F24 on InputPlumber's virtual keyboard while "Stop the screenshot" has
changed its profile (see ayn_button.py in the plugin). Devices come and go (InputPlumber restarting, a resume, the
profile change adding its keyboard), so they are looked for again every few seconds.
"""
from __future__ import annotations

import errno
import os
import select
import struct
import sys
import time
from pathlib import Path

EV_KEY, KEY_RECORD, KEY_F24, BTN_SOUTH = 1, 167, 194, 0x130
INPUT_EVENT = struct.Struct("llHHi")
KEYBOARD_NAME = "InputPlumber Keyboard"
FIFO = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "jarngrip-ayn"
RESCAN_S = 5


def _key_bits(event: Path) -> int:
    """sysfs prints a key bitmap as hex words, the most significant first, each one unsigned long wide."""
    bits = 0
    for word in (event / "device/capabilities/key").read_text().split():
        bits = bits << (struct.calcsize("L") * 8) | int(word, 16)
    return bits


def sources(sys_dir: Path = Path("/sys/class/input"), dev_dir: Path = Path("/dev/input")) -> list:
    """[(device node, key code)] that an AYN button press can arrive as."""
    found = []
    for event in sorted(sys_dir.glob("event*")):
        try:
            bits = _key_bits(event)
            name = (event / "device/name").read_text().strip()
        except (OSError, ValueError):
            continue
        if bits >> KEY_RECORD & 1 and bits >> BTN_SOUTH & 1:
            found.append((dev_dir / event.name, KEY_RECORD))
        elif name.startswith(KEYBOARD_NAME) and bits >> KEY_F24 & 1:
            found.append((dev_dir / event.name, KEY_F24))
    return found


def presses(data: bytes, code: int) -> int:
    """How many presses of a key (not releases or repeats) a read of input events holds."""
    size = INPUT_EVENT.size
    return sum(1 for i in range(0, len(data) - size + 1, size) if INPUT_EVENT.unpack_from(data, i)[2:] == (EV_KEY, code, 1))


def tell(fifo: Path, count: int) -> None:
    """One byte per press into the backend's FIFO. If the backend is not there to read it, the press is dropped."""
    try:
        fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
    except OSError as err:
        if err.errno not in (errno.ENXIO, errno.ENOENT):
            print(f"cannot tell the backend: {err.strerror}", flush=True)
        return
    try:
        os.write(fd, b"p" * count)
    except OSError:
        pass
    finally:
        os.close(fd)


def main() -> None:
    fifo = Path(sys.argv[1]) if len(sys.argv) > 1 else FIFO
    open_fds: dict = {}  # fd -> (node, key code)
    next_scan = 0.0
    while True:
        if time.monotonic() >= next_scan:
            next_scan = time.monotonic() + RESCAN_S
            watched = {node for node, _ in open_fds.values()}
            for node, code in sources():
                if node in watched:
                    continue
                try:
                    open_fds[os.open(node, os.O_RDONLY | os.O_NONBLOCK)] = (node, code)
                    print(f"reading {node} for key {code}", flush=True)
                except OSError as err:
                    print(f"cannot read {node}: {err.strerror}", flush=True)
        ready = select.select(list(open_fds), [], [], RESCAN_S)[0] if open_fds else (time.sleep(RESCAN_S) or [])
        for fd in ready:
            node, code = open_fds[fd]
            try:
                data = os.read(fd, INPUT_EVENT.size * 64)
            except BlockingIOError:
                continue
            except OSError:
                data = b""
            if not data:  # the device went away
                print(f"{node} went away", flush=True)
                os.close(fd)
                del open_fds[fd]
                continue
            count = presses(data, code)
            if count:
                tell(fifo, count)


if __name__ == "__main__":
    main()
