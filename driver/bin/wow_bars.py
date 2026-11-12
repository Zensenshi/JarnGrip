# SPDX-License-Identifier: GPL-3.0-only
"""Reads what the player's WoW action bars hold, as the JarnGrip addon (wow-addon/JarnGrip) saved it, for the number
pad: which spell, item or macro each key of a number and its swipes reaches in the game, and the icon WoW shows for it.

The addon only reads the game (its bindings and action bars) and leaves it to WoW to write its SavedVariables file,
which WoW does when the player logs out, exits or types /reload. Nothing here touches the game either: this reads that
plain-text file from the disk afterwards, as the Raider.IO and WeakAuras companion apps do with theirs.

Plain Python, no GTK: the pad's driver (jarngrip.py) and the Decky backend (main.py) both use it.
"""
from __future__ import annotations

import glob
import os
import re
from pathlib import Path

ADDON_FILE = "JarnGrip.lua"
TABLE = "JarnGripDB"
# Where WoW keeps the addon's file: under its WTF folder, in a Wine or Proton prefix on the Thor. The newest one found
# is used, so a second account or a Classic install does not get in the way of the one played last. A copy put in the
# game's icon folder (synced from a PC that streams the game, say) is looked at too.
PREFIXES = (
    ".local/share/Steam/steamapps/compatdata/*/pfx",
    ".steam/steam/steamapps/compatdata/*/pfx",
    "Games/*", "Games/*/*", "Games/Heroic/Prefixes/*/*",
    ".wine",
    ".local/share/bottles/bottles/*",
    ".var/app/com.usebottles.bottles/data/bottles/bottles/*",
    ".local/share/lutris/runners/wine/*",
)
SD_PREFIXES = ("/run/media/*/steamapps/compatdata/*/pfx", "/run/media/*/*/steamapps/compatdata/*/pfx")
IN_PREFIX = ("drive_c/Program Files (x86)/World of Warcraft/_*_/WTF/Account/*/SavedVariables/" + ADDON_FILE,
             "drive_c/Program Files/World of Warcraft/_*_/WTF/Account/*/SavedVariables/" + ADDON_FILE)
MAX_FILE = 4 * 1024 * 1024  # the addon's file is a few kilobytes; anything this big is not it
# WoW names a key's icon by a number, its file id. A list of the game's icon files ("id;path" a line, as the
# community listfile has them: scripts/wow-icon-names.py makes a small one) turns that into the icon's name, which is
# what the pictures exported from the game are called.
ICON_NAMES = "icon-names.csv"
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".webp")  # what the pad can show (main.PICTURE_TYPES is this one)

# WoW's names for the keys the pad can send, by Linux key code (pad_model and the panel's key list use the codes).
WOW_KEY_NAMES = {
    **{2 + i: str((i + 1) % 10) for i in range(10)}, 12: "-", 13: "=",
    **dict(zip(range(16, 26), "QWERTYUIOP")), **dict(zip(range(30, 39), "ASDFGHJKL")),
    **dict(zip(range(44, 51), "ZXCVBNM")),
    26: "[", 27: "]", 39: ";", 40: "'", 41: "`", 43: "\\", 51: ",", 52: ".", 53: "/",
    1: "ESCAPE", 14: "BACKSPACE", 15: "TAB", 28: "ENTER", 57: "SPACE",
    **{59 + i: f"F{i + 1}" for i in range(10)}, 87: "F11", 88: "F12",
    71: "NUMPAD7", 72: "NUMPAD8", 73: "NUMPAD9", 75: "NUMPAD4", 76: "NUMPAD5", 77: "NUMPAD6",
    79: "NUMPAD1", 80: "NUMPAD2", 81: "NUMPAD3", 82: "NUMPAD0", 83: "NUMPADDECIMAL",
    74: "NUMPADMINUS", 78: "NUMPADPLUS", 55: "NUMPADMULTIPLY", 98: "NUMPADDIVIDE",
    102: "HOME", 103: "UP", 104: "PAGEUP", 105: "LEFT", 106: "RIGHT", 107: "END", 108: "DOWN", 109: "PAGEDOWN",
    110: "INSERT", 111: "DELETE",
}
# Modifier key codes (pad_model.MODIFIERS) in the order WoW writes them in a binding: ALT-CTRL-SHIFT-1.
WOW_MODIFIERS = ((56, "ALT"), (29, "CTRL"), (42, "SHIFT"))
MOD_CODES = {"shift": 42, "ctrl": 29, "alt": 56}
# The number block (pad_model.NUMBER_SLOTS): slot_1 to slot_12 are the keys 1 to 0, - and =, codes 2 to 13. WoW's
# swipes add Shift (up) and Ctrl (down) (pad_model.WOW).
NUMBER_KEYS = {f"slot_{i + 1}": 2 + i for i in range(12)}
WOW_SWIPES = {"up": (42,), "down": (29,)}


