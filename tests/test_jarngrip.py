#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for JarnGrip: the pad's layout and input rules, the touchscreen and vibration motor it picks, its painting
(against a stand-in cairo), and the Decky backend. They need no device, GTK or cairo: python3 tests/test_jarngrip.py
(or pytest)."""
import math
import os
import re
import struct
import sys
import tempfile
import time
import types
from pathlib import Path

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
    views = [("pad", p, False, game) for game in pad_model.GAMES.values() for p in range(len(game.pages))] + [
        ("trackpad", 0, False, pad_model.WOW), ("trackpad", 0, False, pad_model.DESKTOP), ("keyboard", 0, False, pad_model.WOW),
        ("keyboard", 0, True, pad_model.WOW), ("keyboard", 0, False, pad_model.DESKTOP),
        ("keyboard", 0, True, pad_model.DESKTOP), ("settings", 0, False, pad_model.WOW)]
    for view, page, symbols, game in views:
        _, widgets = build_layout(view, page, symbols, game)
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
    def columns(page, game):
        return len({w.x for w in build_layout("pad", page, game=game)[1] if w.kind == "page" and not w.data.radial})

    assert [columns(p, pad_model.WOW) for p in range(2)] == [2, 1]  # Utility is laid out in rows
    assert [columns(p, pad_model.FFXI) for p in range(2)] == [2, 2]


def test_number_keys_are_not_much_taller_than_wide_and_are_centered():
    _, widgets = build_layout("pad", 0)
    numbers = [w for w in widgets if w.kind == "number"]
    assert all(w.h <= w.w * pad_model.NUMBER_TALL + 1e-6 for w in numbers)
    above = min(w.y for w in numbers) - pad_model.PANEL_PAD - pad_model.BODY_Y
    below = pad_model.BODY_Y + pad_model.BODY_H - max(w.y + w.h for w in numbers) - pad_model.PANEL_PAD
    assert above > 0 and abs(above - below) < 1e-6


def test_number_pad_icons_make_the_number_keys_square_and_still_fit_without_overlaps():
    for game in (pad_model.WOW, pad_model.FFXI):
        for page in range(len(game.pages)):
            _, widgets = build_layout("pad", page, game=game, square_numbers=True)
            numbers = [w for w in widgets if w.kind == "number"]
            assert len(numbers) == 12 and all(abs(w.w - w.h) < 1e-6 for w in numbers)
            for w in widgets:
                assert w.x >= 0 and w.y >= 0 and w.x + w.w <= pad_model.W and w.y + w.h <= pad_model.H, w.id
            for i, a in enumerate(widgets):
                for b in widgets[i + 1:]:
                    assert a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y, (a.id, b.id)


def test_a_swipes_square_opens_the_way_it_was_swiped_and_on_the_screen():
    for game in (pad_model.WOW, pad_model.FFXI):
        _, widgets = build_layout("pad", 0, game=game, square_numbers=True)
        numbers = [w for w in widgets if w.kind == "number"]
        bottom = max(w.y for w in numbers)
        for w in numbers:
            up, second, cancel = (pad_model.swipe_square(w, swipe) for swipe in ("up", "down", "cancel"))
            for x, y, size in (up, second, cancel):
                assert 0 <= x and x + size <= pad_model.W and 0 <= y and y + size <= pad_model.H
            # The modifiers' squares are bigger than the key, so that they stand out; cancel's is the key's size.
            assert up[2] == second[2] == w.w * pad_model.SWIPE_GROW > w.w == cancel[2]
            g, edge = pad_model.GAP, pad_model.MARGIN / 2
            assert up[0] == min(w.x, pad_model.W - edge - up[2]), w.id  # from the key's left edge, right
            assert abs(up[1] - max(edge, w.y - g - up[2])) < 1e-6, w.id  # above, the top row's over the tabs
            assert abs(second[0] + second[2] + g - w.x) < 1e-6, w.id  # left of it, down from the key's top
            assert second[1] == w.y or second[1] == up[1] + up[2] + g, w.id  # or below the first, pushed into its way
            # The two never overlap, nor cover the cancel square.
            for a, b in ((up, second), (second, cancel)):
                assert a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[2] <= b[1] or b[1] + b[2] <= a[1], w.id
            assert cancel[0] == w.x  # below, or over the bottom row's own key
            assert abs(cancel[1] - (w.y + w.h + g)) < 1e-6 if w.y < bottom else cancel[1] < w.y + w.h, w.id


def test_icon_mode_leaves_the_number_block_where_it_was():
    for game in (pad_model.WOW, pad_model.FFXI):
        for page in range(len(game.pages)):
            plain = {w.id: w for w in build_layout("pad", page, game=game)[1]}
            icons = {w.id: w for w in build_layout("pad", page, game=game, square_numbers=True)[1]}
            for key in (k for k in plain if k.startswith("number:")):
                assert (icons[key].x, icons[key].w) == (plain[key].x, plain[key].w), key
            for key in (k for k in plain if k.startswith("page:")):
                assert (icons[key].x, icons[key].w) == (plain[key].x, plain[key].w), key


def test_number_pad_icons_change_the_keys_shape_but_not_what_they_send():
    pad, bridge, clock = make()
    icons = {"slot_1": "fireball.png", "slot_1:up": "frostbolt.png", "slot_99": "x.png", "slot_2": 5}
    pad.apply_config({"number_icons": True, "icons": icons})
    one = next(w for w in pad.widgets if w.id == "number:slot_1")
    assert one.w == one.h and pad.number_icons
    assert (pad.icon_of(one.data), pad.icon_of(one.data, "up"), pad.icon_of(one.data, "down")) == \
        ("fireball.png", "frostbolt.png", "")
    assert "slot_2" not in pad.icons
    swipe(pad, clock, "number:slot_1", 0, -120)
    assert bridge.take() == [("key", SHIFT, True), ("key", 2, True), ("key", 2, False), ("key", SHIFT, False)]
    pad.apply_config({"number_icons": False, "icons": icons})
    assert pad.icon_of(one.data) == "" and next(w for w in pad.widgets if w.id == "number:slot_1").h > one.h
    pad.apply_config({"game": "desktop", "number_icons": True, "icons": icons})
    assert not pad.number_icons  # no number block


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
    """One press, one action: what Blizzard allows input software to do. No button may send a sequence of keys. A tap
    on a radial chooses nothing, so it sends nothing, and a second tap closes it. The one exception is a WoW chat slice, which types a channel
    command into the chat box and never sends it (test_every_chat_command_can_be_typed_and_never_presses_enter)."""
    modifiers = set(pad_model.MOD_CODES.values())
    pad, bridge, clock = make()
    for game in pad_model.GAMES:
        pad.apply_config({"game": game})
        for page in range(len(pad.game.pages)):
            tap(pad, clock, f"tab:{page}")
            for widget_id in [w.id for w in pad.widgets if w.kind in ("page", "number")]:
                tap(pad, clock, widget_id)
                pressed = [code for kind, code, down in bridge.take() if kind == "key" and down and code not in modifiers]
                radial = next(w for w in pad.widgets if w.id == widget_id).data.radial
                assert len(pressed) == (0 if radial else 1), (game, widget_id, pressed)
                if radial:
                    tap(pad, clock, widget_id)
                    assert not bridge.take() and not pad.swipes


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


def test_swiping_a_number_up_adds_shift_left_adds_ctrl_and_down_cancels():
    pad, bridge, clock = make()
    assert swipe(pad, clock, "number:slot_5", 10, -90) == "up"
    assert bridge.take() == [("key", SHIFT, True), ("key", 6, True), ("key", 6, False), ("key", SHIFT, False)]
    assert swipe(pad, clock, "number:slot_5", -90, 10) == "down"  # the second modifier's swipe goes left
    assert bridge.take() == [("key", CTRL, True), ("key", 6, True), ("key", 6, False), ("key", CTRL, False)]
    assert swipe(pad, clock, "number:slot_5", -10, 90) == "cancel"
    assert bridge.take() == [] and not pad.lit(next(w for w in pad.widgets if w.id == "number:slot_5"))
    assert swipe(pad, clock, "number:slot_5", 90, 0) is None  # right is a plain press
    assert swipe(pad, clock, "number:slot_5", 30, 0) is None  # a wobble is not a swipe
    assert bridge.take() == [("key", 6, True), ("key", 6, False)] * 2
    assert not pad.swipes


def test_in_ffxi_a_swipe_up_reaches_the_ctrl_macro_bar_and_left_the_alt_one():
    pad, bridge, clock = make()
    pad.apply_config({"game": "ffxi"})
    assert pad.game.titles == ("Menus", "Target", "Utility")
    assert swipe(pad, clock, "number:slot_3", 0, -90) == "up"
    assert bridge.take() == [("key", CTRL, True), ("key", 4, True), ("key", 4, False), ("key", CTRL, False)]
    assert swipe(pad, clock, "number:slot_10", -90, 0) == "down"
    assert bridge.take() == [("key", ALT, True), ("key", 11, True), ("key", 11, False), ("key", ALT, False)]
    swipe(pad, clock, "number:slot_3", 0, 0)
    assert bridge.take() == [("key", 4, True), ("key", 4, False)]  # a tap is the bare number


def test_ffxi_macro_set_buttons_send_one_keystroke_with_ctrl_held_first():
    pad, bridge, clock = make()
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:2")
    for held in (0.05, 2.0):  # a hold is still one change of macro set, not a key repeat
        tid = down(pad, clock, "page:macro_set_up")
        assert bridge.take() == [("key", CTRL, True), ("key", 103, True), ("key", 103, False), ("key", CTRL, False)]
        assert clock.slept[-3:] == [pad_model.MOD_LEAD_S, pad_model.TAP_HOLD_S, pad_model.TAP_HOLD_S]
        clock.now += held
        pad.touch_up(tid, clock.now)
        assert bridge.take() == [] and not pad.key_refs  # the lift sends nothing more


def test_a_macro_set_tap_does_not_hold_up_the_touch_thread():
    pending = []
    pad, bridge, clock = make(later=lambda delay, job: pending.append((delay, job)))
    pad.apply_config({"game": "ffxi"})
    pad.page = 2
    pad._relayout()
    down(pad, clock, "page:macro_set_down")
    assert bridge.take() == [("key", CTRL, True)] and not clock.slept
    for delay, event in ((pad_model.MOD_LEAD_S, ("key", 108, True)), (pad_model.TAP_HOLD_S, ("key", 108, False)),
                         (pad_model.TAP_HOLD_S, ("key", CTRL, False))):
        (wait, job), = pending
        pending.clear()
        assert wait == delay
        job()
        assert bridge.take() == [event]
    assert not pending


def test_swiping_an_ffxi_party_target_right_presses_enter_after_it():
    buzzes = []
    pad, bridge, clock = make(haptic=buzzes.append)
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:1")
    bridge.take()
    buzzes.clear()
    assert swipe(pad, clock, "page:party_2", 90, 10) == "confirm"
    assert bridge.take() == [("key", 61, True), ("key", 61, False), ("key", 28, True), ("key", 28, False)]
    assert clock.slept[-2:] == [pad_model.CONFIRM_GAP_S, pad_model.TAP_HOLD_S]
    assert buzzes == ["press", "tick"]
    for dx, dy in ((0, 0), (-90, 0), (0, 90), (90, 120)):  # a tap, or any other way, is the target alone
        assert swipe(pad, clock, "page:self", dx, dy) is None
        assert bridge.take() == [("key", 59, True), ("key", 59, False)], (dx, dy)
    assert swipe(pad, clock, "page:nearest_npc", 90, 0) is None  # only the party targets confirm
    assert bridge.take() == [("key", 66, True), ("key", 66, False)]


def test_a_target_swipe_sends_no_enter_if_its_button_goes_away():
    pad, bridge, clock = make()
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:1")
    tid = down(pad, clock, "page:party_1")
    x, y = center(pad, "page:party_1")
    pad.touch_move(tid, x + 90, y, clock.now)
    bridge.take()
    tap(pad, clock, "mode:trackpad")  # another finger changes the view
    pad.touch_up(tid, clock.now)
    assert ("key", 28, True) not in bridge.take() and not pad.swipes


def test_wow_targets_ignore_a_swipe_right():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:1")
    bridge.take()
    assert swipe(pad, clock, "page:party_1", 90, 0) is None
    assert bridge.take() == [("key", 60, True), ("key", 60, False)]


def slice_point(x, y, direction):
    """Where a finger is over a slice, halfway out, of a radial centered at (x, y)."""
    angle = pad_model.RADIAL_DIRECTIONS.index(direction) * math.pi / 4
    reach = (pad_model.RADIAL_HUB + pad_model.radial_reach(x, y)) / 2
    return x + reach * math.cos(angle), y + reach * math.sin(angle)


def radial(pad, clock, direction, steps=5):
    """Hold the Chat button and slide onto a slice, or stay put for None. Returns the slice the radial showed chosen. A
    radial that stayed open is closed with a second tap on its button."""
    tid = down(pad, clock, "page:chat")
    x, y = center(pad, "page:chat")
    tx, ty = slice_point(x, y, direction) if direction else (x, y)
    for i in range(1, steps + 1):
        clock.now += 0.02
        pad.touch_move(tid, x + (tx - x) * i / steps, y + (ty - y) * i / steps, clock.now)
    shown = pad.swipes.get("page:chat")
    pad.touch_up(tid, clock.now)
    clock.now += 0.5
    if "page:chat" in pad.swipes:
        tap(pad, clock, "page:chat")
    return shown


def test_the_utility_pages_pair_buttons_in_rows_of_the_same_height():
    def rows(game):
        widgets = [w for w in build_layout("pad", 2, game=game)[1] if w.kind == "page" and not w.data.radial]
        assert {w.h for w in widgets} == {pad_model.PAGE_ROW_H}
        return [[w.id[5:] for w in widgets if w.y == y] for y in sorted({w.y for w in widgets})]

    assert rows(pad_model.WOW) == [["sheathe_weapons", "screenshot"], ["sit_stand"], ["chat_page_up", "chat_page_down"]]
    assert rows(pad_model.FFXI) == [["macro_set_up", "macro_set_down"]]


def test_a_page_of_rows_without_a_radial_fills_the_body_with_its_rows_level_across_the_columns():
    panels, widgets = build_layout("pad", 0, game=pad_model.DESKTOP)
    pages = [w for w in widgets if w.kind == "page"]
    assert len({w.h for w in pages}) == 1 and pages[0].h > pad_model.PAGE_ROW_H
    assert len({w.y for w in pages}) == 4
    assert math.isclose(max(y + h for _, y, _, h, _ in panels), pad_model.BODY_Y + pad_model.BODY_H)


def test_the_chat_button_is_round_and_in_the_middle_of_the_room_between_the_other_buttons():
    below = {"wow": ["chat_page_up", "chat_page_down"], "ffxi": []}
    for game in (pad_model.WOW, pad_model.FFXI):
        panels, widgets = build_layout("pad", 2, game=game)
        chat = next(w for w in widgets if w.id == "page:chat")
        others = [w for w in widgets if w.kind == "page" and w is not chat]
        assert chat.w == chat.h == 2 * pad_model.RADIAL_BUTTON_R
        assert [w.id[5:] for w in others if w.y > chat.y] == below[game.id]
        left = [(y, y + h) for x, y, w, h, _ in panels if x < chat.x]
        top = max(end for start, end in left if start < chat.y) + pad_model.GAP
        bottom = min((start - pad_model.GAP for start, end in left if start > chat.y),
                     default=pad_model.BODY_Y + pad_model.BODY_H)
        assert top < chat.y and chat.y + chat.h < bottom
        assert abs((chat.y - top) - (bottom - chat.y - chat.h)) < 1
        assert chat.center[0] == (min(w.x for w in others) + max(w.x + w.w for w in others)) / 2


def test_a_radial_chooses_the_slice_under_the_finger():
    choice = pad_model.radial_choice
    assert choice(620, 540, 620, 540) is None and choice(620, 540, 690, 540) is None  # over the hub
    for direction in pad_model.RADIAL_DIRECTIONS:
        assert choice(620, 540, *slice_point(620, 540, direction)) == direction
    assert pad_model.radial_reach(620, 540) == pad_model.RADIAL_REACH  # room all round


def test_a_tap_on_the_chat_button_leaves_its_radial_open_for_the_next_finger():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    bridge.take()
    landing = center(pad, "page:chat")
    tid = 1000
    pad.touch_down(tid, landing[0] + 100, landing[1], clock.now)  # on the button, over a slice
    assert pad.radial_growth() == 0.0
    pad.touch_move(tid, landing[0] + 130, landing[1] - 30, clock.now)  # a wobble chooses nothing
    pad.touch_up(tid, clock.now)
    assert "page:chat" in pad.swipes and pad.swipes["page:chat"] is None  # open, nothing chosen
    clock.now += pad_model.RADIAL_OPEN_S + 0.01
    assert pad.radial_growth() == 1.0
    # The next finger is the radial's wherever it lands: on a slice, it chooses it at once.
    tid = 1001
    pad.touch_down(tid, *slice_point(*landing, "left"), clock.now)
    assert pad.swipes["page:chat"] == "left"
    pad.touch_move(tid, *slice_point(*landing, "up"), clock.now + 0.05)
    assert pad.swipes["page:chat"] == "up"
    pad.touch_up(tid, clock.now + 0.1)
    assert [code for _, code, down in bridge.take() if down] == [53, 34, 57]  # "/g "
    assert pad.view == "keyboard" and not pad.swipes
    # Tapping the button's middle, or anywhere outside the radial, closes it and sends nothing.
    for where in ("page:chat", "page:sit_stand", "number:slot_5"):
        tap(pad, clock, "tab:2")
        tap(pad, clock, "page:chat")
        assert "page:chat" in pad.swipes
        tap(pad, clock, where)
        assert not pad.swipes and not bridge.take() and pad.view == "pad"


def test_the_wow_chat_radial_types_the_channel_command_and_opens_the_keyboard_as_it_was():
    buzzes = []
    pad, bridge, clock = make(haptic=buzzes.append)
    tap(pad, clock, "mode:keyboard")
    tap(pad, clock, key_id(pad, "?123"))  # the keyboard was left on its symbols
    tap(pad, clock, "tab:2")
    bridge.take()
    buzzes.clear()
    assert radial(pad, clock, "up") == "up"
    assert bridge.take() == [("key", 53, True), ("key", 53, False), ("key", 34, True), ("key", 34, False),
                             ("key", 57, True), ("key", 57, False)]  # "/g ", and no Enter
    hold, gap, opening = pad_model.TYPE_HOLD_S, pad_model.TYPE_GAP_S, pad_model.TYPE_OPEN_S
    assert clock.slept[-6:] == [hold, opening, hold, gap, hold, gap]
    assert buzzes == ["press", "tick"]
    assert pad.view == "keyboard" and pad.kb_symbols and pad.kb_shift == "off" and not pad.key_refs
    tap(pad, clock, "tab:2")
    radial(pad, clock, "down_right")
    assert [code for _, code, down in bridge.take() if down] == [53, 19, 30, 57]  # "/ra "


def test_cancel_and_the_hub_on_the_chat_radial_send_nothing():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    bridge.take()
    assert radial(pad, clock, "down") == "down"
    assert bridge.take() == [] and pad.view == "pad" and not pad.swipes
    tid = down(pad, clock, "page:chat")
    landing = center(pad, "page:chat")
    pad.touch_move(tid, *slice_point(*landing, "up"), clock.now)
    pad.touch_move(tid, *landing, clock.now)  # and back onto the hub
    assert pad.swipes["page:chat"] is None
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [] and pad.view == "pad" and not pad.swipes
    assert not pad.lit(next(w for w in pad.widgets if w.id == "page:chat"))


def test_the_ffxi_chat_radial_sends_ffxis_own_keys_with_their_remaps():
    pad, bridge, clock = make()
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:2")
    bridge.take()
    radial(pad, clock, "up_left")
    assert bridge.take() == [("key", CTRL, True), ("key", 19, True), ("key", 19, False), ("key", CTRL, False)]
    assert pad.view == "keyboard"
    pad.apply_config({"game": "ffxi", "bindings": {"party_chat": 33}})  # remapped while it was a page button
    tap(pad, clock, "tab:2")
    radial(pad, clock, "up_right")
    assert bridge.take() == [("key", CTRL, True), ("key", 33, True), ("key", 33, False), ("key", CTRL, False)]
    tap(pad, clock, "tab:2")
    assert radial(pad, clock, "right") == "right"  # an empty slice
    assert bridge.take() == [] and pad.view == "pad"


def test_the_chat_keyboard_comes_up_only_once_the_slices_keystroke_is_out():
    pending = []
    pad, bridge, clock = make(later=lambda delay, job: pending.append(job))
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:2")
    bridge.take()
    radial(pad, clock, "up_left")
    assert pad.view == "pad"  # Ctrl is still down: a letter typed now would be Ctrl and the letter
    while pending:
        pending.pop(0)()
    assert bridge.take() == [("key", CTRL, True), ("key", 19, True), ("key", 19, False), ("key", CTRL, False)]
    assert pad.view == "keyboard"
    tap(pad, clock, "tab:2")
    radial(pad, clock, "up_left")
    tap(pad, clock, "mode:trackpad")  # the view changed before the keystroke was out: it stays changed
    while pending:
        pending.pop(0)()
    assert pad.view == "trackpad"


def test_the_radial_repaints_only_while_open_and_blooming():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    assert not pad.blooming()
    tid = down(pad, clock, "page:chat")
    assert pad.blooming()
    pad.touch_up(tid, clock.now)  # a tap leaves it open
    assert pad.blooming()
    pad.touch_up(down(pad, clock, "page:chat"), clock.now)  # and a second closes it, before it has finished blooming
    assert pad.radial_growth() < 1.0 and not pad.blooming()


def test_the_pad_repaints_every_frame_only_while_a_finger_is_on_a_swipeable_button():
    pad, bridge, clock = make()
    assert not pad.swiping()
    tid = down(pad, clock, "number:slot_5")
    assert pad.swiping()  # from the touch, before it is a swipe: the first change of direction shows at once
    x, y = center(pad, "number:slot_5")
    pad.touch_move(tid, x, y - 120, clock.now)
    pad.touch_move(tid, x - 120, y, clock.now)
    assert pad.swiping()
    pad.touch_up(tid, clock.now)
    assert not pad.swiping()
    tid = down(pad, clock, "tab:2")
    assert not pad.swiping()  # a page tab is not swiped
    pad.touch_up(tid, clock.now)
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:1")
    tid = down(pad, clock, "page:party_2")
    assert pad.swiping()  # a target's swipe right confirms it
    pad.touch_up(tid, clock.now)
    assert not pad.swiping()


def test_a_finger_that_takes_over_a_chat_radial_from_a_lost_lift_holds_nothing_on_the_keyboard():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    tid = down(pad, clock, "page:chat")
    pad.touch_move(tid, *slice_point(*center(pad, "page:chat"), "left"), clock.now)  # and its lift is lost
    down(pad, clock, "page:chat")  # the lost finger's slice is sent, and the keyboard comes up
    assert [code for _, code, down in bridge.take() if down] == [53, 31, 57]  # "/s "
    assert pad.view == "keyboard" and not pad.pressed and not pad.swipes


def test_a_radial_sends_nothing_if_its_button_goes_away():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    tid = down(pad, clock, "page:chat")
    pad.touch_move(tid, *slice_point(*center(pad, "page:chat"), "left"), clock.now)
    tap(pad, clock, "mode:trackpad")  # another finger changes the view
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [] and pad.view == "trackpad" and not pad.swipes


def test_every_chat_command_can_be_typed_and_never_presses_enter():
    typed = [s for game in pad_model.GAMES.values() for b in game.buttons for _, s in b.radial if s.text]
    assert typed
    for slot in typed:
        assert all(ch in pad_model.TYPED for ch in slot.text) and "\n" not in slot.text, slot.id
        assert slot.text.startswith("/") and slot.text.endswith(" "), slot.id
    assert all(pad_model.RADIAL_CANCEL not in dict(b.radial) for game in pad_model.GAMES.values() for b in game.buttons)


# ---------------------------------------------------------------------- the Desktop profile

def two_fingers(pad, clock, moves, start_gap=200.0):
    """Two fingers land on the trackpad, side by side, and each step moves them by (dx_a, dy_a, dx_b, dy_b) in all."""
    x, y = center(pad, "surface")
    a, b = (x - start_gap / 2, y), (x + start_gap / 2, y)
    pad.touch_down(901, *a, clock.now)
    pad.touch_down(902, *b, clock.now)
    for i in range(1, 11):
        clock.now += 0.02
        dxa, dya, dxb, dyb = (v * i / 10 for v in moves)
        pad.touch_move(901, a[0] + dxa, a[1] + dya, clock.now)
        pad.touch_move(902, b[0] + dxb, b[1] + dyb, clock.now)
        pad.frame_done()
    clock.now += 0.02
    pad.touch_up(901, clock.now)
    pad.touch_up(902, clock.now)
    clock.now += 0.5


def test_the_desktop_pages_take_the_whole_width_and_back_copy_paste_and_forward_replace_the_modifiers():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    assert pad.game.titles == ("Edit", "Browser")
    assert not [w for w in pad.widgets if w.kind == "number"]
    page = {w.id: w for w in pad.widgets if w.kind == "page"}
    # Navigate's buttons stand right of Edit's, where the number block was.
    assert page["page:undo"].y == page["page:esc"].y and page["page:redo"].x < page["page:esc"].x
    assert page["page:delete"].x + page["page:delete"].w > pad_model.W - 2 * pad_model.MARGIN
    tap(pad, clock, "page:esc")
    assert bridge.take() == [("key", 1, True), ("key", 1, False)]
    tap(pad, clock, "mode:trackpad")
    assert not [w for w in pad.widgets if w.kind == "mod"]
    assert [w.label for w in sorted(pad.widgets, key=lambda w: w.x) if w.kind == "page"] == [
        "Back", "Copy", "Paste", "Forward"]
    for widget_id, key, mod in (("back", 105, ALT), ("copy", 46, CTRL), ("paste", 47, CTRL), ("forward", 106, ALT)):
        tap(pad, clock, f"page:{widget_id}")
        assert bridge.take() == [("key", mod, True), ("key", key, True), ("key", key, False), ("key", mod, False)]
    pad.apply_config({"game": "wow"})
    assert [w.label for w in pad.widgets if w.kind == "mod"] == ["Shift", "Ctrl", "Alt"]


def test_desktop_shortcuts_that_harm_when_repeated_send_one_keystroke_however_long_the_finger_stays():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop", "bindings": {"close_tab": "ctrl+shift+17"}})
    pad.page = 1
    pad._relayout()
    bridge.take()
    tid = down(pad, clock, "page:close_tab")
    assert bridge.take() == [("key", SHIFT, True), ("key", CTRL, True), ("key", 17, True), ("key", 17, False),
                             ("key", CTRL, False), ("key", SHIFT, False)]  # let go at once, remapped
    assert pad.lit(next(w for w in pad.widgets if w.id == "page:close_tab"))
    clock.now += 2
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [] and not pad.key_refs
    pad.page = 0
    pad._relayout()
    tid = down(pad, clock, "page:undo")  # the rest are held, so they repeat
    assert bridge.take() == [("key", CTRL, True), ("key", 44, True)]
    pad.touch_up(tid, clock.now + 2)
    bridge.take()
    tap(pad, clock, "mode:trackpad")
    tid = down(pad, clock, "page:paste")
    assert bridge.take() == [("key", CTRL, True), ("key", 47, True), ("key", 47, False), ("key", CTRL, False)]
    pad.touch_up(tid, clock.now + 2)
    once = {s.id for s in pad_model.DESKTOP.controls if s.once}
    assert once == {"paste", "save", "reload", "new_tab", "close_tab", "reopen_tab", "bookmark", "close_window",
                    "full_screen", "screenshot"}
    assert not [s for g in (pad_model.WOW, pad_model.FFXI) for s in g.controls if s.once]


def test_the_desktop_keyboard_has_f_keys_super_and_arrows_in_place_of_its_trackpad():
    pad, bridge, clock = make()
    tap(pad, clock, "mode:keyboard")
    assert [w for w in pad.widgets if w.kind == "surface"]  # the games keep the small trackpad
    pad.apply_config({"game": "desktop"})  # the keyboard stays up, laid out for the desktop
    assert pad.view == "keyboard" and not [w for w in pad.widgets if w.kind == "surface"]
    top = [w for w in pad.widgets if w.id.startswith("key:top:")]
    keyboard = [w for w in pad.widgets if w.kind == "key" and w not in top]
    assert max(w.y + w.h for w in top) < min(w.y for w in keyboard)
    _, wow = build_layout("keyboard", 0, game=pad_model.WOW)
    assert [(w.x, w.y, w.w, w.h) for w in keyboard] == [(w.x, w.y, w.w, w.h) for w in wow if w.kind == "key"]
    fkeys = [w for w in top if w.label.startswith("F")]
    assert [w.label for w in fkeys] == [f"F{i}" for i in range(1, 13)]
    assert len({w.y for w in fkeys}) == 2 and len({w.x for w in fkeys}) == 6
    arrows = {w.data.icon: w for w in top if w.data.icon}
    assert arrows["up"].x == arrows["down"].x and arrows["up"].y < arrows["down"].y
    assert arrows["left"].y == arrows["down"].y == arrows["right"].y
    assert max(w.x for w in fkeys) < arrows["left"].x < arrows["down"].x < arrows["right"].x
    for label, key in (("F4", 62), ("F12", 88), ("Super", 125)):
        tap(pad, clock, key_id(pad, label))
        assert bridge.take() == [("key", key, True), ("key", key, False)]
    for name, key in (("up", 103), ("left", 105), ("down", 108), ("right", 106)):
        tap(pad, clock, arrows[name].id)
        assert bridge.take() == [("key", key, True), ("key", key, False)]


def test_the_desktop_media_radial_sends_its_key_and_stays_on_the_page():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "tab:1")
    bridge.take()
    landing = center(pad, "page:media")
    tid = down(pad, clock, "page:media")
    pad.touch_move(tid, *slice_point(*landing, "up"), clock.now)
    pad.touch_up(tid, clock.now)
    assert bridge.take() == [("key", 164, True), ("key", 164, False)]  # play / pause
    assert pad.view == "pad" and pad.page == 1 and not pad.swipes
    media = next(w for w in pad.widgets if w.id == "page:media").data
    assert {d: slot.icon for d, slot in media.radial} == {
        "up": "play_pause", "up_left": "previous", "up_right": "next", "left": "volume_down", "right": "volume_up",
        "down_left": "mute"}


def test_a_pinch_on_the_desktop_trackpad_zooms_with_ctrl_and_the_wheel():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    bridge.take()
    two_fingers(pad, clock, (-70, 0, 70, 0))  # 140 px further apart: two steps in
    notch = pad_model.HI_RES_NOTCH
    assert bridge.take() == [("key", CTRL, True), ("scroll", 0, notch), ("scroll", 0, notch), ("key", CTRL, False)]
    two_fingers(pad, clock, (35, 0, -35, 0), start_gap=300)  # 70 px closer: one step out, and no right click
    assert bridge.take() == [("key", CTRL, True), ("scroll", 0, -notch), ("key", CTRL, False)]
    assert not pad.key_refs and pad.pair is None


def test_two_fingers_on_the_desktop_trackpad_still_scroll_and_tap_a_right_click():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    bridge.take()
    two_fingers(pad, clock, (0, 150, 0, 150))
    events = bridge.take()
    assert events and {e[0] for e in events} == {"scroll"} and all(dy < 0 for _, _, dy in events)  # down
    x, y = center(pad, "surface")
    pad.touch_down(911, x - 100, y, clock.now)
    pad.touch_down(912, x + 100, y, clock.now)
    pad.touch_up(911, clock.now + 0.05)
    pad.touch_up(912, clock.now + 0.05)
    assert bridge.take() == [("btn", BTN_RIGHT, True), ("btn", BTN_RIGHT, False)]
    two_fingers(pad, clock, (-300, 0, -300, 0))  # sideways scrolls sideways
    events = bridge.take()
    assert events and {e[0] for e in events} == {"scroll"} and all(dx < 0 and not dy for _, dx, dy in events)


def test_a_pinch_lets_go_of_ctrl_when_the_view_changes_or_a_finger_is_lost():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    x, y = center(pad, "surface")
    for end in ("view", "lost"):
        bridge.take()
        pad.touch_down(921, x - 100, y, clock.now)
        pad.touch_down(922, x + 100, y, clock.now)
        pad.touch_move(921, x - 160, y, clock.now + 0.02)  # one finger moves, the other stays put
        pad.frame_done()
        assert bridge.take() == [("key", CTRL, True), ("scroll", 0, pad_model.HI_RES_NOTCH)]
        if end == "view":
            tap(pad, clock, "mode:keyboard")
            tap(pad, clock, "mode:trackpad")
        else:
            pad.expire(clock.now + 0.02 + pad_model.STALE_CONTACT_S + 0.1)
        assert ("key", CTRL, False) in bridge.take() and not pad.key_refs and pad.pair is None
        pad.all_lifted(clock.now)
        clock.now += 3


def test_a_third_finger_on_the_trackpad_ends_a_pinch_so_it_clicks_without_ctrl():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    x, y = center(pad, "surface")
    bridge.take()
    pad.touch_down(931, x - 100, y, clock.now)
    pad.touch_down(932, x + 100, y, clock.now)
    pad.touch_move(931, x - 160, y, clock.now + 0.02)
    pad.frame_done()
    assert bridge.take() == [("key", CTRL, True), ("scroll", 0, pad_model.HI_RES_NOTCH)]
    pad.touch_down(933, x, y + 150, clock.now + 0.04)
    assert bridge.take() == [("key", CTRL, False)] and not pad.key_refs
    pad.touch_move(931, x - 300, y, clock.now + 0.06)  # the pinch's fingers zoom no more
    pad.frame_done()
    assert bridge.take() == []
    pad.all_lifted(clock.now + 0.1)
    assert pad.pair is None


def test_two_thumbs_that_swing_apart_as_they_scroll_still_scroll():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    bridge.take()
    two_fingers(pad, clock, (-40, -60, 40, -60), start_gap=500)  # 80 px further apart, 60 px up
    events = bridge.take()
    assert events and {e[0] for e in events} == {"scroll"} and all(dy > 0 for _, _, dy in events)  # up
    two_fingers(pad, clock, (-30, 0, 30, 0), start_gap=500)  # but spreading apart in place still zooms
    assert bridge.take()[0] == ("key", CTRL, True)
    x, y = center(pad, "surface")  # and so does spreading with one finger kept still, for as long as it takes
    pad.touch_down(941, x - 100, y, clock.now)
    pad.touch_down(942, x + 100, y, clock.now)
    for i in range(1, 41):
        pad.touch_move(941, x - 100 - 4 * i, y, clock.now + 0.02 * i)
        pad.frame_done()
    events = bridge.take()
    assert events[0] == ("key", CTRL, True) and events.count(("scroll", 0, pad_model.HI_RES_NOTCH)) == 2
    assert pad.key_refs == {CTRL: 1}
    pad.all_lifted(clock.now + 1)
    assert not pad.key_refs


def test_a_slow_pinch_with_one_finger_kept_still_zooms_rather_than_losing_the_still_finger():
    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    tap(pad, clock, "mode:trackpad")
    bridge.take()
    x, y = center(pad, "surface")
    pad.touch_down(961, x - 100, y, clock.now)
    pad.touch_down(962, x + 100, y, clock.now)
    for i in range(1, 121):  # 60 px a second: well past LOST_LIFT_S before it spreads GESTURE_PX
        pad.touch_move(961, x - 100 - i, y, clock.now + 0.016 * i)
        pad.frame_done()
    events = bridge.take()
    assert 962 in pad.touches and pad.pair.mode == "pinch"
    assert events[0] == ("key", CTRL, True) and "rel" not in {e[0] for e in events}
    pad.all_lifted(clock.now + 3)
    assert not pad.key_refs


def test_a_lost_lift_ends_a_two_finger_scroll_once_the_other_finger_has_moved_on_its_own():
    for game in ("wow", "desktop"):
        pad, bridge, clock = make()
        pad.apply_config({"game": game})
        tap(pad, clock, "mode:trackpad")
        x, y = center(pad, "surface")
        pad.touch_down(951, x - 60, y, clock.now)
        pad.touch_down(952, x + 60, y, clock.now)
        clock.now += 0.5  # resting before they move is no lost lift
        t = clock.now
        for i in range(1, 31):  # both scroll down for 0.6 s
            pad.touch_move(951, x - 60, y + 5 * i, t + 0.02 * i)
            pad.touch_move(952, x + 60, y + 5 * i, t + 0.02 * i)
            pad.frame_done()
        events = bridge.take()
        assert events and {e[0] for e in events} == {"scroll"}, game
        t += 0.6  # 952 lifts, and the controller loses the lift: 951 alone goes on
        for i in range(1, 31):
            pad.touch_move(951, x - 60 + 5 * i, y + 150, t + 0.02 * i)
            pad.frame_done()
        events = bridge.take()
        kinds = [e[0] for e in events]
        scrolls = kinds.index("rel")  # the scrolling stops, and the pointer moves
        assert set(kinds[:scrolls]) <= {"scroll"} and set(kinds[scrolls:]) == {"rel"}, game
        assert scrolls * 0.02 <= pad_model.LOST_LIFT_S + 0.1, game
        assert 952 not in pad.touches and not pad.key_refs, game
        pad.touch_move(952, x + 200, y, t + 0.7)  # its id comes back with a new finger, which counts
        assert 952 in pad.touches, game


def test_changing_the_game_lets_go_and_keeps_the_page_when_it_can():
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    tid = down(pad, clock, "page:sheathe_weapons")  # held while the game changes
    assert bridge.take() == [("key", 44, True)]
    pad.apply_config({"game": "ffxi"})
    assert bridge.take() == [("key", 44, False)] and pad.page == 2
    assert "page:macro_set_up" in {w.id for w in pad.widgets} and "page:sheathe_weapons" not in {w.id for w in pad.widgets}
    pad.touch_up(tid, clock.now)
    assert bridge.take() == []
    pad.apply_config({"game": "nonsense"})
    assert pad.game is pad_model.WOW


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
    tap(pad, clock, "status")  # the clock and battery open the status card, like a tab
    tap(pad, clock, "status")  # and a touch closes it
    tap(pad, clock, "mode:trackpad")
    assert buzzes == ["press", "press", "tick", "tick", "tick"]
    for target in ("surface", "strip"):
        pad.touch_down(50, *center(pad, target), clock.now)
        pad.touch_up(50, clock.now + 0.05)
        pad.all_lifted(clock.now + 0.05)
    tap(pad, clock, "mouse:left", held=0.05)
    clock.now -= 0.4
    tap(pad, clock, "mouse:left", held=0.05)  # a double tap locks it: two buzzes
    assert buzzes == ["press", "press", "tick", "tick", "tick", "press", "press", "lock"]


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


def test_a_bare_motor_is_reopened_after_its_last_buzz_and_a_gamepad_is_not():
    with tempfile.TemporaryDirectory() as tmp:
        node = os.path.join(tmp, "event8")
        open(node, "w").close()
        for name, reopens in (("qcom-hv-haptics", True), ("Microsoft X-Box 360 pad 0", False)):
            uploads, looked_at = [], []
            gamepad = os.path.join(tmp, "event7")
            found = [(gamepad, "AYN Odin2 Gamepad", (haptics.FF_RUMBLE,)), (node, name, (haptics.FF_CONSTANT,))]
            motor = haptics.Haptics(find=lambda: found, held=lambda fd: looked_at.append(fd) or False,
                                    upload=lambda fd, kind, effect, ms, strength: uploads.append(effect) or 0)
            open(gamepad, "w").close()
            os.chmod(gamepad, 0)  # root-only, as on the Thor: the first open skips it
            motor.configure(True, 0.7, 5)
            assert uploads == [-1] and motor.name == name
            os.chmod(gamepad, 0o600)  # the reopen must not even look at it now that it could be opened
            rest, haptics.REST_S = haptics.REST_S, 0.05
            try:
                motor.pulse()
                time.sleep(0.02)
                motor.pulse()  # buzzing again puts the rest off: it comes once, after the last buzz
                time.sleep(0.3)
            finally:
                haptics.REST_S = rest
            assert uploads == ([-1, -1] if reopens else [-1]), name  # closed, opened and uploaded once more
            assert motor.fd >= 0 and motor.node == node and len(looked_at) == len(uploads)
            motor._rest(motor._pulses - 1)  # a rest for an older buzz does nothing
            assert len(uploads) == (2 if reopens else 1)
            motor.close()


def test_a_motor_that_fails_to_reopen_is_tried_again_a_second_later():
    clock = Clock()
    with tempfile.TemporaryDirectory() as tmp:
        node = os.path.join(tmp, "event8")
        open(node, "w").close()
        motor = haptics.Haptics(find=lambda: [(node, "qcom-hv-haptics", (haptics.FF_CONSTANT,))], clock=clock,
                                held=lambda fd: False, upload=lambda *args: 0)
        motor.configure(True, 0.7, 5)
        os.remove(node)  # gone for a moment, as the motor is being reopened
        motor._rest(motor._pulses)
        assert motor.fd < 0
        open(node, "w").close()
        clock.now += 0.5
        motor.configure(True, 0.7, 5)
        assert motor.fd < 0  # not at once
        clock.now += 0.5
        motor.configure(True, 0.7, 5)
        assert motor.fd >= 0  # a second later, not RETRY_S
        motor.close()


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
        js = f.read()
    for game in pad_model.GAMES.values():
        listed = json.loads(re.sub(r"(\w+):", r'"\1":', re.search(rf"const {game.id}Defaults=(\{{.*?\}});", js).group(1)))
        slots = game.controls
        assert listed == {s.id: s.key for s in slots}, game.id
    swipes = dict(re.findall(r'(\w+):\{name:"[^"]+",short:"[^"]+",defaults:\w+,mods:\w+,swipes:\[("\w+","\w+")\]', js))
    assert swipes == {g.id: f'"{g.swipes["up"][0]}","{g.swipes["down"][0]}"' for g in pad_model.GAMES.values()}

    sys.path.insert(0, ROOT)
    import main

    assert main.GAMES == tuple(pad_model.GAMES)


def test_every_control_is_listed_once():
    for game in pad_model.GAMES.values():
        ids = [s.id for s in game.controls]
        assert len(ids) == len(set(ids)), game.id


def test_the_decky_key_picker_names_every_default_key_and_knows_the_default_modifiers():
    import json
    import re

    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        js = f.read()
    names = json.loads(re.search(r"const keyNames=(\[.*?\]);", js).group(1))
    codes = [code for code, _ in names]
    assert len(codes) == len(set(codes)) and all(0 < code < 248 for code in codes)
    names_of = {code: name for name, _, code in pad_model.MODIFIERS}
    for game in pad_model.GAMES.values():
        slots = game.controls
        assert {s.key for s in slots} <= set(codes), game.id
        mods = json.loads(re.sub(r"(\w+):", r'"\1":', re.search(rf"const {game.id}Mods=(\{{.*?\}});", js).group(1)))
        assert mods == {s.id: [names_of[m] for m in s.mods] for s in slots if s.mods}, game.id


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



def fake_nmcli(outputs):
    """A stand-in subprocess.run for nmcli: outputs maps its arguments after -t, joined by spaces, to what it prints."""
    asked = []

    def run(args, **kwargs):
        assert args[:2] == ["nmcli", "-t"] and kwargs.get("timeout")
        key = " ".join(args[2:])
        asked.append(key)
        if key not in outputs:
            return types.SimpleNamespace(returncode=10, stdout="")
        return types.SimpleNamespace(returncode=0, stdout=outputs[key])

    run.asked = asked
    return run


def test_the_status_card_reads_the_network_from_networkmanager():
    devices = "-f DEVICE,TYPE,STATE device"
    wifi = "-f ACTIVE,SSID,SIGNAL,FREQ,RATE device wifi list --rescan no"
    run = fake_nmcli({
        devices: "lo:loopback:connected (externally)\np2p-dev-wlp1s0:wifi-p2p:disconnected\nwlp1s0:wifi:connected\n",
        wifi: "no:Neighbours:40:5180 MHz:540 Mbit/s\nyes:Home\\:Net:78:2412 MHz:130 Mbit/s\n",
        "-f IP4.ADDRESS device show wlp1s0": "IP4.ADDRESS[1]:172.20.10.3/28\n",
        "networking connectivity": "full\n",
    })
    network = system_status.read_network(run, local_ip=lambda: "unused")
    assert network == {"kind": "wifi", "device": "wlp1s0", "name": "Home:Net", "signal": 78, "mhz": 2412,
                       "rate": "130 Mbit/s", "ip": "172.20.10.3", "internet": "full"}
    assert "rescan yes" not in " ".join(run.asked)  # never a scan: it stalls the Wi-Fi for seconds

    wired = system_status.read_network(fake_nmcli({devices: "eth0:ethernet:connected\n",
                                                   "networking connectivity": "portal\n"}), local_ip=lambda: "10.0.0.5")
    assert (wired["kind"], wired["ip"], wired["internet"]) == ("ethernet", "10.0.0.5", "portal")
    offline = system_status.read_network(fake_nmcli({devices: "wlp1s0:wifi:disconnected\n"}))
    assert offline["kind"] == ""

    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    assert system_status.read_network(missing, local_ip=lambda: "192.168.1.28")["ip"] == "192.168.1.28"
    assert system_status.read_network(missing, local_ip=lambda: "")["kind"] == ""


def thor_sysfs(tmp, status="Discharging", current="900000"):
    """The Thor's battery, a few of its thermal zones and its fan, as seen on one (2026-11-12)."""
    def write(path, **files):
        os.makedirs(os.path.join(tmp, path), exist_ok=True)
        for key, value in files.items():
            with open(os.path.join(tmp, path, key), "w") as f:
                f.write(value + "\n")

    write("power/battery", type="Battery", status=status, capacity="54", charge_now="3206500",
          charge_full="6413000", charge_full_design="5938000", current_now=current, voltage_now="4000000",
          power_now="40428492", temp="300", cycle_count="5", health="Good")
    write("power/qcom-battmgr-usb", type="USB", current_now="937000", voltage_now="4859000")
    for i, (kind, temp) in enumerate([("cpu7-top-thermal", "44200"), ("cpuss0-thermal", "43800"),
                                      ("gpuss-1-thermal", "41400"), ("gpuss-0-thermal", "40200"),
                                      ("battery", "30000"), ("modem0-thermal", "90000")]):
        write(f"thermal/thermal_zone{i}", type=kind, temp=temp)
    write("hwmon/hwmon1", name="cpuss0_thermal")
    write("hwmon/hwmon40", name="pwmfan", fan1_input="2067")
    return {name: os.path.join(tmp, name) for name in ("power", "thermal", "hwmon")}


