"""The pieces every screen shares: the kinds' icons (drawn in the Matrix's Animator, in ``art/``), the small font,
and text in several colours that slides along when it doesn't fit."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from bongo import sprites

from . import kinds

ART = Path(__file__).parent / "art"
FONT = "tom-thumb"              # 3x5 capitals, 4 px a letter
ROW = 6                         # a line of it, with a gap
GREY, DIM, WHITE, WARN, DARK = (154, 161, 172), (100, 104, 112), (242, 238, 230), (250, 204, 21), (44, 49, 57)
SPEED = 12                      # px/s a line slides at
_icons: dict = {}


def icon(name: str) -> Image.Image:
    """One of the drawings in art/ (RGBA), read once."""
    if name not in _icons:
        _icons[name] = sprites.read(ART / f"{name}.json").frame(0)
    return _icons[name]


def kind_icon(kind: str, big: bool) -> Image.Image:
    return icon(f"{kinds.ART.get(kind, 'other')}_{9 if big else 5}")


def colour(kind: str) -> tuple:
    return kinds.KINDS.get(kind, kinds.KINDS["other"])[1]


def dimmed(img: Image.Image, k: float) -> Image.Image:
    """A drawing at ``k`` of its brightness (the see-through parts stay so)."""
    r, g, b, a = img.split()
    return Image.merge("RGBA", [c.point(lambda v: int(v * k)) for c in (r, g, b)] + [a])


def caps(text: str) -> str:
    return kinds.plain(text).upper()


def width(font, parts) -> int:
    return sum(font.width(text) for text, _ in parts)


def parts_at(img: Image.Image, font, x: int, top: int, room: int, parts, offset: int = 0, bg=(0, 0, 0)) -> None:
    """``parts`` ([(text, colour)], one after another) in a ``room``-px window from ``x``, slid ``offset`` px left,
    on ``bg``."""
    lane = Image.new("RGB", (max(1, room), ROW), bg)
    cx = -offset
    for text, ink in parts:
        if text:
            cx += font.draw(lane, cx, 5, text, ink)
    img.paste(lane, (x, top))


def slide(tw: int, room: int, t: float, hold: float = 1.5, speed: float = SPEED) -> tuple[int, float]:
    """How far a line ``tw`` px wide has slid in a ``room``-px window ``t`` seconds after it came on (held at its
    start, slid through once, held at its end), and how long that takes. (The pop-up slides at 20 px/s: one dot a
    frame at the player's 20 frames a second, rounded so it never skips.)"""
    if tw <= room:
        return 0, 0.0
    travel = tw - room
    need = hold * 2 + travel / speed
    k = t % need
    return (0 if k < hold else min(travel, round((k - hold) * speed))), need


def wrap(font, text: str, room: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        while font.width(word) > room:              # (a word too long for a line is cut where it must be)
            n = max(1, room // max(1, font.width("M")))
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:n])
            word = word[n:]
        trial = f"{line} {word}" if line else word
        if font.width(trial) <= room:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def centred(img: Image.Image, font, top: int, text: str, ink) -> None:
    font.draw(img, max(0, (img.width - font.width(text)) // 2), top + 5, text, ink)
