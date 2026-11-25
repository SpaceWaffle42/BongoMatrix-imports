"""Words typed on the page, written on the wall in the Matrix's own letters: as big as fits, in the middle, on as
few lines as it takes."""
from __future__ import annotations

from PIL import Image

from bongo.fonts import Fonts

FONTS = ("6x10", "5x7", "4x6")   # biggest first
MOST = 60                        # letters a page may send


def lines_for(font, words: list[str], room: int) -> list[str] | None:
    """The words wrapped into lines no wider than ``room``, or None if one word alone is too wide."""
    lines: list[str] = []
    for word in words:
        if font.width(word) > room:
            return None
        if lines and font.width(f"{lines[-1]} {word}") <= room:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def dots(text: str, w: int, h: int, fonts: Fonts | None = None) -> list[int]:
    """The dots of ``text`` on a wall ``w`` x ``h``, as x, y, x, y...: the biggest letters it fits in, centred.
    Too much for the smallest letters: as many lines as fit."""
    fonts = fonts or Fonts()
    words = " ".join(str(text).upper().split())[:MOST].split()
    if not words:
        return []
    for name in FONTS:
        font = fonts(name)
        pitch = font.cap + font.descent + 1
        lines = lines_for(font, words, w - 2)
        if lines is not None and len(lines) * pitch - 1 <= h - 2:
            break
    else:
        font = fonts(FONTS[-1])
        pitch = font.cap + font.descent + 1
        lines = (lines_for(font, words, w - 2) or [" ".join(words)])[:max(1, (h - 1) // pitch)]
    img = Image.new("1", (w, h), 0)
    top = (h - (len(lines) * pitch - 1)) // 2 + font.cap
    for k, line in enumerate(lines):
        font.draw(img, (w - font.width(line)) // 2, top + k * pitch, line, 1)
    out = []
    for x in range(w):                    # column by column, left to right: it reads as writing on the panel
        for y in range(h):
            if img.getpixel((x, y)):
                out += (x, y)
    return out


def clear_of(points: list[int], grid, w: int, h: int, most: int = 12) -> list[int]:
    """The words moved the least it takes (at most ``most`` dots along, a few up or down) so that no dot of theirs
    touches the drawing already there; where there's no such place, where they were."""
    if not points:
        return points
    near = set()                                   # every dot drawn on, and the dots round it
    for k, v in enumerate(grid):
        if v:
            x, y = k % w, k // w
            near.update((x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    xs, ys = points[0::2], points[1::2]
    if not near.intersection(zip(xs, ys)):
        return points
    tries = sorted(((dx, dy) for dx in range(-most, most + 1) for dy in range(-4, 5)), key=lambda d: (abs(d[0]) + 2 * abs(d[1]), d))
    for dx, dy in tries:
        if min(xs) + dx < 0 or max(xs) + dx >= w or min(ys) + dy < 0 or max(ys) + dy >= h:
            continue
        if not any((x + dx, y + dy) in near for x, y in zip(xs, ys)):
            return [v + (dx if k % 2 == 0 else dy) for k, v in enumerate(points)]
    return points
