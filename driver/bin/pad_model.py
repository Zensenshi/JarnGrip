# SPDX-License-Identifier: GPL-3.0-only
"""JarnGrip model: what is on the bottom screen and what each touch does.

No GTK, cairo or uinput in here, so it runs and is tested anywhere. The layout and the input rules follow the
second-screen pad of AYN-Thor-WoW-Launcher (https://github.com/wyattabuntjer/AYN-Thor-WoW-Launcher):

- A page button is a real key: finger down presses it, finger up releases it, and several can be held at once. A few
  of FFXI's send one keystroke per touch instead (the macro sets), and its party targets press Enter after a swipe right.
  So do the Desktop shortcuts that must not repeat while a thumb rests on them, such as Close tab, but at once.
- A number button sends its key when the finger lifts, which lets a swipe change it: up and left add the game's two
  modifiers (Shift and Ctrl for WoW, Ctrl and Alt for FFXI's two macro bars), and down cancels it.
- The trackpad's click buttons hold while pressed, so they drag; a double tap keeps one held until it is tapped again.
- The trackpad view's Shift, Ctrl and Alt are armed by a tap (they let go after the next click), locked by a double
  tap, and cleared by a tap.
- The round Chat button opens a radial of chat channels, which blooms out of its middle. Lifting on a slice opens that
  channel's chat box and shows the keyboard; the slice at the bottom, or lifting in the middle, cancels. A tap leaves
  the radial open for the next finger, which chooses a slice or, landing anywhere else, closes it. FFXI's slices are
  its own chat keys. WoW has no key per channel, so its slices type the channel's command ("/g "), but never Enter:
  nothing is said until the player sends it.
- The Desktop profile, for everything that is not a game, has no number block: its pages take the whole width, two
  columns each. Its keyboard has F1 to F12, Super and the arrows in place of its small trackpad, and its trackpad Back,
  Copy, Paste and Forward in place of the modifiers, and pinch to zoom.
- With number pad icons on, the number keys are square and show the player's own pictures, like a stream deck: one for
  the tap and one for each swipe. A swipe opens squares around the key in place of the fan, with their icons: the first
  modifier's above it, the second's left of it, cancel's below, the one swiped toward lit. A modifier's square fades
  for SWIPE_FADE_S after the key is sent. Only the drawing changes: the keys send what they always did.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, replace
from typing import Any, Callable

from engine import BTN_LEFT, BTN_RIGHT, HI_RES_NOTCH, SCREEN_HEIGHT, SCREEN_WIDTH, STALE_CONTACT_S

W, H = SCREEN_WIDTH, SCREEN_HEIGHT

KEY_LEFTSHIFT, KEY_LEFTCTRL, KEY_LEFTALT = 42, 29, 56
KEY_ENTER = 28
KEY_LEFT, KEY_RIGHT = 105, 106
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
# A one-keystroke button (Slot.tap) holds its modifiers this long before the key, then the key this long, then lets the
# modifiers go after as long again. FFXI reads the keyboard once a frame: a Ctrl and an Up that land in the same frame
# are the camera's Up, not a change of macro set. Emulated on the Thor, its frames run long and uneven, so 0.1 s of Ctrl
# before the Up still lost most taps; these leave several slow frames between each step.
MOD_LEAD_S = 0.3
TAP_HOLD_S = 0.15
CONFIRM_GAP_S = 0.1         # after a target button lets go, the wait before its swipe's Enter (Slot.confirm)
# A chat command (Slot.text) is typed a key at a time: each held this long, with this long between them, and longer
# after the first, the "/" that opens WoW's chat box, so the box is open before the letters arrive.
TYPE_HOLD_S = 0.03
TYPE_GAP_S = 0.03
TYPE_OPEN_S = 0.12
# The Chat button's radial: eight slices, clockwise from the right as screen angles run, around a hub in the middle of
# the round button. The slices reach as far as the screen leaves room for. The bottom slice is always Cancel. The slice
# under the finger is the one chosen, but a finger that landed on the button chooses nothing until it has moved
# RADIAL_PX, so that a tap opens the radial, wherever on the button it lands.
RADIAL_DIRECTIONS = ("right", "down_right", "down", "down_left", "left", "up_left", "up", "up_right")
RADIAL_CANCEL = "down"
RADIAL_PX = 60.0
RADIAL_HUB = 80.0           # the hub's radius: lifting in it chooses nothing
RADIAL_REACH = 320.0        # a slice's outer radius, where the screen leaves room
RADIAL_GROW = 28.0          # how much further the chosen slice reaches
RADIAL_BUTTON_R = 150.0     # the round button that opens a radial
# Which way each swipe on a number goes, and where its fan or square opens: "up" and "down" name the game's first and
# second modifiers (as icons are saved: "slot_5:up"), reached by swiping up and left; swiping down cancels.
SWIPE_SIDES = {"up": "up", "down": "left", "cancel": "down"}
SWIPE_FADE_S = 2.0  # in icon mode, a modifier's square fades for this long after its key is sent
SWIPE_GROW = 1.35   # in icon mode, how much bigger than the key a modifier's square is (cancel's is the key's size)
RADIAL_OPEN_S = 0.28        # how long a radial takes to bloom

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
PAGE_ROW_H = 140.0          # a row of page buttons, on a page laid out in rows around a radial
KEY_ROW_H = 140.0           # five rows low enough for thumbs; the space above them is a small trackpad
MODES = ("settings", "trackpad", "keyboard")
THEMES = (("classic", "Classic"), ("charcoal", "Charcoal"), ("dark", "Dark"), ("glass", "Game Glass"))  # see pad_draw.py
OLD_THEME_IDS = {"steamos": "charcoal", "oled": "dark"}  # earlier names of themes, still accepted from a config
THEME_IDS = tuple(theme for theme, _ in THEMES)
# Two fingers on the trackpad, in a profile with gestures (Game.gestures), are held back from the gesture engine until
# it is clear what they do: spreading apart or pinching together zooms, and anything else is the engine's own
# two-finger scroll.
GESTURE_PX = 24.0           # travel of the fingers, or change in the space between them, that decides
# With both fingers moving, a pinch changes the space between them this many times more than it moves the point
# halfway between them. Two thumbs scrolling swing apart as they go, by about twice as much. A pinch with one finger
# kept still needs only the space to change more.
PINCH_SPREAD = 3.0
PINCH_PX_PER_STEP = 60.0    # change in the space between the fingers per zoom step
# Two fingers on the trackpad move together. One that has said nothing while the other has kept moving for this long
# lifted, and the controller lost the lift: the finger left behind would go on scrolling until STALE_CONTACT_S.
LOST_LIFT_S = 0.3
MOVING_GAP_S = 0.1          # a finger silent for longer than this has stopped moving
THEME_Y, THEME_H = 590.0, 112.0  # the theme buttons on the settings view

# Label heights in pixels.
TAB_TEXT, MOD_TEXT, MOUSE_TEXT, PAGE_TEXT, PAGE_SPLIT_TEXT, NUMBER_TEXT, ROUND_TEXT = 34, 36, 40, 40, 34, 68, 56
KEY_TEXT, KEY_WORD_TEXT = 52, 34  # a one-character key, and a key with a word on it


@dataclass(frozen=True)
class Slot:
    """A pad button: its config id, what it shows and what it sends by default."""
    id: str
    label: str
    key: int
    mods: tuple = ()
    tap: bool = False       # one keystroke per touch, modifiers first, however long the finger stays: no key repeat
    confirm: bool = False   # a swipe right presses Enter after it: FFXI's party targets, to pick one for a <stpt> spell
    text: str = ""          # typed key by key instead of the key: a WoW chat command such as "/g "
    radial: tuple = ()      # (direction, Slot) per slice of the radial this button opens (RADIAL_DIRECTIONS)
    keyboard: bool = False  # a radial whose slices open a chat box: the keyboard comes up after one is chosen
    icon: str = ""          # drawn in place of the label, on a radial's slice
    once: bool = False      # one keystroke per touch, let go at once: a held key would repeat (Close tab, Paste)
    picture: str = ""       # a bundled button icon (driver/icons/<picture>.png) in place of the label, where it is
    tag: str = ""           # written beside the icon: what tells apart buttons that share one (Party 1 to 4)
    color: int = 0          # the label's own color (0xRRGGBB) in place of the theme's: a chat channel's, as in the game


def _id(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _page(label: str, key: int, *mods: int, tap: bool = False, confirm: bool = False, icon: str = "",
          once: bool = False) -> Slot:
    return Slot(_id(label), label, key, mods, tap, confirm, icon=icon, once=once)


def _radial(label: str, keyboard: bool = False, picture: str = "", **slices: Slot) -> Slot:
    assert set(slices) <= set(RADIAL_DIRECTIONS) - {RADIAL_CANCEL}
    return Slot(_id(label), label, 0, radial=tuple((d, slices[d]) for d in RADIAL_DIRECTIONS if d in slices),
                keyboard=keyboard, picture=picture)


def _typed(label: str, text: str, color: int = 0) -> Slot:
    """A radial slice that types a chat command. Its id is kept apart from the page buttons' (WoW has a Guild button)."""
    return Slot(f"chat_{_id(label)}", label, 0, text=text, color=color)


