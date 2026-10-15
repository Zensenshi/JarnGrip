# SPDX-License-Identifier: GPL-3.0-only
"""Paints the pad with cairo, in one of a few themes.

The Classic theme (dark stone buttons, gold trim and cream serif lettering) follows the second-screen pad of
AYN-Thor-WoW-Launcher; Charcoal and Dark are flat; Game Glass shows a picture through frosted glass buttons. Everything is drawn in code (no artwork), and nothing here needs
GTK: paint() takes any cairo context that is 1240 by 1080 units.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields

import cairo

from pad_model import BODY_Y, KEY_TEXT, KEY_WORD_TEXT, MARGIN, PANEL_PAD, THEME_IDS, THEME_Y, H, W, PadController, Widget


def _rgb(value: int) -> tuple:
    return ((value >> 16) & 0xFF) / 255.0, ((value >> 8) & 0xFF) / 255.0, (value & 0xFF) / 255.0


@dataclass(frozen=True)
class Theme:
    """Colors are given as 0xRRGGBB and kept as cairo's (r, g, b)."""
    background: int
    key: tuple          # (top, bottom) of a resting button's gradient
    raised: tuple       # the number block stands out a little
    pressed: tuple
    border: int
    border_active: int  # the trim of a pressed button
    border_bright: int  # the heavier outline of a locked button
    border_muted: int   # the trim of a resting secondary button
    inner: tuple | None  # (normal, muted) second, thin trim line inside the first; None for a single line
    accent: int         # group backing, scroll strip
    text: int
    text_pressed: int
    glow: int
    font: str               # a bundled font (driver/fonts) or a generic family
    fallback: str = "sans-serif"  # if the bundled font could not be loaded
    trim: float = 1.0       # scales the trim widths
    rounding: float = 1.0   # scales the corner radii
    shadow: float = 0.55    # how dark the drop shadow under a resting button is
    sheen: float = 0.07     # the light across a button's top half
    shade: float = 0.22     # the dark along its bottom edge
    danger: tuple = (0xE5484D, 0xA8282D)  # (top, bottom) of a Cancel fan
    danger_text: int = 0xFFFFFF
    glass: bool = False     # frosted glass over the backdrop picture instead of colored faces
    text_shadow: float = 0.0  # a dark shadow under lettering, for text over a picture

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, int) and not isinstance(value, bool):
                object.__setattr__(self, f.name, _rgb(value))
            elif isinstance(value, tuple):
                object.__setattr__(self, f.name, tuple(_rgb(v) for v in value))


THEMES = {
    "classic": Theme(
        background=0x0A0807, key=(0x30261D, 0x17120E), raised=(0x45382A, 0x271D15), pressed=(0x784E16, 0x462C0C),
        border=0xB08C40, border_active=0xB08C40, border_bright=0xDEBA64,
        border_muted=0x5B4825, inner=(0x5E461C, 0x362914),  # muted: the gold blended 55 % into the key face
        accent=0xB08C40, text=0xECDEBA, text_pressed=0xFFECB4, glow=0xFFE08A, font="Cinzel", fallback="serif",
        danger=(0x8E2B22, 0x5C1810), danger_text=0xFFECB4),
    # Blue-black, slate buttons, and bright blue for what is pressed or on.
    "charcoal": Theme(
        background=0x0E141B, key=(0x3A414D, 0x2A2F38), raised=(0x4B5361, 0x3A404C), pressed=(0x1A9FFF, 0x1488E0),
        border=0x58616F, border_active=0x1A9FFF, border_bright=0xFFFFFF, border_muted=0x434A56, inner=None,
        accent=0x1A9FFF, text=0xDCDEDF, text_pressed=0xFFFFFF, glow=0x67C1F5, font="sans-serif",
        trim=0.5, rounding=0.5, sheen=0.08),
    # Dark: pure black, so that the OLED panel stays dark around the buttons; a pressed button turns white. A shadow
    # would not show on black, so the buttons stand out by their faces and sheen, shaded darker toward the bottom.
    "dark": Theme(
        background=0x000000, key=(0x262626, 0x0E0E0E), raised=(0x323232, 0x161616), pressed=(0xEDEDED, 0xD0D0D0),
        border=0x404040, border_active=0xEDEDED, border_bright=0xFFFFFF, border_muted=0x2E2E2E, inner=None,
        accent=0x8E8E93, text=0xF2F2F2, text_pressed=0x000000, glow=0xFFFFFF, font="sans-serif",
        trim=0.6, rounding=0.8, shadow=0.0, sheen=0.08, shade=0.32),
    # A picture (or a built-in color wash) behind frosted glass: each button blurs and darkens what is behind it just
    # enough for white lettering to read, and a pressed one lights up.
    "glass": Theme(
        background=0x0B0E14, key=(0x000000, 0x000000), raised=(0x000000, 0x000000), pressed=(0xFFFFFF, 0xFFFFFF),
        border=0xFFFFFF, border_active=0xFFFFFF, border_bright=0xFFFFFF, border_muted=0xFFFFFF, inner=None,
        accent=0xFFFFFF, text=0xFFFFFF, text_pressed=0x14161C, glow=0xFFFFFF, font="Nunito",
        trim=0.5, shadow=0.35, sheen=0.12, shade=0.10, glass=True, text_shadow=0.6),
}
assert set(THEMES) == set(THEME_IDS)
LOW = 0xE5484D  # a warning red: low battery, a cancelled swipe
GLASS_TINT = {"rest": 0.30, "muted": 0.36, "raised": 0.22}  # how much a glass button darkens what is behind it
GLASS_LIT = 0.45      # a pressed glass button frosts over white, translucent, with dark lettering
BACKDROP_DIM = 0.15   # the picture itself is dimmed a little, so that a busy one does not fight the buttons

