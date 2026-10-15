# SPDX-License-Identifier: MIT
# Copied unchanged from Ratatoskr (https://github.com/venatrix-ritz/Ratatoskr), MIT License,
# Copyright (c) 2026 Ven (venatrix-ritz) and Thor Input Contributors. See driver/RATATOSKR-MIT-LICENSE.txt.
"""Turns raw multitouch evdev bytes into per-frame contact changes.

Kept free of GTK and uinput so it can be tested anywhere. The kernel timestamp of each SYN_REPORT is carried
on the frame: gestures time themselves with it, not with the moment this process happened to read the bytes
(a stall in the reader would otherwise make a whole batch of frames look simultaneous).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable

EVENT_STRUCT = struct.Struct("llHHi")

EV_SYN = 0x00
EV_ABS = 0x03
SYN_REPORT = 0
SYN_DROPPED = 3
ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39


@dataclass
class Frame:
    ts: float                                   # kernel timestamp of the SYN_REPORT, seconds
    dropped: bool = False                       # the kernel buffer overflowed: all state was discarded
    downs: list[tuple[int, float, float]] = field(default_factory=list)   # (tracking id, x, y) new contacts
    moves: list[tuple[int, float, float]] = field(default_factory=list)   # contacts that moved
    ups: list[int] = field(default_factory=list)                           # contacts that lifted
    live: int = 0                                                          # contacts down after this frame


class TouchFrameParser:
    def __init__(self, to_screen: Callable[[int, int], tuple[float, float]]) -> None:
        self._to_screen = to_screen
        self._tail = b""
        self._reset()

    def _reset(self) -> None:
        self.slot = 0
        self.raw: dict[int, list[int]] = {}
        self.tracking: dict[int, int] = {}                       # slot -> tracking id
        self.active: dict[int, tuple[float, float]] = {}         # tracking id -> last screen position

    def feed(self, data: bytes) -> list[Frame]:
        """Consume bytes read from the device and return the frames completed by them."""
        data = self._tail + data
        usable = len(data) - len(data) % EVENT_STRUCT.size
        self._tail = data[usable:]
        frames: list[Frame] = []
        for off in range(0, usable, EVENT_STRUCT.size):
            sec, usec, etype, code, value = EVENT_STRUCT.unpack_from(data, off)
            if etype == EV_SYN and code == SYN_DROPPED:
                self._reset()
                frames.append(Frame(ts=sec + usec * 1e-6, dropped=True))
            elif etype == EV_ABS:
                if code == ABS_MT_SLOT:
                    self.slot = value
                elif code == ABS_MT_TRACKING_ID:
                    if value >= 0:
                        self.tracking[self.slot] = value
                    else:
                        self.tracking.pop(self.slot, None)
                elif code in (ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
                    self.raw.setdefault(self.slot, [0, 0])[code - ABS_MT_POSITION_X] = value
            elif etype == EV_SYN and code == SYN_REPORT:
                frames.append(self._close_frame(sec + usec * 1e-6))
        return frames

    def resync(self, slots: dict[int, tuple[int, int, int]], ts: float) -> Frame:
        """Rebuild the contact state from the kernel's slot table after SYN_DROPPED.

        slots maps slot -> (tracking id, raw x, raw y) for the live slots (EVIOCGMTSLOTS). Without this, a finger that
        was already down when the buffer overflowed stays invisible until it lifts. Returns a frame whose downs are
        those contacts, for the caller to hand to its touch-down handler."""
        self._reset()
        for slot, (tid, x, y) in slots.items():
            if tid < 0:
                continue
            self.tracking[slot] = tid
            self.raw[slot] = [x, y]
        return self._close_frame(ts)

    def _close_frame(self, ts: float) -> Frame:
        live: dict[int, tuple[float, float]] = {}
        for slot, tid in self.tracking.items():
            x, y = self.raw.get(slot, [0, 0])
            live[tid] = self._to_screen(x, y)
        frame = Frame(ts=ts, live=len(live))
        for tid in list(self.active):
            if tid not in live:
                self.active.pop(tid)
                frame.ups.append(tid)
        for tid, pos in live.items():
            if tid not in self.active:
                self.active[tid] = pos
                frame.downs.append((tid, pos[0], pos[1]))
            elif pos != self.active[tid]:
                self.active[tid] = pos
                frame.moves.append((tid, pos[0], pos[1]))
        return frame
