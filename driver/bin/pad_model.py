# SPDX-License-Identifier: GPL-3.0-only
"""JarnGrip model: what is on the bottom screen and what each touch does.

No GTK, cairo or uinput in here, so it runs and is tested anywhere. The layout and the input rules follow the
second-screen pad of AYN-Thor-WoW-Launcher (https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher):

- A page button is a real key: finger down presses it, finger up releases it, and several can be held at once.
- A number button sends its key when the finger lifts, which lets a swipe change it: up adds Shift, down adds Ctrl,
  and left cancels it.
- The trackpad's click buttons hold while pressed, so they drag; a double tap keeps one held until it is tapped again.
- The trackpad view's Shift, Ctrl and Alt are armed by a tap (they let go after the next click), locked by a double
  tap, and cleared by a tap.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from engine import BTN_LEFT, BTN_RIGHT, HI_RES_NOTCH, SCREEN_HEIGHT, SCREEN_WIDTH, STALE_CONTACT_S

W, H = SCREEN_WIDTH, SCREEN_HEIGHT

KEY_LEFTSHIFT, KEY_LEFTCTRL, KEY_LEFTALT = 42, 29, 56
MODIFIERS = (("shift", "Shift", KEY_LEFTSHIFT), ("ctrl", "Ctrl", KEY_LEFTCTRL), ("alt", "Alt", KEY_LEFTALT))
MOD_CODES = {name: code for name, _, code in MODIFIERS}

DOUBLE_TAP_S = 0.35
# A press shorter than this is stretched: two touch frames read in one batch would otherwise be a zero-length key press.
MIN_PRESS_S = 0.03
# The controller sometimes loses a finger-lift (engine.STALE_CONTACT_S). A button whose finger has reported nothing for
# this long is let go, so a lost lift cannot leave a key held. Longer than the trackpad's limit: buttons are held on purpose.
BUTTON_STALE_S = STALE_CONTACT_S * 3
FLASH_S = 0.12              # a tapped button stays lit this long, so a quick tap is still seen
STRIP_PX_PER_NOTCH = 40.0   # finger travel on the scroll strip per wheel notch
SWIPE_PX = 50.0             # finger travel on a number button that makes a press a swipe (about 3 mm)
SWIPE_MODS = {"shift": (KEY_LEFTSHIFT,), "ctrl": (KEY_LEFTCTRL,)}

# Layout, in bottom-screen pixels.
MARGIN = 16.0
GAP = 12.0
PANEL_PAD = 8.0
HEADER_Y, HEADER_H = 8.0, 108.0
BODY_Y = HEADER_Y + HEADER_H + 8.0
BODY_H = H - BODY_Y - 8.0
MODE_W = 104.0
STATUS_W = 150.0            # the clock and battery, between the page tabs and the mode buttons
SINGLE_COLUMN_MAX = 8       # a page with more buttons than this splits into two columns
NUMBER_TALL = 1.1           # a number key is at most this many times as tall as it is wide
KEY_ROW_H = 140.0           # five rows low enough for thumbs; the space above them is a small trackpad
MODES = ("settings", "trackpad", "keyboard")
THEMES = (("classic", "Classic"), ("charcoal", "Charcoal"), ("dark", "Dark"), ("glass", "Game Glass"))  # see pad_draw.py
OLD_THEME_IDS = {"steamos": "charcoal", "oled": "dark"}  # earlier names of themes, still accepted from a config
THEME_IDS = tuple(theme for theme, _ in THEMES)
THEME_Y, THEME_H = 590.0, 112.0  # the theme buttons on the settings view

# Label heights in pixels.
TAB_TEXT, MOD_TEXT, MOUSE_TEXT, PAGE_TEXT, PAGE_SPLIT_TEXT, NUMBER_TEXT = 34, 36, 40, 40, 34, 68
KEY_TEXT, KEY_WORD_TEXT = 52, 34  # a one-character key, and a key with a word on it


@dataclass(frozen=True)
class Slot:
    """A pad button: its config id, what it shows and what it sends by default."""
    id: str
    label: str
    key: int
    mods: tuple = ()


def _page(label: str, key: int, *mods: int) -> Slot:
    return Slot(re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_"), label, key, mods)


# WoW's default bindings, as Linux key codes.
PAGES = (
    ("Interface", (
        _page("Character", 46), _page("Spellbook", 25), _page("Talents", 49), _page("Quest Log", 38),
        _page("Map", 50), _page("Social", 24), _page("Guild", 36), _page("Group Finder", 23),
        _page("Achievements", 21), _page("Professions", 37), _page("Bags", 48), _page("System", 1),
    )),
    ("Target", (
        _page("Self", 59), _page("Party 1", 60), _page("Party 2", 61), _page("Party 3", 62), _page("Party 4", 63),
        _page("Next enemy", 15), _page("Previous enemy", 15, KEY_LEFTSHIFT),
    )),
    ("Utility", (
        _page("Sheathe weapons", 44), _page("Auto-run", 69), _page("Walk / run", 98), _page("Sit / stand", 45),
        _page("Hide UI", 44, KEY_LEFTALT), _page("Enemy nameplates", 47), _page("Friendly nameplates", 47, KEY_LEFTSHIFT),
        _page("Chat page up", 104), _page("Chat page down", 109), _page("Screenshot", 99),
    )),
)
PAGE_TITLES = tuple(title for title, _ in PAGES)

# Action bar 1, slots 1 to 12.
NUMBER_SLOTS = tuple(
    Slot(f"slot_{i + 1}", label, code)
    for i, (label, code) in enumerate(zip(("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="), range(2, 14)))
)


def combo_for(slot: Slot, bindings: dict) -> tuple:
    """What a button sends as (key, modifiers): its default, or the binding saved for its id.

    A number replaces the key and keeps the button's own modifiers (this is what the Decky panel writes). Text such
    as "shift+47" or "33" replaces the whole combination."""
    value = bindings.get(slot.id)
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 248:
        return value, slot.mods
    if isinstance(value, str):
        *names, key = [part.strip().lower() for part in value.split("+")]
        if key.isdigit() and 0 < int(key) < 248 and all(name in MOD_CODES for name in names):
            return int(key), tuple(code for name, code in MOD_CODES.items() if name in names)
    return slot.key, slot.mods


@dataclass(frozen=True)
class KeySpec:
    """One key of the on-screen keyboard."""
    label: str = ""
    shifted: str = ""
    code: int = 0
    weight: float = 1.0
    letter: bool = False
    action: str = "input"       # input, plain (never shifted), shift, symbols
    send_shifted: bool = False  # symbol keys that type the shifted character
    icon: str = ""


def _letters(text: str, first: int) -> list:
    return [KeySpec(ch, ch.upper(), first + i, letter=True) for i, ch in enumerate(text)]


def _sym(label: str, code: int, shifted: bool = False) -> KeySpec:
    return KeySpec(label, code=code, send_shifted=shifted)


# (keys, indent) per row; the indent is in key widths on each side.
KEYBOARD_MAIN = (
    ([KeySpec(ch, sh, 2 + i) for i, (ch, sh) in enumerate(zip("1234567890", "!@#$%^&*()"))], 0.0),
    (_letters("qwertyuiop", 16), 0.0),
    (_letters("asdfghjkl", 30), 0.5),
    ([KeySpec("Shift", weight=1.5, action="shift")] + _letters("zxcvbnm", 44)
     + [KeySpec(code=14, weight=1.5, action="plain", icon="backspace")], 0.0),
    ([KeySpec("?123", weight=1.5, action="symbols"), KeySpec(",", "<", 51), KeySpec("/", "?", 53),
      KeySpec("Space", code=57, weight=4.0, action="plain"), KeySpec(".", ">", 52),
      KeySpec("Enter", code=28, weight=1.5, action="plain")], 0.0),
)
KEYBOARD_SYMBOLS = (
    ([_sym(ch, 2 + i, True) for i, ch in enumerate("!@#$%^&*()")]
     + [KeySpec(code=14, weight=1.75, action="plain", icon="backspace")], 0.0),
    ([_sym("-", 12), _sym("_", 12, True), _sym("=", 13), _sym("+", 13, True), _sym("[", 26), _sym("]", 27),
      _sym("{", 26, True), _sym("}", 27, True), _sym("\\", 43), _sym("|", 43, True)], 0.0),
    ([_sym(";", 39), _sym(":", 39, True), _sym("'", 40), _sym('"', 40, True), _sym("`", 41), _sym("~", 41, True),
      _sym("<", 51, True), _sym(">", 52, True), _sym("/", 53), _sym("?", 53, True),
      KeySpec("Enter", code=28, weight=1.75, action="plain")], 0.0),
    ([KeySpec("ABC", weight=1.5, action="symbols"), KeySpec("Space", code=57, weight=6.0, action="plain"),
      KeySpec(code=105, weight=1.25, action="plain", icon="left"), KeySpec(code=108, weight=1.25, action="plain", icon="down"),
      KeySpec(code=103, weight=1.25, action="plain", icon="up"), KeySpec(code=106, weight=1.25, action="plain", icon="right")], 0.0),
)


@dataclass
class Widget:
    """Something on the screen that a finger can land on."""
    id: str
    kind: str   # tab, mode, status, page, number, mod, mouse, surface, strip, key, theme, unstick, close
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    data: Any = None
    size: float = 32.0  # label height in pixels
    wrap: bool = False

    def contains(self, x: float, y: float, slack: float = 0.0) -> bool:
        return self.x - slack <= x <= self.x + self.w + slack and self.y - slack <= y <= self.y + self.h + slack


def _row(widgets: list, items: list, x: float, y: float, w: float, h: float, make: Callable) -> None:
    """Lay items out left to right in equal cells; make(item, x, y, w, h) returns each widget."""
    cell = (w - (len(items) - 1) * GAP) / len(items)
    for i, item in enumerate(items):
        widgets.append(make(item, x + i * (cell + GAP), y, cell, h))


def _modifier_row(widgets: list, x: float, y: float, w: float, h: float) -> None:
    _row(widgets, list(MODIFIERS), x, y, w, h,
         lambda m, bx, by, bw, bh: Widget(f"mod:{m[0]}", "mod", bx, by, bw, bh, m[1], data=m[2], size=MOD_TEXT))


def build_layout(view: str, page: int, symbols: bool = False) -> tuple:
    """(panels, widgets) for a view. Panels are (x, y, w, h, strong): the faint gold backing behind a group."""
    panels: list = []
    widgets: list = []
    full_w = W - 2 * MARGIN

    # Header: the page tabs share the left, the settings / trackpad / keyboard buttons keep the right.
    panels.append((MARGIN, HEADER_Y, full_w, HEADER_H, False))
    hx, hy, hh = MARGIN + PANEL_PAD, HEADER_Y + PANEL_PAD, HEADER_H - 2 * PANEL_PAD
    modes_w = len(MODES) * MODE_W + (len(MODES) - 1) * GAP
    status_x = W - MARGIN - PANEL_PAD - modes_w - GAP - STATUS_W
    widgets.append(Widget("status", "status", status_x, hy, STATUS_W, hh))
    _row(widgets, list(enumerate(PAGE_TITLES)), hx, hy, status_x - GAP - hx, hh,
         lambda t, bx, by, bw, bh: Widget(f"tab:{t[0]}", "tab", bx, by, bw, bh, t[1], data=t[0], size=TAB_TEXT))
    _row(widgets, list(MODES), W - MARGIN - PANEL_PAD - modes_w, hy, modes_w, hh,
         lambda m, bx, by, bw, bh: Widget(f"mode:{m}", "mode", bx, by, bw, bh, data=m))

    if view == "trackpad":
        click_h, mod_h = 128.0, 88.0
        click_y = BODY_Y + BODY_H - click_h
        mod_y = click_y - GAP - mod_h
        surface_h = mod_y - GAP - BODY_Y
        # The strip comes first: it lies on the surface's right edge and must win the hit test.
        widgets.append(Widget("strip", "strip", W - MARGIN - 8 - 64, BODY_Y + 8, 64, surface_h - 16))
        widgets.append(Widget("surface", "surface", MARGIN, BODY_Y, full_w, surface_h))
        _modifier_row(widgets, MARGIN, mod_y, full_w, mod_h)
        _row(widgets, [("left", "Left click", BTN_LEFT), ("right", "Right click", BTN_RIGHT)], MARGIN, click_y, full_w, click_h,
             lambda b, bx, by, bw, bh: Widget(f"mouse:{b[0]}", "mouse", bx, by, bw, bh, b[1], data=b[2], size=MOUSE_TEXT))
    elif view == "keyboard":
        rows = KEYBOARD_SYMBOLS if symbols else KEYBOARD_MAIN
        # Both pages take the same height (the symbols page has fewer, taller rows), so the keys never jump.
        kb_h = len(KEYBOARD_MAIN) * KEY_ROW_H
        top = BODY_Y + BODY_H - kb_h
        row_h = kb_h / len(rows)
        widgets.append(Widget("surface", "surface", MARGIN, BODY_Y, full_w, top - GAP / 2 - BODY_Y))
        for r, (keys, indent) in enumerate(rows):
            unit = (full_w - (len(keys) - 1) * GAP) / (sum(k.weight for k in keys) + 2 * indent)
            x = MARGIN + indent * unit
            for c, spec in enumerate(keys):
                kw = spec.weight * unit
                widgets.append(Widget(f"key:{int(symbols)}:{r}:{c}", "key", x, top + r * row_h + GAP / 2, kw,
                                      row_h - GAP, spec.label, data=spec))
                x += kw + GAP
    elif view == "settings":
        _row(widgets, list(THEMES), MARGIN + 200, THEME_Y, full_w - 400, THEME_H,
             lambda t, bx, by, bw, bh: Widget(f"theme:{t[0]}", "theme", bx, by, bw, bh, t[1], data=t[0], size=MOD_TEXT))
        _row(widgets, [("unstick", "Unstick keys"), ("close", "Close pad")], MARGIN + 200, BODY_Y + BODY_H - 136,
             full_w - 400, 128, lambda b, bx, by, bw, bh: Widget(b[0], b[0], bx, by, bw, bh, b[1], size=MOUSE_TEXT))
    else:
        half_w = (full_w - GAP) / 2
        slots = PAGES[page][1]
        split = len(slots) > SINGLE_COLUMN_MAX
        columns = [slots[: (len(slots) + 1) // 2], slots[(len(slots) + 1) // 2:]] if split else [slots]
        col_w = (half_w - (len(columns) - 1) * GAP) / len(columns)
        for ci, column in enumerate(columns):
            px = MARGIN + ci * (col_w + GAP)
            panels.append((px, BODY_Y, col_w, BODY_H, False))
            bh = (BODY_H - 2 * PANEL_PAD - (len(column) - 1) * GAP) / len(column)
            for ri, slot in enumerate(column):
                widgets.append(Widget(f"page:{slot.id}", "page", px + PANEL_PAD, BODY_Y + PANEL_PAD + ri * (bh + GAP),
                                      col_w - 2 * PANEL_PAD, bh, slot.label, data=slot,
                                      size=PAGE_SPLIT_TEXT if split else PAGE_TEXT, wrap=split))
        # Right half: the number block, centered top to bottom. Swipes give it Shift and Ctrl, so it needs no modifier
        # row.
        rx = MARGIN + half_w + GAP
        key_w = (half_w - 2 * PANEL_PAD - 2 * GAP) / 3
        row_h = min((BODY_H - 2 * PANEL_PAD - 3 * GAP) / 4, key_w * NUMBER_TALL)
        num_h = 4 * row_h + 3 * GAP + 2 * PANEL_PAD
        num_y = BODY_Y + (BODY_H - num_h) / 2
        panels.append((rx, num_y, half_w, num_h, True))
        for r in range(4):
            _row(widgets, list(NUMBER_SLOTS[r * 3: r * 3 + 3]), rx + PANEL_PAD, num_y + PANEL_PAD + r * (row_h + GAP),
                 half_w - 2 * PANEL_PAD, row_h,
                 lambda s, bx, by, bw, bh: Widget(f"number:{s.id}", "number", bx, by, bw, bh, s.label, data=s, size=NUMBER_TEXT))
    return panels, widgets


def swipe_of(dx: float, dy: float) -> str | None:
    """What a finger's travel on a number button asks for: "shift" (up), "ctrl" (down), "cancel" (left), or None for a
    plain press. Right counts as a plain press: there is no room for a fan right of the right-hand column."""
    if max(abs(dx), abs(dy)) <= SWIPE_PX:
        return None
    if abs(dy) >= abs(dx):
        return "shift" if dy < 0 else "ctrl"
    return "cancel" if dx < 0 else None


@dataclass
class Touch:
    widget: Widget | None   # where the finger landed; it keeps that owner until it lifts
    seen: float             # kernel time of its last report
    x: float
    y: float
    release: Callable | None = None  # what lifting the finger, or the button going away, lets go of
    commit: Callable | None = None   # what lifting the finger sends (a number button); dropped if the button goes away
    start_x: float = 0.0
    start_y: float = 0.0


@dataclass
class MouseButton:
    locked: bool = False
    last_down: float = -10.0


class PadController:
    """Pad state and touch handling. The bridge is engine.UInputBridge (or anything with key, mouse_button and
    emit_scroll); the gesture engine drives the pointer for touches on the trackpad surface."""

    def __init__(self, bridge, gesture, on_change: Callable = lambda: None, on_close: Callable = lambda: None,
                 haptic: Callable = lambda pattern: None, on_theme: Callable = lambda theme: None,
                 clock: Callable = time.monotonic, sleep: Callable = time.sleep, later: Callable | None = None) -> None:
        self.bridge = bridge
        self.gesture = gesture
        self.on_change = on_change  # something visible changed: redraw
        self.on_close = on_close    # "Close pad" was tapped
        self.haptic = haptic        # haptic(pattern): "press", "tick" or "lock" (see haptics.PATTERNS)
        self.on_theme = on_theme    # a theme was picked on the settings view: keep it
        self._clock = clock
        self._sleep = sleep
        # later(delay, job) runs job after delay seconds without holding up the touch thread meanwhile; the app runs
        # it under its touch lock. Without one, the wait is slept through (tests).
        self._later = later or (lambda delay, job: (self._sleep(delay), job()))

        self.view = "pad"   # pad, trackpad, keyboard, settings
        self.page = 0
        self.kb_symbols = False
        self.kb_shift = "off"   # off, on (next key only), caps
        self.bindings: dict = {}
        self.tap_to_click = True
        self.theme = THEME_IDS[0]
        self.info_lines: list = []  # shown on the settings view

        self.touches: dict = {}         # tracking id -> Touch
        self.pressed: set = set()       # ids of the widgets with a finger on them
        self.flash_until: dict = {}     # widget id -> clock time until which it still draws as pressed
        self.key_typed: dict = {}       # keyboard widget id -> the character it typed, for the preview over the finger
        self._expired: set = set()      # ids dropped as stale: the kernel may reuse them for a new finger
        self.key_refs: dict = {}        # key code -> how many holders want it down
        self.held_mods: dict = {}       # modifier code -> when it was armed
        self.locked_mods: set = set()
        self.mouse = {BTN_LEFT: MouseButton(), BTN_RIGHT: MouseButton()}
        self.strip_rest = 0.0
        self.last_touch: tuple | None = None    # (x, y, widget id) of the newest touch, for the settings view
        self.swipes: dict = {}          # number widget id -> "shift", "ctrl" or "cancel" while a finger swipes on it
        self.status_info: tuple | None = None   # (clock text, battery percent or None, charging) for the header
        # Burn-in protection, set by the app before each paint: how far everything is shifted, how bright it is,
        # and how visible the trackpad hints still are.
        self.shift = (0.0, 0.0)
        self.brightness = 1.0
        self.hint_alpha = 1.0
        self.backdrop: tuple | None = None  # (sharp, blurred) picture surfaces for the Game Glass theme, set by the app
        self.panels: list = []
        self.widgets: list = []
        self._relayout()

    # ------------------------------------------------------------------ configuration

    def apply_config(self, cfg: dict) -> None:
        bindings = cfg.get("bindings")
        self.bindings = dict(bindings) if isinstance(bindings, dict) else {}
        self.tap_to_click = bool(cfg.get("tap_to_click", True))
        theme = OLD_THEME_IDS.get(cfg.get("theme"), cfg.get("theme"))
        if theme in THEME_IDS:
            self.theme = theme

        def number(key: str, default: float) -> float:  # a hand-edited config must not stop the pad
            try:
                return float(cfg.get(key, default))
            except (TypeError, ValueError):
                return default

        self.gesture.set_settings(sensitivity=number("sensitivity", 1.0), glide=bool(cfg.get("glide", False)),
                                  scroll_speed=number("scroll_speed", 3), two_finger_right_click=True)
        self._sync_tap_clicks()

    def set_page_by_title(self, title: str) -> None:
        if title in PAGE_TITLES:
            self.page = PAGE_TITLES.index(title)
            self._relayout()

    # ------------------------------------------------------------------ what the painter asks

    def lit(self, widget: Widget) -> bool:
        return widget.id in self.pressed or self._clock() < self.flash_until.get(widget.id, 0.0)

    def glows(self, widget: Widget) -> bool:
        """True for the buttons an armed modifier will apply to: the click buttons."""
        return bool(self.held_mods) and widget.kind == "mouse"

    def key_label(self, spec: KeySpec) -> str:
        if spec.action == "shift":
            return "Caps" if self.kb_shift == "caps" else "Shift"
        shifted = self.kb_shift != "off" if spec.letter else self.kb_shift == "on"
        return spec.shifted if shifted and spec.shifted else spec.label

    # ------------------------------------------------------------------ key output

    def _press(self, code: int) -> None:
        count = self.key_refs.get(code, 0)
        self.key_refs[code] = count + 1
        if count == 0:
            self.bridge.key(code, True)

    def _release(self, code: int) -> None:
        count = self.key_refs.get(code, 0)
        if count > 1:
            self.key_refs[code] = count - 1
            return
        self.key_refs.pop(code, None)
        if count == 1:
            self.bridge.key(code, False)

    def _after_min(self, pressed_at: float, job: Callable) -> None:
        """Run job (a key-up) once the press has lasted MIN_PRESS_S: now, or later if it was shorter. The touch thread
        never waits for it, so a quick tap does not delay the next finger."""
        wait = MIN_PRESS_S - (self._clock() - pressed_at)
        if wait > 0:
            self._later(wait, job)
        else:
            job()

    # ------------------------------------------------------------------ modifiers

    def _tap_modifier(self, code: int) -> None:
        now = self._clock()
        if code not in self.held_mods:
            self.held_mods[code] = now
            self._press(code)
        elif code not in self.locked_mods and now - self.held_mods[code] <= DOUBLE_TAP_S:
            self.locked_mods.add(code)
        else:
            self._drop_modifier(code)

    def _drop_modifier(self, code: int) -> None:
        del self.held_mods[code]
        self.locked_mods.discard(code)
        self._release(code)

    def _release_armed_modifiers(self) -> None:
        """A click was used: the armed modifiers let go. Locked ones stay down."""
        for code in [c for c in self.held_mods if c not in self.locked_mods]:
            self._drop_modifier(code)

    def _release_all_modifiers(self) -> None:
        for code in list(self.held_mods):
            self._drop_modifier(code)

    # ------------------------------------------------------------------ buttons

    def _press_slot(self, slot: Slot, extra: tuple = ()) -> Callable:
        """Press a button's combination, plus extra modifiers (a swipe's). Returns what lets it go."""
        key, mods = combo_for(slot, self.bindings)
        mods = extra + tuple(code for code in mods if code not in extra)
        for code in mods:
            self._press(code)
        self._press(key)
        pressed_at = self._clock()

        def up() -> None:
            self._release(key)
            for code in reversed(mods):
                self._release(code)

        return lambda: self._after_min(pressed_at, up)

    def _mouse_down(self, code: int) -> Callable | None:
        button = self.mouse[code]
        now = self._clock()
        if button.locked:
            button.locked = False
            self.bridge.mouse_button(code, False)
            self._sync_tap_clicks()
            return None
        self.bridge.mouse_button(code, True)
        lock = now - button.last_down <= DOUBLE_TAP_S
        button.last_down = now

        def up() -> None:
            self.bridge.mouse_button(code, False)
            self._release_armed_modifiers()

        def release() -> None:
            if lock:
                button.locked = True  # second tap of a double tap: stays pressed until it is tapped again
                self._sync_tap_clicks()
                self.haptic("lock")
                return
            self._after_min(now, up)

        return release

    def _commit_number(self, widget: Widget, touch: Touch) -> None:
        """A number button's finger lifted: send its key, with the modifier its swipe chose, or nothing for a cancel."""
        swipe = swipe_of(touch.x - touch.start_x, touch.y - touch.start_y)
        if swipe == "cancel":
            self.flash_until.pop(widget.id, None)  # nothing was sent: do not light it up
            return
        self._press_slot(widget.data, SWIPE_MODS.get(swipe, ()))()

    def unstick(self) -> None:
        """Make the game let go of Shift, Ctrl and Alt. A game can miss a key-up, for instance when Steam's overlay
        opens in the middle of a press (Shift+Tab opens it), and then acts as if the key were still held. A fresh press
        and release of each modifier puts it right. Modifiers the pad itself holds are let go first."""
        self._release_all_modifiers()
        for code in MOD_CODES.values():
            if not self.key_refs.get(code):  # a page button still held keeps its own
                self.bridge.key(code, True)
                self.bridge.key(code, False)

    def _sync_tap_clicks(self) -> None:
        # A locked button must survive quick trackpad touches, which would otherwise click (and so release it).
        self.gesture.tap_to_click = self.tap_to_click and not any(b.locked for b in self.mouse.values())

    def _key_down(self, spec: KeySpec) -> Callable | None:
        if spec.action == "shift":
            self.kb_shift = {"off": "on", "on": "caps", "caps": "off"}[self.kb_shift]
            return None
        if spec.action == "symbols":
            self.kb_symbols = not self.kb_symbols
            self._relayout()
            return None
        code = spec.code
        shift = spec.action == "input" and (
            spec.send_shifted or self.kb_shift == "on" or (self.kb_shift == "caps" and spec.letter))
        # Shift wraps only the key-down, so a fast next key that overlaps this one is not shifted too.
        if shift:
            self._press(KEY_LEFTSHIFT)
        self._press(code)
        if shift:
            self._release(KEY_LEFTSHIFT)
        if spec.action == "input" and self.kb_shift == "on":
            self.kb_shift = "off"
        pressed_at = self._clock()

        return lambda: self._after_min(pressed_at, lambda: self._release(code))

    # ------------------------------------------------------------------ views

    def _relayout(self) -> None:
        self.panels, self.widgets = build_layout(self.view, self.page, self.kb_symbols)

    def _set_view(self, view: str, page: int | None = None) -> None:
        """Show a view. Everything a finger was holding is let go first: its button is about to disappear."""
        self._release_touches()
        if view != self.view:
            self._release_all_modifiers()
            for code, button in self.mouse.items():
                if button.locked:
                    button.locked = False
                    self.bridge.mouse_button(code, False)
            self._sync_tap_clicks()
            self.kb_shift = "off"
        self.view = view
        if page is not None:
            self.page = page
        self._relayout()

    def _release_touches(self) -> None:
        """Let go of what every finger holds, and send nothing a lift would have sent. The fingers stay known, but
        own nothing until they lift."""
        for touch in self.touches.values():
            if touch.release:
                touch.release()
            touch.release = touch.commit = None
            touch.widget = None
        self.pressed.clear()
        self.swipes.clear()
        self.gesture.reset_all()

    def widget_at(self, x: float, y: float) -> Widget | None:
        for widget in self.widgets:
            if widget.contains(x, y):
                return widget
        for widget in self.widgets:  # the gap between two buttons belongs to the nearer one
            if widget.kind not in ("surface", "strip") and widget.contains(x, y, GAP / 2):
                return widget
        return None

    # ------------------------------------------------------------------ touches

    def touch_down(self, tid: int, x: float, y: float, ts: float) -> None:
        self._expired.discard(tid)
        widget = self.widget_at(x, y)
        self.last_touch = (x, y, widget.id if widget else "")
        touch = Touch(widget, ts, x, y, start_x=x, start_y=y)
        self.touches[tid] = touch
        if widget is None or widget.kind == "status":
            touch.widget = None
            if self.view == "settings":
                self.on_change()
            return
        kind = widget.kind
        if kind == "surface":
            self.gesture.touch_down(tid, x, y, ts)
            return
        if kind in ("tab", "mode", "theme"):
            self.haptic("tick")
        elif kind not in ("strip", "mod"):
            self.haptic("press")
        if kind == "tab":
            self._set_view("pad", widget.data)
        elif kind == "mode":
            self._set_view("pad" if self.view == widget.data else widget.data)
        elif kind == "theme":
            if widget.data != self.theme:
                self.theme = widget.data
                self.on_theme(widget.data)
        else:
            if widget.id in self.pressed:
                # Another contact already holds this button. A second finger cannot fit on it, so the first is a lost
                # lift: end it and let this finger take over.
                for other_tid, other in list(self.touches.items()):
                    if other is not touch and other.widget is widget:
                        self._end_touch(other_tid, inside=False)
                        self._expired.add(other_tid)
            self.pressed.add(widget.id)
            if kind == "page":
                touch.release = self._press_slot(widget.data)
            elif kind == "number":
                touch.commit = lambda: self._commit_number(widget, touch)
            elif kind == "mod":
                was_locked = widget.data in self.locked_mods
                self._tap_modifier(widget.data)
                self.haptic("lock" if widget.data in self.locked_mods and not was_locked else "press")
            elif kind == "mouse":
                touch.release = self._mouse_down(widget.data)
            elif kind == "key":
                if widget.data.action == "input":
                    self.key_typed[widget.id] = self.key_label(widget.data)  # before a one-shot Shift lets go
                touch.release = self._key_down(widget.data)
            elif kind == "strip":
                self.strip_rest = 0.0
        self.on_change()

    def touch_move(self, tid: int, x: float, y: float, ts: float) -> None:
        touch = self.touches.get(tid)
        if touch is None:
            if tid in self._expired:
                # A new finger landed in the slot of a contact dropped as stale: the kernel keeps the old id and
                # reports movement. It moves, so it is a real finger.
                self.touch_down(tid, x, y, ts)
            return
        dy = y - touch.y
        touch.seen, touch.x, touch.y = ts, x, y
        if touch.widget is None:
            return
        if touch.widget.kind == "surface":
            self.gesture.touch_move(tid, x, y, ts)
        elif touch.widget.kind == "number":
            swipe = swipe_of(x - touch.start_x, y - touch.start_y)
            if swipe != self.swipes.get(touch.widget.id):
                if swipe:
                    self.swipes[touch.widget.id] = swipe
                else:
                    self.swipes.pop(touch.widget.id, None)
                self.haptic("tick")
                self.on_change()
        elif touch.widget.kind == "strip":
            # Sliding down scrolls down, which is a negative wheel value.
            self.strip_rest -= dy * HI_RES_NOTCH / STRIP_PX_PER_NOTCH
            step = int(self.strip_rest)
            if step:
                self.strip_rest -= step
                self.bridge.emit_scroll(0, step)

    def touch_up(self, tid: int, ts: float) -> None:
        self._expired.discard(tid)
        self._end_touch(tid, inside=True, ts=ts)

    def _end_touch(self, tid: int, inside: bool, ts: float = 0.0) -> None:
        touch = self.touches.pop(tid, None)
        if touch is None or touch.widget is None:
            return
        widget = touch.widget
        if widget.kind == "surface":
            self.gesture.touch_up(tid, ts or touch.seen)
            return
        self.pressed.discard(widget.id)
        self.swipes.pop(widget.id, None)
        self.flash_until[widget.id] = self._clock() + FLASH_S
        if touch.commit:
            touch.commit()
        if touch.release:
            touch.release()
        if widget.kind in ("close", "unstick") and inside and widget.contains(touch.x, touch.y, GAP / 2):
            if widget.kind == "close":
                self.on_close()
            else:
                self.unstick()
        self.on_change()

    def all_lifted(self, ts: float) -> None:
        """The digitizer reports no contact at all: whatever is still tracked here has lifted."""
        for tid in list(self.touches):
            self._end_touch(tid, inside=False, ts=ts)
        self._expired.clear()
        self.gesture.reset_all()

    def expire(self, now: float) -> None:
        """Drop contacts that have gone silent (a lost finger-lift). now is on the kernel's event clock."""
        self.gesture.expire_stale(now)
        for tid, touch in list(self.touches.items()):
            if touch.widget is not None and touch.widget.kind != "surface" and now - touch.seen > BUTTON_STALE_S:
                self._end_touch(tid, inside=False, ts=now)
                self._expired.add(tid)

    def release_everything(self) -> None:
        """Let go of every key and button, modifiers included. For a discarded touch state and for shutdown."""
        self._release_touches()
        self.touches.clear()
        self._expired.clear()
        self._release_all_modifiers()
        for code, button in self.mouse.items():
            button.locked = False
        self._sync_tap_clicks()
        self.bridge.release_all()
        self.key_refs.clear()
        self.on_change()