def key_name(key: int, mods: tuple = ()) -> str:
    """WoW's name for a key and its modifiers ("CTRL-SHIFT-F1"), or "" for a key WoW's names are not known for here."""
    name = WOW_KEY_NAMES.get(key)
    if not name:
        return ""
    return "".join(f"{word}-" for code, word in WOW_MODIFIERS if code in mods) + name


def _combo(slot_id: str, bindings: dict) -> tuple:
    """What a number sends, as (key, modifiers): the same rule as pad_model.combo_for, for the number block alone (whose
    keys have no modifiers of their own), so that the backend need not load the pad's model."""
    value = bindings.get(slot_id)
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < 248:
        return value, ()
    if isinstance(value, str):
        *names, key = [part.strip().lower() for part in value.split("+")]
        if key.isdigit() and 0 < int(key) < 248 and all(name in MOD_CODES for name in names):
            return int(key), tuple(MOD_CODES[name] for name in names)
    return NUMBER_KEYS[slot_id], ()


def slot_keys(bindings: dict) -> dict:
    """icon id ("slot_5", "slot_5:up", as pad_model.icon_id) -> the key it sends in WoW's words ("5", "SHIFT-5"),
    remaps included. A number remapped to a key WoW's names are not known for here is left out."""
    keys = {}
    for slot_id in NUMBER_KEYS:
        key, mods = _combo(slot_id, bindings if isinstance(bindings, dict) else {})
        for swipe, extra in (("", ()), *WOW_SWIPES.items()):
            name = key_name(key, mods + tuple(code for code in extra if code not in mods))
            if name:
                keys[f"{slot_id}:{swipe}" if swipe else slot_id] = name
    return keys


# ---------------------------------------------------------------------------------------------- the addon's file

def find_file(home: Path, also: Path | None = None) -> Path | None:
    """The addon's SavedVariables file most recently written, in the places WoW keeps it (PREFIXES) or at also."""
    found = [Path(p) for prefix in PREFIXES for inner in IN_PREFIX
             for p in glob.glob(glob.escape(str(home)) + "/" + prefix + "/" + inner)]
    found += [Path(p) for prefix in SD_PREFIXES for inner in IN_PREFIX for p in glob.glob(prefix + "/" + inner)]
    if also is not None:
        found.append(also / ADDON_FILE)
    newest, newest_time = None, -1
    for path in found:
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            continue
        if path.is_file() and mtime > newest_time:
            newest, newest_time = path, mtime
    return newest


class LuaError(ValueError):
    pass


_TOKEN = re.compile(r"""
    (?P<space>\s+|--\[(?P<eq>=*)\[.*?\](?P=eq)\]|--[^\n]*)
  | (?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<number>-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>[{}\[\]=,;])
""", re.VERBOSE | re.DOTALL)
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'",
            "\n": "\n"}