def test_the_status_card_reads_the_battery_temperatures_and_fan():
    with tempfile.TemporaryDirectory() as tmp:
        roots = thor_sysfs(tmp)
        battery = system_status.read_battery_details(roots["power"])
        assert battery["status"] == "Discharging" and battery["percent"] == 54
        assert abs(battery["watts"] - 3.6) < 1e-9  # volts times amps: the driver's power_now says 40 W
        assert (battery["temp"], battery["cycles"], battery["health"]) == (30.0, 5, "Good")
        assert system_status.read_temperatures(roots["thermal"]) == {"CPU": 44.2, "GPU": 41.4, "Battery": 30.0}
        assert system_status.read_fan(roots["hwmon"]) == 2067
        assert system_status.read_battery_details(os.path.join(tmp, "nothing")) is None

    rate = system_status.BatteryRate()
    for second in range(2):
        rate.add(battery, 100.0 + second)
    assert rate.hours(battery) is None  # too soon to tell
    rate.add(battery, 102.0)
    assert abs(rate.hours(battery) - 3206500 / 900000) < 1e-9
    charging = dict(battery, status="Charging")
    rate.add(charging, 103.0)  # plugged in: the drain says nothing about the charge
    assert rate.hours(charging) is None
    for second in range(4, 7):
        rate.add(charging, 100.0 + second)
    assert abs(rate.hours(charging) - (6413000 - 3206500) / 900000) < 1e-9

    sections = dict(system_status.card_sections(
        {"kind": "wifi", "device": "wlp1s0", "name": "Home", "signal": 78, "mhz": 2412, "rate": "130 Mbit/s",
         "ip": "172.20.10.3", "internet": "full"}, battery, 3.55, {"CPU": 44.2, "GPU": 41.4}, 2067))
    assert sections["Network"] == [("Wi-Fi", "Home"), ("Signal", "78% · Strong"), ("Band", "2.4 GHz · 130 Mbit/s"),
                                   ("IP address", "172.20.10.3"), ("Internet", "Connected")]
    assert sections["Battery"] == [("Charge", "54% · on battery"), ("Time left", "3 h 33 min"),
                                   ("Power", "Using 3.6 W"), ("Health", "Good · 5 cycles")]
    assert sections["Temperatures"] == [("CPU", "44 °C"), ("GPU", "41 °C"), ("Battery", "30 °C"),
                                        ("Fan", "2067 rpm")]
    full = dict(system_status.card_sections(None, dict(battery, status="Charging", percent=100), 0.0, {}, None))
    assert full["Network"] == [("Status", "Looking…")]
    assert ("Until full", "Full") in full["Battery"]
    assert dict(system_status.card_sections({"kind": ""}, None, None, {}, None)) == {"Network": [("Status", "Offline")]}


