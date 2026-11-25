"""The wall's looks on the panel. Two screens for the playlist: the wall (the drawing as it stands, with the pens of
whoever is drawing on it now) and its history; two that are only ever pop-ups: the wall cutting in while someone
draws, and a drawing that has just been sent. The pictures are the phones' own; the fixed art (the pencil, the
pen's point and the squiggle of an empty wall) is drawn in the Animator, in art/."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from bongo import sprites
from bongo.module import Style

from . import shared
from .wall import PALETTE

ART = Path(__file__).parent / "art"
GREY, DARK, WHITE = (180, 186, 194), (58, 63, 71), (242, 238, 230)
INTRO = 2.0        # s who drew it and when show, on their own, as the wall comes on
SHOWN = 3.0        # s each drawing of the history shows for (after who sent it, if that's shown)
WHO_FOR = 0.8      # s who sent a drawing of the history shows for, before it
HISTORY_INTRO = 1.6
CARD_FROM, CARD_TO = 0.4, 2.6   # s into a sent pop-up that who sent it shows (then the drawing grows)
TAG_STAYS = 3.0    # s a name on the panel stays where it is at least, even if a pen comes under it
# (names, then the line under them): the biggest letters that fit, tried in this order, with the most lines under
CARDS = (("9x15B", "5x7", 1), ("6x10", "5x7", 1), ("9x15B", "5x7", 2), ("6x10", "5x7", 2), ("6x10", "4x6", 1),
         ("5x7", "4x6", 1), ("5x7", "4x6", 2), ("4x6", "4x6", 2))


def dim(colour, k: float):
    return tuple(int(v * max(0.0, min(1.0, k))) for v in colour)


def paint(img: Image.Image, grid: bytes, w: int, h: int, dx: int = 0, k: float = 1.0, grow: float = 1.0) -> None:
    """A picture of the wall in the middle of the panel (dot for dot when they're the same size), ``dx`` along,
    dimmed by ``k``, and grown from the middle by ``grow`` (0 to 1)."""
    if grow <= 0:
        return
    px, W, H = img.load(), img.width, img.height
    ox, oy = (W - w) // 2, (H - h) // 2
    cx, cy = W / 2, H / 2
    colours = [None] + [dim(c, k) for c in PALETTE[1:]]
    for y in range(H):
        sy = int(cy + (y + 0.5 - cy) / grow) - oy if grow < 1 else y - oy
        if not 0 <= sy < h:
            continue
        row = sy * w
        for x in range(W):
            sx = (int(cx + (x + 0.5 - cx) / grow) if grow < 1 else x) - ox - dx
            if 0 <= sx < w and grid[row + sx] and 0 <= x < W:
                px[x, y] = colours[grid[row + sx]]


def centred(img, font, baseline: int, text: str, colour) -> None:
    font.draw(img, (img.width - font.width(text)) // 2, baseline, text, colour)


def _wrap(font, text: str, room: int, most: int) -> list[str] | None:
    lines: list[str] = []
    for word in text.split():
        if lines and font.width(f"{lines[-1]} {word}") <= room:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines if len(lines) <= most and all(font.width(l) <= room for l in lines) else None


def _names(people: list[tuple[str, tuple]]) -> list[list[tuple[str, tuple]]]:
    """Ways to write several names, best first: all on one line, then on two, then the first and how many more.
    Each way is its lines, each line its pieces of (text, colour)."""
    def line(group):
        out = []
        for k, (name, colour) in enumerate(group):
            if k:
                out.append((" & " if k == len(group) - 1 else ", ", GREY))
            out.append((name, colour))
        return out
    ways = [[line(people)]]
    if len(people) > 1:
        half = (len(people) + 1) // 2
        ways.append([line(people[:half]), line(people[half:])])
        ways.append([[people[0], (f" +{len(people) - 1}", GREY)]])
    return ways


def who_card(img, fonts, people: list[tuple[str, tuple]], under: str, k: float = 1.0) -> None:
    """Who, as big as fits, each in their own colour, and a line under them (when, or what they did), in the middle
    of the panel."""
    room = img.width - 2
    ways = _names(people)

    def fits():
        for group in (ways[:2], ways[2:]):           # everyone named, if it can be done; else the first and "+2"
            for big_name, small_name, most in CARDS:
                if most > 1 and img.height < 48:     # (two lines under the names only where there's height for it)
                    continue
                big, small = fonts(big_name), fonts(small_name)
                below = _wrap(small, under, room, most)
                if below is None:
                    continue
                for lines in group:
                    if len(lines) > 1 and img.height < 48:
                        continue
                    height = len(lines) * (big.cap + 2) - 2 + 3 + len(below) * (small.cap + 2) - 2
                    if height <= img.height - 2 and all(sum(big.width(t) for t, _ in l) <= room for l in lines):
                        return big, small, below, lines, height
        big, small = fonts("4x6"), fonts("4x6")
        return big, small, [under], ways[-1], big.cap * 2 + 3

    big, small, below, lines, height = fits()
    top = (img.height - height) // 2
    y = top
    for l in lines:
        y += big.cap
        x = (img.width - sum(big.width(t) for t, _ in l)) // 2
        for text, colour in l:
            x += big.draw(img, x, y, text, dim(colour, k))
        y += 2
    y += 1
    for text in below:
        y += small.cap
        centred(img, small, y, text, dim(GREY, k))
        y += 2


def name_tag(img, fonts, name: str, colour, at: tuple[int, int]) -> int:
    """A name on a black box, in that person's colour, at ``at``. Returns its width."""
    small = fonts("4x6")
    w = small.width(name) + 2
    img.paste((0, 0, 0), (at[0], at[1], at[0] + w, at[1] + 7))
    small.draw(img, at[0] + 1, at[1] + 6, name, colour)
    return w


class Art:
    """The Animator drawings, read once."""
    _read = None

    @classmethod
    def get(cls):
        if cls._read is None:
            point = sprites.read(ART / "wall_point.json")
            squiggle = sprites.read(ART / "wall_squiggle.json").frame(0)
            alpha = squiggle.getchannel("A")
            tops = []
            for x in range(squiggle.width):           # where the line is in each column: the pencil's tip follows it
                ys = [y for y in range(squiggle.height) if alpha.getpixel((x, y))]
                tops.append(ys[len(ys) // 2] if ys else squiggle.height // 2)
            cls._read = {"point": point, "pencil": sprites.read(ART / "wall_pencil.json").frame(0),
                         "squiggle": squiggle, "tops": tops}
        return cls._read


def pens(img, at: float, offset: tuple[int, int], seconds: float) -> None:
    """Each phone drawing now: its point, blinking, where its finger is (and the dot under it in the pen's colour)."""
    point = Art.get()["point"]
    for k, (_, pen) in enumerate(shared.drawing_now(at)):
        if at - pen["at"] > shared.PEN_SHOWS:
            continue
        x, y = pen["x"] + offset[0], pen["y"] + offset[1]
        if pen["c"] and 0 <= x < img.width and 0 <= y < img.height:
            img.putpixel((x, y), PALETTE[pen["c"]])
        frame = point.at(seconds + k * 0.13)
        img.paste(frame, (x - frame.width // 2, y - frame.height // 2), frame)


def names(img, fonts, at: float, offset: tuple[int, int]) -> None:
    """Who's drawing, for the first moments of their spell, on a black strip in a corner (one name) or along the
    top or bottom (two or more). They stay put: they move only when a pen comes under them, and then not again
    for a few seconds (shared.TAGS)."""
    now = [(pen["who"], PALETTE[pen["colour"]], (pen["x"] + offset[0], pen["y"] + offset[1]))
           for _, pen in shared.drawing_now(at) if at - pen["since"] < shared.NAME_SHOWS and at - pen["at"] < shared.PEN_SHOWS]
    if not now:
        return
    small = fonts("4x6")
    widths = [small.width(who) + 2 for who, _, _ in now[:3]]
    width, W, H = sum(widths) + len(widths) - 1, img.width, img.height
    spots = {"bottom right": (W - width, H - 7), "top right": (W - width, 0), "bottom left": (0, H - 7), "top left": (0, 0)}
    if len(now) > 1:
        spots = {"bottom left": spots["bottom left"], "top left": spots["top left"]}
    pens = [p for _, _, p in now]

    def covers(spot):
        x, y = spots[spot]
        return any(x - 1 <= px <= x + width and y - 1 <= py <= y + 7 for px, py in pens)

    def far(spot):
        x, y = spots[spot]
        return min(abs(px - (x + width / 2)) + 2 * abs(py - (y + 3)) for px, py in pens)

    tags, key = shared.TAGS, tuple(who for who, _, _ in now[:3])
    spot = tags.get("spot") if tags.get("names") == key and tags.get("spot") in spots else None
    if spot is None or (covers(spot) and at - tags.get("at", 0.0) >= TAG_STAYS):
        better = sorted(spots, key=lambda s: (covers(s), -far(s)))[0]
        if better != spot:
            spot = better
            tags["at"] = at
    tags.update(spot=spot, names=key)
    x, y = spots[spot]
    for who, colour, _ in now[:3]:
        x += name_tag(img, fonts, who, colour, (x, y)) + 1


def draw_on_me(img, fonts, seconds: float) -> None:
    """An empty wall that says so: DRAW ON ME, where (the Matrix's address), and the squiggle drawn by a little
    pencil, again every 7 s. Side by side on a wide panel, one under another on the rest. The whole pencil always
    shows: there is room for it above the squiggle, under the words, and beyond the squiggle's end."""
    art = Art.get()
    squiggle, pencil, tops = art["squiggle"], art["pencil"], art["tops"]
    font, small = fonts("5x7"), fonts("4x6")
    words, where = "DRAW ON ME", shared.address()
    W, H = img.width, img.height
    reach_up = pencil.height - 1 - min(tops)        # rows the pencil can stand above the squiggle's top row
    reach_right = pencil.width - 1                  # dots it can stand beyond the squiggle's last column
    if W >= 2 * H and W >= 110:                     # wide: the words on the left, the squiggle on the right
        wanted = max(font.width(words), small.width(where))
        between = max(6, min(10, W - 2 - squiggle.width - reach_right - wanted))   # (narrower, before the name scrolls)
        block = min(wanted, W - 2 - between - squiggle.width - reach_right)
        x0 = (W - (block + between + squiggle.width + reach_right)) // 2
        top = (H - (font.cap + 4 + small.cap)) // 2
        font.draw(img, x0 + (block - font.width(words)) // 2, top + font.cap, words, WHITE)
        marquee(img, small, x0, block, top + font.cap + 4 + small.cap, where, dim(GREY, 0.8), seconds)
        sx = x0 + block + between
        sy = max(reach_up, (H - squiggle.height) // 2 + 1)
    else:
        gap = 4 if H < 48 else 8
        lines = [where]
        name, dot, rest = where.partition(".")
        if small.width(where) > W - 2 and H >= 48 and dot and max(small.width(name), small.width(dot + rest)) <= W - 2:
            lines = [name, dot + rest]               # (tall enough: the name, then .LOCAL under it, rather than scroll)
        above = max(gap, reach_up + 1)               # words to squiggle: room for the pencil and a clear row
        height = font.cap + above + squiggle.height + gap + len(lines) * (small.cap + 2) - 2 + small.descent
        top = max(0, (H - height) // 2)
        centred(img, font, top + font.cap, words, WHITE)
        sx, sy = (W - squiggle.width - reach_right) // 2, top + font.cap + above
        for k, line in enumerate(lines):
            marquee(img, small, 1, W - 2, sy + squiggle.height + gap + small.cap + k * (small.cap + 2), line, dim(GREY, 0.8), seconds)
    k = seconds % 7.0
    shown = min(squiggle.width, int(k * 30))
    if shown:
        img.paste(squiggle.crop((0, 0, shown, squiggle.height)), (sx, sy), squiggle.crop((0, 0, shown, squiggle.height)))
    if k < 6.2:                                      # the pencil, its tip on the end of the line, then gone a moment
        tip = (sx + min(shown, squiggle.width - 1), sy + tops[min(shown, squiggle.width - 1)])
        img.paste(pencil, (tip[0], tip[1] - pencil.height + 1), pencil)


def marquee(img, font, x0: int, width: int, baseline: int, text: str, colour, seconds: float) -> None:
    """``text`` in the middle of ``width`` dots from ``x0``; if it's longer, it scrolls through that space (from
    its first letter, held a moment each time round) and never past it."""
    tw = font.width(text)
    if tw <= width:
        font.draw(img, x0 + (width - tw) // 2, baseline, text, colour)
        return
    span, speed, hold = tw + 12, 15.0, 1.5
    t = seconds % (hold + span / speed)
    off = int(max(0.0, t - hold) * speed)
    strip = Image.new("RGB", img.size)
    font.draw(strip, -off, baseline, text, colour)
    font.draw(strip, span - off, baseline, text, colour)
    top, bottom = max(0, baseline - font.cap - 1), min(img.height, baseline + font.descent + 2)
    img.paste(strip.crop((0, top, width, bottom)), (x0, top))


def seen(ctx) -> None:
    """A screen drawn on the panel knows the panel's size: the wall takes it (shared.SEEN, for the task)."""
    if not ctx.preview:
        shared.SEEN["size"] = (ctx.width, ctx.height)


class WallScreen(Style):
    """The newest drawing, as it stands, for its seconds in the playlist; who drew it and when first, for a moment
    (if "Show who drew it" is on). While someone draws on it, every dot shows as it comes, with their pen, and it
    stays on (Stay on while live) until a quiet spell. An empty wall skips its turn, or says "Draw on me"."""
    fps = 20

    def setup(self):
        seen(self.ctx)
        self.began = None

    def render(self, now):
        img = self.ctx.canvas()
        at, wall, settings = time.time(), shared.wall(), self.ctx.module_settings
        if self.began is None:
            self.began = now
        into = (now - self.began).total_seconds()
        live = shared.drawing_now(at)
        self.stay = bool(live) and not self.ctx.preview
        if wall.empty() and not live:
            if shared.setting(settings, "when_empty") == shared.SKIP and not self.ctx.preview:
                self.finished = True                 # nothing on the wall: hand over before it's seen
                return img
            draw_on_me(img, self.ctx.fonts, into)
            return img
        drawers = wall.drawers()
        if not live and into < INTRO and shared.setting(settings, "show_who") and drawers and wall.last:
            fade = 1.0 if into < INTRO - 0.3 else (INTRO - into) / 0.3
            people = [(who, PALETTE[wall.colours.get(device, 3)]) for device, who in drawers]
            who_card(img, self.ctx.fonts, people, shared.when(wall.last["at"], now), fade)
            return img
        paint(img, wall.grid, wall.w, wall.h)
        offset = ((img.width - wall.w) // 2, (img.height - wall.h) // 2)
        pens(img, at, offset, into)
        if shared.setting(settings, "show_who"):
            names(img, self.ctx.fonts, at, offset)
        return img


class HistoryScreen(Style):
    """The last few drawings sent, newest first: who sent it and when, on their own, then the drawing slides in and
    shows for 3 s. Dots at the bottom right say which it is. Nothing sent yet: it skips its turn."""
    fps = 20

    def setup(self):
        seen(self.ctx)
        self.began = None

    def render(self, now):
        img = self.ctx.canvas()
        items = shared.wall().history
        fonts = self.ctx.fonts
        if self.began is None:
            self.began = now
        into = (now - self.began).total_seconds()
        small, words = fonts("4x6"), fonts("5x7")
        if not items:
            if not self.ctx.preview:
                self.finished = True
                return img
            centred(img, small, img.height // 2 - 1, "NOTHING SENT", GREY)
            centred(img, small, img.height // 2 + 6, "YET", GREY)
            return img
        show_who = shared.setting(self.ctx.module_settings, "show_who")
        turns = [(WHO_FOR if show_who and item["who"] else 0.0) for item in items]
        total = HISTORY_INTRO + sum(t + 0.2 + SHOWN for t in turns)
        self.busy = into < total                     # (it goes through them all once, even past its seconds)
        k = into % total
        if k < HISTORY_INTRO:                        # WALL / HISTORY, in the same letters as DRAW ON ME
            top = (img.height - (2 * words.cap + 3)) // 2
            centred(img, words, top + words.cap, "WALL", GREY)
            centred(img, words, top + 2 * words.cap + 3, "HISTORY", WHITE)
            self.marks(img, -1, len(items))
            return img
        q, n = k - HISTORY_INTRO, 0
        while n < len(items) - 1 and q >= turns[n] + 0.2 + SHOWN:
            q -= turns[n] + 0.2 + SHOWN
            n += 1
        item, wall = items[n], shared.wall()
        if q < turns[n]:
            who_card(img, fonts, [(item["who"], PALETTE[wall.colours.get(item["by"], 3)])], shared.when(item["at"], now),
                     1.0 if q < turns[n] - 0.2 else (turns[n] - q) / 0.2)
        else:
            j = q - turns[n]
            slide = round((1 - j / 0.2) * img.width) if j < 0.2 else 0
            paint(img, item["g"], item["w"], item["h"], dx=slide)
        self.marks(img, n, len(items))
        return img

    @staticmethod
    def marks(img, n: int, of: int) -> None:
        """Which drawing this is: a dot for each (the one showing lit; none yet on the title), always in the same
        place, on a black strip at the bottom right."""
        if of < 2:
            return
        width, y = of * 3 - 1, img.height - 1
        x0 = img.width - width - 1
        img.paste((0, 0, 0), (x0 - 1, y - 1, x0 + width + 1, y + 1))
        for k in range(of):
            img.putpixel((x0 + k * 3, y), WHITE if k == n else DARK)
            img.putpixel((x0 + k * 3 + 1, y), WHITE if k == n else DARK)


class LiveLook(WallScreen):
    """The wall cutting in while someone draws (a pop-up of the module's own: shared.LIVE). It shows every dot as
    it comes, the pens, and who's drawing, and ends itself once they've stopped for a quiet spell, or when a
    drawing is sent (its own pop-up follows)."""
    popup_only = True

    def render(self, now):
        at = time.time()
        if self.ctx.popup is None:                   # the import's test screen: the wall as it would show
            return super().render(now)
        live = shared.LIVE
        if self.began is None:
            live["shown"] = at
            self.started = at
        if not shared.drawing_now(at) or live["sent"] > self.started:
            live["ended"] = at
            self.finished = True
        img = self.ctx.canvas()
        if self.began is None:
            self.began = now
        wall = shared.wall()
        paint(img, wall.grid, wall.w, wall.h)
        offset = ((img.width - wall.w) // 2, (img.height - wall.h) // 2)
        pens(img, at, offset, (now - self.began).total_seconds())
        if shared.setting(self.ctx.module_settings, "show_who"):
            names(img, self.ctx.fonts, at, offset)
        self.stay = False
        return img


class SentLook(Style):
    """A drawing just sent, cutting in: a frame runs round the edge in the sender's colour, who sent it (if "Show who
    drew it" is on), then the drawing grows from the middle and stays for the pop-up's seconds."""
    popup_only = True
    fps = 20

    def setup(self):
        seen(self.ctx)
        given = self.ctx.popup or {}
        wall = shared.wall()
        item = next((i for i in wall.history if i["id"] == given.get("id")), None)
        if item is None:                             # (a test screen, or a restart lost it: the wall as it stands)
            item = wall.history[0] if wall.history else {"g": bytes(wall.grid), "w": wall.w, "h": wall.h, "who": ""}
        self.item = item
        self.who = str(given.get("who") or item.get("who") or "")[:8]
        pc = given.get("pc")
        self.colour = PALETTE[pc] if isinstance(pc, int) and 1 <= pc <= 9 else PALETTE[3]
        self.began = None

    def render(self, now):
        img = self.ctx.canvas()
        if self.began is None:
            self.began = now
        k = (now - self.began).total_seconds()
        w, h = img.width, img.height
        around = 2 * (w + h) - 4
        lit = int(around * min(1.0, k / 0.35))
        colour = self.colour if k < CARD_TO else dim(self.colour, 1 - (k - CARD_TO) * 2)
        if any(colour):
            for i in range(lit):                     # the frame runs round, clockwise from the top left
                if i < w:
                    x, y = i, 0
                elif i < w + h - 1:
                    x, y = w - 1, i - w + 1
                elif i < 2 * w + h - 2:
                    x, y = w - 1 - (i - w - h + 2), h - 1
                else:
                    x, y = 0, h - 1 - (i - 2 * w - h + 3)
                img.putpixel((x, y), colour)
        show_who = shared.setting(self.ctx.module_settings, "show_who") and self.who
        if show_who and CARD_FROM < k < CARD_TO:     # who sent it, for a good two seconds, as big as fits
            who_card(img, self.ctx.fonts, [(self.who, self.colour)], "SENT YOU THIS", 1.0 if k < CARD_TO - 0.2 else (CARD_TO - k) / 0.2)
        start = CARD_TO if show_who else CARD_FROM
        if k >= start:
            paint(img, self.item["g"], self.item["w"], self.item["h"], grow=min(1.0, (k - start) / 0.45))
        return img