# The backdrop of the current paint: (sharp, blurred) screen-sized surfaces, and the burn-in shift it is drawn under.
_backdrop: tuple | None = None
_shift = (0.0, 0.0)
_tab_size = 0.0  # the page tabs' shared lettering size in the current paint
LOADED_FONTS: set = set()  # the bundled font families the app managed to load; set at start-up


def _font(t: Theme) -> str:
    return t.font if t.font in LOADED_FONTS or t.font in ("serif", "sans-serif") else t.fallback


def _blur(src, width: int, height: int, halvings: int):
    """A soft blur without a blur filter: halve the picture a few times, then double it back up the same way. Each
    step filters, so the result is smooth instead of blocky."""
    sizes = [(width, height)]
    for _ in range(halvings):
        w, h = sizes[-1]
        sizes.append((max(1, w // 2), max(1, h // 2)))
    surface = src
    for (w0, h0), (w1, h1) in list(zip(sizes, sizes[1:])) + list(zip(sizes[::-1], sizes[::-1][1:])):
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w1, h1)
        cr = cairo.Context(out)
        cr.scale(w1 / w0, h1 / h0)
        cr.set_source_surface(surface, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.get_source().set_extend(cairo.EXTEND_PAD)
        cr.paint()
        surface = out
    return surface


def make_backdrop(src, src_w: int, src_h: int, halvings: int = 3) -> tuple:
    """(sharp, blurred) screen-sized surfaces from a picture of any size, scaled to cover the screen and centered."""
    sharp = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(sharp)
    scale = max(W / src_w, H / src_h)
    cr.translate((W - src_w * scale) / 2, (H - src_h * scale) / 2)
    cr.scale(scale, scale)
    cr.set_source_surface(src, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    return sharp, _blur(sharp, W, H, halvings)


def default_backdrop(halvings: int = 3) -> tuple:
    """The backdrop when no picture is chosen: a deep blue wash with three soft colored glows."""
    src = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(src)
    base = cairo.LinearGradient(0, 0, W, H)
    base.add_color_stop_rgb(0, *_rgb(0x1B1036))
    base.add_color_stop_rgb(1, *_rgb(0x071A2B))
    cr.set_source(base)
    cr.paint()
    for cx, cy, r, color, alpha in ((260, 300, 460, 0x7B2FF7, 0.55), (1010, 240, 420, 0x00B4D8, 0.45),
                                    (720, 920, 480, 0xFF6B35, 0.35)):
        glow = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
        glow.add_color_stop_rgba(0, *_rgb(color), alpha)
        glow.add_color_stop_rgba(1, *_rgb(color), 0)
        cr.set_source(glow)
        cr.paint()
    return src, _blur(src, W, H, halvings)


def _round_rect(cr, x: float, y: float, w: float, h: float, r: float) -> None:
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, math.pi * 1.5)
    cr.close_path()


def _panel(cr, t: Theme, x: float, y: float, w: float, h: float, strong: bool) -> None:
    """The faint backing behind a group of buttons; the number block's is the strongest."""
    _round_rect(cr, x, y, w, h, 26 * t.rounding)
    cr.set_source_rgba(*t.accent, 0x21 / 255.0 if strong else 0x0F / 255.0)
    cr.fill_preserve()
    cr.set_source_rgba(*t.accent, 0x59 / 255.0 if strong else 0x2E / 255.0)
    cr.set_line_width(2)
    cr.stroke()


def _face(cr, t: Theme, x: float, y: float, w: float, h: float, radius: float = 22, active: bool = False,
          emphasized: bool = False, muted: bool = False, raised: bool = False) -> None:
    """One button face. active is the pressed look, emphasized adds the heavy bright outline used for "locked",
    muted dims the trim of a resting secondary button."""
    radius *= t.rounding
    if t.glass:
        _glass_face(cr, t, x, y, w, h, radius, active, emphasized, muted, raised)
        return
    if not active and t.shadow:
        # Two offset layers make a soft drop shadow (cairo has no blur), which lifts the button off the background.
        for drop, grow, alpha in ((7.0, 2.0, 0.45), (4.0, 0.0, 0.8)):
            _round_rect(cr, x - grow, y + drop - grow, w + 2 * grow, h + 2 * grow, radius + grow)
            cr.set_source_rgba(0, 0, 0, t.shadow * alpha)
            cr.fill()
    top, bottom = t.pressed if active else t.raised if raised else t.key
    gradient = cairo.LinearGradient(0, y, 0, y + h)
    gradient.add_color_stop_rgb(0, *top)
    gradient.add_color_stop_rgb(1, *bottom)
    _round_rect(cr, x, y, w, h, radius)
    cr.set_source(gradient)
    cr.fill()

    # Light from above: a sheen over the top half and a darker bottom edge on a resting button; a pressed one is
    # pushed in, so its top is in shadow instead.
    shading = cairo.LinearGradient(0, y, 0, y + h)
    if active:
        shading.add_color_stop_rgba(0, 0, 0, 0, t.shade)
        shading.add_color_stop_rgba(0.35, 0, 0, 0, 0)
    else:
        shading.add_color_stop_rgba(0, 1, 1, 1, t.sheen)
        shading.add_color_stop_rgba(0.5, 1, 1, 1, 0)
        shading.add_color_stop_rgba(0.75, 0, 0, 0, 0)
        shading.add_color_stop_rgba(1, 0, 0, 0, t.shade)
    _round_rect(cr, x, y, w, h, radius)
    cr.set_source(shading)
    cr.fill()

    dim = muted and not active and not emphasized
    width = (7.0 if emphasized else 3.0 if dim else 5.0) * t.trim
    _round_rect(cr, x + width / 2, y + width / 2, w - width, h - width, radius - width / 2)
    cr.set_source_rgb(*(t.border_bright if emphasized else t.border_active if active else t.border_muted if dim
                        else t.border))
    cr.set_line_width(width)
    cr.stroke()

    if t.inner:
        inset = width + 3.0
        _round_rect(cr, x + inset, y + inset, w - 2 * inset, h - 2 * inset, radius - inset)
        cr.set_source_rgb(*t.inner[1 if dim else 0])
        cr.set_line_width(1.5)
        cr.stroke()


def _frost(cr, t: Theme, path, tint: tuple) -> None:
    """Fill path() with frosted glass: the blurred backdrop, lined up with the picture behind it, under a tint
    ((r, g, b), alpha)."""
    cr.save()
    path()
    cr.clip()
    if _backdrop:
        cr.set_source_surface(_backdrop[1], -_shift[0], -_shift[1])
    else:
        cr.set_source_rgb(*t.background)
    cr.paint()
    cr.set_source_rgba(*tint[0], tint[1])
    cr.paint()
    cr.restore()


def _glass_face(cr, t: Theme, x: float, y: float, w: float, h: float, radius: float, active: bool, emphasized: bool,
                muted: bool, raised: bool) -> None:
    """Frosted glass: the blurred backdrop inside the button, darkened (lightened when pressed), with a sheen across
    the top and a thin light rim."""
    if not active:
        for drop, grow, alpha in ((6.0, 2.0, 0.45), (3.0, 0.0, 0.8)):
            _round_rect(cr, x - grow, y + drop - grow, w + 2 * grow, h + 2 * grow, radius + grow)
            cr.set_source_rgba(0, 0, 0, t.shadow * alpha)
            cr.fill()
    tint = ((1.0, 1.0, 1.0), GLASS_LIT) if active else \
        ((0.0, 0.0, 0.0), GLASS_TINT["raised" if raised else "muted" if muted else "rest"])
    _frost(cr, t, lambda: _round_rect(cr, x, y, w, h, radius), tint)
    sheen = cairo.LinearGradient(0, y, 0, y + h)
    sheen.add_color_stop_rgba(0, 1, 1, 1, t.sheen)
    sheen.add_color_stop_rgba(0.5, 1, 1, 1, 0)
    sheen.add_color_stop_rgba(1, 0, 0, 0, t.shade)
    _round_rect(cr, x, y, w, h, radius)
    cr.set_source(sheen)
    cr.fill()
    width = 3.5 if emphasized else 1.5
    _round_rect(cr, x + width / 2, y + width / 2, w - width, h - width, radius - width / 2)
    cr.set_source_rgba(1, 1, 1, 0.95 if emphasized else 0.6 if active else 0.18 if muted else 0.28)
    cr.set_line_width(width)
    cr.stroke()


_fitted: dict = {}  # (font, lines, size, room) -> the size that fits: every paint fits the same labels again


def _fit(cr, t: Theme, lines: list, size: float, max_w: float) -> float:
    """The largest size, from size down in steps of 2, at which the widest line fits in max_w. Leaves the context set
    to that font and size."""
    font = _font(t)
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    key = (font, tuple(lines), size, round(max_w))
    fitted = _fitted.get(key)
    if fitted is None:
        fitted = size
        while True:
            cr.set_font_size(fitted)
            if fitted <= 14 or max(cr.text_extents(line).width for line in lines) <= max_w:
                break
            fitted -= 2
        if len(_fitted) > 4096:  # keep the cache bounded, whatever labels come and go
            _fitted.clear()
        _fitted[key] = fitted
    cr.set_font_size(fitted)
    return fitted


def _text(cr, t: Theme, cx: float, cy: float, lines: list, size: float, color: tuple, max_w: float,
          alpha: float = 1.0) -> None:
    """Centered lettering. It shrinks until the widest line fits."""
    size = _fit(cr, t, lines, size, max_w)
    step = size * 1.15
    # The baseline sits a third of the letter height under the line's middle, the same for every label.
    top = cy - (len(lines) - 1) * step / 2 + size * 0.34
    # A shadow helps light lettering over a picture; dark lettering (on a pressed glass button) needs none.
    light = sum(color) / 3 > 0.5
    layers = [((0.0, max(1.5, size * 0.05)), (0.0, 0.0, 0.0), t.text_shadow * alpha)] if t.text_shadow and light else []
    for (dx, dy), rgb, a in layers + [((0.0, 0.0), color, alpha)]:
        cr.set_source_rgba(*rgb, a)
        baseline = top
        for line in lines:
            ext = cr.text_extents(line)
            cr.move_to(cx - ext.x_bearing - ext.width / 2 + dx, baseline + dy)
            cr.show_text(line)
            baseline += step


def _wrap(label: str) -> list:
    """In the narrow two-column pages a long, multi-word label drops its last word onto a second line."""
    cut = label.rfind(" ")
    if len(label) > 8 and cut > 0 and "/" not in label:
        return [label[:cut], label[cut + 1:]]
    return [label]


def _glow(cr, t: Theme, cx: float, cy: float, radius: float) -> None:
    gradient = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
    gradient.add_color_stop_rgba(0, *t.glow, 0.28)
    gradient.add_color_stop_rgba(1, *t.glow, 0.0)
    cr.set_source(gradient)
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.fill()


def _icon(cr, name: str, cx: float, cy: float, s: float, color: tuple) -> None:
    """Line icons, drawn so that no font has to carry them. s is half the icon's size."""
    cr.set_source_rgb(*color)
    cr.set_line_width(max(3.0, s * 0.16))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    if name == "settings":
        for i in range(8):
            a = i * math.pi / 4
            cr.move_to(cx + math.cos(a) * s * 0.62, cy + math.sin(a) * s * 0.62)
            cr.line_to(cx + math.cos(a) * s * 0.95, cy + math.sin(a) * s * 0.95)
        cr.stroke()
        cr.arc(cx, cy, s * 0.55, 0, 2 * math.pi)
        cr.stroke()
        cr.arc(cx, cy, s * 0.18, 0, 2 * math.pi)
        cr.fill()
    elif name == "trackpad":
        _round_rect(cr, cx - s, cy - s * 0.78, 2 * s, s * 1.56, s * 0.22)
        cr.move_to(cx - s, cy + s * 0.28)
        cr.line_to(cx + s, cy + s * 0.28)
        cr.move_to(cx, cy + s * 0.28)
        cr.line_to(cx, cy + s * 0.78)
        cr.stroke()
    elif name == "keyboard":
        _round_rect(cr, cx - s * 1.1, cy - s * 0.7, s * 2.2, s * 1.4, s * 0.2)
        cr.stroke()
        for row in (-0.3, 0.02):
            for col in (-0.66, -0.22, 0.22, 0.66):
                cr.arc(cx + col * s, cy + row * s, s * 0.08, 0, 2 * math.pi)
                cr.fill()
        cr.move_to(cx - s * 0.5, cy + s * 0.38)
        cr.line_to(cx + s * 0.5, cy + s * 0.38)
        cr.stroke()
    elif name == "backspace":
        cr.move_to(cx - s, cy)
        cr.line_to(cx - s * 0.4, cy - s * 0.6)
        cr.line_to(cx + s, cy - s * 0.6)
        cr.line_to(cx + s, cy + s * 0.6)
        cr.line_to(cx - s * 0.4, cy + s * 0.6)
        cr.close_path()
        cr.move_to(cx + s * 0.05, cy - s * 0.25)
        cr.line_to(cx + s * 0.55, cy + s * 0.25)
        cr.move_to(cx + s * 0.55, cy - s * 0.25)
        cr.line_to(cx + s * 0.05, cy + s * 0.25)
        cr.stroke()
    else:  # an arrow: left, right, up or down
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[name]
        tip_x, tip_y = cx + dx * s * 0.8, cy + dy * s * 0.8
        cr.move_to(cx - dx * s * 0.8, cy - dy * s * 0.8)
        cr.line_to(tip_x, tip_y)
        # the head: two strokes back from the tip, one to each side
        for side in (-1, 1):
            cr.move_to(tip_x, tip_y)
            cr.line_to(tip_x - dx * s * 0.5 + side * dy * s * 0.5, tip_y - dy * s * 0.5 + side * dx * s * 0.5)
        cr.stroke()


def _strip(cr, t: Theme, w: Widget, touched: bool) -> None:
    """The scroll strip: a faint fixed line with a small arrow at each end, brighter under a finger."""
    cx = w.x + w.w / 2
    cr.set_source_rgba(*t.accent, 0xA0 / 255.0 if touched else 0x4D / 255.0)
    _round_rect(cr, cx - 3, w.y + 48, 6, w.h - 96, 3)
    cr.fill()
    cr.set_source_rgba(*t.accent, 0xC0 / 255.0 if touched else 0x70 / 255.0)
    for tip, base in ((w.y + 14, w.y + 30), (w.y + w.h - 14, w.y + w.h - 30)):
        cr.move_to(cx, tip)
        cr.line_to(cx - 11, base)
        cr.line_to(cx + 11, base)
        cr.close_path()
        cr.fill()


def _bubble(cr, t: Theme, w: Widget, bw: float, bh: float, label: str, size: float, color: tuple) -> None:
    """A label in a bubble just above a button, where the thumb on the button does not cover it."""
    bx = min(max(w.x + w.w / 2 - bw / 2, MARGIN / 2), W - MARGIN / 2 - bw)
    by = max(w.y - bh - 6, 4.0)
    cr.set_source_rgba(0, 0, 0, 0.45)  # a soft shadow lifts it off whatever it covers
    _round_rect(cr, bx + 4, by + 8, bw, bh, 22 * t.rounding)
    cr.fill()
    _face(cr, t, bx, by, bw, bh, radius=22, raised=True, emphasized=True)
    _text(cr, t, bx + bw / 2, by + bh / 2, [label], size, color, bw - 24)


def _preview(cr, t: Theme, w: Widget, label: str) -> None:
    """What a key typed, enlarged above it."""
    bw, bh = max(w.w * 1.3, 140.0), w.h * 1.2
    _bubble(cr, t, w, bw, bh, label, bh * 0.55, t.text)


FAN_SPREAD = math.radians(40)   # each side of the fan's middle
FAN_REACH = 230.0               # how far the fan reaches past the finger
FAN_ROUND = 30.0                # the radius of its rounded outer corners
FAN_TIP = 22.0                  # the radius of its round tip, under the finger
FAN_LABEL_PAD = 40.0            # room between the lettering and the fan's sides
FAN_DIRECTIONS = {"shift": -math.pi / 2, "ctrl": math.pi / 2, "cancel": math.pi}  # up, down, left
FAN_MIN_TEXT = 22.0             # the smallest lettering a fan shrinks to where the screen ends
FAN_SIDE_EXTRA = 60.0           # a sideways fan's extra length, for lettering that runs along it
FAN_CLEAR = 100.0               # a fan's lettering starts at least this far out: the swiping finger is closer in
FAN_FADE = 0.55                 # a fan is solid from this far out, in key sizes: about the key's edge


def _fan_reach(cx: float, cy: float, angle: float) -> float:
    """How far a fan from (cx, cy) may reach in its direction before the screen ends."""
    dx, dy = round(math.cos(angle)), round(math.sin(angle))  # the directions are straight up, down or left
    room = {(0, -1): cy, (0, 1): H - cy, (-1, 0): cx, (1, 0): W - cx}[(dx, dy)]
    return room - MARGIN / 2


def _fan_path(cr, cx: float, cy: float, tip: float, outer: float, a0: float, a1: float, r: float) -> None:
    """A petal from the point (cx, cy) out to radius outer, between angles a0 and a1: a round tip of radius tip at the
    narrow end and its two outer corners rounded to radius r, each corner a small circle touching both sides."""
    d_out = math.asin(r / (outer - r))
    middle = (a0 + a1) / 2
    tip_at = tip / math.sin((a1 - a0) / 2)  # the tip's circle touches both straight sides

    def at(radius: float, angle: float) -> tuple:
        return cx + radius * math.cos(angle), cy + radius * math.sin(angle)

    cr.new_path()
    cr.arc(*at(outer - r, a0 + d_out), r, a0 - math.pi / 2, a0 + d_out)
    cr.arc(cx, cy, outer, a0 + d_out, a1 - d_out)
    cr.arc(*at(outer - r, a1 - d_out), r, a1 - d_out, a1 + math.pi / 2)
    cr.arc(*at(tip_at, middle), tip, a1 + math.pi / 2, a0 + 1.5 * math.pi)
    cr.close_path()


def _shape(cr, t: Theme, path, inset_path, fill, cancel: bool) -> None:
    """A fan, or a label's tag, dressed like the theme's pressed buttons: path() and inset_path() trace its outline and
    the trim just inside it, fill is the gradient of its face (glass draws its own frost instead)."""
    if t.shadow:
        cr.save()
        cr.translate(4, 8)
        path()
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.fill()
        cr.restore()
    if t.glass:
        _frost(cr, t, path, (_rgb(LOW), 0.7) if cancel else ((1.0, 1.0, 1.0), GLASS_LIT))
        path()
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        cr.stroke()
        return
    path()
    cr.set_source(fill)
    cr.fill()
    path()
    # The theme's trim: Classic's gold; on the flat themes the edge takes the face's own color.
    cr.set_source_rgb(*(t.border_active if t.inner or not cancel else t.danger[0]))
    cr.set_line_width(5 * t.trim)
    cr.stroke()
    if t.inner:
        inset_path()
        cr.set_source_rgb(*t.inner[0])
        cr.set_line_width(1.5)
        cr.stroke()


def _swipe_fan(cr, t: Theme, w: Widget, swipe: str) -> None:
    """What lifting the finger will send from a swiped number: a rounded fan opening from the button in the swipe's
    direction, with the modifier written large in it. Where the screen ends first (Ctrl on the bottom row), the fan is
    shorter and its lettering smaller, but it stays whole and on the screen."""
    cancel = swipe == "cancel"
    label = {"shift": "Shift", "ctrl": "Ctrl", "cancel": "Cancel"}[swipe]
    color = t.danger_text if cancel else t.text_pressed
    top, bottom = t.danger if cancel else t.pressed
    cx, cy = w.x + w.w / 2, w.y + w.h / 2
    angle = FAN_DIRECTIONS[swipe]
    sideways = abs(math.cos(angle)) > 0.5
    inner = min(w.w, w.h) * 0.3  # the fan reaches FAN_REACH past this; its tip is under the finger
    # A sideways fan is longer: its lettering runs along it, not across.
    outer = min(inner + FAN_REACH + (FAN_SIDE_EXTRA if sideways else 0.0), _fan_reach(cx, cy, angle))
    label_at = outer - min(FAN_REACH * 0.4, outer * 0.38)
    a0, a1 = angle - FAN_SPREAD, angle + FAN_SPREAD
    trim = 5 * t.trim + 4  # where the inner trim line runs

    fill = cairo.RadialGradient(cx, cy, inner, cx, cy, outer)
    fill.add_color_stop_rgba(0, *top, 0.97)
    fill.add_color_stop_rgba(1, *bottom, 0.97)
    # The inner trim is the same petal with its point moved along the middle, so that each side runs `trim` inside.
    step = trim / math.sin(FAN_SPREAD)
    ix, iy = cx + step * math.cos(angle), cy + step * math.sin(angle)
    # The fan is drawn aside, then laid down through a mask that fades it into the key: clear at the key's middle,
    # solid by its edge. Shadow, trim and glass fade with it.
    cr.push_group()
    _shape(cr, t, lambda: _fan_path(cr, cx, cy, FAN_TIP, outer, a0, a1, FAN_ROUND),
           lambda: _fan_path(cr, ix, iy, FAN_TIP, outer - trim - step, a0, a1, FAN_ROUND - trim / 2), fill, cancel)
    cr.pop_group_to_source()
    fade = cairo.RadialGradient(cx, cy, FAN_TIP, cx, cy, min(w.w, w.h) * FAN_FADE)
    fade.add_color_stop_rgba(0, 0, 0, 0, 0)
    fade.add_color_stop_rgba(1, 0, 0, 0, 1)
    cr.mask(fade)
    size = max(FAN_MIN_TEXT, min(46.0, (outer - label_at) * 1.2))
    if sideways:
        # The lettering runs along the fan: it starts clear of the finger, where the fan has grown tall enough for
        # the letters, and ends FAN_LABEL_PAD short of the rounded end.
        start = max(FAN_CLEAR, (size * 0.6 + FAN_LABEL_PAD / 2) / math.tan(FAN_SPREAD))
        end = outer - FAN_LABEL_PAD
        max_w, label_at = end - start, (start + end) / 2
    else:
        # Up or down: the lettering runs across the fan, FAN_LABEL_PAD from its sides where it sits.
        max_w = 2 * label_at * math.sin(FAN_SPREAD) - 2 * FAN_LABEL_PAD
    _text(cr, t, cx + label_at * math.cos(angle), cy + label_at * math.sin(angle), [label], size, color,
          max(max_w, 60.0))


def _status(cr, t: Theme, w: Widget, info: tuple | None) -> None:
    """The clock, and under it the battery: an outline filled to its charge, a bolt while charging."""
    if not info:
        return
    clock, percent, charging = info
    cx = w.x + w.w / 2
    _text(cr, t, cx, w.y + w.h * 0.32, [clock], 32, t.text, w.w - 8)
    if percent is None:
        return
    low = percent <= 15 and not charging
    color = _rgb(LOW) if low else t.text
    bw, bh = 34.0, 17.0
    _text(cr, t, cx + 22, w.y + w.h * 0.74, [f"{percent}%"], 22, color, w.w - 60, alpha=0.85)
    bx, by = cx - 62, w.y + w.h * 0.74 - bh / 2
    cr.set_source_rgba(*color, 0.85)
    cr.set_line_width(2)
    _round_rect(cr, bx, by, bw, bh, 3)
    cr.stroke()
    cr.rectangle(bx + bw, by + 5, 3, bh - 10)  # the terminal nub
    cr.fill()
    cr.rectangle(bx + 3, by + 3, (bw - 6) * max(0, min(100, percent)) / 100, bh - 6)
    cr.fill()
    if charging:
        cr.set_source_rgb(*t.background)
        mx, my = bx + bw / 2, by + bh / 2
        cr.move_to(mx + 2, my - 8)
        cr.line_to(mx - 5, my + 1)
        cr.line_to(mx, my + 1)
        cr.line_to(mx - 2, my + 8)
        cr.line_to(mx + 5, my - 1)
        cr.line_to(mx, my - 1)
        cr.close_path()
        cr.fill()


def _widget(cr, t: Theme, pad: PadController, w: Widget) -> None:
    cx, cy = w.x + w.w / 2, w.y + w.h / 2
    kind = w.kind
    lit = pad.lit(w)
    if kind == "strip":
        _strip(cr, t, w, w.id in pad.pressed)
    elif kind == "status":
        _status(cr, t, w, pad.status_info)
    elif kind == "surface":
        _face(cr, t, w.x, w.y, w.w, w.h, radius=34)
        if pad.hint_alpha > 0:  # the hint fades away after a while: a fixed line of text is what burns in first
            _text(cr, t, cx, cy, ["Move  ·  tap to click  ·  two fingers scroll"], 26, t.text, w.w - 160,
                  alpha=0.3 * pad.hint_alpha)
    elif kind == "tab":
        active = pad.view == "pad" and pad.page == w.data
        _face(cr, t, w.x, w.y, w.w, w.h, radius=24, active=active, muted=True)
        _text(cr, t, cx, cy, [w.label], _tab_size, t.text_pressed if active else t.text, w.w - 28)
    elif kind == "mode":
        active = pad.view == w.data
        _face(cr, t, w.x, w.y, w.w, w.h, radius=24, active=active, muted=True)
        _icon(cr, w.data, cx, cy, 24, t.text_pressed if active else t.text)
    elif kind == "mod":
        active = w.data in pad.held_mods
        _face(cr, t, w.x, w.y, w.w, w.h, radius=24, active=active, emphasized=w.data in pad.locked_mods, muted=True)
        _text(cr, t, cx, cy, [w.label], w.size, t.text_pressed if active else t.text, w.w - 28)
    elif kind == "mouse":
        locked = pad.mouse[w.data].locked
        _face(cr, t, w.x, w.y, w.w, w.h, radius=24, active=lit or locked, emphasized=locked)
        if pad.glows(w):
            _glow(cr, t, cx, cy, w.h * 0.7)
        _text(cr, t, cx, cy, [w.label], w.size, t.text_pressed if lit or locked else t.text, w.w - 28)
    elif kind == "key":
        spec = w.data
        shift_key = spec.action == "shift"
        active = lit or (shift_key and pad.kb_shift != "off")
        _face(cr, t, w.x, w.y, w.w, w.h, radius=18, active=active, emphasized=shift_key and pad.kb_shift == "caps")
        color = t.text_pressed if active else t.text
        if spec.icon:
            _icon(cr, spec.icon, cx, cy, 26, color)
        else:
            label = pad.key_label(spec)
            _text(cr, t, cx, cy, [label], KEY_TEXT if len(label) == 1 else KEY_WORD_TEXT, color, w.w - 20)
    elif kind == "theme":
        # Each theme button is drawn in its own theme, so it doubles as a sample.
        own = THEMES[w.data]
        chosen = pad.theme == w.data
        _round_rect(cr, w.x - 6, w.y - 6, w.w + 12, w.h + 12, 28 * own.rounding)
        cr.set_source_rgb(*own.background)
        cr.fill()
        _face(cr, own, w.x, w.y, w.w, w.h, radius=24, emphasized=chosen, raised=chosen, muted=not chosen)
        _text(cr, own, cx, cy, [w.label], w.size, own.text, w.w - 28)
    else:  # page, number, unstick, close
        number = kind == "number"
        _face(cr, t, w.x, w.y, w.w, w.h, active=lit, muted=not number, raised=number)
        _text(cr, t, cx, cy, _wrap(w.label) if w.wrap else [w.label], w.size, t.text_pressed if lit else t.text,
              w.w - 28)


def _swipe_guide(cr, t: Theme, pad: PadController) -> None:
    """Over the number block, where there is room: which way to swipe for what, above the column it fits best. It
    fades with the other hints (burn-in protection)."""
    numbers = [w for w in pad.widgets if w.kind == "number"]
    room = min(w.y for w in numbers) - PANEL_PAD - BODY_Y if numbers else 0
    if room < 30 or pad.hint_alpha <= 0:
        return
    y = BODY_Y + room / 2
    color = tuple(c * 0.6 * pad.hint_alpha + b * (1 - 0.6 * pad.hint_alpha) for c, b in zip(t.text, t.background))
    # The arrows are drawn, not typed: the bundled fonts have no arrow characters.
    for w, word, arrow, side in zip(numbers[:3], ("Cancel", "Shift", "Ctrl"), ("left", "up", "down"), (-1, -1, -1)):
        cx = w.x + w.w / 2
        _text(cr, t, cx - side * 14, y, [word], 24, t.text, w.w - 50, alpha=0.6 * pad.hint_alpha)
        half = cr.text_extents(word).width / 2
        _icon(cr, arrow, cx - side * 14 + side * (half + 22), y, 11, color)


def _settings(cr, t: Theme, pad: PadController) -> None:
    _text(cr, t, 620, 190, ["JarnGrip"], 52, t.border_bright, 1100)
    y = 280.0
    for line in pad.info_lines:
        _text(cr, t, 620, y, [line], 28, t.text, 1140, alpha=0.85)
        y += 48
    if pad.last_touch:
        x, ty, where = pad.last_touch
        _text(cr, t, 620, y + 12, [f"Last touch: {x:.0f}, {ty:.0f}" + (f"  on {where}" if where else "")], 26, t.text,
              1140, alpha=0.6)
    _text(cr, t, 620, THEME_Y - 40, ["Theme"], 30, t.text, 1140, alpha=0.85)
    _text(cr, t, 620, 880, ["Closing the pad gives the bottom screen back to what was running before it."], 26, t.text,
          1140, alpha=0.6)


def paint(cr, pad: PadController) -> None:
    global _backdrop, _shift
    t = THEMES.get(pad.theme, THEMES["classic"])
    _backdrop, _shift = pad.backdrop, pad.shift
    cr.set_source_rgb(*t.background)
    cr.paint()
    if t.glass and _backdrop:
        cr.set_source_surface(_backdrop[0], 0, 0)
        cr.paint()
        cr.set_source_rgba(0, 0, 0, BACKDROP_DIM)
        cr.paint()
    # Burn-in protection: everything drifts a pixel or two, and is dimmed when the pad has not been touched for a while.
    cr.save()
    cr.translate(*pad.shift)
    _paint_pad(cr, t, pad)
    cr.restore()
    if pad.brightness < 1.0:
        cr.set_source_rgba(0, 0, 0, 1.0 - pad.brightness)
        cr.paint()


def _paint_pad(cr, t: Theme, pad: PadController) -> None:
    global _tab_size
    tabs = [w for w in pad.widgets if w.kind == "tab"]
    # The page tabs share one lettering size: the largest at which every one of them fits.
    _tab_size = min((_fit(cr, t, [w.label], w.size, w.w - 28) for w in tabs), default=0)
    for x, y, w, h, strong in pad.panels:
        _panel(cr, t, x, y, w, h, strong)
    # The scroll strip lies on the trackpad surface, so it is painted after it.
    for widget in sorted(pad.widgets, key=lambda w: w.kind == "strip"):
        _widget(cr, t, pad, widget)
    if pad.view == "settings":
        _settings(cr, t, pad)
    elif pad.view == "pad":
        _swipe_guide(cr, t, pad)
    # Key previews last: they reach over the keys above and over the trackpad.
    for widget in pad.widgets:
        if widget.kind == "key" and widget.data.action == "input" and pad.lit(widget):
            _preview(cr, t, widget, pad.key_typed.get(widget.id) or pad.key_label(widget.data))
        elif widget.kind == "number" and widget.id in pad.swipes:
            _swipe_fan(cr, t, widget, pad.swipes[widget.id])
