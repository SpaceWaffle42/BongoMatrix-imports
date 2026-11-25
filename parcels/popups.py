"""The pop-up's own look (module API 3), as in the mockup: a band drops in from the top over whatever was playing,
in the colour of the news. Out for delivery: "OUT TODAY", the van driving in with the parcel's nickname
beside it, and the time slot and courier under them. Delivered: the tick and "DELIVERED", the box dropping in with
the nickname, and when and where it was left, and by whom. It goes back up just before the pop-up's time is over.

The background task hands it what to say in ``self.ctx.popup`` (``tracker.pop_up_data``); the words it gives too
("New Boots (DPD), 12:15–13:15") are what the panel shows instead if this look ever fails. On a tall panel (64 x 64)
the screen's own scene sits below the band, on a wide one (128 x 32) beside it. The van, box, tick, house and
doorstep are the module's Animator drawings in ``art/``: this code only places and moves them."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from bongo import sprites
from bongo.module import Context, Style

from .screen import DARK, GREY, TRACK, WHITE, Parcels, _paste, dim
from .view import INK, Shown

ART = Path(__file__).parent / "art"
BAND = 21                       # rows: a line, the heading, the parcel, the line under it, a line
SHORT = 15                      # rows on a panel too short for that: a line, the heading, the parcel, a line
TALL_FROM, ROUTE_ROWS, SCENE_GAP = 48, 12, 3   # a panel this tall has the scene below the band (rows, and the gap)
DOOR_ROWS = 32                  # rows of the doubled doorstep shown on a tall panel (its bottom: the step and the box)


def tall_top(h: int) -> int:
    """The band's top row on a tall panel, the same for both pop-ups: where out for delivery's band and route sit in
    the middle."""
    return max(0, (h - (BAND + SCENE_GAP + ROUTE_ROWS * 2)) // 2)

WIDE_FROM, WIDE_BAND = 96, 64   # a panel this wide has the route on the right, the band in the left 64 dots
SHADE = {"out": (0x2e, 0x28, 0x10), "delivered": (0x12, 0x30, 0x1e)}   # the band: the news's colour, very dark
TITLE = {"out": "OUT TODAY", "delivered": "DELIVERED"}   # (as the words' title says: "Out today")
DROP, RISE, GONE = 0.4, 0.5, 0.2   # s the band takes to drop in, to go back up, and empty at the very end
HOLD, SPEED = 1.0, 20           # s a long line is held at its start and at its end; px/s between (one dot a frame
#                                 at the player's 20 frames a second, so it moves evenly)
LETTER = 4                      # px a letter of the small font takes (tom-thumb)
SHORTEST, LONGEST = 10.0, 20.0  # s a pop-up is up: never more than 20 (the Matrix allows 3 to 30)
SAMPLE = {"kind": "out", "name": "NEW BOOTS", "under": "12:15-13:15 COURIER"}   # (the import's test screen)


class Parcel(Style):
    """A parcel is out for delivery, or has been delivered. Only ever a pop-up: never in Add a module or the
    playlist."""
    popup_only = True
    private = True              # (as the screen: on the panel only, a padlocked stand-in in pictures on the web)
    fps = 20                    # (the pace the player asks a pop-up at: a slower look is shown at half its rate)

    def setup(self):
        self.font = self.ctx.fonts("tom-thumb")
        given = self.ctx.popup if isinstance(self.ctx.popup, dict) else SAMPLE
        self.kind = given.get("kind") if given.get("kind") in TITLE else "out"
        self.name = _caps(given.get("name"), 60) or "YOUR PARCEL"
        self.under = _caps(given.get("under"), 80)
        van = sprites.read(ART / "parcels_van.json")
        self.van = [van.layer("Van", k) for k in range(len(van.frames))]
        self.trail = [van.layer("Trail", k) for k in range(len(van.frames))]
        self.box = sprites.read(ART / "parcels_box.json").frame(0)
        self.tick = sprites.read(ART / "parcels_tick.json").frame(0)
        self.doorstep = sprites.read(ART / "parcels_doorstep.json").frame(0)
        self.house = sprites.read(ART / "parcels_house.json").layer("House")
        self.began, self.scene = None, None

    def render(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        if self.began is None:
            self.began = now.timestamp()
        t = now.timestamp() - self.began
        shown = min(1.0, t / DROP, (self.left(now) - GONE) / RISE)   # 0: up out of sight, 1: in place
        if self.ctx.popup is None:
            shown, t = 1.0, 3.0                 # (the import's test screen draws it once: settled, not on its way)
        if shown <= 0:
            return img
        block = self.block(w, h, max(0.0, t - DROP), now)
        top = tall_top(h) if h >= TALL_FROM else max(0, (h - block.height) // 2)   # (tall: the band at one row)
        img.paste(block, (0, round(top - (1 - shown) * (top + block.height))))
        return img

    def block(self, w: int, h: int, t: float, now) -> Image.Image:
        """The band, and where there's room the parcel's scene from the screen with it, coming and going together:
        below it on a tall panel (64 x 64: the van driving along the route to the house, or the box landing on the
        doorstep), beside it on a wide one (128 x 32: the route and the house, the band in the left 64 dots)."""
        if h >= TALL_FROM:
            if self.kind == "delivered":                              # (the doubled door, its top rows left off to fit
                scene, gap = self.doorstep_scene(w, t, 2, DOOR_ROWS), 1   # above a bottom margin, the band where it is
            else:                                                         # for out for delivery)
                scene, gap = self.big_route(w, ROUTE_ROWS * 2, now), SCENE_GAP
            block = Image.new("RGB", (w, BAND + gap + scene.height))
            block.paste(self.band(w, BAND, t), (0, 0))
            block.paste(scene, (0, BAND + gap))
            return block
        if w >= WIDE_FROM and h >= BAND:
            block = Image.new("RGB", (w, BAND))
            block.paste(self.band(WIDE_BAND, BAND, t), (0, 0))
            block.paste(self.route_scene(w - WIDE_BAND - 1, BAND, now), (WIDE_BAND, 0))   # (a dot clear of the edge)
            return block
        return self.band(w, BAND if h >= BAND else SHORT, t)       # (a panel under 21 dots high: no line under)

    def drive(self, now) -> float:
        """How far the van has come, 0 (the depot) to 1 (just short of the house): once, over the pop-up's time."""
        t = now.timestamp() - (self.began or now.timestamp())
        ends = self.hand_over_at
        drive = max(3.0, (ends - self.began - 2.0) if ends is not None and self.began else 8.0)
        return min(1.0, max(0.0, t - DROP) / drive)

    def route_scene(self, w: int, rows: int, now) -> Image.Image:
        """The route bar from the screen (screen.Parcels.route): out for delivery, the van driving once from the
        depot to just short of the house over the pop-up's time (no jumping back); delivered, the bar full, the
        house's window lit and the box at its door."""
        if self.scene is None or self.scene.ctx.width != w or self.scene.ctx.height != rows:
            self.scene = Parcels(Context(width=w, height=rows, tz=self.ctx.tz, fonts=self.ctx.fonts), {})
        out = self.kind == "out"
        shown = Shown("", self.name, self.kind, TITLE[self.kind], INK[self.kind], self.under, "", 2 if out else 3, out,
                      None, None, None)
        pos = 1 + 1.6 * self.drive(now) if out else 3.0                # (stops short of the house)
        img = Image.new("RGB", (w, rows))
        bar_y = (rows - 10) // 2 + 8                                   # (the house and bar, 10 rows, in the middle)
        self.scene.route(img, shown, now, bar_y, pos=pos)
        if not out:                                                    # the box, left at the door
            rgba = img.convert("RGBA")
            _paste(rgba, self.box, w - 7 - self.box.width - 1, bar_y - self.box.height)
            img = rgba.convert("RGB")
        return img

    def big_route(self, w: int, rows: int, now) -> Image.Image:
        """The route on a tall panel: the van and the house at twice their size (the Animator's drawings doubled) on a
        line two dots thick with small stops, the van moving a dot at a time at its own pace, from the depot to two dots
        short of the house, never over it."""
        img = Image.new("RGBA", (w, rows), (0, 0, 0, 255))
        ink = INK[self.kind]
        house = _double(self.house)
        hx, line = w - house.width - 1, rows - 3                       # the house at the right; the line's top row
        _paste(img, house, hx, line + 2 - house.height)
        k = int(now.timestamp() * 8) % 2                               # the wheels turn
        van, trail = _double(self.van[k]), _double(self.trail[k])
        start, end = 0, hx - 3 - van.width                             # its left edge: from the panel's edge to 3 dots short
        vx = round(start + (end - start) * self.drive(now))
        front = vx + van.width
        for x in range(2, hx - 1):                                     # the line: lit up to the van
            colour = dim(ink, 0.7) if x < front else TRACK
            img.paste(colour + (255,), (x, line, x + 1, line + 2))
        for sx in (2, 2 + (hx - 4) // 3, 2 + 2 * (hx - 4) // 3):      # three stops, small: 4 dots square,
            if sx + 4 <= vx + 8 or sx >= front:                        # but none under the van (its body: 8 dots in)
                img.paste((ink if sx < front else DARK) + (255,), (sx, line - 1, sx + 4, line + 3))
        _paste(img, trail, vx, line - van.height + 1)
        _paste(img, van, vx, line - van.height + 1)
        return img.convert("RGB")

    def doorstep_scene(self, w: int, t: float, scale: int = 1, rows: int | None = None) -> Image.Image:
        """The doorstep from the screen, with the box dropping onto it (``scale`` times the size; ``rows``: only its
        bottom rows, the door's top left off)."""
        step, box = (_double(self.doorstep), _double(self.box)) if scale == 2 else (self.doorstep, self.box)
        img = Image.new("RGBA", (w, step.height), (0, 0, 0, 255))
        x = (w - step.width) // 2
        _paste(img, step, x, 0)
        _paste(img, box, x + 10 * scale, scale + round(12 * scale * min(1.0, t / 0.5)))
        img = img.convert("RGB")
        return img.crop((0, img.height - rows, w, img.height)) if rows and rows < img.height else img

    def left(self, now) -> float:
        """Seconds until the pop-up hands over (the player says when); as good as for ever if it hasn't said."""
        ends = self.hand_over_at
        return 1e9 if ends is None else max(0.0, ends - now.timestamp())

    def band(self, w: int, rows: int, t: float) -> Image.Image:
        ink = INK[self.kind]
        band = Image.new("RGB", (w, rows), SHADE[self.kind])
        band.paste(ink, (0, 0, w, 1))
        band.paste(ink, (0, rows - 1, w, rows))
        rgba = band.convert("RGBA")
        if self.kind == "out":
            k = int(t * 8) % 2                                       # the wheels turn
            vx = round(-14 + 15 * min(1.0, t / 0.6))                 # the van drives in from the left, then idles on
            bob = -1 if t > 0.6 and int(t * 4) % 4 == 0 else 0
            _paste(rgba, self.trail[k], vx, 8 + bob)
            _paste(rgba, self.van[k], vx, 8 + bob)
            name_x, heading_x = 17, 1                                  # (a clear dot after the van; OUT TODAY a dot in)
        else:
            cols = max(0, min(self.tick.width, int(t * 20) + 1))    # the tick, drawn in from the left
            if cols:
                part = self.tick.crop((0, 0, cols, self.tick.height))
                rgba.alpha_composite(part, (1, 2))
            drop = min(1.0, t / 0.4)                                 # the box drops into place, in its own row
            row = rgba.crop((0, 7, w, 14))                           # (so it never passes over the tick)
            _paste(row, self.box, 1, round(2 - 6 * (1 - drop)))
            rgba.paste(row, (0, 7))
            name_x, heading_x = 9, 10
        band.paste(rgba.convert("RGB"))
        self.heading(band, ink, heading_x, TITLE[self.kind])
        room = w - name_x - 1                                        # the nickname slides first, then the line under
        self.slide(band, name_x, 8, room, self.name, WHITE, t)
        if rows < BAND:
            return band
        if self.under:
            self.slide(band, 1, 14, w - 2, self.under, GREY, t - slide_time(self.font.width(self.name) - 1, room))
        else:                                                        # nothing more to say: a quieter rule instead
            band.paste(dim(ink, 0.35), (1, 16, w - 1, 17))
        return band

    def heading(self, band, ink, x, words) -> None:
        """The heading, from ``x`` (only its first word on a panel too narrow for it all)."""
        room = band.width - x
        while self.font.width(words) - 1 > room and len(words) > 3:
            words = words.split(" ")[0] if " " in words else words[:-1]
        self.font.draw(band, x, 2 + self.font.cap, words, ink)

    def slide(self, band, x, top, room, text, ink, t):
        """``text`` in ``room`` px from ``x``: still if it fits; otherwise held at its start, slid through to its
        end, and held there (``t``: seconds since its turn began)."""
        if room <= 0:
            return
        width = self.font.width(text) - 1
        lane = band.crop((x, 0, x + room, band.height))
        stops = [self.font.width(text[:k]) for k in range(len(text))]           # (where each letter begins)
        self.font.draw(lane, -slide_offset(width, room, t, stops), top + self.font.cap, text, ink)
        band.paste(lane, (x, 0))


def slide_time(width: int, room: int) -> float:
    """Seconds a line ``width`` px wide takes to be read in ``room`` px: held, slid to its end, held (0: it fits)."""
    return 0.0 if width <= room else HOLD * 2 + (width - room) / SPEED


def slide_offset(width: int, room: int, t: float, stops=()) -> int:
    """How far a long line has slid: held, then a dot a frame (rounded, so never 0 then 2), and it ends on the first
    letter (``stops``: where each begins) that shows the whole end of the line, never on half a letter."""
    if width <= room:
        return 0
    end = min((s for s in stops if s >= width - room), default=width - room)
    return min(end, round(max(0.0, t - HOLD) * SPEED))


def seconds_for(data: dict) -> float:
    """How long the pop-up is up: long enough for the nickname and then the line under it to be read through once
    each on a 64-dot-wide panel, between SHORTEST and LONGEST. Only what the look needs: if it fails, the Matrix gives
    its words the time they need to be read (module API 3)."""
    def wide(text):
        return max(0, len(_caps(text, 80)) * LETTER - 1)
    name_room = 64 - (17 if data.get("kind") == "out" else 9) - 1
    need = DROP + slide_time(wide(data.get("name")), name_room) + slide_time(wide(data.get("under")), 62) + RISE + GONE + 1.0
    return min(LONGEST, max(SHORTEST, math.ceil(need * 10) / 10))   # (rounded up: never a moment short)


def _double(picture: Image.Image) -> Image.Image:
    """An Animator drawing at twice its size, dot for dot."""
    return picture.resize((picture.width * 2, picture.height * 2), Image.NEAREST)


def _caps(value, most: int) -> str:
    return " ".join(str(value or "").upper().split())[:most]