# WoW's own colors for its chat channels, as the chat window shows them before a player changes them.
WOW_CHAT_COLORS = {"say": 0xFFFFFF, "yell": 0xFF4040, "whisper": 0xFF80FF, "party": 0xAAAAFF, "raid": 0xFF7F00,
                   "instance": 0xFF7F00, "guild": 0x40FF40}


def _channel(label: str, text: str) -> Slot:
    """A WoW chat channel's slice, its name in the channel's color."""
    return _typed(label, text, WOW_CHAT_COLORS[_id(label)])


def _radial_in(entries: tuple) -> Slot | None:
    """The radial button among a column's entries, if it has one."""
    return next((e for e in entries if isinstance(e, Slot) and e.radial), None)


def _row_of(entry: Slot | tuple) -> tuple:
    """A page entry as a row of buttons: a lone button is a row of its own. None in a row leaves its cell empty."""
    return entry if isinstance(entry, tuple) else (entry,)


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


# The number row: WoW's action bar 1, slots 1 to 12, or FFXI's macro palette with a swipe.
NUMBER_SLOTS = tuple(
    Slot(f"slot_{i + 1}", label, code)
    for i, (label, code) in enumerate(zip(("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "="), range(2, 14)))
)


@dataclass(frozen=True)
class Game:
    """A game the pad is laid out for: its page tabs and what a swipe up or left on a number adds."""
    id: str
    name: str
    pages: tuple    # (title, column, ...) per page tab, a column being (Slot or a row of Slots, ...)
    swipes: dict    # "up" / "down" (swiped up / left: SWIPE_SIDES) -> (label, modifier key codes)
    numbers: tuple = NUMBER_SLOTS  # the number block, right of the pages; () for none
    trackpad: tuple = ()    # Slots in place of the trackpad's Shift, Ctrl and Alt
    gestures: bool = False  # pinch to zoom on the trackpad (GESTURE_PX)
    keyboard_top: tuple = ()  # rows of KeySpecs (None for a gap) above the keyboard, in place of its small trackpad

    @property
    def titles(self) -> tuple:
        return tuple(title for title, *_ in self.pages)

    @property
    def buttons(self) -> tuple:
        """Every page button, a row's included."""
        return tuple(s for _, *columns in self.pages for column in columns for entry in column for s in _row_of(entry)
                     if s)

    @property
    def controls(self) -> tuple:
        """Every button a remap can change, the number row and a radial's key slices included. A radial button and a
        typed slice send no key of their own, so they cannot be remapped."""
        slots = list(self.buttons) + list(self.numbers) + list(self.trackpad)
        slots = [inner for s in slots for inner in ([part for _, part in s.radial] if s.radial else [s])]
        return tuple({s.id: s for s in slots if not s.text}.values())  # Desktop's trackpad reuses page buttons


# WoW's default bindings, as Linux key codes.
WOW_PAGES = (
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
        (_page("Sheathe weapons", 44), _page("Screenshot", 99)),
        _page("Sit / stand", 45),
        _radial("Chat", keyboard=True, picture="chat_say", up=_channel("Guild", "/g "), up_right=_channel("Party", "/p "),
                right=_channel("Yell", "/y "), down_right=_channel("Raid", "/ra "),
                down_left=_channel("Instance", "/i "), left=_channel("Say", "/s "), up_left=_channel("Whisper", "/w ")),
        (_page("Chat page up", 104), _page("Chat page down", 109)),
    )),
)

# FFXI's default keyboard controls (full keyboard layout): the menus open with Ctrl (or Alt) and a letter, F1 to F6 pick
# party members, F8 and F9 the nearest NPC or player, and Ctrl (or Alt) with Up or Down changes the macro set. A
# spell cast on <stpt> asks for a party member and then Enter: a swipe right on a party target sends both.
FFXI_PAGES = (
    ("Menus", (
        _page("Main menu", 12), _page("Confirm", 28), _page("Cancel", 1), _page("Equipment", 18, KEY_LEFTCTRL),
        _page("Items", 23, KEY_LEFTCTRL), _page("Magic", 50, KEY_LEFTCTRL), _page("Job abilities", 36, KEY_LEFTCTRL),
        _page("Weapon skills", 17, KEY_LEFTCTRL), _page("Pet commands", 48, KEY_LEFTCTRL),
    )),
    ("Target", (
        _page("Self", 59, confirm=True), _page("Party 1", 60, confirm=True), _page("Party 2", 61, confirm=True),
        _page("Party 3", 62, confirm=True), _page("Party 4", 63, confirm=True), _page("Party 5", 64, confirm=True),
        _page("Nearest NPC", 66), _page("Nearest player", 67), _page("Lock target", 55),
        _page("Attack", 30, KEY_LEFTCTRL), _page("Check", 46, KEY_LEFTCTRL), _page("Ranged attack", 32, KEY_LEFTCTRL),
    )),
    # The chat slices keep the ids they had as page buttons, so that their remaps still apply. They sit where WoW's
    # nearest channels do: Linkshell for Guild, a tell for a whisper.
    ("Utility", (
        (_page("Macro set up", 103, KEY_LEFTCTRL, tap=True), _page("Macro set down", 108, KEY_LEFTCTRL, tap=True)),
        _radial("Chat", keyboard=True, up=Slot("linkshell_chat", "Linkshell", 38, (KEY_LEFTCTRL,), tap=True),
                up_right=Slot("party_chat", "Party", 25, (KEY_LEFTCTRL,), tap=True),
                left=Slot("say", "Say", 31, (KEY_LEFTCTRL,), tap=True),
                up_left=Slot("reply_to_tell", "Reply", 19, (KEY_LEFTCTRL,), tap=True)),
    )),
)

def _pictured(pages: tuple) -> tuple:
    """Pages whose buttons show their icon (driver/icons/<id>.png) in place of their label. Party 1 to 4 share
    party.png, with their number beside it. A radial keeps its own (and its slices their lettering)."""
    def one(slot):
        if slot is None or slot.radial:
            return slot
        party = re.fullmatch(r"party_(\d)", slot.id)
        return replace(slot, picture="party", tag=party.group(1)) if party else replace(slot, picture=slot.id)

    return tuple((title, *(tuple(tuple(one(s) for s in entry) if isinstance(entry, tuple) else one(entry)
                                 for entry in column) for column in columns))
                 for title, *columns in pages)


WOW = Game("wow", "World of Warcraft", _pictured(WOW_PAGES),
           {"up": ("Shift", (KEY_LEFTSHIFT,)), "down": ("Ctrl", (KEY_LEFTCTRL,))})
# FFXI's macro palette: Ctrl + 1 to 0 is its upper bar, Alt + 1 to 0 the lower one.
FFXI = Game("ffxi", "Final Fantasy XI", FFXI_PAGES,
            {"up": ("Ctrl", (KEY_LEFTCTRL,)), "down": ("Alt", (KEY_LEFTALT,))})

# Everything that is not a game: a browser, a file manager, an office program. The usual shortcuts of Linux desktops
# and browsers, each still one key (with its modifiers) per press. Those that do harm when repeated are sent once per
# touch: a thumb resting on Close tab must not close several.
COPY = _page("Copy", 46, KEY_LEFTCTRL)
PASTE = _page("Paste", 47, KEY_LEFTCTRL, once=True)
BACK = _page("Back", KEY_LEFT, KEY_LEFTALT)
FORWARD = _page("Forward", KEY_RIGHT, KEY_LEFTALT)
# Two tabs of two columns each, over the whole width: the F keys and the arrows are on the keyboard instead.
DESKTOP_PAGES = (
    ("Edit", (
        (_page("Undo", 44, KEY_LEFTCTRL), _page("Redo", 44, KEY_LEFTCTRL, KEY_LEFTSHIFT)),
        (_page("Cut", 45, KEY_LEFTCTRL), COPY),
        (PASTE, _page("Select all", 30, KEY_LEFTCTRL)),
        (_page("Find", 33, KEY_LEFTCTRL), _page("Save", 31, KEY_LEFTCTRL, once=True)),
    ), (
        (_page("Esc", 1), _page("Delete", 111)),
        (_page("Tab", 15), _page("Enter", 28)),
        (_page("Home", 102), _page("End", 107)),
        (_page("Page up", 104), _page("Page down", 109)),
    )),
    ("Browser", (
        (BACK, FORWARD),
        (_page("Reload", 63, once=True), _page("Address bar", 38, KEY_LEFTCTRL)),
        (_page("New tab", 20, KEY_LEFTCTRL, once=True), _page("Close tab", 17, KEY_LEFTCTRL, once=True)),
        (_page("Previous tab", 15, KEY_LEFTCTRL, KEY_LEFTSHIFT), _page("Next tab", 15, KEY_LEFTCTRL)),
        (_page("Reopen tab", 20, KEY_LEFTCTRL, KEY_LEFTSHIFT, once=True), _page("Bookmark", 32, KEY_LEFTCTRL, once=True)),
        (_page("Zoom out", 12, KEY_LEFTCTRL), _page("Zoom in", 13, KEY_LEFTCTRL)),
    ), (
        (_page("Switch window", 15, KEY_LEFTALT), _page("Close window", 62, KEY_LEFTALT, once=True)),
        _page("Full screen", 87, once=True),
        _radial("Media", up=_page("Play / pause", 164, icon="play_pause"),
                up_left=_page("Previous", 165, icon="previous"), up_right=_page("Next", 163, icon="next"),
                left=_page("Volume down", 114, icon="volume_down"), right=_page("Volume up", 115, icon="volume_up"),
                down_left=_page("Mute", 113, icon="mute")),
        (_page("Screenshot", 99, once=True), _page("Menu", 127)),
    )),
)
# Above the keyboard: F1 to F12 in two rows on the left, and on the right, past a gap, Super and the arrows, Up above
# Down. Ten cells to a row, so each key sits over one of the digits.
_F_KEYS = [KeySpec(f"F{i + 1}", code=code, action="plain")
           for i, code in enumerate((59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 87, 88))]
DESKTOP_KEYBOARD_TOP = (
    _F_KEYS[:6] + [None, KeySpec("Super", code=125, action="plain"), KeySpec(code=103, action="plain", icon="up"),
                   None],
    _F_KEYS[6:] + [None, KeySpec(code=KEY_LEFT, action="plain", icon="left"),
                   KeySpec(code=108, action="plain", icon="down"), KeySpec(code=KEY_RIGHT, action="plain", icon="right")],
)
DESKTOP = Game("desktop", "Desktop", DESKTOP_PAGES,
               {"up": ("Ctrl", (KEY_LEFTCTRL,)), "down": ("Alt", (KEY_LEFTALT,))}, numbers=(),
               trackpad=(BACK, COPY, PASTE, FORWARD), gestures=True, keyboard_top=DESKTOP_KEYBOARD_TOP)
GAMES = {game.id: game for game in (WOW, FFXI, DESKTOP)}


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
# The unshifted characters a chat command (Slot.text) can use, and their keys.
TYPED = {spec.label: spec.code for keys, _ in KEYBOARD_MAIN for spec in keys if spec.action == "input"} | {" ": 57}


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

    @property
    def center(self) -> tuple:
        return self.x + self.w / 2, self.y + self.h / 2


def _row(widgets: list, items: list, x: float, y: float, w: float, h: float, make: Callable) -> None:
    """Lay items out left to right in equal cells; make(item, x, y, w, h) returns each widget. None leaves a cell empty."""
    cell = (w - (len(items) - 1) * GAP) / len(items)
    for i, item in enumerate(items):
        if item is not None:
            widgets.append(make(item, x + i * (cell + GAP), y, cell, h))


def _modifier_row(widgets: list, x: float, y: float, w: float, h: float) -> None:
    _row(widgets, list(MODIFIERS), x, y, w, h,
         lambda m, bx, by, bw, bh: Widget(f"mod:{m[0]}", "mod", bx, by, bw, bh, m[1], data=m[2], size=MOD_TEXT))


def _page_column(panels: list, widgets: list, entries: tuple, x: float, w: float, row_h: float) -> None:
    """One column of a page's buttons, w wide at x, top to bottom of the body; a row of them is row_h high."""
    radial = _radial_in(entries)

    def page_button(slot: Slot, bx: float, by: float, bw: float, bh: float, narrow: bool) -> Widget:
        return Widget(f"page:{slot.id}", "page", bx, by, bw, bh, slot.label, data=slot,
                      size=PAGE_SPLIT_TEXT if narrow else PAGE_TEXT, wrap=narrow)

    if radial or any(isinstance(e, tuple) for e in entries):
        # A column with rows: each row row_h high, its buttons side by side. The rows after a radial go at the
        # bottom, and its round button in the middle of the room left between them.
        room_top, room_bottom = BODY_Y, BODY_Y + BODY_H
        cut = entries.index(radial) if radial else len(entries)
        for group, top in ((entries[:cut], True), (entries[cut + 1:], False)):
            if not group:
                continue
            group_h = 2 * PANEL_PAD + len(group) * row_h + (len(group) - 1) * GAP
            gy = BODY_Y if top else BODY_Y + BODY_H - group_h
            panels.append((x, gy, w, group_h, False))
            for ri, entry in enumerate(group):
                row = _row_of(entry)
                narrow = len(row) > 1
                _row(widgets, list(row), x + PANEL_PAD, gy + PANEL_PAD + ri * (row_h + GAP), w - 2 * PANEL_PAD,
                     row_h, lambda s, bx, by, bw, bh: page_button(s, bx, by, bw, bh, narrow))
            if top:
                room_top = gy + group_h + GAP
            else:
                room_bottom = gy - GAP
        if radial:
            bx, by = x + w / 2, (room_top + room_bottom) / 2
            widgets.append(Widget(f"page:{radial.id}", "page", bx - RADIAL_BUTTON_R, by - RADIAL_BUTTON_R,
                                  2 * RADIAL_BUTTON_R, 2 * RADIAL_BUTTON_R, radial.label, data=radial, size=ROUND_TEXT))
    else:
        split = len(entries) > SINGLE_COLUMN_MAX
        columns = [entries[: (len(entries) + 1) // 2], entries[(len(entries) + 1) // 2:]] if split else [entries]
        col_w = (w - (len(columns) - 1) * GAP) / len(columns)
        for ci, column in enumerate(columns):
            px = x + ci * (col_w + GAP)
            panels.append((px, BODY_Y, col_w, BODY_H, False))
            bh = (BODY_H - 2 * PANEL_PAD - (len(column) - 1) * GAP) / len(column)
            for ri, slot in enumerate(column):
                widgets.append(page_button(slot, px + PANEL_PAD, BODY_Y + PANEL_PAD + ri * (bh + GAP),
                                           col_w - 2 * PANEL_PAD, bh, split))


def build_layout(view: str, page: int, symbols: bool = False, game: Game = WOW, square_numbers: bool = False) -> tuple:
    """(panels, widgets) for a view. Panels are (x, y, w, h, strong): the faint gold backing behind a group.
    square_numbers makes the number keys square, for their icons."""
    panels: list = []
    widgets: list = []
    full_w = W - 2 * MARGIN

    # Header: the page tabs share the left, the settings / trackpad / keyboard buttons keep the right.
    panels.append((MARGIN, HEADER_Y, full_w, HEADER_H, False))
    hx, hy, hh = MARGIN + PANEL_PAD, HEADER_Y + PANEL_PAD, HEADER_H - 2 * PANEL_PAD
    modes_w = len(MODES) * MODE_W + (len(MODES) - 1) * GAP
    status_x = W - MARGIN - PANEL_PAD - modes_w - GAP - STATUS_W
    widgets.append(Widget("status", "status", status_x, hy, STATUS_W, hh))
    _row(widgets, list(enumerate(game.titles)), hx, hy, status_x - GAP - hx, hh,
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
        if game.trackpad:
            _row(widgets, list(game.trackpad), MARGIN, mod_y, full_w, mod_h,
                 lambda s, bx, by, bw, bh: Widget(f"page:{s.id}", "page", bx, by, bw, bh, s.label, data=s, size=MOD_TEXT))
        else:
            _modifier_row(widgets, MARGIN, mod_y, full_w, mod_h)
        _row(widgets, [("left", "Left click", BTN_LEFT), ("right", "Right click", BTN_RIGHT)], MARGIN, click_y, full_w, click_h,
             lambda b, bx, by, bw, bh: Widget(f"mouse:{b[0]}", "mouse", bx, by, bw, bh, b[1], data=b[2], size=MOUSE_TEXT))
    elif view == "keyboard":
        rows = KEYBOARD_SYMBOLS if symbols else KEYBOARD_MAIN
        # Both pages take the same height (the symbols page has fewer, taller rows), so the keys never jump.
        kb_h = len(KEYBOARD_MAIN) * KEY_ROW_H
        top = BODY_Y + BODY_H - kb_h
        row_h = kb_h / len(rows)
        if game.keyboard_top:
            # The game's own keys take the room above the keyboard, in equal cells.
            top_h = (top - BODY_Y) / len(game.keyboard_top)
            for r, keys in enumerate(game.keyboard_top):
                _row(widgets, [None if spec is None else (c, spec) for c, spec in enumerate(keys)], MARGIN,
                     BODY_Y + r * top_h + GAP / 2, full_w, top_h - GAP,
                     lambda k, bx, by, bw, bh, r=r: Widget(f"key:top:{r}:{k[0]}", "key", bx, by, bw, bh, k[1].label,
                                                           data=k[1]))
        else:
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
        # The page's columns side by side, and the number block, if the game has one, right of them.
        columns = game.pages[page][1:]
        count = len(columns) + (1 if game.numbers else 0)
        col_w = (full_w - (count - 1) * GAP) / count
        # A page with a radial keeps its rows PAGE_ROW_H high, to leave the round button room. One without shares the
        # body's height between its longest column's rows, so that its rows still line up across the columns.
        row_h = PAGE_ROW_H
        if not any(_radial_in(entries) for entries in columns):
            most = max(len(entries) for entries in columns)
            row_h = (BODY_H - 2 * PANEL_PAD - (most - 1) * GAP) / most
        for ci, entries in enumerate(columns):
            _page_column(panels, widgets, entries, MARGIN + ci * (col_w + GAP), col_w, row_h)
        if game.numbers:
            # The number block, centered top to bottom. Swipes give it the game's modifiers, so it needs no
            # modifier row.
            rx = MARGIN + len(columns) * (col_w + GAP)
            key_w = (col_w - 2 * PANEL_PAD - 2 * GAP) / 3
            row_h = min((BODY_H - 2 * PANEL_PAD - 3 * GAP) / 4, key_w * (1.0 if square_numbers else NUMBER_TALL))
            num_h = 4 * row_h + 3 * GAP + 2 * PANEL_PAD
            num_y = BODY_Y + (BODY_H - num_h) / 2
            panels.append((rx, num_y, col_w, num_h, True))
            for r in range(4):
                _row(widgets, list(game.numbers[r * 3: r * 3 + 3]), rx + PANEL_PAD,
                     num_y + PANEL_PAD + r * (row_h + GAP), col_w - 2 * PANEL_PAD, row_h,
                     lambda s, bx, by, bw, bh: Widget(f"number:{s.id}", "number", bx, by, bw, bh, s.label, data=s,
                                                      size=NUMBER_TEXT))
    return panels, widgets


def icon_id(slot: Slot, swipe: str | None = None) -> str:
    """What a number's icon is saved under: "slot_5" for its tap, "slot_5:up" and "slot_5:down" for its swipes."""
    return f"{slot.id}:{swipe}" if swipe else slot.id


def swipe_square(widget: Widget, swipe: str) -> tuple:
    """Where a swipe's square opens beside a number in icon mode, as (x, y, size), one gap past the key the way the
    swipe goes (SWIPE_SIDES): the first modifier's above it, the second's left of it, both SWIPE_GROW times the key's
    size, and cancel's below, the key's size. The two modifiers' grow from the key's top left corner away from each
    other, the first's to the right and the second's down, so that they never overlap. Kept on the screen, so the top
    row's first goes over the page tabs and the top of its own key, and the bottom row's cancel over its own key."""
    base = min(widget.w, widget.h)
    kx, ky = widget.x + (widget.w - base) / 2, widget.y + (widget.h - base) / 2
    side = SWIPE_SIDES[swipe]
    size = base if side == "down" else base * SWIPE_GROW
    x, y = {"up": (kx, ky - GAP - size), "left": (kx - GAP - size, ky), "down": (kx, ky + base + GAP)}[side]
    edge = MARGIN / 2
    x, y = min(max(x, edge), W - edge - size), min(max(y, edge), H - edge - size)
    if side == "left":
        # The top right key's first square is pushed left and down by the screen's edges, into this one's way: this
        # one goes down below it.
        ux, uy, usize = swipe_square(widget, "up")
        if ux < x + size and uy + usize + GAP > y:
            y = min(uy + usize + GAP, H - edge - size)
    return x, y, size


def swipe_of(dx: float, dy: float) -> str | None:
    """What a finger's travel on a number button asks for (SWIPE_SIDES): "up" (swiped up: the game's first modifier),
    "down" (swiped left: its second), "cancel" (swiped down), or None for a plain press. Right counts as a plain press:
    there is no room for a fan right of the right-hand column."""
    if max(abs(dx), abs(dy)) <= SWIPE_PX:
        return None
    if abs(dy) >= abs(dx):
        return "up" if dy < 0 else "cancel"
    return "down" if dx < 0 else None


def confirms(dx: float, dy: float) -> bool:
    """Whether a finger's travel on a target button (Slot.confirm) is a swipe right, which adds an Enter."""
    return dx > SWIPE_PX and dx >= abs(dy)


def radial_reach(cx: float, cy: float) -> float:
    """How far the slices of a radial centered at (cx, cy) reach: RADIAL_REACH, or less where it would not be whole on
    the screen, its chosen slice included."""
    return min(RADIAL_REACH, min(cx, W - cx, cy, H - cy) - RADIAL_GROW - MARGIN / 2)


def radial_choice(cx: float, cy: float, x: float, y: float) -> str | None:
    """The slice of a radial (RADIAL_DIRECTIONS) centered at (cx, cy) under a finger at (x, y), or None over the hub."""
    dx, dy = x - cx, y - cy
    if math.hypot(dx, dy) <= RADIAL_HUB:
        return None
    return RADIAL_DIRECTIONS[round(math.atan2(dy, dx) / (math.pi / 4)) % len(RADIAL_DIRECTIONS)]


@dataclass
class Touch:
    widget: Widget | None   # where the finger landed; it keeps that owner until it lifts
    seen: float             # kernel time of its last report
    x: float
    y: float
    release: Callable | None = None  # what lifting the finger, or the button going away, lets go of
    commit: Callable | None = None   # what lifting the finger sends (a number, a target's Enter); dropped if the button goes away
    start_x: float = 0.0
    start_y: float = 0.0
    choosing: bool = False  # a radial's finger may choose: it moved RADIAL_PX, or landed on a radial left open
    moving: float = 0.0     # kernel time it began to move this time, if it is moving (MOVING_GAP_S)


@dataclass
class Pair:
    """Two fingers on the trackpad in a profile with gestures (Game.gestures), and what they turned out to do."""
    tids: tuple
    spread: float           # the space between them when the second landed
    starts: tuple           # where each of them was then
    mode: str = ""          # "" until decided, then "pinch" or "scroll" (left to the engine), and "done"
    steps: int = 0          # zoom steps sent: in is positive


@dataclass
class MouseButton:
    locked: bool = False
    last_down: float = -10.0


class PadController:
    """Pad state and touch handling. The bridge is engine.UInputBridge (or anything with key, mouse_button and
    emit_scroll); the gesture engine drives the pointer for touches on the trackpad surface."""

    def __init__(self, bridge, gesture, on_change: Callable = lambda widget=None: None, on_close: Callable = lambda: None,
                 haptic: Callable = lambda pattern: None, on_theme: Callable = lambda theme: None,
                 clock: Callable = time.monotonic, sleep: Callable = time.sleep, later: Callable | None = None) -> None:
        self.bridge = bridge
        self.gesture = gesture
        self.on_change = on_change  # something visible changed: redraw; on_change(widget) when only its swipe did
        self.on_close = on_close    # "Close pad" was tapped
        self.haptic = haptic        # haptic(pattern): "press", "tick" or "lock" (see haptics.PATTERNS)
        self.on_theme = on_theme    # a theme was picked on the settings view: keep it
        self._clock = clock
        self._sleep = sleep
        # later(delay, job) runs job after delay seconds without holding up the touch thread meanwhile; the app runs
        # it under its touch lock. Without one, the wait is slept through (tests).
        self._later = later or (lambda delay, job: (self._sleep(delay), job()))

        self.view = "pad"   # pad, trackpad, keyboard, settings
        self.game = WOW
        self.page = 0
        self.kb_symbols = False
        self.kb_shift = "off"   # off, on (next key only), caps
        self.bindings: dict = {}
        self.number_icons = False   # the number keys show icons (only in a game with a number block)
        self.icons: dict = {}       # icon_id -> a picture's file name, in the game's icon folder
        self.icon_surfaces: dict = {}  # file name -> its picture, square (pad_draw.make_icon); set by the app
        # icon_id -> {"name", "picture"}: what the key holds on the player's WoW action bars (wow_bars.pad_bars); set
        # by the app. A picture picked for the key wins over the bars'.
        self.wow_bars: dict = {}
        # Whether the WoW addon's Japanese keyboard bindings are on (wow_bars.last_character): the = key does what ^
        # does on a JIS keyboard, and is labelled ^. Set by the app with wow_bars.
        self.wow_jis = False
        self.tap_to_click = True
        self.theme = THEME_IDS[0]
        self.info_lines: list = []  # shown on the settings view

        self.touches: dict = {}         # tracking id -> Touch
        self.pressed: set = set()       # ids of the widgets with a finger on them
        self.flash_until: dict = {}     # widget id -> clock time until which it still draws as pressed
        # In icon mode, number widget id -> (swipe, clock time it was sent): its square fades out (SWIPE_FADE_S).
        self.swipe_echoes: dict = {}
        self.key_typed: dict = {}       # keyboard widget id -> the character it typed, for the preview over the finger
        self._expired: set = set()      # ids dropped as stale: the kernel may reuse them for a new finger
        self.key_refs: dict = {}        # key code -> how many holders want it down
        self.held_mods: dict = {}       # modifier code -> when it was armed
        self.locked_mods: set = set()
        self.mouse = {BTN_LEFT: MouseButton(), BTN_RIGHT: MouseButton()}
        self.strip_rest = 0.0
        self.pair: Pair | None = None
        self.last_touch: tuple | None = None    # (x, y, widget id) of the newest touch, for the settings view
        # widget id -> "up", "down" or "cancel" while a finger swipes on a number, "confirm" on a target button, and
        # the slice under the finger, or None, for as long as a radial is open
        self.swipes: dict = {}
        self.radial_opened = -10.0              # clock time the last radial began to bloom
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
        game = GAMES.get(cfg.get("game"), WOW)
        if game is not self.game:
            # Its buttons are about to change: let go of what they hold.
            self._release_touches()
            self.game = game
            self.page = min(self.page, len(game.pages) - 1)
            self._relayout()
        bindings = cfg.get("bindings")
        self.bindings = dict(bindings) if isinstance(bindings, dict) else {}
        icons = cfg.get("icons")
        self.icons = {key: name for key, name in icons.items() if isinstance(key, str) and isinstance(name, str) and name} \
            if isinstance(icons, dict) else {}
        number_icons = bool(cfg.get("number_icons")) and bool(self.game.numbers)
        if number_icons != self.number_icons:
            # The number keys change shape: let go of what they hold.
            self._release_touches()
            self.number_icons = number_icons
            self._relayout()
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
        if title in self.game.titles:
            self.page = self.game.titles.index(title)
            self._relayout()

    # ------------------------------------------------------------------ what the painter asks

    def icon_of(self, slot: Slot, swipe: str | None = None) -> str:
        """The file name of the icon a number, or one of its swipes, shows in icon mode: the one picked for it, or the
        one of what it holds on the WoW action bars; "" for its lettering."""
        if not self.number_icons:
            return ""
        key = icon_id(slot, swipe)
        return self.icons.get(key) or self.wow_bars.get(key, {}).get("picture", "")

    def name_of(self, slot: Slot, swipe: str | None = None) -> str:
        """In icon mode, the name of what a number, or one of its swipes, holds on the WoW action bars ("Lightning
        Bolt"), for a key without a picture; "" where the bars say nothing."""
        return self.wow_bars.get(icon_id(slot, swipe), {}).get("name", "") if self.number_icons else ""

    def number_label(self, widget: Widget) -> str:
        """What a number key is labelled: its key, or ^ for = while the WoW addon's Japanese keyboard bindings are on."""
        return "^" if self.wow_jis and widget.label == "=" else widget.label

    def picture_names(self) -> set:
        """The file names of every picture icon mode can show: those picked and those of the bars."""
        if not self.number_icons:
            return set()
        return {*self.icons.values(), *(bar.get("picture") for bar in self.wow_bars.values())} - {"", None}

    def lit(self, widget: Widget) -> bool:
        return widget.id in self.pressed or self._clock() < self.flash_until.get(widget.id, 0.0)

    def radial_growth(self) -> float:
        """How far the open radial has bloomed: 0 when it opens, 1 after RADIAL_OPEN_S."""
        return min(1.0, max(0.0, (self._clock() - self.radial_opened) / RADIAL_OPEN_S))

    def blooming(self) -> bool:
        """A radial is open and still blooming: the app repaints until it has."""
        return self.radial_growth() < 1.0 and any(w.kind == "page" and w.data.radial and w.id in self.swipes
                                                  for w in self.widgets)

    def swiping(self) -> list:
        """The number and target buttons (Slot.confirm) a finger is on, whose swipe can change with any touch frame:
        the app repaints their swipes' areas every frame until it lifts (pad_draw.swipe_areas). In game, a single redraw
        asked for when the swipe changes direction waits its turn, and the fan or square lags behind the finger. It
        only reads (the painter calls it, off the lock)."""
        return [t.widget for t in list(self.touches.values()) if t.widget is not None
                and (t.widget.kind == "number" or (t.widget.kind == "page" and t.widget.data.confirm))]

    def echoes(self) -> list:
        """In icon mode, the squares of modifiers just sent, fading: (widget, swipe, opacity from 1 down to 0). A key
        swiped again shows its swipe instead. Read from copies: the touch thread may change them while this paints."""
        now = self._clock()
        echoes, swipes = dict(self.swipe_echoes), dict(self.swipes)
        return [(w, swipe, 1.0 - (now - sent) / SWIPE_FADE_S) for w in self.widgets if w.id in echoes
                and w.id not in swipes for swipe, sent in (echoes[w.id],) if now - sent < SWIPE_FADE_S]

    def fading(self) -> bool:
        """A swipe's square is still fading: the app repaints until it has gone. It only reads (the painter calls it,
        off the lock): an echo that has gone is replaced by the key's next one (_commit_number), or cleared with the
        view."""
        now = self._clock()
        return self.number_icons and any(now - sent < SWIPE_FADE_S for _, sent in list(self.swipe_echoes.values()))

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

    def _tap(self, key: int, mods: tuple = (), then: Callable | None = None) -> None:
        """Send one keystroke whatever the finger does next: the modifiers, MOD_LEAD_S later the key for TAP_HOLD_S,
        and the modifiers let go TAP_HOLD_S after that, and then then(). The touch thread never waits for it."""
        def mods_up() -> None:
            for code in reversed(mods):
                self._release(code)
            if then:
                then()

        def key_up() -> None:
            self._release(key)
            if mods:
                self._later(TAP_HOLD_S, mods_up)
            elif then:
                then()

        def key_down() -> None:
            self._press(key)
            self._later(TAP_HOLD_S, key_up)

        for code in mods:
            self._press(code)
        if mods:
            self._later(MOD_LEAD_S, key_down)
        else:
            key_down()

    def _type(self, text: str, then: Callable | None = None) -> None:
        """Type text a key at a time (TYPE_HOLD_S, TYPE_GAP_S, TYPE_OPEN_S), and then then(). The touch thread never
        waits for it."""
        codes = [TYPED[ch] for ch in text]

        def step(i: int) -> None:
            if i == len(codes):
                if then:
                    then()
                return

            def up() -> None:
                self._release(codes[i])
                self._later(TYPE_OPEN_S if i == 0 else TYPE_GAP_S, lambda: step(i + 1))

            self._press(codes[i])
            self._later(TYPE_HOLD_S, up)

        step(0)

    def _radial_choice(self, widget: Widget, touch: Touch) -> str | None:
        """The slice of widget's radial under touch, or None (see RADIAL_PX). A finger that landed outside a radial
        that a tap left open chooses nothing either: it only closes it."""
        if not touch.choosing:
            return None
        cx, cy = widget.center
        if math.hypot(touch.start_x - cx, touch.start_y - cy) > radial_reach(cx, cy) + RADIAL_GROW:
            return None
        return radial_choice(cx, cy, touch.x, touch.y)

    def _open_radial(self) -> Widget | None:
        """A radial that a tap left open, with no finger on it: the next finger to land is its."""
        return next((w for w in self.widgets if w.kind == "page" and w.data.radial and w.id in self.swipes
                     and w.id not in self.pressed), None)

    def _commit_radial(self, widget: Widget, touch: Touch, opening: bool) -> None:
        """A radial's finger lifted: send the slice it chose and, for a chat radial (Slot.keyboard), show the keyboard
        as it was last left (letters or symbols). Cancel, the middle or an empty slice send nothing and leave the page
        as it is, but a tap on the button that opened the radial leaves it open."""
        chosen = dict(widget.data.radial).get(self._radial_choice(widget, touch))
        if chosen is None:
            self.flash_until.pop(widget.id, None)  # nothing was sent: do not light it up
            if opening and not touch.choosing:
                self.swipes[widget.id] = None
            return
        # The keyboard comes up once the slice's keystroke is out: a key typed sooner would land among its letters,
        # or with its Ctrl.
        then = self._chat_keyboard if widget.data.keyboard else None
        if chosen.text:
            self._type(chosen.text, then)
        else:
            self._tap(*combo_for(chosen, self.bindings), then=then)

    def _chat_keyboard(self) -> None:
        if self.view == "pad":  # unless another finger has changed the view meanwhile
            self._set_view("keyboard")
            self.on_change()

    def _commit_target(self, widget: Widget, touch: Touch) -> None:
        """A target button's finger lifted, after its key let go: a swipe right confirms the target with Enter."""
        if confirms(touch.x - touch.start_x, touch.y - touch.start_y):
            self._later(CONFIRM_GAP_S, lambda: self._tap(KEY_ENTER))

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
        self.swipe_echoes.pop(widget.id, None)
        if swipe == "cancel":
            self.flash_until.pop(widget.id, None)  # nothing was sent: do not light it up
            return
        if swipe and self.number_icons:
            self.swipe_echoes[widget.id] = (swipe, self._clock())  # what was sent stays a moment, fading
        self._press_slot(widget.data, self.game.swipes[swipe][1] if swipe else ())()

    # ------------------------------------------------------------------ two-finger gestures

    def _pair_down(self) -> None:
        """A finger landed on the trackpad: two of them start a gesture, and a third leaves an undecided one to the
        engine and ends a pinch. The engine's own count is used: it forgets the fingers whose lift was lost."""
        fingers = self.gesture.active_contacts
        if self.pair is None and self.game.gestures and len(fingers) == 2 and all(t in self.touches for t in fingers):
            (ax, ay), (bx, by) = ((self.touches[tid].x, self.touches[tid].y) for tid in fingers)
            self.pair = Pair(tuple(fingers), math.hypot(bx - ax, by - ay), ((ax, ay), (bx, by)))
        elif self.pair and not self.pair.mode and len(fingers) > 2:
            self.pair.mode = "scroll"
        elif self.pair and self.pair.mode == "pinch":
            # The engine forgot the pinch's fingers, so this one would point and click with the pinch's Ctrl held.
            self.pair.mode = "done"
            self._release(KEY_LEFTCTRL)

    def _pair_move(self, tid: int) -> bool:
        """A trackpad finger moved. Returns whether its gesture takes the move from the engine: until it is decided,
        and after, unless it is a scroll. Once done, or once one finger has lifted, the other moves nothing."""
        return self.pair is not None and tid in self.pair.tids and self.pair.mode != "scroll"

    def frame_done(self) -> None:
        """Every finger of a touch frame has been reported. The fingers of one frame arrive one at a time, so a
        two-finger gesture is judged here: in the middle of a frame, two fingers sliding together look like a pinch."""
        pair = self.pair
        if pair is None or pair.mode in ("scroll", "done") or any(t not in self.touches for t in pair.tids):
            return
        (ax, ay), (bx, by) = ((self.touches[t].x, self.touches[t].y) for t in pair.tids)
        (sax, say), (sbx, sby) = pair.starts
        spread = math.hypot(bx - ax, by - ay) - pair.spread
        moved = math.hypot((ax + bx - sax - sbx) / 2, (ay + by - say - sby) / 2)
        if not pair.mode:
            if max(abs(spread), moved) < GESTURE_PX:
                return
            still = min(math.hypot(ax - sax, ay - say), math.hypot(bx - sbx, by - sby)) < GESTURE_PX / 3
            if abs(spread) <= moved * (1.0 if still else PINCH_SPREAD):
                pair.mode = "scroll"  # the engine catches up with the next move on the travel it was not given
                return
            pair.mode = "pinch"
            self.gesture.reset_all()  # the engine forgets the two fingers: their lift must not click
            self._press(KEY_LEFTCTRL)
        # Ctrl and the wheel, which is how a browser receives a touchpad's pinch.
        steps = int(spread / PINCH_PX_PER_STEP)
        while pair.steps != steps:
            step = 1 if steps > pair.steps else -1
            pair.steps += step
            self.bridge.emit_scroll(0, step * HI_RES_NOTCH)
            self.haptic("tick")

    def _pair_up(self) -> None:
        """A trackpad finger lifted, or was let go of: its gesture ends once neither of its fingers is left."""
        pair = self.pair
        if pair is None:
            return
        if not pair.mode:
            pair.mode = "scroll"  # lifted before it was decided: a two-finger tap, the engine's to click
        elif pair.mode == "pinch":
            pair.mode = "done"
            self._release(KEY_LEFTCTRL)
        if not any(t in self.touches for t in pair.tids):
            self.pair = None

    def _end_pair(self) -> None:
        if self.pair and self.pair.mode == "pinch":
            self._release(KEY_LEFTCTRL)
        self.pair = None

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
        self.panels, self.widgets = build_layout(self.view, self.page, self.kb_symbols, self.game, self.number_icons)

    def _set_view(self, view: str, page: int | None = None) -> None:
        """Show a view. Everything a finger was holding is let go first: its button is about to disappear."""
        self._release_touches()
        self.swipe_echoes.clear()
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
        self._end_pair()
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
        widget = self._open_radial() or self.widget_at(x, y)
        self.last_touch = (x, y, widget.id if widget else "")
        touch = Touch(widget, ts, x, y, start_x=x, start_y=y, moving=ts)
        self.touches[tid] = touch
        if widget is None or widget.kind == "status":
            touch.widget = None
            if self.view == "settings":
                self.on_change()
            return
        kind = widget.kind
        if kind == "surface":
            self.gesture.touch_down(tid, x, y, ts)
            self._pair_down()
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
                if touch.widget is None:  # ending it changed the view (a chat radial's keyboard): its button is gone
                    self.on_change()
                    return
            self.pressed.add(widget.id)
            if kind == "page" and widget.data.radial:
                opening = widget.id not in self.swipes
                touch.choosing = not opening
                if opening:
                    self.radial_opened = self._clock()
                self.swipes[widget.id] = self._radial_choice(widget, touch)
                touch.commit = lambda: self._commit_radial(widget, touch, opening)
            elif kind == "page" and widget.data.tap:
                self._tap(*combo_for(widget.data, self.bindings))
            elif kind == "page" and widget.data.once:
                self._press_slot(widget.data)()  # let go as soon as MIN_PRESS_S allows
            elif kind == "page":
                touch.release = self._press_slot(widget.data)
                if widget.data.confirm:
                    touch.commit = lambda: self._commit_target(widget, touch)
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
        if ts - touch.seen > MOVING_GAP_S:
            touch.moving = ts
        touch.seen, touch.x, touch.y = ts, x, y
        if touch.widget is None:
            return
        if touch.widget.kind == "surface":
            self._lift_lost_fingers(touch, ts)
            if not self._pair_move(tid):
                self.gesture.touch_move(tid, x, y, ts)
        elif touch.widget.kind == "number" or (touch.widget.kind == "page" and touch.widget.data.confirm):
            # A number's swipe adds a modifier or cancels it; a target's swipe right confirms it.
            sx, sy = x - touch.start_x, y - touch.start_y
            swipe = swipe_of(sx, sy) if touch.widget.kind == "number" else ("confirm" if confirms(sx, sy) else None)
            if swipe != self.swipes.get(touch.widget.id):
                if swipe:
                    self.swipes[touch.widget.id] = swipe
                else:
                    self.swipes.pop(touch.widget.id, None)
                self.haptic("tick")
                self.on_change(touch.widget)  # only its swipe changed: the app repaints just that
        elif touch.widget.kind == "page" and touch.widget.data.radial:
            touch.choosing = touch.choosing or math.hypot(x - touch.start_x, y - touch.start_y) > RADIAL_PX
            chosen = self._radial_choice(touch.widget, touch)
            if chosen != self.swipes.get(touch.widget.id):
                self.swipes[touch.widget.id] = chosen
                self.haptic("tick")
                self.on_change()
        elif touch.widget.kind == "strip":
            # Sliding down scrolls down, which is a negative wheel value.
            self.strip_rest -= dy * HI_RES_NOTCH / STRIP_PX_PER_NOTCH
            step = int(self.strip_rest)
            if step:
                self.strip_rest -= step
                self.bridge.emit_scroll(0, step)

    def _lift_lost_fingers(self, touch: Touch, ts: float) -> None:
        """touch moved on the trackpad: the other fingers there that have said nothing for as long as it has been
        moving, LOST_LIFT_S at least, lifted (LOST_LIFT_S). Not in a pinch, nor in a pair that may yet turn out to be
        one: one of its fingers may be kept still, and a slow pinch takes a while to spread GESTURE_PX."""
        if self.pair and self.pair.mode in ("", "pinch"):
            return
        for tid, other in list(self.touches.items()):
            if (other is not touch and other.widget is not None and other.widget.kind == "surface"
                    and ts - max(other.seen, touch.moving) > LOST_LIFT_S):
                self._end_touch(tid, inside=False, ts=ts)
                self._expired.add(tid)  # the kernel may reuse its id for a new finger

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
            self._pair_up()
            return
        self.pressed.discard(widget.id)
        self.swipes.pop(widget.id, None)
        self.flash_until[widget.id] = self._clock() + FLASH_S
        # The key a finger held lets go before what its lift sends: a target's Enter comes after its own key.
        if touch.release:
            touch.release()
        if touch.commit:
            touch.commit()
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
        if self.pair and any(now - self.touches[t].seen > STALE_CONTACT_S for t in self.pair.tids if t in self.touches):
            self._end_pair()  # a lost lift must not leave Ctrl held
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