def _unquote(text: str) -> str:
    raw, body, i = bytearray(), text[1:-1], 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            raw += ch.encode("utf-8")
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        digits = re.match(r"\d{1,3}", body[i + 1:])
        if digits:  # \ddd is a byte: WoW writes non-ASCII text as UTF-8 bytes, some of them escaped this way
            raw.append(int(digits.group()) & 0xFF)
            i += 1 + len(digits.group())
        elif nxt == "x" and re.fullmatch(r"[0-9a-fA-F]{2}", body[i + 2:i + 4]):
            raw.append(int(body[i + 2:i + 4], 16))
            i += 4
        else:
            raw += _ESCAPES.get(nxt, nxt).encode("utf-8")
            i += 2
    return raw.decode("utf-8", "replace")


def _tokens(text: str) -> list:
    tokens, pos = [], 0
    while pos < len(text):
        found = _TOKEN.match(text, pos)
        if not found:
            raise LuaError(f"unexpected {text[pos:pos + 10]!r} at {pos}")
        pos = found.end()
        if found.group("space") is None:
            kind = found.lastgroup
            tokens.append((kind, found.group(kind)))
    return tokens


def parse_saved_variables(text: str) -> dict:
    """The globals a SavedVariables file sets ("Name = value" each), as Python values: a table is a dict, its keys
    as Lua has them (strings or numbers). Only data is read: a file with anything else in it is refused."""
    tokens = _tokens(text)
    pos = 0

    def take(kind: str | None = None, value: str | None = None):
        nonlocal pos
        if pos >= len(tokens):
            raise LuaError("unexpected end of file")
        token = tokens[pos]
        if (kind and token[0] != kind) or (value is not None and token[1] != value):
            raise LuaError(f"expected {value or kind}, found {token[1]!r}")
        pos += 1
        return token

    def peek(value: str) -> bool:
        return pos < len(tokens) and tokens[pos][0] == "op" and tokens[pos][1] == value

    def value_():
        kind, text_ = take()
        if kind == "string":
            return _unquote(text_)
        if kind == "number":
            if "x" in text_.lower():
                return int(text_, 16)
            return int(text_) if re.fullmatch(r"-?\d+", text_) else float(text_)
        if kind == "name" and text_ in ("true", "false", "nil"):
            return {"true": True, "false": False, "nil": None}[text_]
        if kind == "op" and text_ == "{":
            table, index = {}, 1
            while not peek("}"):
                if peek("["):
                    take()
                    key = value_()
                    take("op", "]")
                    take("op", "=")
                    table[key] = value_()
                elif pos + 1 < len(tokens) and tokens[pos][0] == "name" and tokens[pos + 1] == ("op", "="):
                    key = take()[1]
                    take()
                    table[key] = value_()
                else:
                    table[index] = value_()
                    index += 1
                if not peek("}"):
                    if not (peek(",") or peek(";")):
                        raise LuaError("expected , or }")
                    take()
            take()
            return table
        raise LuaError(f"unexpected {text_!r}")

    result = {}
    while pos < len(tokens):
        name = take("name")[1]
        take("op", "=")
        result[name] = value_()
    return result


def read_file(path: Path | None) -> dict:
    """What the addon saved: its table, or {} where there is no file or it cannot be read."""
    if path is None:
        return {}
    try:
        if path.stat().st_size > MAX_FILE:
            return {}
        saved = parse_saved_variables(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, LuaError, ValueError, RecursionError):
        return {}
    table = saved.get(TABLE)
    return table if isinstance(table, dict) else {}


def last_character(saved: dict) -> dict:
    """The bars of the character played last: {"character", "spec", "saved", "keys": {WoW key: {name, icon, kind}},
    "jis"}. jis is whether the addon's Japanese keyboard bindings are on (/jarngrip jis): = does what ^ does, so the pad
    labels its = key ^. What the addon saved for = is already what it does then."""
    characters = saved.get("characters")
    who = saved.get("last")
    entry = characters.get(who) if isinstance(characters, dict) and isinstance(who, str) else None
    if not isinstance(entry, dict) or not isinstance(entry.get("keys"), dict):
        return {}
    keys = {key: value for key, value in entry["keys"].items()
            if isinstance(key, str) and isinstance(value, dict) and isinstance(value.get("name"), str)}
    return {"character": who, "spec": entry.get("spec") if isinstance(entry.get("spec"), str) else "",
            "saved": entry.get("saved") if isinstance(entry.get("saved"), (int, float)) else 0, "keys": keys,
            "jis": saved.get("jis") is True}


