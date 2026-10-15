# SPDX-License-Identifier: GPL-3.0-only
"""Facts about the device the pad runs on: the clock and battery in its header, and which screen is the bottom one. No
GTK in here, so it is tested anywhere."""
from __future__ import annotations

import glob
import os
import time


def clock_text(clock_24h: bool = False, now: float | None = None) -> str:
    stamp = time.localtime(now)
    return time.strftime("%H:%M", stamp) if clock_24h else time.strftime("%I:%M", stamp).lstrip("0")


def read_battery(root: str = "/sys/class/power_supply") -> tuple:
    """(percent, charging) of the first battery, or (None, False) if there is none."""
    for device in sorted(glob.glob(os.path.join(root, "*"))):
        try:
            with open(os.path.join(device, "type"), encoding="utf-8") as f:
                if f.read().strip() != "Battery":
                    continue
            with open(os.path.join(device, "capacity"), encoding="utf-8") as f:
                percent = int(f.read().strip())
            try:
                with open(os.path.join(device, "status"), encoding="utf-8") as f:
                    status = f.read().strip()
            except OSError:
                status = ""
        except (OSError, ValueError):
            continue
        return max(0, min(100, percent)), status in ("Charging", "Full")
    return None, False


def bottom_screen(sizes: list, width: float = 1240, height: float = 1080) -> int | None:
    """Of the desktop's screens, given as (width, height) in any unit, the index of the bottom one: the one shaped most
    like it. In Desktop Mode the top screen is 16:9 and the bottom one about 8:7, so the shape tells them apart
    whatever scale the desktop gives each."""
    if not sizes:
        return None
    return min(range(len(sizes)), key=lambda i: abs(sizes[i][0] / max(sizes[i][1], 1) - width / height))