def test_tapping_the_clock_opens_the_status_card_and_any_touch_closes_it():
    opened = []
    pad, bridge, clock = make(on_card=opened.append)
    tap(pad, clock, "status")
    assert pad.card_open and opened == [True]
    tap(pad, clock, "number:slot_5")  # closes the card, and presses nothing under it
    assert not pad.card_open and opened == [True, False]
    assert bridge.take() == []
    tap(pad, clock, "number:slot_5")  # with the card closed, the key works again
    assert ("key", 6, True) in bridge.take()

    tap(pad, clock, "status")
    tap(pad, clock, "status")  # the clock closes it too
    assert not pad.card_open
    tap(pad, clock, "status")
    clock.now += pad_model.CARD_S - 1
    pad.expire_card()
    assert pad.card_open
    clock.now += 1
    pad.expire_card()  # it never stays on the OLED
    assert not pad.card_open and opened[-1] is False


def test_the_status_card_paints_in_every_theme_and_fits_the_screen():
    pad_draw = painter()
    with tempfile.TemporaryDirectory() as tmp:
        roots = thor_sysfs(tmp)
        battery = system_status.read_battery_details(roots["power"])
        sections = system_status.card_sections(
            {"kind": "wifi", "name": "A network with a very long name indeed", "signal": 20, "mhz": 5180,
             "rate": "866 Mbit/s", "ip": "192.168.100.200", "internet": "limited"}, battery, None,
            system_status.read_temperatures(roots["thermal"]), system_status.read_fan(roots["hwmon"]))
    for theme in pad_model.THEME_IDS:
        pad, bridge, clock = make()
        pad.apply_config({"theme": theme})
        tap(pad, clock, "status")
        pad_draw.paint(Context(), pad)  # before the facts arrive
        pad.card_sections = sections
        pad_draw.paint(Context(), pad)
        x, y, w, h = pad_draw.card_box(pad)
        assert x >= 0 and x + w <= pad_model.W and y >= pad_model.BODY_Y and y + h <= pad_model.H

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
    main.ICONS = main.BACKGROUNDS / "Icons"
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


