# SPDX-License-Identifier: MIT
# Copied unchanged from Ratatoskr (https://github.com/venatrix-ritz/Ratatoskr), MIT License,
# Copyright (c) 2026 Ven (venatrix-ritz) and Thor Input Contributors. See driver/RATATOSKR-MIT-LICENSE.txt.
"""Active OLED burn-in protection engine for Ratatoskr on the AYN Thor.

Features:
1. Orbital micro-shifter: periodic subpixel/pixel circular orbit (+-1.5 px) that moves
   rendering origins over a 90-second period, preventing sharp-edge static diode wear.
2. Trackpad hint auto-fader: smoothly fades out center hint text after 5 seconds to eliminate
   the primary burn-in hotspot in the center of the glass.
3. Idle luminance throttling: scales static UI luminance down to 40% after 30 seconds of inactivity,
   instantly waking back to 100% upon touch contact.
"""
from __future__ import annotations

import math
import time


class BurnInProtector:
    def __init__(
        self,
        shift_radius: float = 1.5,
        cycle_seconds: float = 90.0,
        idle_timeout: float = 30.0,
        idle_floor: float = 0.4,
        hint_duration: float = 5.0,
    ) -> None:
        self.shift_radius = shift_radius
        self.cycle_seconds = cycle_seconds
        self.idle_timeout = idle_timeout
        self.idle_floor = idle_floor
        self.hint_duration = hint_duration

        self.start_time = time.monotonic()
        self.last_touch_time = self.start_time
        self.mode_change_time = self.start_time

    def record_touch(self, now: float | None = None) -> None:
        """Call whenever any touch contact lands on the digitizer."""
        self.last_touch_time = time.monotonic() if now is None else now

    def notify_mode_change(self, now: float | None = None) -> None:
        """Call whenever the user switches bottom-screen modes."""
        self.mode_change_time = time.monotonic() if now is None else now

    def get_orbital_offset(self, now: float | None = None) -> tuple[float, float]:
        """Return (dx, dy) pixel shift within +-shift_radius based on current time."""
        t = time.monotonic() if now is None else now
        phase = (t % self.cycle_seconds) / self.cycle_seconds * (2.0 * math.pi)
        dx = self.shift_radius * math.cos(phase)
        dy = self.shift_radius * math.sin(phase * 1.5)
        return (dx, dy)

    def get_hint_alpha(self, now: float | None = None) -> float:
        """Return 0.0 to 1.0 opacity for the center hint text. Fades out after hint_duration."""
        t = time.monotonic() if now is None else now
        elapsed = min(t - self.start_time, t - self.mode_change_time)
        if elapsed < self.hint_duration:
            return 1.0
        fade_time = 1.5
        fade_elapsed = elapsed - self.hint_duration
        if fade_elapsed >= fade_time:
            return 0.0
        return max(0.0, 1.0 - (fade_elapsed / fade_time))

    def get_luminance_scale(self, now: float | None = None) -> float:
        """Return 1.0 (active) down to idle_floor (idle rest state) after idle_timeout."""
        t = time.monotonic() if now is None else now
        idle_elapsed = t - self.last_touch_time
        if idle_elapsed <= self.idle_timeout:
            return 1.0
        fade_time = 5.0
        progress = min(1.0, (idle_elapsed - self.idle_timeout) / fade_time)
        return 1.0 - (1.0 - self.idle_floor) * progress