# ---------------------------------------------------------------------------------------------- pictures

def list_pictures(folder: Path) -> list:
    """The pictures in an icon folder that the pad can show, by file name."""
    try:
        return sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in PICTURE_TYPES)
    except OSError:
        return []


def icon_line(line: str) -> tuple | None:
    """(file id, path) from a line of the community listfile ("136048;interface/icons/spell_nature_lightning.blp")
    when it is an icon's (Interface/Icons), else None. scripts/wow-icon-names.py keeps the same lines."""
    file_id, _, file_path = line.strip().partition(";")
    if file_id.isdigit() and file_path.replace("\\", "/").lower().startswith("interface/icons/"):
        return int(file_id), file_path
    return None


def read_icon_names(path: Path) -> dict:
    """File id -> icon name ("spell_nature_lightning") from a list of the game's icon files (icon_line); the whole
    community listfile works too, slowly: the pad reads it off its drawing thread."""
    names = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                found = icon_line(line)
                if found:
                    names[found[0]] = Path(found[1].replace("\\", "/").lower()).stem
    except OSError:
        pass
    return names


def normalized(name: str) -> str:
    """A name as pictures and spells are compared: case, apostrophes, dashes, underscores and the extension ignored."""
    stem = Path(name).stem if Path(name).suffix.lower() in (*PICTURE_TYPES, ".blp", ".tga") else name
    return re.sub(r"[\W_]+", " ", stem.lower().replace("'", "").replace("’", "")).strip()


def picture_for(entry: dict, pictures: dict, icon_names: dict) -> str:
    """The picture in the icon folder for a key's action: one named for the icon WoW shows (its file id, or its name
    from icon_names, or its path in older clients), else one named for the spell, item or macro. pictures is
    normalized() name -> file name. "" where none is."""
    icon = entry.get("icon")
    wanted = []
    if isinstance(icon, (int, float)) and not isinstance(icon, bool):
        wanted += [str(int(icon)), icon_names.get(int(icon), "")]
    elif isinstance(icon, str):
        wanted.append(icon.replace("\\", "/").rsplit("/", 1)[-1])
    wanted.append(entry.get("name") or "")
    for name in wanted:
        found = pictures.get(normalized(name)) if name else None
        if found:
            return found
    return ""


def pad_bars(bars: dict, bindings: dict, pictures: list, icon_names: dict) -> dict:
    """icon id -> {"name": what the key holds in WoW, "picture": its picture in the icon folder or ""}, for the numbers
    and swipes whose keys hold something on the character's bars (last_character)."""
    by_name: dict = {}
    for picture in sorted(pictures):
        by_name.setdefault(normalized(picture), picture)
    keys = bars.get("keys") or {}
    result = {}
    for icon_id, key in slot_keys(bindings).items():
        entry = keys.get(key)
        if entry:
            result[icon_id] = {"name": entry["name"].strip(), "picture": picture_for(entry, by_name, icon_names)}
    return result


def lookup(found: Path | None, folder: Path, bindings: dict, icon_names: dict) -> tuple:
    """(bars, keys): the bars of the character played last, from the addon's file found (last_character), and what
    each number and swipe shows of them with the pictures in folder (pad_bars). The pad and the icon page both use it,
    so that they agree."""
    bars = last_character(read_file(found))
    return bars, (pad_bars(bars, bindings if isinstance(bindings, dict) else {}, list_pictures(folder), icon_names)
                  if bars else {})


def mtime(path: Path | None) -> int | None:
    try:
        return os.stat(path).st_mtime_ns if path is not None else None
    except OSError:
        return None