def test_each_game_keeps_its_own_controls_and_profiles():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        call("save_config", {"bindings": {"character": "shift+46"}})
        call("save_profile", "Raid")
        cfg = call("select_game", "ffxi")["config"]
        assert (cfg["game"], cfg["bindings"], list(cfg["profiles"]), cfg["active_profile"]) == ("ffxi", {}, ["Default"], "Default")
        call("save_config", {"bindings": {"slot_1": 3}})
        call("save_profile", "Macros")
        cfg = call("select_game", "wow")["config"]
        assert cfg["bindings"] == {"character": "shift+46"} and cfg["active_profile"] == "Raid"
        assert sorted(cfg["profiles"]) == ["Default", "Raid"]
        cfg = call("select_game", "ffxi")["config"]
        assert cfg["bindings"] == {"slot_1": 3} and cfg["active_profile"] == "Macros"
        assert set(cfg["games"]) == {"wow"}  # the current game's are at the top, not also set aside
        assert call("select_game", "ffxi")["config"] == cfg  # the same game again changes nothing
        assert not call("select_game", "../x")["ok"]
        assert call("save_config", {"game": "wow"})["config"]["game"] == "ffxi"  # only select_game changes it


def test_the_shortcut_setting_defaults_on_and_saves():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        assert call("get_config")["shortcut"] is True
        assert call("save_config", {"shortcut": False})["config"]["shortcut"] is False
        assert call("save_config", {"theme": "dark"})["config"]["shortcut"] is False  # other settings leave it alone
        assert call("get_config")["shortcut_buttons"] == [1 << 13 | 1 << 14, 0]  # Home + Start
        for bad in ([0, 0], [1 << 32, 0], [-1, 0], [1], "x", [True, 0]):
            assert call("save_config", {"shortcut_buttons": bad})["config"]["shortcut_buttons"] == [1 << 13 | 1 << 14, 0]
        assert call("save_config", {"shortcut_buttons": [0, 1 << 31]})["config"]["shortcut_buttons"] == [0, 1 << 31]


# The profile InputPlumber had loaded on a Thor, as GetProfileYaml returned it (2026-10-16).
THOR_PROFILE = (
    "version: 1\nkind: DeviceProfile\nname: Default\nmapping:\n- name: LeftTop\n  source_event:\n    gamepad:\n"
    "      button: LeftTop\n  target_events:\n  - gamepad:\n      button: LeftPaddle1\n- name: QuickAccess2\n"
    "  source_event:\n    gamepad:\n      button: QuickAccess2\n  target_events:\n  - gamepad:\n"
    "      button: Screenshot\n- name: Left Dial Clockwise\n  source_event:\n    gamepad:\n      dial:\n"
    "        name: LeftStickDial\n        direction: clockwise\n  target_events:\n  - keyboard: KeyVolumeUp\n")


