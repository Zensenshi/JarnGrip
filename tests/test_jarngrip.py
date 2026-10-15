#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for JarnGrip: the pad's layout and input rules, the touchscreen and vibration motor it picks, its painting
(against a stand-in cairo), and the Decky backend. They need no device, GTK or cairo: python3 tests/test_jarngrip.py
(or pytest)."""
import math
import os
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "driver"))
sys.path.insert(0, os.path.join(ROOT, "driver", "bin"))

import debug_codes  # noqa: E402
import haptics  # noqa: E402
import system_status  # noqa: E402
from burn_in import BurnInProtector  # noqa: E402

debug_codes.LOG_PATH = os.devnull  # the engine logs every key press

import pad_model  # noqa: E402
import touch_device  # noqa: E402
from engine import BTN_LEFT, BTN_RIGHT, TouchGestureProcessor  # noqa: E402
from pad_model import BUTTON_STALE_S, MIN_PRESS_S, PadController, build_layout  # noqa: E402

SHIFT, CTRL, ALT = 42, 29, 56


class Bridge:
    """Records what would have gone to the virtual mouse and keyboard."""

    def __init__(self):
        self.events = []
        self.released_all = 0

    def key(self, code, down):
        self.events.append(("key", code, down))

    def mouse_button(self, code, down):
        self.events.append(("btn", code, down))

    def tap_button(self, code, delay_s=0.02):
        self.events += [("btn", code, True), ("btn", code, False)]

    def tap_key(self, code, delay_s=0.02):
        self.events += [("key", code, True), ("key", code, False)]

    def emit_mouse_rel(self, dx, dy):
        self.events.append(("rel", dx, dy))

    def emit_scroll(self, dx, dy):
        self.events.append(("scroll", dx, dy))

    def release_all(self):
        self.released_all += 1

    def take(self):
        events, self.events = self.events, []
        return events


class Clock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def make(**kwargs):
    bridge, clock = Bridge(), Clock()
    pad = PadController(bridge, TouchGestureProcessor(bridge), clock=clock, sleep=clock.sleep, **kwargs)
    pad.apply_config({})
    return pad, bridge, clock


def center(pad, widget_id):
    w = next(w for w in pad.widgets if w.id == widget_id)
    return w.x + w.w / 2, w.y + w.h / 2


_next_tid = [0]


def down(pad, clock, widget_id):
    _next_tid[0] += 1
    pad.touch_down(_next_tid[0], *center(pad, widget_id), clock.now)
    return _next_tid[0]


def tap(pad, clock, widget_id, held=0.08):
    tid = down(pad, clock, widget_id)
    clock.now += held
    pad.touch_up(tid, clock.now)
    clock.now += 0.5  # well past the double-tap time


# ---------------------------------------------------------------------- choosing the touchscreen

def test_only_the_bottom_touchscreen_matches():
    assert touch_device.is_bottom_touchscreen("bottom_touchscreen\n")
    assert not touch_device.is_bottom_touchscreen("top_touchscreen")  # the old rule ("touch" and "screen") took this one
    assert not touch_device.is_bottom_touchscreen("Thor Virtual Trackpad")


def test_the_top_touchscreen_is_never_picked_and_there_is_no_fallback():
    with tempfile.TemporaryDirectory() as tmp:
        dev, sysfs = os.path.join(tmp, "dev"), os.path.join(tmp, "sys")
        os.makedirs(dev)

        def add(node, name):
            open(os.path.join(dev, node), "w").close()
            os.makedirs(os.path.join(sysfs, node, "device"))
            with open(os.path.join(sysfs, node, "device", "name"), "w") as f:
                f.write(name + "\n")

        add("event4", "top_touchscreen")
        add("event5", "gpio-keys")
        assert touch_device.find_bottom_touchscreen(dev, sysfs) is None
        add("event7", "bottom_touchscreen")
        assert touch_device.find_bottom_touchscreen(dev, sysfs) == os.path.join(dev, "event7")


# ---------------------------------------------------------------------- layout

def test_every_view_fits_the_screen_without_overlaps():
    views = [("pad", p, False) for p in range(len(pad_model.PAGES))] + [
        ("trackpad", 0, False), ("keyboard", 0, False), ("keyboard", 0, True), ("settings", 0, False)]
    for view, page, symbols in views:
        _, widgets = build_layout(view, page, symbols)
        assert len({w.id for w in widgets}) == len(widgets), view
        for w in widgets:
            assert w.x >= 0 and w.y >= 0 and w.x + w.w <= pad_model.W and w.y + w.h <= pad_model.H, (view, w.id)
            assert w.w > 60 and w.h > 60, (view, w.id)
        solid = [w for w in widgets if w.kind != "strip"]
        for i, a in enumerate(solid):
            for b in solid[i + 1:]:
                apart = a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
                assert apart, (view, a.id, b.id)


def test_a_page_with_more_than_eight_buttons_splits_into_two_columns():
    def columns(page):
        return len({w.x for w in build_layout("pad", page)[1] if w.kind == "page"})

    assert [columns(p) for p in range(3)] == [2, 1, 2]


def test_number_keys_are_not_much_taller_than_wide_and_are_centered():
    _, widgets = build_layout("pad", 0)
    numbers = [w for w in widgets if w.kind == "number"]
    assert all(w.h <= w.w * pad_model.NUMBER_TALL + 1e-6 for w in numbers)
    above = min(w.y for w in numbers) - pad_model.PANEL_PAD - pad_model.BODY_Y
    below = pad_model.BODY_Y + pad_model.BODY_H - max(w.y + w.h for w in numbers) - pad_model.PANEL_PAD
    assert above > 0 and abs(above - below) < 1e-6


def test_the_gap_between_two_buttons_belongs_to_one_of_them():
    pad, _, _ = make()
    a = next(w for w in pad.widgets if w.id == "number:slot_1")
    assert pad.widget_at(a.x + a.w + pad_model.GAP * 0.4, a.y + 10).id == "number:slot_1"
    assert pad.widget_at(a.x + a.w + pad_model.GAP * 0.6, a.y + 10).id == "number:slot_2"


# ---------------------------------------------------------------------- buttons and modifiers

def test_a_page_button_is_held_for_as_long_as_the_finger_is_down():
    pad, bridge, clock = make()
    tid = down(pad, clock, "page:character")
    assert bridge.take() == [("key", 46, True)]
    clock.now += 2.0
    pad.touch_move(tid, *center(pad, "page:map"), clock.now)  # sliding off does not let go
    assert bridge.take() == []
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("key", 46, False)]


def test_two_page_buttons_can_be_held_at_once():
    pad, bridge, clock = make()
    first, second = down(pad, clock, "page:character"), down(pad, clock, "page:map")
    clock.now += 1
    pad.touch_up(first, clock.now)
    pad.touch_up(second, clock.now)
    assert bridge.take() == [("key", 46, True), ("key", 50, True), ("key", 46, False), ("key", 50, False)]


def test_every_button_sends_one_key_per_press():
    """One press, one action: what Blizzard allows input software to do. No button may send a sequence of keys."""
    modifiers = set(pad_model.MOD_CODES.values())
    pad, bridge, clock = make()
    for page in range(len(pad_model.PAGES)):
        tap(pad, clock, f"tab:{page}")
        for widget_id in [w.id for w in pad.widgets if w.kind in ("page", "number")]:
            tap(pad, clock, widget_id)
            pressed = [code for kind, code, down in bridge.take() if kind == "key" and down and code not in modifiers]
            assert len(pressed) == 1, (widget_id, pressed)


def test_a_number_is_sent_when_the_finger_lifts():
    pad, bridge, clock = make()
    tid = down(pad, clock, "number:slot_1")
    clock.now += 1.0
    assert bridge.take() == []
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("key", 2, True), ("key", 2, False)]


def swipe(pad, clock, widget_id, dx, dy, steps=5):
    tid = down(pad, clock, widget_id)
    x, y = center(pad, widget_id)
    for i in range(1, steps + 1):
        clock.now += 0.02
        pad.touch_move(tid, x + dx * i / steps, y + dy * i / steps, clock.now)
    shown = pad.swipes.get(widget_id)
    pad.touch_up(tid, clock.now)
    clock.now += 0.5
    return shown


def test_swiping_a_number_up_adds_shift_down_adds_ctrl_and_left_cancels():
    pad, bridge, clock = make()
    assert swipe(pad, clock, "number:slot_5", 10, -90) == "shift"
    assert bridge.take() == [("key", SHIFT, True), ("key", 6, True), ("key", 6, False), ("key", SHIFT, False)]
    assert swipe(pad, clock, "number:slot_5", -10, 90) == "ctrl"
    assert bridge.take() == [("key", CTRL, True), ("key", 6, True), ("key", 6, False), ("key", CTRL, False)]
    assert swipe(pad, clock, "number:slot_5", -90, 10) == "cancel"
    assert bridge.take() == [] and not pad.lit(next(w for w in pad.widgets if w.id == "number:slot_5"))
    assert swipe(pad, clock, "number:slot_5", 90, 0) is None  # right is a plain press
    assert swipe(pad, clock, "number:slot_5", 30, 0) is None  # a wobble is not a swipe
    assert bridge.take() == [("key", 6, True), ("key", 6, False)] * 2
    assert not pad.swipes


def test_a_swipe_decides_where_the_finger_lifts():
    buzzes = []
    pad, bridge, clock = make(haptic=buzzes.append)
    tid = down(pad, clock, "number:slot_1")
    x, y = center(pad, "number:slot_1")
    pad.touch_move(tid, x, y - 80, clock.now)
    pad.touch_move(tid, x - 80, y, clock.now)
    pad.touch_move(tid, x + 5, y, clock.now)  # back to the middle: a plain press after all
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("key", 2, True), ("key", 2, False)]
    assert buzzes == ["press", "tick", "tick", "tick"]


def test_a_number_tap_does_not_hold_up_the_touch_thread():
    pending = []
    pad, bridge, clock = make(later=lambda delay, job: pending.append((delay, job)))
    tid = down(pad, clock, "number:slot_1")
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("key", 2, True)] and not clock.slept  # down at once, nothing slept
    (delay, job), = pending
    assert delay == MIN_PRESS_S
    job()  # the timer fires
    assert bridge.take() == [("key", 2, False)]


def test_a_very_short_press_is_stretched():
    pad, bridge, clock = make()
    tid = down(pad, clock, "number:slot_1")
    pad.touch_up(tid, clock.now)  # both frames arrived in one read
    assert clock.slept == [MIN_PRESS_S]


def test_an_armed_modifier_applies_to_the_next_click_and_then_lets_go():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:shift")
    assert bridge.take() == [("key", SHIFT, True)]
    assert pad.glows(next(w for w in pad.widgets if w.id == "mouse:left"))
    tap(pad, clock, "mouse:left")
    assert bridge.take() == [("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False), ("key", SHIFT, False)]
    assert not pad.held_mods


def test_a_double_tap_locks_a_modifier_until_it_is_tapped_again():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:ctrl", held=0.05)
    clock.now -= 0.4  # the second tap follows 0.15 s after the first
    tap(pad, clock, "mod:ctrl")
    assert CTRL in pad.locked_mods
    tap(pad, clock, "mouse:left")
    tap(pad, clock, "mouse:right")
    assert bridge.take() == [("key", CTRL, True), ("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False),
                             ("btn", BTN_RIGHT, True), ("btn", BTN_RIGHT, False)]
    tap(pad, clock, "mod:ctrl")
    assert bridge.take() == [("key", CTRL, False)] and not pad.held_mods


def test_a_second_tap_after_the_double_tap_time_turns_the_modifier_off():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:alt")
    tap(pad, clock, "mod:alt")
    assert bridge.take() == [("key", ALT, True), ("key", ALT, False)]


def test_the_number_block_has_no_modifier_row():
    _, widgets = build_layout("pad", 0)
    assert not [w for w in widgets if w.kind == "mod"]
    assert [w for w in build_layout("trackpad", 0)[1] if w.kind == "mod"]


def test_a_page_button_sends_its_own_modifiers():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:1")
    tap(pad, clock, "page:previous_enemy")
    assert bridge.take() == [("key", SHIFT, True), ("key", 15, True), ("key", 15, False), ("key", SHIFT, False)]


def test_bindings_from_the_config():
    pad, bridge, clock = make()
    pad.apply_config({"bindings": {"character": 30, "slot_1": "ctrl+59", "spellbook": "nonsense", "talents": 999}})
    tap(pad, clock, "page:character")
    assert bridge.take() == [("key", 30, True), ("key", 30, False)]
    tap(pad, clock, "number:slot_1")
    assert bridge.take() == [("key", CTRL, True), ("key", 59, True), ("key", 59, False), ("key", CTRL, False)]
    tap(pad, clock, "page:spellbook")
    tap(pad, clock, "page:talents")
    assert bridge.take() == [("key", 25, True), ("key", 25, False), ("key", 49, True), ("key", 49, False)]
    pad.apply_config({"bindings": {"previous_enemy": 33}, "sensitivity": "oops"})  # a number keeps the button's Shift
    tap(pad, clock, "tab:1")
    tap(pad, clock, "page:previous_enemy")
    assert bridge.take() == [("key", SHIFT, True), ("key", 33, True), ("key", 33, False), ("key", SHIFT, False)]


def test_switching_view_lets_go_of_held_buttons_and_modifiers():
    pad, bridge, clock = make()
    held = down(pad, clock, "page:character")
    pending = down(pad, clock, "number:slot_1")
    clock.now += 1
    tap(pad, clock, "mode:trackpad")
    assert pad.view == "trackpad"
    # Character was down and is let go; the number had sent nothing yet and never will.
    assert bridge.take() == [("key", 46, True), ("key", 46, False)]
    pad.touch_up(held, clock.now)  # the fingers lift later: nothing more happens
    pad.touch_up(pending, clock.now)
    assert bridge.take() == []
    tap(pad, clock, "mod:shift")
    clicking = down(pad, clock, "mouse:left")
    tap(pad, clock, "mode:keyboard")
    assert bridge.take() == [("key", SHIFT, True), ("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False),
                             ("key", SHIFT, False)]
    pad.touch_up(clicking, clock.now)
    assert bridge.take() == []
    tap(pad, clock, "mode:keyboard")
    assert pad.view == "pad"
    tap(pad, clock, "mode:keyboard")
    tap(pad, clock, "tab:2")
    assert (pad.view, pad.page) == ("pad", 2)


def test_click_buttons_hold_and_a_double_tap_locks():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tid = down(pad, clock, "mouse:right")
    assert bridge.take() == [("btn", BTN_RIGHT, True)]
    clock.now += 3  # held: this is how the camera is turned
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("btn", BTN_RIGHT, False)]

    clock.now += 1
    tap(pad, clock, "mouse:left", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mouse:left", held=0.05)
    assert bridge.take() == [("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False), ("btn", BTN_LEFT, True)]
    assert pad.mouse[BTN_LEFT].locked and not pad.gesture.tap_to_click
    tap(pad, clock, "mouse:left")
    assert bridge.take() == [("btn", BTN_LEFT, False)]
    assert not pad.mouse[BTN_LEFT].locked and pad.gesture.tap_to_click


def test_the_surface_moves_the_pointer_and_a_tap_clicks():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    x, y = center(pad, "surface")
    pad.touch_down(1, x, y, clock.now)
    for i in range(1, 6):
        pad.touch_move(1, x + 20 * i, y, clock.now + 0.02 * i)
    pad.touch_up(1, clock.now + 0.5)
    moves = [e for e in bridge.take() if e[0] == "rel"]
    assert moves and all(dx > 0 and dy == 0 for _, dx, dy in moves)

    pad.all_lifted(clock.now + 0.5)
    pad.touch_down(2, x, y, clock.now + 2.0)
    pad.touch_up(2, clock.now + 2.05)
    assert bridge.take() == [("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False)]


def test_the_scroll_strip_scrolls_and_never_moves_the_pointer():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    x, y = center(pad, "strip")
    assert pad.widget_at(x, y).id == "strip"
    pad.touch_down(1, x, y, clock.now)
    for i in range(1, 9):
        pad.touch_move(1, x - 30 * i, y + 10 * i, clock.now + 0.02 * i)  # drifting off the strip sideways
    events = bridge.take()
    assert {e[0] for e in events} == {"scroll"}
    assert sum(e[2] for e in events) == -240  # 80 px down: two notches down


# ---------------------------------------------------------------------- keyboard

def key_id(pad, label):
    return next(w.id for w in pad.widgets if w.kind == "key" and w.data.label == label)


def test_the_keyboard_types_with_one_shot_shift_and_caps():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:keyboard")
    tap(pad, clock, key_id(pad, "a"))
    assert bridge.take() == [("key", 30, True), ("key", 30, False)]
    tap(pad, clock, key_id(pad, "Shift"))
    assert pad.kb_shift == "on" and pad.key_label(next(w.data for w in pad.widgets if w.id == key_id(pad, "1"))) == "!"
    tap(pad, clock, key_id(pad, "a"))
    assert bridge.take() == [("key", SHIFT, True), ("key", 30, True), ("key", SHIFT, False), ("key", 30, False)]
    assert pad.kb_shift == "off"
    tap(pad, clock, key_id(pad, "Shift"))
    tap(pad, clock, key_id(pad, "Shift"))
    assert pad.kb_shift == "caps"
    tap(pad, clock, key_id(pad, "1"))  # caps does not shift the digits
    tap(pad, clock, key_id(pad, "Enter"))
    assert bridge.take() == [("key", 2, True), ("key", 2, False), ("key", 28, True), ("key", 28, False)]


def test_the_symbols_page_types_the_character_it_shows():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:keyboard")
    tap(pad, clock, key_id(pad, "?123"))
    assert pad.kb_symbols
    tap(pad, clock, key_id(pad, "!"))
    tap(pad, clock, key_id(pad, "-"))
    assert bridge.take() == [("key", SHIFT, True), ("key", 2, True), ("key", SHIFT, False), ("key", 2, False),
                             ("key", 12, True), ("key", 12, False)]
    tap(pad, clock, key_id(pad, "ABC"))
    assert not pad.kb_symbols


def test_the_keyboard_sits_low_under_a_small_trackpad():
    for symbols in (False, True):
        _, widgets = build_layout("keyboard", 0, symbols)
        keys = [w for w in widgets if w.kind == "key"]
        surface = next(w for w in widgets if w.kind == "surface")
        top = min(k.y for k in keys)
        assert top >= pad_model.BODY_Y + pad_model.BODY_H - 5 * pad_model.KEY_ROW_H, symbols  # both pages fill the same height
        assert surface.y + surface.h < top and surface.h >= 200


def test_the_keyboard_trackpad_moves_and_clicks_without_typing():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:keyboard")
    x, y = center(pad, "surface")
    pad.touch_down(1, x, y, clock.now)
    for i in range(1, 6):
        pad.touch_move(1, x + 20 * i, y, clock.now + 0.02 * i)
    pad.touch_up(1, clock.now + 0.5)
    assert {e[0] for e in bridge.take()} == {"rel"}
    pad.touch_down(2, x, y, clock.now + 2.0)
    pad.touch_up(2, clock.now + 2.05)
    assert bridge.take() == [("btn", BTN_LEFT, True), ("btn", BTN_LEFT, False)]


def test_the_preview_shows_what_a_key_typed():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:keyboard")
    tap(pad, clock, key_id(pad, "Shift"))
    a = key_id(pad, "a")
    tid = down(pad, clock, a)
    assert pad.kb_shift == "off" and pad.key_typed[a] == "A"  # the one-shot Shift has let go, the preview keeps it
    pad.touch_up(tid, clock.now)


# ---------------------------------------------------------------------- haptics and themes

def test_a_buzz_for_every_button_but_not_for_the_trackpad():
    buzzes = []
    pad, bridge, clock = make(haptic=buzzes.append)
    tap(pad, clock, "number:slot_1")
    tap(pad, clock, "page:character")
    tap(pad, clock, "status")  # the clock and battery are not a button
    tap(pad, clock, "mode:trackpad")
    assert buzzes == ["press", "press", "tick"]
    for target in ("surface", "strip"):
        pad.touch_down(50, *center(pad, target), clock.now)
        pad.touch_up(50, clock.now + 0.05)
        pad.all_lifted(clock.now + 0.05)
    tap(pad, clock, "mouse:left", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mouse:left", held=0.05)  # a double tap locks it: two buzzes
    assert buzzes == ["press", "press", "tick", "press", "press", "lock"]


def test_locking_a_modifier_buzzes_twice():
    buzzes = []
    pad, bridge, clock = make(haptic=buzzes.append)
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:ctrl", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mod:ctrl")
    assert buzzes == ["tick", "press", "lock"]


def test_a_theme_picked_on_the_pad_is_shown_and_kept():
    saved = []
    pad, bridge, clock = make(on_theme=saved.append)
    tap(pad, clock, "mode:settings")
    tap(pad, clock, "theme:charcoal")
    assert pad.theme == "charcoal" and saved == ["charcoal"]
    tap(pad, clock, "theme:charcoal")
    assert saved == ["charcoal"]
    pad.apply_config({"theme": "nonsense"})
    assert pad.theme == "charcoal"
    pad.apply_config({"theme": "dark"})
    assert pad.theme == "dark"
    pad.apply_config({"theme": "oled"})  # the old name of Dark
    assert pad.theme == "dark"
    pad.apply_config({"theme": "steamos"})  # the old name of Charcoal
    assert pad.theme == "charcoal"


def test_the_decky_panel_and_backend_list_the_same_themes():
    import re

    sys.path.insert(0, ROOT)
    import main

    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        listed = re.findall(r'data:"(\w+)"', re.search(r"const themeOptions=(\[.*?\]);", f.read()).group(1))
    assert tuple(listed) == pad_model.THEME_IDS == main.THEMES

def test_the_force_feedback_effect_has_the_kernels_layout():
    if haptics.struct.calcsize("P") == 8:
        assert haptics.EFFECT_SIZE == 48 and haptics.EVIOCSFF == 0x40304580
    buf = haptics.pack_effect(haptics.FF_RUMBLE, -1, 20, 1.0)
    assert haptics.struct.unpack_from("HhHHHHH", buf) == (haptics.FF_RUMBLE, -1, 0, 0, 0, 20, 0)
    assert haptics.struct.unpack_from("HH", buf, haptics._UNION_AT) == (0xFFFF, 0xFFFF)


def test_the_vibration_motor_is_found_by_what_it_can_play():
    with tempfile.TemporaryDirectory() as tmp:
        dev, sysfs = os.path.join(tmp, "dev"), os.path.join(tmp, "sys")
        os.makedirs(dev)

        def add(node, name, ff):
            open(os.path.join(dev, node), "w").close()
            os.makedirs(os.path.join(sysfs, node, "device", "capabilities"))
            with open(os.path.join(sysfs, node, "device", "name"), "w") as f:
                f.write(name + "\n")
            with open(os.path.join(sysfs, node, "device", "capabilities", "ff"), "w") as f:
                f.write(ff + "\n")

        # As read on an AYN Thor (64-bit longs).
        add("event2", "bottom_touchscreen", "0")
        add("event7", "AYN Odin2 Gamepad", "30000 0")
        add("event8", "qcom-hv-haptics", "100070000 0")
        add("event11", "Microsoft X-Box 360 pad 0", "10000 0")
        found = [(os.path.basename(n), name, kinds) for n, name, kinds in haptics.find_motors(dev, sysfs)]
        if haptics._LONG_BITS == 64:
            assert found == [  # event7 is root-only on the Thor: opening it fails and the next one is tried
                ("event11", "Microsoft X-Box 360 pad 0", (haptics.FF_RUMBLE,)),
                ("event7", "AYN Odin2 Gamepad", (haptics.FF_RUMBLE, haptics.FF_PERIODIC)),
                ("event8", "qcom-hv-haptics", (haptics.FF_CONSTANT, haptics.FF_RUMBLE, haptics.FF_PERIODIC))]


def test_a_vibration_device_held_by_another_program_is_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        nodes = {name: os.path.join(tmp, name) for name in ("haptics", "pad")}
        for node in nodes.values():
            open(node, "w").close()
        found = [(nodes["haptics"], "qcom-hv-haptics", (haptics.FF_CONSTANT,)),
                 (nodes["pad"], "Microsoft X-Box 360 pad 0", (haptics.FF_RUMBLE,))]
        answers = [True, False]  # the motor is held, the virtual pad is free
        uploads = []
        motor = haptics.Haptics(find=lambda: found, held=lambda fd: answers.pop(0),
                                upload=lambda fd, kind, effect, ms, strength: uploads.append(kind) or 0)
        motor.configure(True, 0.7, 20)
        assert uploads == [haptics.FF_RUMBLE] and motor.status.startswith("Microsoft X-Box 360 pad 0")
        motor.close()
        motor = haptics.Haptics(find=lambda: found, held=lambda fd: True)
        motor.configure(True, 0.7, 20)
        assert motor.fd < 0 and "held by another program" in motor.status


def test_each_buzz_is_started_and_then_stopped():
    from touch_frames import EVENT_STRUCT

    read_end, write_end = os.pipe()
    motor = haptics.Haptics(find=lambda: [])
    motor.fd, motor.effect, motor.length_ms = write_end, 3, 5
    motor.pulse()
    events = [EVENT_STRUCT.unpack(os.read(read_end, EVENT_STRUCT.size))[2:] for _ in range(2)]  # waits for the stop
    assert events == [(haptics.EV_FF, 3, 1), (haptics.EV_FF, 3, 0)]
    motor.pulse("lock")  # two buzzes
    events = [EVENT_STRUCT.unpack(os.read(read_end, EVENT_STRUCT.size))[2:] for _ in range(4)]
    assert [value for _, _, value in events] == [1, 0, 1, 0]
    motor.fd = -1
    os.close(read_end)
    os.close(write_end)


def test_haptics_without_a_motor_do_nothing_and_look_again_later():
    clock = Clock()
    looked = []
    motor = haptics.Haptics(find=lambda: looked.append(1) or [], clock=clock)
    motor.configure(True, 0.7, 20)
    motor.pulse()
    assert motor.status == "no vibration motor found" and len(looked) == 1
    motor.configure(True, 0.7, 20)
    assert len(looked) == 1
    clock.now += haptics.RETRY_S
    motor.configure(True, 0.7, 20)
    assert len(looked) == 2
    motor.configure(False, 0.7, 20)
    assert motor.status == "off"
    motor.configure(True, 0.7, 20, effect="rumble")  # a forced effect type looks again at once
    assert len(looked) == 3 and motor.effect_kind == haptics.FF_RUMBLE


# ---------------------------------------------------------------------- lost lifts and shutdown

def test_a_button_whose_lift_was_lost_is_let_go():
    pad, bridge, clock = make()
    tid = down(pad, clock, "page:character")
    bridge.take()
    pad.expire(clock.now + BUTTON_STALE_S - 0.1)
    assert bridge.take() == []
    pad.expire(clock.now + BUTTON_STALE_S + 0.1)
    assert bridge.take() == [("key", 46, False)]
    # A new finger in the ghost's slot keeps the old id and shows up as movement: it is a new touch.
    pad.touch_move(tid, *center(pad, "page:map"), clock.now + 10)
    assert bridge.take() == [("key", 50, True)]


def test_a_new_finger_on_a_button_replaces_a_stuck_one():
    pad, bridge, clock = make()
    down(pad, clock, "page:character")
    clock.now += 1
    second = down(pad, clock, "page:character")
    assert bridge.take() == [("key", 46, True), ("key", 46, False), ("key", 46, True)]
    pad.touch_up(second, clock.now + 1)
    assert bridge.take() == [("key", 46, False)] and not pad.pressed


def test_no_contacts_left_means_nothing_is_held():
    pad, bridge, clock = make()
    down(pad, clock, "number:slot_1")
    down(pad, clock, "page:map")
    pad.all_lifted(clock.now + 1)
    assert [e for e in bridge.take() if not e[2]] == [("key", 2, False), ("key", 50, False)]
    assert not pad.touches and not pad.key_refs


def test_release_everything_leaves_nothing_down():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:shift", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mod:shift")
    down(pad, clock, "mouse:left")
    pad.release_everything()
    downs = {e[1] for e in bridge.events if e[2]}
    ups = {e[1] for e in bridge.events if not e[2]}
    assert downs == ups and bridge.released_all == 1
    assert not pad.key_refs and not pad.held_mods and not pad.touches


def test_unstick_presses_and_releases_every_modifier_and_lets_go_of_locked_ones():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:trackpad")
    tap(pad, clock, "mod:ctrl", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mod:ctrl")  # locked on
    bridge.take()
    tap(pad, clock, "mode:settings")  # switching view lets go of it already
    bridge.take()
    tap(pad, clock, "unstick")
    assert bridge.take() == [("key", SHIFT, True), ("key", SHIFT, False), ("key", CTRL, True), ("key", CTRL, False),
                             ("key", ALT, True), ("key", ALT, False)]
    assert not pad.key_refs and not pad.held_mods


def test_tapping_close_asks_to_close_only_when_released_on_it():
    closed = []
    pad, bridge, clock = make()
    pad.on_close = lambda: closed.append(1)
    tap(pad, clock, "mode:settings")
    tid = down(pad, clock, "close")
    pad.touch_move(tid, 100, 300, clock.now)
    pad.touch_up(tid, clock.now)
    assert not closed
    tap(pad, clock, "close")
    assert closed == [1]


def test_the_decky_panel_lists_the_same_controls_and_default_keys():
    import json
    import re

    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        listed = json.loads(re.sub(r"(\w+):", r'"\1":', re.search(r"const defaults=(\{.*?\});", f.read()).group(1)))
    slots = [s for _, page in pad_model.PAGES for s in page] + list(pad_model.NUMBER_SLOTS)
    assert listed == {s.id: s.key for s in slots}


def test_the_decky_key_picker_names_every_default_key_and_knows_the_default_modifiers():
    import json
    import re

    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        js = f.read()
    names = json.loads(re.search(r"const keyNames=(\[.*?\]);", js).group(1))
    codes = [code for code, _ in names]
    assert len(codes) == len(set(codes)) and all(0 < code < 248 for code in codes)
    slots = [s for _, page in pad_model.PAGES for s in page] + list(pad_model.NUMBER_SLOTS)
    assert {s.key for s in slots} <= set(codes)
    mods = json.loads(re.sub(r"(\w+):", r'"\1":', re.search(r"const defaultMods=(\{.*?\});", js).group(1)))
    names_of = {code: name for name, _, code in pad_model.MODIFIERS}
    assert mods == {s.id: [names_of[m] for m in s.mods] for s in slots if s.mods}


# ---------------------------------------------------------------------- header status and burn-in

def test_the_battery_is_read_from_sysfs():
    with tempfile.TemporaryDirectory() as tmp:
        def add(name, kind, **files):
            os.makedirs(os.path.join(tmp, name))
            for key, value in dict(type=kind, **files).items():
                with open(os.path.join(tmp, name, key), "w") as f:
                    f.write(value + "\n")

        assert system_status.read_battery(tmp) == (None, False)
        add("ac", "Mains", online="1")
        add("battery", "Battery", capacity="82", status="Charging")
        assert system_status.read_battery(tmp) == (82, True)
    assert system_status.clock_text(True, 0).count(":") == 1
    assert not system_status.clock_text(False, 0).startswith("0")


def test_burn_in_dims_an_untouched_pad_and_a_touch_wakes_it():
    burn = BurnInProtector(idle_timeout=60.0, idle_floor=0.4)
    burn.record_touch(1000.0)
    assert burn.get_luminance_scale(1050.0) == 1.0
    assert abs(burn.get_luminance_scale(1100.0) - 0.4) < 1e-9
    burn.record_touch(1100.0)
    assert burn.get_luminance_scale(1100.5) == 1.0
    assert all(abs(v) <= 1.5 for v in burn.get_orbital_offset(1234.0))


# ---------------------------------------------------------------------- Decky backend

def backend(tmp):
    import asyncio
    import importlib
    from pathlib import Path

    sys.path.insert(0, ROOT)
    main = importlib.import_module("main")
    main.CFG = Path(tmp) / "config.json"
    main.BACKGROUNDS = Path(tmp) / "Pictures"
    main.APP_MENU = Path(tmp) / "applications" / "jarngrip.desktop"
    main.AUTOSTART = Path(tmp) / "autostart" / "jarngrip.desktop"
    main.UID, main.GID = os.getuid(), os.getgid()
    plugin = main.Plugin()
    return lambda name, *args: asyncio.run(getattr(plugin, name)(*args))


def test_the_backend_never_asks_decky_for_root():
    import json

    with open(os.path.join(ROOT, "plugin.json"), encoding="utf-8") as f:
        assert "root" not in json.load(f).get("flags", [])


def test_the_backend_keeps_what_a_save_leaves_out_and_ignores_nonsense():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        call("save_config", {"sensitivity": 2.5, "theme": "dark", "haptics": False})
        cfg = call("save_config", {"sensitivity": "oops", "theme": "nope", "glass_blur": 9, "bindings": "x"})["config"]
        assert (cfg["sensitivity"], cfg["theme"], cfg["haptics"], cfg["glass_blur"]) == (2.5, "dark", False, 5)
        assert cfg["bindings"] == {}
        assert call("save_config", {"background_image": "../../etc/passwd"})["config"]["background_image"] == ""


def test_desktop_mode_adds_and_removes_the_autostart_entry():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        import main

        call("save_config", {"desktop_mode": True})
        assert main.AUTOSTART.exists() and main.APP_MENU.exists()
        assert "--autostart" in main.AUTOSTART.read_text()
        call("save_config", {"theme": "dark"})  # other settings leave it alone
        assert main.AUTOSTART.exists()
        call("save_config", {"desktop_mode": False})
        assert not main.AUTOSTART.exists() and main.APP_MENU.exists()


def test_the_desktop_entries_start_the_same_driver_as_the_service():
    with open(os.path.join(ROOT, "systemd", "jarngrip.service"), encoding="utf-8") as f:
        driver = next(word for word in f.read().split() if word.endswith("jarngrip.py"))
    for name in ("jarngrip.desktop", "jarngrip-autostart.desktop"):
        with open(os.path.join(ROOT, "desktop", name), encoding="utf-8") as f:
            exec_line = next(line for line in f if line.startswith("Exec="))
        assert driver in exec_line and "--desktop" in exec_line and "GDK_BACKEND=wayland" in exec_line


def test_the_bottom_screen_is_picked_by_its_shape():
    # As KDE reported them on a Thor in Desktop Mode: the top screen 960x540, the bottom 443x386 (scale 2.8).
    assert system_status.bottom_screen([(960, 540), (443, 386)]) == 1
    assert system_status.bottom_screen([(443, 386), (960, 540)]) == 0
    assert system_status.bottom_screen([]) is None


def test_profiles_can_be_saved_switched_and_deleted():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        call("save_config", {"bindings": {"map": 33}})
        assert call("save_profile", "  Raid  ")["config"]["active_profile"] == "Raid"
        call("save_config", {"bindings": {}})
        cfg = call("select_profile", "Raid")["config"]
        assert cfg["bindings"] == {"map": 33}
        assert sorted(cfg["profiles"]) == ["Default", "Raid"]
        cfg = call("delete_profile", "Raid")["config"]
        assert cfg["active_profile"] == "Default" and cfg["bindings"] == {}
        assert not call("delete_profile", "Default")["ok"]  # the last one stays
        assert not call("save_profile", "x" * 25)["ok"]


# ---------------------------------------------------------------------- painting

class Anything:
    def __getattr__(self, name):
        return lambda *a, **k: None


class Context(Anything):
    """A stand-in cairo context: it draws nothing, and every letter is 10 units wide."""

    def text_extents(self, text):
        return types.SimpleNamespace(x_bearing=0.0, width=10.0 * len(text))


def painter():
    """pad_draw, imported against a stand-in cairo, to run the drawing code without a display."""
    sys.modules.setdefault("cairo", types.SimpleNamespace(
        LinearGradient=lambda *a: Anything(), RadialGradient=lambda *a: Anything(), FONT_SLANT_NORMAL=0,
        FONT_WEIGHT_BOLD=1, LINE_CAP_ROUND=1, LINE_JOIN_ROUND=1))
    import pad_draw

    return pad_draw


def test_every_swipe_fan_stays_on_the_screen():
    pad_draw = painter()
    _, widgets = build_layout("pad", 0)
    for w in (w for w in widgets if w.kind == "number"):
        cx, cy = w.x + w.w / 2, w.y + w.h / 2
        for swipe, angle in pad_draw.FAN_DIRECTIONS.items():
            reach = pad_draw._fan_reach(cx, cy, angle)
            end_x, end_y = cx + reach * math.cos(angle), cy + reach * math.sin(angle)
            assert 0 <= end_x <= pad_model.W and 0 <= end_y <= pad_model.H, (w.id, swipe)
            assert reach > 100, (w.id, swipe)  # room for at least a short fan with its lettering

def test_every_bundled_font_is_used_by_a_theme_and_ships_with_its_license():
    pad_draw = painter()
    folder = os.path.join(ROOT, "driver", "fonts")
    families = {name.split("-")[0] for name in os.listdir(folder) if name.endswith(".ttf")}
    assert families == {t.font for t in pad_draw.THEMES.values()} - {"serif", "sans-serif"}
    assert all(os.path.exists(os.path.join(folder, f"{family}-OFL.txt")) for family in families)


def test_a_theme_without_its_bundled_font_falls_back():
    pad_draw = painter()
    pad_draw.LOADED_FONTS = set()
    assert pad_draw._font(pad_draw.THEMES["classic"]) == "serif"
    pad_draw.LOADED_FONTS = {"Cinzel", "Nunito"}
    assert pad_draw._font(pad_draw.THEMES["classic"]) == "Cinzel"
    assert pad_draw._font(pad_draw.THEMES["glass"]) == "Nunito"
    assert pad_draw._font(pad_draw.THEMES["charcoal"]) == "sans-serif"


def test_every_view_paints():
    """Runs the real painter against a stand-in cairo, to catch mistakes in the drawing code without a display."""
    pad_draw = painter()

    for theme in pad_model.THEME_IDS:
        pad, bridge, clock = make()
        pad.apply_config({"theme": theme})
        pad.info_lines = ["Touch: /dev/input/event5 (bottom_touchscreen)"]
        pad.status_info = ("12:34", 9, False)
        pad.shift, pad.brightness, pad.hint_alpha = (1.0, -0.5), 0.4, 0.5
        tid = down(pad, clock, "number:slot_1")
        x, y = center(pad, "number:slot_1")
        pad.touch_move(tid, x - 90, y, clock.now)  # its swipe hint is painted
        pad_draw.paint(Context(), pad)
        pad.status_info = ("1:05", 100, True)
        for target in ("tab:0", "tab:1", "tab:2", "mode:trackpad", "mode:keyboard", "mode:settings"):
            tap(pad, clock, target)
            pad_draw.paint(Context(), pad)
        tap(pad, clock, "mode:keyboard")
        down(pad, clock, key_id(pad, "q"))  # held: its preview is painted
        down(pad, clock, key_id(pad, "p"))
        pad_draw.paint(Context(), pad)
        tap(pad, clock, key_id(pad, "?123"))
        pad_draw.paint(Context(), pad)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   ", name)
            except Exception as err:  # noqa: BLE001
                failed += 1
                print("FAIL ", name, "-", type(err).__name__, err)
    sys.exit(1 if failed else 0)