def test_the_ayn_button_is_heard_as_record_on_the_pad_or_f24_on_the_keyboard():
    import ayn_listen as ayn_button

    with tempfile.TemporaryDirectory() as tmp:
        sys_dir = Path(tmp)
        bits = struct.calcsize("L") * 8

        def device(event, name, *codes):
            value = sum(1 << c for c in codes)
            words = [(value >> (bits * i)) & ((1 << bits) - 1) for i in range(768 // bits)]
            folder = sys_dir / event / "device"
            (folder / "capabilities").mkdir(parents=True)
            (folder / "capabilities/key").write_text(" ".join(f"{w:x}" for w in reversed(words)).lstrip("0 ") or "0")
            (folder / "name").write_text(name + "\n")

        device("event3", "gpio-keys-ayn", ayn_button.KEY_RECORD)                            # not a pad
        device("event7", "AYN Odin2 Gamepad", ayn_button.BTN_SOUTH)                         # no Record key
        device("event11", "Microsoft X-Box 360 pad 0", ayn_button.BTN_SOUTH, ayn_button.KEY_RECORD)
        device("event13", "Thor Virtual Keyboard", ayn_button.KEY_F24)                      # JarnGrip's own keyboard
        device("event14", "InputPlumber Keyboard", ayn_button.KEY_F24, ayn_button.KEY_RECORD)
        assert ayn_button.sources(sys_dir, Path("/dev/input")) == [
            (Path("/dev/input/event11"), ayn_button.KEY_RECORD), (Path("/dev/input/event14"), ayn_button.KEY_F24)]

    press = lambda code, value: ayn_button.INPUT_EVENT.pack(0, 0, ayn_button.EV_KEY, code, value)
    data = press(167, 1) + press(167, 2) + press(167, 0) + press(194, 1)
    assert ayn_button.presses(data, 167) == 1 and ayn_button.presses(data, 194) == 1
    assert ayn_button.presses(data[:-3], 194) == 0  # a torn last event is left alone

    with tempfile.TemporaryDirectory() as tmp:
        fifo = Path(tmp) / "jarngrip-ayn"
        ayn_button.tell(fifo, 1)  # no backend yet: dropped, no error
        os.mkfifo(fifo)
        ayn_button.tell(fifo, 1)  # made but nobody reading: dropped
        reader = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        try:
            ayn_button.tell(fifo, 2)
            assert os.read(reader, 64) == b"pp"
        finally:
            os.close(reader)


def test_the_press_fifo_is_made_and_never_reads_as_ended():
    import main

    with tempfile.TemporaryDirectory() as tmp:
        fifo = Path(tmp) / "jarngrip-ayn"
        fifo.write_text("left over")  # not a FIFO: replaced
        fd = main._open_fifo(fifo)
        try:
            assert stat_is_fifo(fifo)
            try:
                os.read(fd, 64)
                raise AssertionError("read something, or an end, from an empty FIFO")
            except BlockingIOError:
                pass  # no writer but itself: waits, rather than reading as ended
        finally:
            os.close(fd)


def stat_is_fifo(path):
    import stat

    return stat.S_ISFIFO(os.stat(path).st_mode)


def test_the_ayn_listener_service_runs_the_installed_listener():
    with open(os.path.join(ROOT, "systemd", "jarngrip-ayn.service"), encoding="utf-8") as f:
        unit = f.read()
    with open(os.path.join(ROOT, "systemd", "jarngrip.service"), encoding="utf-8") as f:
        driver = next(word for word in f.read().split() if word.endswith("jarngrip.py"))
    assert driver.replace("jarngrip.py", "ayn_listen.py") in unit and "Restart=on-failure" in unit


def test_stopping_the_screenshot_changes_only_the_ayn_mapping():
    import ayn_button

    changed = ayn_button.without_screenshot(THOR_PROFILE, ["xb360"])
    assert 'name: "Default + JarnGrip"' in changed
    assert "target_devices:\n- xb360\n- keyboard\nmapping:\n" in changed
    assert "Screenshot" not in changed and changed.count("button: QuickAccess2") == 1
    assert "keyboard: KeyF24" in changed
    assert "button: LeftPaddle1" in changed and "keyboard: KeyVolumeUp" in changed  # the rest is kept
    # Applied again (InputPlumber hands back its own version), it changes nothing more.
    assert ayn_button.without_screenshot(changed, ["xb360", "keyboard"]) == changed
    # A profile without the mapping gets it; one with target devices of its own gets ours instead.
    bare = "version: 1\nkind: DeviceProfile\nname: 'Mine: custom'\ntarget_devices:\n- deck-uhid\nmapping: []\n"
    out = ayn_button.without_screenshot(bare, ["deck-uhid"])
    assert 'name: "Mine: custom + JarnGrip"' in out and out.count("target_devices:") == 1
    assert "- deck-uhid\n- keyboard\n" in out and "keyboard: KeyF24" in out
    for bad in ("", "version: 1\nkind: Something\nmapping: []\n", "version: 1\nkind: DeviceProfile\nname: x\n"):
        try:
            ayn_button.without_screenshot(bad, [])
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")


def test_the_ayn_device_is_looked_up_once_but_never_remembered_as_missing():
    import ayn_button

    tree = {"out": ""}  # InputPlumber not up yet
    runs = []

    class Done:
        @property
        def stdout(self):
            return tree["out"]

    real = ayn_button.subprocess.run, ayn_button._get, ayn_button._busctl
    ayn_button.subprocess.run = lambda *args, **kwargs: runs.append(args) or Done()
    ayn_button._get = lambda path, interface, prop: "AYN Thor"
    ayn_button._known = []
    try:
        assert ayn_button._ayn_devices() == []
        tree["out"] = "/org/shadowblip/InputPlumber\n/org/shadowblip/InputPlumber/CompositeDevice0\n"
        dev = ("/org/shadowblip/InputPlumber/CompositeDevice0", "AYN Thor")
        assert ayn_button._ayn_devices() == [dev] and ayn_button._ayn_devices() == [dev]
        assert len(runs) == 2  # the empty answer was not kept; the found device was

        def fail(*args):
            raise ayn_button.BusError("The name is not activatable")

        ayn_button._busctl = fail
        ayn_button._get = lambda *args: fail()
        with tempfile.TemporaryDirectory() as tmp:
            assert ayn_button.sync(True, Path(tmp) / "state.json").startswith("Could not change")
        assert ayn_button._known == []  # looked up again next time
    finally:
        ayn_button.subprocess.run, ayn_button._get, ayn_button._busctl = real
        ayn_button._known = []


def test_the_screenshot_setting_loads_the_change_and_puts_the_old_profile_back():
    import ayn_button

    dev = "/org/shadowblip/InputPlumber/CompositeDevice0"
    ip = {"name": "Default", "path": "/usr/share/inputplumber/profiles/default.yaml", "yaml": THOR_PROFILE,
          "targets": ["xb360"], "loads": []}

    def busctl(*args):
        if args[0] == "get-property":
            prop = args[4]
            if prop == "Name":
                return "AYN Thor"
            if prop == "ProfileName":
                return ip["name"]
            if prop == "ProfilePath":
                return ip["path"]
            if prop == "TargetDevices":
                return [f"/target/{t}" for t in ip["targets"]]
            if prop == "DeviceType":
                return args[2].rsplit("/", 1)[1]
        method = args[4]
        if method == "GetProfileYaml":
            return [ip["yaml"]]
        if method == "LoadProfileFromYaml":
            text = args[6]
            ip["loads"].append("yaml")
            ip["yaml"], ip["path"] = text, ""
            ip["name"] = next(l[6:].strip().strip('"') for l in text.splitlines() if l.startswith("name:"))
            lines = text.splitlines()  # the targets are the profile's, as in the real InputPlumber
            ip["targets"] = [l[2:] for l in lines[lines.index("target_devices:") + 1:lines.index("mapping:")]]
            return None
        if method == "LoadProfilePath":
            ip["loads"].append(args[6])
            ip["name"], ip["path"], ip["yaml"] = "Default", args[6], THOR_PROFILE
            return None
        raise AssertionError(args)

    calls = []

    def counted(*args):
        calls.append(args)
        return busctl(*args)

    real = ayn_button._busctl, ayn_button._ayn_devices, ayn_button.os.path.isfile
    ayn_button._busctl, ayn_button._ayn_devices = counted, lambda: [(dev, "AYN Thor")]
    ayn_button.os.path.isfile = lambda path: True
    try:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "inputplumber.json"
            assert ayn_button.sync(False, state) == "" and ip["loads"] == []  # never on: InputPlumber is left alone
            # At boot InputPlumber switches its targets: a load with no gamepad among them would leave none at all.
            for targets in ([], ["keyboard"], ["mouse", "keyboard"]):
                ip["targets"] = targets
                assert ayn_button.sync(True, state) == ayn_button.WAITING
                assert ip["loads"] == [] and not state.exists(), targets
            ip["targets"] = ["deck-uhid"]
            assert ayn_button.sync(True, state) == ""
            assert ip["targets"] == ["deck-uhid", "keyboard"] and "- deck-uhid" in ip["yaml"]
            ip.update(name="Default", path="/usr/share/inputplumber/profiles/default.yaml", yaml=THOR_PROFILE,
                      targets=["xb360"], loads=[])
            state.unlink()
            assert ayn_button.sync(True, state) == ""
            assert ip["name"] == "Default + JarnGrip" and "keyboard" in ip["targets"] and state.exists()
            calls.clear()
            assert ayn_button.sync(True, state) == "" and ip["loads"] == ["yaml"]  # already done: not loaded again
            assert len(calls) == 4  # the check every few seconds: the profile's name, the targets and their types
            # The gamepad went missing with our profile loaded: it is brought back, but only if still missing at the
            # next check, so that a switch Steam is making is not fought.
            ip["targets"] = ["keyboard"]
            assert ayn_button.sync(True, state) == ayn_button.WAITING and ip["loads"] == ["yaml"]
            ip["targets"] = ["deck", "keyboard"]  # it was a switch: left alone
            assert ayn_button.sync(True, state) == "" and ip["loads"] == ["yaml"]
            ip["targets"] = ["keyboard"]
            ayn_button.sync(True, state)
            assert ayn_button.sync(True, state) == "" and ip["loads"] == ["yaml", "yaml"]
            assert ip["targets"] == ["xb360", "keyboard"]
            # InputPlumber restarted: its stock profile is back, and the keyboard is gone.
            ip.update(name="Default", path="/usr/share/inputplumber/profiles/default.yaml", yaml=THOR_PROFILE,
                      targets=["xb360"])
            ayn_button.sync(True, state)
            assert ip["loads"] == ["yaml"] * 3 and ip["name"].endswith("+ JarnGrip")
            assert ayn_button.sync(False, state) == ""
            assert ip["loads"][-1] == "/usr/share/inputplumber/profiles/default.yaml" and ip["name"] == "Default"
            assert not state.exists()

            def refuse(*args):
                if args[0] == "call" and args[4].startswith("Load"):
                    raise ayn_button.BusError("Access denied")
                return busctl(*args)

            ayn_button._busctl = refuse
            assert "Reinstall JarnGrip" in ayn_button.sync(True, state)
    finally:
        ayn_button._busctl, ayn_button._ayn_devices, ayn_button.os.path.isfile = real


def test_the_ayn_button_toggles_the_pad_only_while_its_switch_is_on():
    import asyncio
    import main

    with tempfile.TemporaryDirectory() as tmp:
        backend(tmp)
        plugin = main.Plugin()
        plugin._ignore_until = 0.0
        calls = []

        async def set_enabled(enabled):
            calls.append(enabled)
            return {"enabled": enabled}

        plugin.set_enabled = set_enabled
        active, main._active = main._active, lambda unit: False

        def run(presses, queued=False):
            """The listener's bytes, one per press. Queued: they arrived while a toggle was still under way."""
            plugin._ignore_until = time.monotonic() + 60 if queued else 0.0
            read, write = os.pipe()
            os.set_blocking(read, False)
            os.write(write, b"p" * presses)
            os.close(write)
            try:
                asyncio.run(plugin._read_presses(read))  # a pipe ends when written; the backend's FIFO never does
            finally:
                os.close(read)

        try:
            run(1)
            assert calls == []  # the switch is off by default
            main._write({**main._read(), "ayn_button": True})
            run(1)
            assert calls == [True]
            run(2)  # read together: one toggle, not on and straight off again
            assert calls == [True, True]
            run(1, queued=True)
            assert calls == [True, True]
        finally:
            main._active = active


def test_the_ayn_button_is_heard_when_the_fifo_folder_comes_late_or_is_made_again():
    """At boot Decky can start before the user's session makes /run/user/1000, and the session makes it afresh when it
    starts again. Neither may leave the AYN button dead until Decky restarts."""
    import asyncio
    import shutil
    import ayn_listen
    import main

    with tempfile.TemporaryDirectory() as tmp:
        backend(tmp)
        main._write({**main._read(), "ayn_button": True})
        run_dir = Path(tmp) / "run"
        fifo = run_dir / "jarngrip-ayn"
        saved = main.WATCH_RETRY_S, main._active
        main.WATCH_RETRY_S, main._active = 0.05, lambda unit: False
        plugin = main.Plugin()
        calls = []

        async def set_enabled(enabled):
            calls.append(enabled)
            return {"enabled": enabled}

        plugin.set_enabled = set_enabled

        async def press_until_heard(count):
            plugin._ignore_until = 0.0
            for _ in range(100):
                ayn_listen.tell(fifo, 1)
                await asyncio.sleep(0.02)
                if len(calls) >= count:
                    return
            raise AssertionError("the press was never heard")

        async def scenario():
            listening = asyncio.ensure_future(plugin._listen_for_presses(fifo))
            await asyncio.sleep(0.15)
            assert not listening.done()  # no folder yet: still trying
            run_dir.mkdir()
            await press_until_heard(1)
            shutil.rmtree(run_dir)
            run_dir.mkdir()  # the session made it afresh
            await press_until_heard(2)
            listening.cancel()
            await asyncio.gather(listening, return_exceptions=True)
            assert plugin._fifo == -1

        try:
            asyncio.run(scenario())
        finally:
            main.WATCH_RETRY_S, main._active = saved


def test_uninstalling_from_decky_puts_things_back_and_keeps_the_settings():
    import asyncio
    import main

    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        call("save_config", {"theme": "dark"})
        home = Path(tmp)
        saved = {k: getattr(main, k) for k in ("APP", "UNIT_FILE", "LISTENER_FILE", "AYN_STATE", "AYN_FIFO", "MARKER",
                                               "INSTALLED_MARKER", "_systemctl")}
        main.INSTALLED_MARKER = home / "var-lib/installed"
        main.LISTENER_FILE, main.AYN_FIFO = home / "systemd/jarngrip-ayn.service", home / "run/jarngrip-ayn"
        main.APP, main.UNIT_FILE = home / "share/jarngrip", home / "systemd/jarngrip.service"
        main.AYN_STATE, main.MARKER = home / "state/inputplumber.json", home / "state/restore.json"
        (main.APP / "bin").mkdir(parents=True)
        (main.APP / "bin/jarngrip.py").write_text("")
        for path in (main.UNIT_FILE, main.LISTENER_FILE, main.APP_MENU, main.AUTOSTART, main.INSTALLED_MARKER, main.AYN_FIFO):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        main.MARKER.parent.mkdir(parents=True, exist_ok=True)
        main.MARKER.write_text('{"bottom_screen": true, "ratatoskr": false}')
        ran = []
        main._systemctl = lambda action, unit=None: ran.append((action, unit)) or True
        plugin = main.Plugin()
        synced = []

        async def sync(wanted=None):
            synced.append(wanted)
            return ""

        plugin._sync_screenshot = sync
        try:
            asyncio.run(plugin._uninstall())
            assert synced == [False]  # the AYN button gets its screenshot back
            assert ("stop", "jarngrip.service") in ran and ("stop", "jarngrip-ayn.service") in ran
            assert ("start", "armada-bottom-screen.service") in ran
            assert ("start", "touch-master.service") not in ran and ran[-1] == ("daemon-reload", None)
            assert not any(p.exists() for p in (main.APP, main.UNIT_FILE, main.LISTENER_FILE, main.APP_MENU, main.AUTOSTART,
                                                main.MARKER, main.AYN_FIFO, main.INSTALLED_MARKER))
            assert main.CFG.exists() and call("get_config")["theme"] == "dark"  # settings stay
        finally:
            for k, v in saved.items():
                setattr(main, k, v)


def test_the_polkit_rule_applies_only_to_profile_loading_by_armada_while_installed():
    with open(os.path.join(ROOT, "polkit", "49-jarngrip-inputplumber.rules"), encoding="utf-8") as f:
        rule = f.read()
    actions = set(re.findall(r'"(org\.shadowblip\.[A-Za-z.]+)"', rule))
    assert actions == {"org.shadowblip.Input.CompositeDevice.LoadProfileFromYaml",
                       "org.shadowblip.Input.CompositeDevice.LoadProfilePath"}
    # The marker it checks must be outside the home folder, which polkitd cannot look inside.
    assert 'subject.user == "armada"' in rule and '"/var/lib/jarngrip/installed"' in rule and "/home/" not in rule
    with open(os.path.join(ROOT, "scripts", "install-on-device.sh"), encoding="utf-8") as f:
        script = f.read()
        assert "polkit/49-jarngrip-inputplumber.rules" in script and "-o armada -g armada /dev/null /var/lib/jarngrip/installed" in script
    with open(os.path.join(ROOT, "scripts", "uninstall-on-device.sh"), encoding="utf-8") as f:
        script = f.read()
        assert "rm -f /etc/polkit-1/rules.d/49-jarngrip-inputplumber.rules" in script and "rm -rf /var/lib/jarngrip" in script


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


def test_systemctl_goes_direct_and_never_runs_a_command_twice():
    import subprocess
    import main

    runs = []

    def run(direct_connects, answers):
        def fake(cmd, **kwargs):
            runs.append(cmd)
            if "--machine=armada@.host" not in cmd and not direct_connects:
                return subprocess.CompletedProcess(cmd, 1, "", "Failed to connect to user scope bus via local transport")
            return subprocess.CompletedProcess(cmd, *answers)
        return fake

    real = main.subprocess.run, main._systemctl_form
    try:
        main._systemctl_form = None
        main.subprocess.run = run(True, (3, "inactive\n", ""))
        assert main._active("jarngrip.service") is False
        assert runs == [["systemctl", "--user", "is-active", "jarngrip.service"]]  # once, and direct
        runs.clear()
        assert main._systemctl("start", "jarngrip.service") is False  # a failed start is not tried again
        assert len(runs) == 1

        main._systemctl_form, runs[:] = None, []
        main.subprocess.run = run(False, (0, "active\n", ""))
        assert main._active("jarngrip.service") is True
        assert [("--machine=armada@.host" in cmd) for cmd in runs] == [False, True]  # direct failed: the fallback
        runs.clear()
        main._active("jarngrip.service")
        assert len(runs) == 1 and "--machine=armada@.host" in runs[0]  # and from then on, the one that works
    finally:
        main.subprocess.run, main._systemctl_form = real


def test_the_backend_never_keeps_decky_waiting():
    """Decky's requests, its stop request among them, are served on the plugin's event loop: blocking work (systemctl,
    busctl, copying files) must run beside it. On the Thor, a stuck loop made Decky kill the plugin unloaded."""
    import asyncio
    import main

    with tempfile.TemporaryDirectory() as tmp:
        backend(tmp)
        names = ("_systemctl", "_active", "_install_runtime", "AYN_FIFO", "UNLOAD_BUDGET_S", "WATCH_RETRY_S", "MARKER")
        saved = {k: getattr(main, k) for k in names}
        slow = {"s": 0.6}

        def systemctl(action, unit=None):
            time.sleep(slow["s"])  # a slow or stuck systemctl
            return True

        main._systemctl, main._active = systemctl, lambda unit: False
        main._install_runtime = lambda: time.sleep(slow["s"]) or False
        main.AYN_FIFO, main.MARKER = Path(tmp) / "jarngrip-ayn", Path(tmp) / "restore.json"
        main.UNLOAD_BUDGET_S, main.WATCH_RETRY_S = 0.3, 60

        async def ticks_during(coro):
            """How often the loop got to run something else (every 20 ms) while coro ran."""
            count = 0

            async def ticker():
                nonlocal count
                while True:
                    await asyncio.sleep(0.02)
                    count += 1

            task = asyncio.ensure_future(ticker())
            await coro
            task.cancel()
            return count

        async def scenario():
            plugin = main.Plugin()
            plugin._sync_screenshot = lambda wanted=None: asyncio.sleep(0, "")
            start = time.monotonic()
            await plugin._main()
            assert time.monotonic() - start < 0.1  # the slow start-up runs afterwards
            assert await ticks_during(plugin.set_enabled(True)) >= 10  # opening the pad: the loop kept going
            slow["s"] = 10  # stuck for good
            start = time.monotonic()
            await plugin._unload()
            assert time.monotonic() - start < 1  # gave up within its budget, well inside Decky's 5 seconds

        try:
            asyncio.run(scenario())
        finally:
            for k, v in saved.items():
                setattr(main, k, v)


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


def test_number_pad_icons_are_kept_per_game_and_with_each_profile():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        listed = call("list_icons")
        assert listed == {"folder": str(Path(tmp) / "Pictures" / "Icons" / "wow"), "icons": []}
        (Path(listed["folder"]) / "fireball.png").write_bytes(b"")
        (Path(listed["folder"]) / "notes.txt").write_bytes(b"")
        assert call("list_icons")["icons"] == ["fireball.png"]
        icons = {"slot_1": "fireball.png", "slot_12:down": "later.webp", "slot_13": "a.png", "slot_1:left": "a.png",
                 "slot_2": "../x.png", "slot_3": "notes.txt", "slot_4": ".png", "slot_5": ""}
        cfg = call("save_config", {"number_icons": True, "icons": icons})["config"]
        # A picture not in the folder yet is kept; anything that is not a number's or a swipe's picture is not.
        assert cfg["icons"] == {"slot_1": "fireball.png", "slot_12:down": "later.webp"} and cfg["number_icons"]
        call("save_profile", "Mage")
        call("save_config", {"icons": {}})
        assert call("select_profile", "Mage")["config"]["icons"] == {"slot_1": "fireball.png", "slot_12:down": "later.webp"}
        assert call("select_profile", "Default")["config"]["icons"] == {}
        call("select_profile", "Mage")
        cfg = call("select_game", "ffxi")["config"]
        assert (cfg["icons"], cfg["number_icons"]) == ({}, False)
        assert call("list_icons")["folder"].endswith("/Icons/ffxi")
        cfg = call("select_game", "wow")["config"]
        assert (cfg["icons"]["slot_1"], cfg["number_icons"], cfg["active_profile"]) == ("fireball.png", True, "Mage")


def test_the_number_keys_show_their_spell_names_on_the_tall_keys_and_in_the_fans():
    pad_draw = painter()
    pad, bridge, clock = make()
    pad.wow_bars = {"slot_5": {"name": "Frostbolt", "picture": "frost.png"},
                    "slot_5:up": {"name": "Shadow Word: Pain", "picture": ""}}
    pad.icon_surfaces = {"frost.png": Anything()}
    key = next(w for w in pad.widgets if w.id == "number:slot_5")
    assert pad.number_pad == "names" and not pad.number_icons and key.w != key.h  # the tall keys, not squares
    named, fans = [], []
    real_named, real_fan = pad_draw._named_key, pad_draw._swipe_fan
    pad_draw._named_key = lambda cr, t, w, name, lit, label: named.append((w.id, name, label))
    pad_draw._swipe_fan = lambda cr, t, w, swipe, label, name=False: fans.append((swipe, label, name))
    try:
        pad_draw.paint(Context(), pad)
        assert ("number:slot_5", "Frostbolt", "5") in named  # its name, never its picture: that is icon mode
        x, y = center(pad, "number:slot_5")
        for dx, dy in ((0, -90), (-90, 0), (0, 90)):
            tid = down(pad, clock, "number:slot_5")
            pad.touch_move(tid, x + dx, y + dy, clock.now)
            pad_draw.paint(Context(), pad)
            pad.touch_up(tid, clock.now)
            clock.now += 0.5
        # What the swipe casts, else its modifier; a cancel stays a cancel.
        assert fans == [("up", "Shadow Word: Pain", True), ("down", "Ctrl", False), ("cancel", "Cancel", False)]
    finally:
        pad_draw._named_key, pad_draw._swipe_fan = real_named, real_fan
    pad_draw.paint(Context(), pad)  # the real fan, its name on two lines
    assert pad_model.number_pad_mode({}) == "names"
    assert pad_model.number_pad_mode({"number_icons": True}) == "icons"  # a config from before the names
    assert pad_model.number_pad_mode({"number_pad": "numbers", "number_icons": True}) == "numbers"


def test_the_number_pad_mode_is_kept_per_game_and_old_configs_carry_over():
    import json

    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        import main

        assert main.NUMBER_PAD_MODES == pad_model.NUMBER_PAD_MODES
        cfg = call("get_config")
        assert (cfg["number_pad"], cfg["number_icons"]) == ("names", False)
        cfg = call("save_config", {"number_pad": "icons"})["config"]
        assert (cfg["number_pad"], cfg["number_icons"]) == ("icons", True)  # kept for a pad from before the names
        assert call("save_config", {"number_pad": "pictures"})["config"]["number_pad"] == "icons"
        # A panel from before the names: icons off leaves the names, and never turns numbers into names.
        assert call("save_config", {"number_icons": False})["config"]["number_pad"] == "names"
        call("save_config", {"number_pad": "numbers"})
        assert call("save_config", {"number_icons": False})["config"]["number_pad"] == "numbers"
        assert call("select_game", "ffxi")["config"]["number_pad"] == "names"
        assert call("select_game", "wow")["config"]["number_pad"] == "numbers"

        # A config saved before there was a number_pad, with a game set aside in it.
        Path(tmp, "config.json").write_text(json.dumps({"game": "wow", "number_icons": False,
                                                        "games": {"ffxi": {"number_icons": True}}}))
        assert call("get_config")["number_pad"] == "names"
        cfg = call("select_game", "ffxi")["config"]
        assert (cfg["number_pad"], cfg["number_icons"]) == ("icons", True)
        Path(tmp, "config.json").write_text(json.dumps({"number_icons": True}))
        assert call("get_config")["number_pad"] == "icons"


def test_the_icon_page_gets_small_pictures_themselves_and_big_ones_by_name():
    import base64

    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        folder = Path(call("list_icons")["folder"])
        (folder / "fire.PNG").write_bytes(b"\x89PNG small")
        (folder / "huge.jpg").write_bytes(b"x" * (256 * 1024 + 1))
        assert call("list_icons")["icons"] == ["fire.PNG", "huge.jpg"]
        previews = call("icon_previews", ["fire.PNG", "huge.jpg", "../config.json", "absent.png", 5])
        assert previews == {"previews": {"fire.PNG": "data:image/png;base64,"
                                         + base64.b64encode(b"\x89PNG small").decode()}, "more": []}
        assert call("icon_previews", "fire.PNG") == {"previews": {}, "more": []}
        names = [f"{i:04}.png" for i in range(300)]
        for name in names:
            (folder / name).write_bytes(b"x")
        reply = call("icon_previews", names)  # a page at a time, never the whole folder: the rest is asked for next
        assert len(reply["previews"]) == 200 and reply["more"] == names[200:]
        # One reply holds at most PREVIEW_REPLY bytes of pictures, and always the first, so that every one comes.
        big = [f"big{i}.png" for i in range(40)]
        for name in big:
            (folder / name).write_bytes(b"x" * (256 * 1024))
        reply = call("icon_previews", big)
        assert list(reply["previews"]) == big[:32] and reply["more"] == big[32:]
        assert list(call("icon_previews", reply["more"])["previews"]) == big[32:]


def test_pictures_named_for_a_number_and_swipe_fill_those_icons():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        folder = Path(call("list_icons")["folder"])
        names = ["5.png", "5-fireball.png", "5 Shift frostbolt.png", "minus_down.webp", "0-up-x.jpg", "2-alt.png",
                 "7-upheaval.png", "2023-screenshot.png", "10.png", "equals.PNG", "frost_nova.png"]
        for name in names:
            (folder / name).write_bytes(b"")
        call("save_config", {"icons": {"slot_5": "old.png", "slot_3": "keep.png"}})
        result = call("fill_icons")
        # The first by name wins a number; Alt is not one of WoW's swipes; "upheaval" is a name, not a swipe.
        assert result["config"]["icons"] == {
            "slot_3": "keep.png", "slot_5": "5-fireball.png", "slot_5:up": "5 Shift frostbolt.png",
            "slot_11:down": "minus_down.webp", "slot_10:up": "0-up-x.jpg", "slot_7": "7-upheaval.png",
            "slot_12": "equals.PNG"}
        assert result["filled"] == 6
        call("select_game", "ffxi")
        folder = Path(call("list_icons")["folder"])
        for name in ("1-ctrl.png", "1-alt.png", "1-shift.png"):
            (folder / name).write_bytes(b"")
        assert call("fill_icons")["config"]["icons"] == {"slot_1:up": "1-ctrl.png", "slot_1:down": "1-alt.png"}


def test_the_backend_names_the_same_swipe_modifiers_as_the_pad():
    import importlib

    sys.path.insert(0, ROOT)
    main = importlib.import_module("main")
    for game_id, words in main.SWIPE_WORDS.items():
        swipes = pad_model.GAMES[game_id].swipes
        assert words == {swipes[swipe][0].lower(): swipe for swipe in ("up", "down")}, game_id
    assert set(main.SWIPE_WORDS) == {g.id for g in pad_model.GAMES.values() if g.numbers}


def test_the_decky_panel_never_sends_back_the_icons_the_icon_page_saved():
    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        panel = f.read()
    content = panel[panel.index("function Content()"):panel.index("function IconPage()")]
    # The side panel saves through saveConfig, which leaves the icons out; only the icon page sends them.
    assert 'call("save_config"' not in content and "saveConfig(" in content
    assert 'const saveConfig=c=>{const {icons,...rest}=c;return call("save_config",rest)}' in panel


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
        FONT_WEIGHT_BOLD=1, LINE_CAP_ROUND=1, LINE_JOIN_ROUND=1, FORMAT_ARGB32=0, ImageSurface=lambda *a: Anything(),
        Context=lambda surface: Context()))
    import pad_draw

    return pad_draw


def test_every_swipe_fan_stays_on_the_screen():
    pad_draw = painter()
    _, widgets = build_layout("pad", 0)
    targets = [w for w in build_layout("pad", 1, game=pad_model.FFXI)[1] if w.kind == "page" and w.data.confirm]
    assert len(targets) == 6
    fans = [(w, s) for w in widgets if w.kind == "number" for s in pad_draw.FAN_DIRECTIONS if s != "confirm"]
    for w, swipe in fans + [(w, "confirm") for w in targets]:
        cx, cy = w.x + w.w / 2, w.y + w.h / 2
        for angle in (pad_draw.FAN_DIRECTIONS[swipe],):
            reach = pad_draw._fan_reach(cx, cy, angle)
            end_x, end_y = cx + reach * math.cos(angle), cy + reach * math.sin(angle)
            assert 0 <= end_x <= pad_model.W and 0 <= end_y <= pad_model.H, (w.id, swipe)
            assert reach > 100, (w.id, swipe)  # room for at least a short fan with its lettering

def test_an_open_radial_is_whole_on_the_screen_and_reaches_past_its_button():
    for game in pad_model.GAMES.values():
        for page in range(len(game.pages)):
            for w in build_layout("pad", page, game=game)[1]:
                if w.kind != "page" or not w.data.radial:
                    continue
                cx, cy = w.center
                reach = pad_model.radial_reach(cx, cy)
                outer = reach + pad_model.RADIAL_GROW
                assert outer <= cx <= pad_model.W - outer and outer <= cy <= pad_model.H - outer, game.id
                assert reach > w.w / 2 + 120, (game.id, reach)


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


class Clipped(Context):
    """A stand-in cairo context whose paint is clipped to a few boxes, as a redraw of a swipe's areas is."""

    def __init__(self, boxes):
        self.boxes = boxes

    def copy_clip_rectangle_list(self):
        return self.boxes


def test_a_swipe_change_repaints_only_its_own_areas():
    pad_draw = painter()
    changes = []
    pad, bridge, clock = make(on_change=lambda widget=None: changes.append(widget))
    tid = down(pad, clock, "number:slot_5")
    x, y = center(pad, "number:slot_5")
    changes.clear()
    pad.touch_move(tid, x, y - 90, clock.now)
    pad.touch_move(tid, x - 90, y, clock.now)
    five = next(w for w in pad.widgets if w.id == "number:slot_5")
    assert changes == [five, five]  # the key's swipe changed, nothing else
    pad.touch_up(tid, clock.now)
    assert changes[-1] is None  # a lift repaints everything: the key may light up, its square fade

    for icons in (False, True):
        pad.apply_config({"number_icons": icons})
        five = next(w for w in pad.widgets if w.id == "number:slot_5")
        areas = pad_draw.swipe_areas(pad, five)
        assert len(areas) == 4  # the key, and each swipe's fan or square

        def inside(px, py):
            return any(ax <= px <= ax + aw and ay <= py <= ay + ah for ax, ay, aw, ah in areas)

        cx, cy = five.x + five.w / 2, five.y + five.h / 2
        for swipe in ("up", "down", "cancel"):
            if icons:  # every corner of each square
                sx, sy, size = pad_model.swipe_square(five, swipe)
                assert all(inside(sx + i * size, sy + j * size) for i in (0, 1) for j in (0, 1)), swipe
            else:  # the far end of each fan
                angle = pad_draw.FAN_DIRECTIONS[swipe]
                outer = pad_draw._fan_outer(five, angle)
                assert inside(cx + outer * math.cos(angle), cy + outer * math.sin(angle)), swipe

        # Painted through those areas, only the widgets under them are drawn; with no clip, every one is.
        drawn = []
        real = pad_draw._widget
        pad_draw._widget = lambda cr, t, p, w: drawn.append(w.id)
        try:
            tid = down(pad, clock, "number:slot_5")
            pad.touch_move(tid, cx - 90, cy, clock.now)
            pad_draw.paint(Clipped(areas), pad)
            assert "number:slot_5" in drawn and "number:slot_4" in drawn  # the key, and its neighbour under the swipe
            assert not any(w.startswith(("mode:", "tab:")) for w in drawn)  # far from it
            clipped = len(drawn)
            assert clipped < len(pad.widgets) / 2
            drawn.clear()
            pad_draw.paint(Context(), pad)
            assert len(drawn) == len(pad.widgets) > clipped
            pad.touch_up(tid, clock.now)
        finally:
            pad_draw._widget = real


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
        tap(pad, clock, "tab:2")
        tid = down(pad, clock, "page:chat")
        pad_draw.paint(Context(), pad)  # open, nothing chosen
        clock.now += pad_model.RADIAL_OPEN_S / 2
        pad_draw.paint(Context(), pad)  # half grown out of its button
        clock.now += pad_model.RADIAL_OPEN_S
        for direction in ("down", "up_left"):  # Cancel, then a channel
            pad.touch_move(tid, *slice_point(*center(pad, "page:chat"), direction), clock.now)
            pad_draw.paint(Context(), pad)
        pad.release_everything()

    pad, bridge, clock = make()
    pad.apply_config({"game": "ffxi"})
    tap(pad, clock, "tab:2")
    tid = down(pad, clock, "page:chat")
    pad.touch_move(tid, *slice_point(*center(pad, "page:chat"), "right"), clock.now)  # an empty slice
    pad_draw.paint(Context(), pad)
    pad.release_everything()
    for target, dy in (("tab:0", -90), ("tab:1", 90), ("tab:2", 0)):
        tap(pad, clock, target)
        tid = down(pad, clock, "number:slot_1")
        x, y = center(pad, "number:slot_1")
        pad.touch_move(tid, x, y + dy, clock.now)  # its Ctrl or Alt fan is painted
        pad_draw.paint(Context(), pad)
        pad.touch_up(tid, clock.now)
    tap(pad, clock, "tab:1")
    tid = down(pad, clock, "page:party_5")
    x, y = center(pad, "page:party_5")
    pad.touch_move(tid, x + 90, y, clock.now)  # its Enter fan is painted
    pad_draw.paint(Context(), pad)

    pad, bridge, clock = make()
    pad.apply_config({"game": "desktop"})
    for target in ("tab:0", "tab:1", "mode:trackpad", "mode:keyboard"):
        tap(pad, clock, target)
        pad_draw.paint(Context(), pad)
    tap(pad, clock, "tab:1")
    tid = down(pad, clock, "page:media")
    clock.now += pad_model.RADIAL_OPEN_S
    pad.touch_move(tid, *slice_point(*center(pad, "page:media"), "down_left"), clock.now)
    pad_draw.paint(Context(), pad)


def test_number_pad_icons_paint_with_and_without_their_pictures():
    pad_draw = painter()
    assert pad_draw.make_icon(Anything(), 300, 120) is not None
    for theme in pad_model.THEME_IDS:
        pad, bridge, clock = make()
        pad.apply_config({"theme": theme, "number_icons": True,
                          "icons": {"slot_1": "a.png", "slot_1:up": "b.png", "slot_10:down": "c.png", "slot_2": "gone.png"}})
        pad.icon_surfaces = {name: Anything() for name in ("a.png", "b.png", "c.png")}
        pad_draw.paint(Context(), pad)  # at rest: icons, and numbers where there are none
        for widget_id, dx, dy in (("number:slot_1", 0, -90), ("number:slot_1", 0, 90), ("number:slot_1", -90, 0),
                                  ("number:slot_10", 0, 90), ("number:slot_2", 0, -90)):
            tid = down(pad, clock, widget_id)
            x, y = center(pad, widget_id)
            pad.touch_move(tid, x + dx, y + dy, clock.now)  # its square, pressed key and all
            pad_draw.paint(Context(), pad)
            pad.touch_up(tid, clock.now)
            clock.now += 0.5


# ---------------------------------------------------------------------------------------------- WoW action bars

WOW_SAVED = r"""
JarnGripDB = {
["characters"] = {
["Thrall - Area 52"] = {
["keys"] = {
["1"] = {
["kind"] = "spell",
["icon"] = 136048,
["name"] = "Lightning Bolt",
},
["SHIFT-1"] = {
["icon"] = "Interface\\Icons\\Spell_Nature_EarthShock",
["name"] = "Earth Shock",
},
["CTRL-1"] = {
["icon"] = 999999,
["name"] = "Healing Stream Totem",
},
["2"] = {
["icon"] = 135990,
["name"] = "Caf\195\169 \"Special\"",
},
["CTRL-SHIFT-F1"] = {
["name"] = "Hex",
},
["SHIFT-3"] = {
["name"] = "Open/Close World Map",
["kind"] = "binding",
},
},
["spec"] = "Elemental",
["saved"] = 1793000000,
},
["Old - Realm"] = {
["keys"] = {
["4"] = {
["name"] = "Not me",
},
},
},
},
["last"] = "Thrall - Area 52",
["version"] = 1,
}
"""


def test_the_wow_addons_file_is_read_as_data_and_nothing_else():
    import wow_bars

    saved = wow_bars.parse_saved_variables(WOW_SAVED + "\nOther = { 1, -2.5, 0x1F, true, nil, x = 'y\\65' ; } --[==[ a\n]==]")
    assert saved["Other"] == {1: 1, 2: -2.5, 3: 31, 4: True, 5: None, "x": "yA"}
    keys = saved["JarnGripDB"]["characters"]["Thrall - Area 52"]["keys"]
    assert keys["2"]["name"] == 'Café "Special"' and keys["SHIFT-1"]["icon"].endswith("Spell_Nature_EarthShock")
    for code in ('JarnGripDB = os.execute("rm -rf ~")', "JarnGripDB = { [1] = }", "JarnGripDB = {", "x = y"):
        try:
            wow_bars.parse_saved_variables(code)
        except wow_bars.LuaError:
            continue
        raise AssertionError(f"accepted {code!r}")
    bars = wow_bars.last_character(saved["JarnGripDB"])
    assert (bars["character"], bars["spec"], bars["saved"]) == ("Thrall - Area 52", "Elemental", 1793000000)
    assert "4" not in bars["keys"]  # another character's
    assert wow_bars.last_character({}) == {} and wow_bars.last_character({"last": "x", "characters": {"x": 5}}) == {}


def test_each_number_and_swipe_is_matched_to_the_key_it_sends_in_wow():
    import wow_bars

    bindings = {"slot_1": "ctrl+59", "slot_2": 33, "slot_3": "alt+shift+30", "slot_4": "f2"}
    keys = wow_bars.slot_keys(bindings)
    assert (keys["slot_5"], keys["slot_5:up"], keys["slot_5:down"]) == ("5", "SHIFT-5", "CTRL-5")
    assert (keys["slot_11"], keys["slot_11:up"], keys["slot_12:down"]) == ("-", "SHIFT--", "CTRL-=")
    assert (keys["slot_1"], keys["slot_1:up"], keys["slot_1:down"]) == ("CTRL-F1", "CTRL-SHIFT-F1", "CTRL-F1")
    assert (keys["slot_2"], keys["slot_3:down"], keys["slot_4"]) == ("F", "ALT-CTRL-SHIFT-A", "4")
    # The same keys the pad itself presses for them.
    pad, bridge, clock = make()
    pad.apply_config({"bindings": bindings})
    for slot in pad_model.NUMBER_SLOTS:
        for swipe in ("", "up", "down"):
            key, mods = pad_model.combo_for(slot, pad.bindings)
            extra = pad_model.WOW.swipes[swipe][1] if swipe else ()
            assert keys[f"{slot.id}:{swipe}" if swipe else slot.id] == wow_bars.key_name(key, mods + extra)
    assert wow_bars.key_name(999) == "" and "slot_1" not in wow_bars.slot_keys({"slot_1": 240})


def test_the_wow_addons_file_is_found_where_wow_keeps_it_the_newest_first():
    import wow_bars

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        assert wow_bars.find_file(home, home / "Icons") is None
        wtf = "drive_c/Program Files (x86)/World of Warcraft/_retail_/WTF/Account/123#1/SavedVariables"
        steam = home / ".local/share/Steam/steamapps/compatdata/4242/pfx" / wtf / "JarnGrip.lua"
        lutris = home / "Games/battlenet" / wtf.replace("_retail_", "_forever_") / "JarnGrip.lua"
        copy = home / "Icons" / "JarnGrip.lua"
        for i, path in enumerate((steam, lutris, copy)):
            path.parent.mkdir(parents=True)
            path.write_text(WOW_SAVED)
            os.utime(path, (1000 + i, 1000 + i))
        assert wow_bars.find_file(home, home / "Icons") == copy
        os.utime(steam, (5000, 5000))
        assert wow_bars.find_file(home, home / "Icons") == steam
        assert wow_bars.read_file(steam)["last"] == "Thrall - Area 52"
        steam.write_text("JarnGripDB = {")
        assert wow_bars.read_file(steam) == {} and wow_bars.read_file(home / "absent.lua") == {}


def test_a_keys_wow_icon_finds_its_picture_by_icon_or_by_name():
    import wow_bars

    with tempfile.TemporaryDirectory() as tmp:
        names_file = Path(tmp) / "icon-names.csv"
        names_file.write_text("136048;interface/icons/spell_nature_lightning.blp\n1;interface/cinematics/logo.avi\n"
                              "135990;Interface/Icons/Spell_Frost_FrostBolt02.blp\n")
        names = wow_bars.read_icon_names(names_file)
        assert names == {136048: "spell_nature_lightning", 135990: "spell_frost_frostbolt02"}
        pictures = ["Spell_Nature_Lightning.png", "spell_nature_earthshock.jpg", "healing-stream_totem.webp",
                    "135990.png", "spell_frost_frostbolt02.png"]
        bars = wow_bars.last_character(wow_bars.parse_saved_variables(WOW_SAVED)["JarnGripDB"])
        result = wow_bars.pad_bars(bars, {"slot_1": "ctrl+59"}, pictures, names)
        assert result["slot_1:up"] == {"name": "Hex", "picture": ""}  # Ctrl+F1 with Shift
        result = wow_bars.pad_bars(bars, {}, pictures, names)
        assert result["slot_1"] == {"name": "Lightning Bolt", "picture": "Spell_Nature_Lightning.png"}  # by its icon
        assert result["slot_1:up"]["picture"] == "spell_nature_earthshock.jpg"  # by its path, in older clients
        assert result["slot_1:down"]["picture"] == "healing-stream_totem.webp"  # by the spell's name
        assert result["slot_2"]["picture"] == "135990.png"  # a picture named for the file id comes first
        assert result["slot_3:up"] == {"name": "Open/Close World Map", "picture": ""}
        assert "slot_4" not in result and "slot_3" not in result
        assert wow_bars.pad_bars({}, {}, pictures, names) == {}


def test_a_key_without_a_picture_of_its_own_shows_its_wow_icon_or_name():
    pad, bridge, clock = make()
    slot1, slot2 = pad_model.NUMBER_SLOTS[:2]
    pad.wow_bars = {"slot_1": {"name": "Lightning Bolt", "picture": "bolt.png"},
                    "slot_1:up": {"name": "Earth Shock", "picture": ""}, "slot_2": {"name": "Hex", "picture": ""}}
    # By default the keys show names, and no pictures; with numbers, neither.
    assert pad.icon_of(slot1) == "" and pad.name_of(slot1) == "Lightning Bolt" and pad.picture_names() == set()
    pad.apply_config({"number_pad": "numbers"})
    assert pad.name_of(slot1) == "" and pad.name_of(slot1, "up") == ""
    pad.apply_config({"number_icons": True, "icons": {"slot_2": "mine.png"}})
    assert (pad.icon_of(slot1), pad.name_of(slot1)) == ("bolt.png", "Lightning Bolt")
    assert (pad.icon_of(slot1, "up"), pad.name_of(slot1, "up")) == ("", "Earth Shock")
    assert pad.icon_of(slot2) == "mine.png"  # a picture picked for the key wins
    assert pad.picture_names() == {"bolt.png", "mine.png"}
    # Painted at rest and while swiped, with and without pictures, long names included.
    pad_draw = painter()
    pad.wow_bars["slot_3:down"] = {"name": "Summon Elemental Lord of the Very Long Spell Names", "picture": ""}
    pad.icon_surfaces = {"bolt.png": Anything()}
    for theme, mode in ((theme, mode) for theme in pad_model.THEME_IDS for mode in ("icons", "names")):
        pad.apply_config({"theme": theme, "number_pad": mode})
        pad_draw.paint(Context(), pad)
        for widget_id, dy in (("number:slot_1", -90), ("number:slot_1", 90), ("number:slot_3", 90)):
            tid = down(pad, clock, widget_id)
            x, y = center(pad, widget_id)
            pad.touch_move(tid, x, y + dy, clock.now)
            pad_draw.paint(Context(), pad)
            pad.touch_up(tid, clock.now)
            clock.now += 0.5
    classic = pad_draw.THEMES["classic"]
    # The stand-in's letters are 10 wide at any size: two words fit in 100, and in 40 not even one more shrinking helps.
    assert pad_draw._name_lines(Context(), classic, "One Two Three Four Five", 30, 100) == (
        ["One Two", "Three Four", "Five"], 30)
    assert pad_draw._name_lines(Context(), classic, "One Two Three Four Five", 30, 40) == (
        ["One", "Two", "Three Four Five"], 14)


def test_the_icon_page_learns_what_the_wow_bars_hold():
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        import main
        main.HOME = Path(tmp) / "home"
        bars = call("wow_bars")
        assert (bars["file"], bars["keys"], bars["icon_list"]) == ("", {}, False)
        folder = Path(call("list_icons")["folder"])
        (folder / "JarnGrip.lua").write_text(WOW_SAVED)
        (folder / "lightning bolt.png").write_bytes(b"")
        bars = call("wow_bars")
        assert bars["file"] == str(folder / "JarnGrip.lua") and bars["character"] == "Thrall - Area 52"
        assert bars["keys"]["slot_1"] == {"name": "Lightning Bolt", "picture": "lightning bolt.png"}
        assert call("get_config")["wow_bars"] is True
        assert call("save_config", {"wow_bars": False})["config"]["wow_bars"] is False


def test_the_wow_addon_saves_what_the_pad_reads():
    import wow_bars

    addon = Path(ROOT) / "wow-addon" / "JarnGrip"
    toc = (addon / "JarnGrip.toc").read_text()
    assert f"## SavedVariables: {wow_bars.TABLE}" in toc and "\nJarnGrip.lua" in toc
    interfaces = toc.split("\n", 1)[0].removeprefix("## Interface: ").split(", ")
    assert {"16001", "120105"} <= set(interfaces)  # WoW Forever (1.60.1) and retail
    lua = (addon / "JarnGrip.lua").read_text()
    for field in ("JarnGripDB.last", "JarnGripDB.characters[who]", "keys = keys", "spec = specName()", "saved = time()"):
        assert field in lua, field
    # It looks at every key the pad's numbers can send in WoW, with Shift and Ctrl.
    listed = re.search(r"local KEYS = \{(.*?)\}", lua, re.DOTALL).group(1)
    for name in ("1", "0", "-", "="):
        assert f'"{name}"' in listed
    assert '"SHIFT-"' in lua and '"CTRL-"' in lua and '"CTRL-SHIFT-"' in lua
    assert "SendChat" not in lua and "RunMacro" not in lua and "CastSpell" not in lua  # it only reads



def test_japanese_keyboard_bindings_make_the_equals_key_a_caret():
    import wow_bars

    # The addon mirrors each JIS key's saved binding onto the US key in its place, as session-only overrides, only
    # when turned on, and saves that it is on for the pad.
    lua = (Path(ROOT) / "wow-addon" / "JarnGrip" / "JarnGrip.lua").read_text()
    assert '{ "=", "^" }' in lua and "SetOverrideBinding(owner" in lua and "ClearOverrideBindings(owner)" in lua
    assert "if JarnGripDB.jis then" in lua and "JarnGripDB.jis = JarnGripDB.jis == true" in lua
    assert "GetBindingAction(modifier .. pair[2])  --" in lua  # the saved binding, never an override
    assert "SaveBindings" not in lua and "SetBinding(" not in lua  # the account's bindings are never changed
    saved = wow_bars.parse_saved_variables(WOW_SAVED)["JarnGripDB"]
    assert wow_bars.last_character(saved)["jis"] is False
    assert wow_bars.last_character({**saved, "jis": True})["jis"] is True
    assert wow_bars.last_character({**saved, "jis": "yes"})["jis"] is False
    # The pad labels its = key ^ while they are on, and only that key.
    pad, bridge, clock = make()
    numbers = [w for w in pad.widgets if w.kind == "number"]
    equals = next(w for w in numbers if w.data.id == "slot_12")
    assert [pad.number_label(w) for w in numbers][-2:] == ["-", "="]
    pad.wow_jis = True
    assert pad.number_label(equals) == "^" and [pad.number_label(w) for w in numbers][:3] == ["1", "2", "3"]
    pad_draw = painter()
    for icons in (False, True):
        pad.apply_config({"number_icons": icons})
        drawn = Recorder()
        pad_draw.paint(drawn, pad)
        assert "^" in drawn.texts and "=" not in drawn.texts, icons
    # The icon page labels it too.
    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        panel = f.read()
    assert 'label==="="&&bars.jis' in panel

def driver_app():
    """jarngrip.py, imported against a stand-in GTK, and a PadApp of it with only what the icon and WoW bars code
    uses: its methods run without a display."""
    import importlib
    import threading

    class GLibError(Exception):
        message = "unreadable"

    loads = []

    class Pixbuf:
        @staticmethod
        def new_from_file_at_scale(path, w, h, keep):
            loads.append(Path(path).name)
            if Path(path).read_bytes() == b"broken":
                raise GLibError()
            return types.SimpleNamespace(apply_embedded_orientation=lambda: None, get_width=lambda: 64,
                                         get_height=lambda: 64)

    idle = []
    repository = types.SimpleNamespace(
        Gdk=types.SimpleNamespace(cairo_surface_create_from_pixbuf=lambda *a: Anything()),
        GdkPixbuf=types.SimpleNamespace(Pixbuf=Pixbuf),
        GLib=types.SimpleNamespace(Error=GLibError, idle_add=lambda fn, *args: idle.append((fn, args))),
        Gtk=types.SimpleNamespace())
    sys.modules["gi"] = types.SimpleNamespace(require_version=lambda *a: None, repository=repository)
    sys.modules["gi.repository"] = repository
    painter()  # pad_draw against the stand-in cairo
    jarngrip = importlib.import_module("jarngrip")
    # Imported once: each call's stand-ins replace the last one's, so that loads and idle are this call's.
    jarngrip.Gdk, jarngrip.GdkPixbuf, jarngrip.GLib = repository.Gdk, repository.GdkPixbuf, repository.GLib
    app = jarngrip.PadApp.__new__(jarngrip.PadApp)
    app.pad, _, _ = make()
    app.lock, app.stop, app._wow_wake = threading.RLock(), threading.Event(), threading.Event()
    app._icon_cache, app._config, app._config_mtime, app._wow_inputs = {}, {}, 1, (False, {}, None)
    app._last_error_log = 0.0
    app.logger = types.SimpleNamespace(lines=[])
    app.logger.log = lambda code, text: app.logger.lines.append(text)
    app.area = types.SimpleNamespace(draws=0)
    app.area.queue_draw = lambda: setattr(app.area, "draws", app.area.draws + 1)
    return jarngrip, app, loads, idle


def test_the_pad_shows_a_picture_copied_in_or_replaced_without_a_setting_changing():
    with tempfile.TemporaryDirectory() as tmp:
        jarngrip, app, loads, idle = driver_app()
        jarngrip.ICONS = Path(tmp)
        folder = Path(tmp) / "wow"
        folder.mkdir()
        app.pad.apply_config({"number_icons": True, "icons": {"slot_1": "fire.png", "slot_2": "bad.png"}})
        assert app._update_icons() is False and app.pad.icon_surfaces == {}  # neither is there yet
        (folder / "fire.png").write_bytes(b"one")
        (folder / "bad.png").write_bytes(b"broken")
        assert app._update_icons() is True and set(app.pad.icon_surfaces) == {"fire.png"}
        assert app._update_icons() is False and loads == ["bad.png", "fire.png"]  # neither loaded again
        assert len(app.logger.lines) == 1  # the broken one is logged once
        (folder / "fire.png").write_bytes(b"two")  # the same name, another picture
        os.utime(folder / "fire.png", ns=(1, 1))
        assert app._update_icons() is True and loads[-1] == "fire.png"


def test_the_pad_looks_up_the_wow_bars_on_their_own_thread():
    import threading

    with tempfile.TemporaryDirectory() as tmp:
        jarngrip, app, loads, idle = driver_app()
        jarngrip.ICONS = Path(tmp) / "Icons"
        folder = jarngrip.ICONS / "wow"
        folder.mkdir(parents=True)
        (folder / "JarnGrip.lua").write_text(WOW_SAVED)
        (folder / "earth shock.png").write_bytes(b"x")
        app._config = {"bindings": {}}
        app.pad.apply_config({"number_icons": True})
        app._ask_wow_bars()
        assert app._wow_inputs[0] is True and app._wow_wake.is_set()
        worker = threading.Thread(target=app._wow_worker, daemon=True)
        worker.start()
        for _ in range(200):
            if idle:
                break
            time.sleep(0.01)
        app.stop.set()
        app._wow_wake.set()
        worker.join(1)
        assert not worker.is_alive() and len(idle) == 1
        fn, args = idle[0]
        assert fn(*args) is False  # handed to the GTK thread, once
        assert app.pad.wow_bars["slot_1:up"] == {"name": "Earth Shock", "picture": "earth shock.png"}
        assert "earth shock.png" in app.pad.icon_surfaces and app.area.draws == 1
        app.pad.apply_config({"number_pad": "numbers"})
        app._ask_wow_bars()  # numbers only: still read, for the = key's ^ (wow_jis), but the names are not shown
        assert app._wow_inputs[0] is True and app.pad.wow_bars
        assert app.pad.name_of(pad_model.NUMBER_SLOTS[0], "up") == ""
        app._config = {"wow_bars": False}
        app._ask_wow_bars()  # turned off: forgotten at once, and redrawn
        assert app.pad.wow_bars == {} and app.area.draws == 2
        fn(*args)  # a result that arrives late is not shown
        assert app.pad.wow_bars == {}


def test_a_wow_bars_lookup_that_fails_is_tried_again():
    import threading
    import wow_bars

    with tempfile.TemporaryDirectory() as tmp:
        jarngrip, app, loads, idle = driver_app()
        jarngrip.ICONS = Path(tmp) / "Icons"
        folder = jarngrip.ICONS / "wow"
        folder.mkdir(parents=True)
        (folder / "JarnGrip.lua").write_text(WOW_SAVED)
        app._config = {"bindings": {}}
        app.pad.apply_config({"number_icons": True})
        real, calls = wow_bars.lookup, []

        def flaky(*args):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("the file was being rewritten")
            return real(*args)

        app._log_error = lambda *a: None
        jarngrip.wow_bars.lookup = flaky
        try:
            worker = threading.Thread(target=app._wow_worker, daemon=True)
            worker.start()
            for _ in range(2):  # the second wake, with nothing changed, tries the same files again
                app._ask_wow_bars()
                for _ in range(200):
                    if len(calls) >= 2 or (len(calls) == 1 and not app._wow_wake.is_set()):
                        break
                    time.sleep(0.01)
                time.sleep(0.05)
            for _ in range(200):
                if idle:
                    break
                time.sleep(0.01)
            app.stop.set()
            app._wow_wake.set()
            worker.join(1)
        finally:
            jarngrip.wow_bars.lookup = real
        assert len(calls) == 2 and len(idle) == 1

def test_review_fixes_in_the_backend_the_script_and_the_panel():
    import importlib
    import wow_bars

    sys.path.insert(0, ROOT)
    import main

    assert main.PICTURE_TYPES == wow_bars.PICTURE_TYPES
    # A full-width or Arabic-Indic digit is not one of the pad's numbers, and does not stop the fill.
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        folder = Path(call("list_icons")["folder"])
        for name in ("５-fireball.png", "٣.png", "5-frost.png"):
            (folder / name).write_bytes(b"")
        result = call("fill_icons")
        assert result["filled"] == 1 and result["config"]["icons"] == {"slot_5": "5-frost.png"}
    # The script keeps the lines the pad reads.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    script = importlib.import_module("wow-icon-names")
    lines = ["132089;interface/icons/ability_ambush.blp\n", "1;interface/cinematics/logo.avi\n",
             "x;interface/icons/a.blp\n", "5;Interface\\Icons\\B.blp\n"]
    assert list(script.icons(lines)) == ["132089;interface/icons/ability_ambush.blp\n", "5;Interface\\Icons\\B.blp\n"]
    assert [wow_bars.icon_line(line) for line in lines] == [(132089, "interface/icons/ability_ambush.blp"), None, None,
                                                            (5, "Interface\\Icons\\B.blp")]
    with open(os.path.join(ROOT, "dist", "index.js"), encoding="utf-8") as f:
        panel = f.read()
    assert "bars.character?`WoW bars:" in panel  # a file with no character in it is not "saved 20399 days ago"
    with open(os.path.join(ROOT, "wow-addon", "JarnGrip", "JarnGrip.lua"), encoding="utf-8") as f:
        lua = f.read()
    assert 'if waitingForItems and JarnGripDB then queue() end' in lua



class Recorder(Context):
    """A stand-in cairo context that remembers the color each piece of text was drawn in, and the icons masked."""

    def __init__(self):
        self.rgba, self.texts, self.masks, self.faint = None, {}, 0, 0

    def set_source_rgba(self, *rgba):
        self.rgba = rgba

    def set_source_rgb(self, *rgb):
        self.rgba = (*rgb, 1.0)

    def show_text(self, text):
        self.texts[text] = self.rgba  # the last layer drawn: the lettering over its shadow

    def mask_surface(self, *args):
        self.masks += 1

    def paint_with_alpha(self, alpha):
        self.faint += 1


def test_the_wow_chat_petals_are_lettered_in_the_games_channel_colors():
    pad_draw = painter()
    radial = next(s for s in pad_model.WOW.buttons if s.radial)
    colors = {slot.label: slot.color for _, slot in radial.radial}
    assert colors == {"Guild": 0x40FF40, "Party": 0xAAAAFF, "Yell": 0xFF4040, "Raid": 0xFF7F00, "Instance": 0xFF7F00,
                      "Say": 0xFFFFFF, "Whisper": 0xFF80FF}
    assert radial.picture == "chat_say"
    ffxi = next(s for s in pad_model.FFXI.buttons if s.radial)
    assert not ffxi.picture and not any(slot.color for _, slot in ffxi.radial)  # FFXI's stay as they were
    for theme_id, theme in pad_draw.THEMES.items():
        pad, bridge, clock = make()
        pad.apply_config({"theme": theme_id})
        tap(pad, clock, "tab:2")
        landing = center(pad, "page:chat")
        tid = down(pad, clock, "page:chat")
        clock.now += pad_model.RADIAL_OPEN_S + 0.01
        pad.touch_move(tid, *slice_point(*landing, "right"), clock.now)  # Yell chosen
        cr = Recorder()
        pad_draw.paint(cr, pad)
        rgb = lambda name: tuple(round(c, 3) for c in cr.texts[name][:3])
        assert rgb("Guild") == (round(0x40 / 255, 3), 1.0, round(0x40 / 255, 3)), theme_id
        assert rgb("Whisper") == (1.0, round(0x80 / 255, 3), 1.0), theme_id
        assert rgb("Yell") == tuple(round(c, 3) for c in theme.text_pressed), theme_id  # chosen: as a pressed button
        pad.touch_up(tid, clock.now)


def test_the_chat_button_shows_its_icon_where_it_is_and_its_name_where_it_is_not():
    pad_draw = painter()
    pad, bridge, clock = make()
    tap(pad, clock, "tab:2")
    try:
        pad_draw.BUTTON_ICONS = {}
        cr = Recorder()
        pad_draw.paint(cr, pad)
        assert "Chat" in cr.texts and cr.masks == 0
        pad_draw.BUTTON_ICONS = {"chat_say": Anything()}
        cr = Recorder()
        pad_draw.paint(cr, pad)
        assert "Chat" not in cr.texts and cr.masks == 1
        tid = down(pad, clock, "page:chat")  # open: in the hub too
        clock.now += pad_model.RADIAL_OPEN_S + 0.01
        cr = Recorder()
        pad_draw.paint(cr, pad)
        assert "Chat" not in cr.texts and cr.masks == 2 and "Say" in cr.texts
        pad.touch_up(tid, clock.now)
    finally:
        pad_draw.BUTTON_ICONS = {}


def test_the_bundled_button_icons_are_installed_and_loaded():
    with tempfile.TemporaryDirectory() as tmp:
        jarngrip, app, loads, idle = driver_app()
        folder = Path(tmp) / "icons"
        assert app._load_button_icons(folder) == {}  # none bundled: every button keeps its label
        folder.mkdir()
        for name, data in (("chat_say.png", b"x"), ("broken.png", b"broken"), ("notes.txt", b"x")):
            (folder / name).write_bytes(data)
        assert set(app._load_button_icons(folder)) == {"chat_say"} and len(app.logger.lines) == 1
        # The backend copies them next to the driver, and takes away those no longer bundled.
        sys.path.insert(0, ROOT)
        import main
        saved = (main.PLUGIN, main.APP, main.UNIT_FILE, main.LISTENER_FILE, main._systemctl, main._install_desktop_entries)
        main.UID, main.GID = os.getuid(), os.getgid()  # the files are made by whoever runs the tests
        try:
            plugin, app_dir = Path(tmp) / "plugin", Path(tmp) / "app"
            for sub in ("driver/bin", "driver/fonts", "driver/icons", "systemd"):
                (plugin / sub).mkdir(parents=True)
            (plugin / "driver/icons/chat_say.png").write_bytes(b"x")
            for unit in ("jarngrip.service", "jarngrip-ayn.service"):
                (plugin / "systemd" / unit).write_text("")
            main.PLUGIN, main.APP = plugin, app_dir
            main.UNIT_FILE = Path(tmp) / "units" / "jarngrip.service"
            main.LISTENER_FILE = main.UNIT_FILE.parent / "jarngrip-ayn.service"
            main._systemctl = lambda *a: True
            main._install_desktop_entries = lambda on: None
            (app_dir / "icons").mkdir(parents=True)
            (app_dir / "icons" / "old.png").write_bytes(b"x")
            assert main._install_runtime() is True
            assert sorted(p.name for p in (app_dir / "icons").iterdir()) == ["chat_say.png"]
            assert main._install_runtime() is False  # nothing changed the second time
        finally:
            (main.PLUGIN, main.APP, main.UNIT_FILE, main.LISTENER_FILE, main._systemctl,
             main._install_desktop_entries) = saved



def test_every_wow_button_has_its_icon_and_every_icon_a_button():
    folder = Path(ROOT) / "driver" / "icons"
    shipped = {p.stem for p in folder.glob("*.png")}
    wanted = {s.picture for s in pad_model.WOW.buttons} - {""}
    assert wanted == shipped
    labels = {s.label: (s.picture, s.tag) for s in pad_model.WOW.buttons}
    assert labels["Map"] == ("map", "") and labels["Sit / stand"] == ("sit_stand", "")
    assert labels["Party 3"] == ("party", "3") and labels["Chat"] == ("chat_say", "")
    radial = next(s for s in pad_model.WOW.buttons if s.radial)
    assert not any(slot.picture for _, slot in radial.radial)  # the chat petals keep their words
    for game in (pad_model.FFXI, pad_model.DESKTOP):
        assert not any(s.picture for s in game.buttons), game.id


def test_wow_buttons_show_their_icons_in_place_of_their_labels():
    pad_draw = painter()
    names = {s.picture for s in pad_model.WOW.buttons} - {""}
    try:
        for page, title in enumerate(pad_model.WOW.titles):
            pad, bridge, clock = make()
            tap(pad, clock, f"tab:{page}")
            buttons = [w for w in pad.widgets if w.kind == "page"]
            pad_draw.BUTTON_ICONS = {name: Anything() for name in names}
            cr = Recorder()
            pad_draw.paint(cr, pad)
            assert cr.masks == len(buttons), title  # one icon a button, Chat's included
            for w in buttons:
                assert w.label not in cr.texts, (title, w.label)
            if title == "Target":
                assert {"1", "2", "3", "4"} <= set(cr.texts)  # the party members' numbers, beside their icon
            pad_draw.BUTTON_ICONS = {}  # missing: the labels come back
            cr = Recorder()
            pad_draw.paint(cr, pad)
            assert cr.masks == 0 and all(w.label in cr.texts or w.wrap for w in buttons), title
        pad, bridge, clock = make()
        pad.apply_config({"game": "ffxi"})
        pad_draw.BUTTON_ICONS = {name: Anything() for name in names}
        cr = Recorder()
        pad_draw.paint(cr, pad)
        assert cr.masks == 0 and "Confirm" in cr.texts  # FFXI keeps its words
    finally:
        pad_draw.BUTTON_ICONS = {}



def test_a_swipe_lights_its_square_and_a_modifier_sent_fades_for_two_seconds():
    pad_draw = painter()
    for theme in pad_model.THEME_IDS:
        pad, bridge, clock = make()
        pad.apply_config({"theme": theme, "number_icons": True})
        x, y = center(pad, "number:slot_5")
        for dx, dy, echo in ((0, -90, True), (-90, 0, True), (0, 90, False)):  # Shift, Ctrl, cancel
            tid = down(pad, clock, "number:slot_5")
            pad.touch_move(tid, x + dx, y + dy, clock.now)
            cr = Recorder()
            pad_draw.paint(cr, pad)
            assert cr.faint == 2, (theme, dx, dy)  # all three squares, the two not swiped toward faint
            pad.touch_up(tid, clock.now)
            clock.now += 0.5
            cr = Recorder()
            pad_draw.paint(cr, pad)
            assert cr.faint == (1 if echo else 0) and pad.fading() == echo, (theme, dx, dy)  # sent: fading
            clock.now += pad_model.SWIPE_FADE_S
            cr = Recorder()
            pad_draw.paint(cr, pad)
            assert cr.faint == 0 and not pad.fading(), (theme, dx, dy)  # gone after two seconds
        pad.apply_config({"number_icons": False})  # without icons: the fan, no squares, nothing fading
        tid = down(pad, clock, "number:slot_5")
        pad.touch_move(tid, x, y - 90, clock.now)
        cr = Recorder()
        pad_draw.paint(cr, pad)
        assert cr.faint == 0
        pad.touch_up(tid, clock.now)
        assert not pad.fading()



def test_swipe_words_and_fans_follow_the_new_directions():
    import math

    pad_draw = painter()
    # The fans open the way the finger goes: the second modifier's left, cancel's down, a target's confirm right.
    assert pad_draw.FAN_DIRECTIONS == {"up": -math.pi / 2, "down": math.pi, "cancel": math.pi / 2, "confirm": 0.0}
    with tempfile.TemporaryDirectory() as tmp:
        call = backend(tmp)
        folder = Path(call("list_icons")["folder"])
        for name in ("5-left-frost.png", "6-down-fire.png", "7-ctrl-nova.png"):
            (folder / name).write_bytes(b"")
        icons = call("fill_icons")["config"]["icons"]
        # "left" names the second modifier's swipe; "down" still does, as pictures were named before.
        assert icons == {"slot_5:down": "5-left-frost.png", "slot_6:down": "6-down-fire.png",
                         "slot_7:down": "7-ctrl-nova.png"}


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
