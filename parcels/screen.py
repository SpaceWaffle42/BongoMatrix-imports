"""The Parcels screen: one parcel (its nickname, how it's getting on, when, the courier, and a van along a route bar
to the house), several taking turns, and a box on the doorstep once one is delivered. With nothing coming it hands
over before it is seen, so the playlist carries straight on.

The van, house, box, doorstep and tick are Animator drawings in ``art/`` (open them in the Animator to change
them); this code only places, tints and moves them."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image

from bongo import sprites
from bongo.module import Style

from . import store, view

try:                                   # (a Matrix from before bongo.scroll: lines scroll the same, without the waiting)
    from bongo.scroll import HOLD, Scrolls
except ImportError:                    # pragma: no cover - only on an older Matrix
    HOLD = 2.0

    class Scrolls:
        def scrolled(self, key, now, need):
            starts = self.__dict__.setdefault("_starts", {})
            return now.timestamp() - starts.setdefault(key, now.timestamp())

        def line(self, img, font, x, baseline, width, text, ink, now, speed=14, gap=16, times=1, outline=None, key=None):
            tw = font.width(text)
            if tw <= width:
                font.draw(img, x, baseline, text, ink)
                return
            period = tw + gap
            off = int(max(0.0, self.scrolled(key or text, now, 0) - HOLD) * speed) % period
            lane = img.crop((x, 0, x + width, img.height))
            for k in (0, 1):
                font.draw(lane, -off + k * period, baseline, text, ink)
            img.paste(lane, (x, 0))

        def turns(self, key, items, now, seconds, name=str):
            total = sum(max(0.1, float(seconds(i))) for i in items)
            t = now.timestamp() % total
            for item in items:
                span = max(0.1, float(seconds(item)))
                if t < span:
                    return item, t
                t -= span
            return items[-1], 0.0

ART = Path(__file__).parent / "art"
EACH = 5.0             # s each parcel has when they take turns (longer if its nickname needs it to scroll through)
SLIDE = 0.45           # s the next parcel takes to slide in
SPEED = 14             # px/s a long nickname scrolls (bongo.scroll's own)
GREY = (0x9a, 0xa1, 0xac)
WHITE = (0xf2, 0xee, 0xe6)
TRACK = (0x2a, 0x2e, 0x35)
DARK = (0x3a, 0x3f, 0x47)


def dim(colour, k):
    return tuple(int(round(c * k)) for c in colour)


class Parcels(Scrolls, Style):
    fps = 15
    private = True          # what's coming and where it was left: on the panel only, never in a picture on the web

    def setup(self):
        self.font = self.ctx.fonts("tom-thumb")
        van = sprites.read(ART / "parcels_van.json")
        self.van = [van.layer("Van", k) for k in range(len(van.frames))]
        self.trail = [van.layer("Trail", k) for k in range(len(van.frames))]
        house = sprites.read(ART / "parcels_house.json")
        self.house, self.lit = house.layer("House"), house.layer("Lit window")
        self.box = sprites.read(ART / "parcels_box.json").frame(0)
        self.doorstep = sprites.read(ART / "parcels_doorstep.json").frame(0)
        self.tick = sprites.read(ART / "parcels_tick.json").frame(0)
        if not self.parcels(self.ctx.now()):
            self.finished = True               # nothing coming: skipped before its first frame (the Matrix's P6)

    # -- which parcels, and whose turn ---------------------------------------------------------------------------
    def parcels(self, now) -> list[view.Shown]:
        found = view.shown(self.ctx.module_settings or {}, store.shared(), now)
        if not found and self.ctx.preview:             # a picture for the dashboard: an example, said to be one
            found = [view.Shown("EXAMPLE", "EXAMPLE PARCEL", "today", view.WORDS["today"], view.INK["today"], "BY 18:00", "BY 18:00",
                                view.PLACE["today"], True, None, None, None)]
        return found

    def render(self, now):
        w, h = self.ctx.width, self.ctx.height
        found = self.parcels(now)
        if not found:
            self.finished = True                       # nothing coming: hand over before it's seen
            return self.ctx.canvas()
        if len(found) == 1:
            one = found[0]
            into = self.scrolled(("on", one.number, one.state), now, 0)
            return self.card(one, now, into, None)
        item, into = self.turns("parcels", found, now, self.seconds, name=lambda p: p.number)
        k = [p.number for p in found].index(item.number)
        img = self.card(item, now, into, f"{k + 1}/{len(found)}")
        if into < SLIDE:                               # the next one slides in over the last
            dx = round((1 - into / SLIDE) * w)
            before = found[k - 1]
            frame = self.ctx.canvas()
            frame.paste(self.card(before, now, self.seconds(before), f"{(k - 1) % len(found) + 1}/{len(found)}", still=True), (dx - w, 0))
            frame.paste(img, (dx, 0))
            return frame
        return img

    def seconds(self, p: view.Shown) -> float:
        """A parcel's turn: 5 s, or long enough for its nickname and the line under it to scroll through once."""
        need = EACH
        for text, room in ((p.nickname, self.ctx.width - 2 - (self.font.width("9/9") + 3)), (p.line, self.ctx.width - 2),
                           (p.words, self.ctx.width - 1)):
            tw = self.font.width(text)
            if tw - 1 > room:
                need = max(need, HOLD + (tw + 16) / SPEED + 0.5)
        return need

    # -- one parcel ------------------------------------------------------------------------------------------------
    def card(self, p: view.Shown, now, into: float, corner: str | None, still: bool = False) -> Image.Image:
        if p.state == "delivered" and self.ctx.width >= 48 and self.ctx.height >= 26:
            return self.doorstep_card(p, now, into, corner, still)
        w, h = self.ctx.width, self.ctx.height
        img = self.ctx.canvas()
        top = max(0, (h - 32) // 2) if h > 32 else 0
        self.name_row(img, p, now, corner, top, still)
        tall = h >= 30
        status = top + (14 if tall else 13)
        self.text(img, 1, status, w - 1, p.words, p.ink, now, ("words", p.number, p.words), still)   # (to the last column)
        if p.state == "delivered" and self.font.width(p.words) + 10 <= w:
            self.ticked(img, 1 + self.font.width(p.words) + 2, status - 5, into)
        if tall and p.line:
            self.text(img, 1, top + 21, w - 2, p.line, GREY, now, ("line", p.number), still)
        if h >= 21:
            self.route(img, p, now, top + 32 - 3 if tall else h - 3)
        return img

    def name_row(self, img, p, now, corner, top, still):
        w = self.ctx.width
        room = w - 2
        if corner:
            cw = self.font.width(corner)
            self.font.draw(img, w - cw, top + 6, corner, GREY)
            room = w - 2 - cw - 2
        self.text(img, 1, top + 6, room, p.nickname, WHITE, now, ("name", p.number), still)

    def text(self, img, x, baseline, width, text, ink, now, key, still):
        if self.font.width(text) - 1 <= width:         # (a font's width counts the gap after the last letter)
            self.font.draw(img, x, baseline, text, ink)
            return
        if still and self.font.width(text) > width:    # (the one sliding away: held at its start, never scrolled)
            lane = img.crop((x, 0, x + width, img.height))
            self.font.draw(lane, 0, baseline, text, ink)
            img.paste(lane, (x, 0))
            return
        self.line(img, self.font, x, baseline, width, text, ink, now, speed=SPEED, key=key)

    def ticked(self, img, x, y, into):
        """The tick, drawn in from the left over a third of a second."""
        cols = max(0, min(self.tick.width, int((into - 0.3) * 20) + 1)) if into < 2 else self.tick.width
        if cols:
            img.paste(self.tick.crop((0, 0, cols, self.tick.height)), (x, y), self.tick.crop((0, 0, cols, self.tick.height)))

    def route(self, img, p: view.Shown, now, bar_y, pos=None):
        """Posted, at the depot, out for delivery, home: the bar fills up to the van; the house lights when it's in.
        ``pos`` (0 to 3) puts the van at a place of the caller's (the pop-up drives it along once)."""
        w = self.ctx.width
        hx = w - 7
        stops = [2 + round(k * (hx - 2) / 3) for k in range(3)]
        xs = stops + [hx + 3]
        t = now.timestamp()
        if pos is None:
            pos = p.place
            if p.moving:                               # creeping on between stops, driving on when it's out
                pos = 2 + (t * 0.12) % 0.6 if p.state == "out" else p.place + (t * 0.05) % 0.6
        i = min(2, int(pos))
        vx = round(xs[i] + (xs[i + 1] - xs[i]) * (pos - i))
        for x in range(2, hx):
            img.putpixel((x, bar_y), TRACK)
        for x in range(2, max(2, min(vx, hx))):
            img.putpixel((x, bar_y), dim(p.ink, 0.7))
        for k, sx in enumerate(stops):
            colour = p.ink if k <= pos else DARK
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    img.putpixel((sx + dx, bar_y + dy), colour)
        rgba = img.convert("RGBA")
        rgba.alpha_composite(self.house, (hx, bar_y - 7))
        if pos >= 3:
            rgba.alpha_composite(self.lit, (hx, bar_y - 7))
        else:
            k = int(t * 8) % 2 if p.moving else 0
            bob = -1 if p.moving and int(t * 4) % 4 == 0 else 0
            x, y = max(-4, vx - 9), bar_y - 5 + bob      # (the drawing has 4 columns of speed lines before the van;
            #                                              at the start the van itself stays on the panel)
            if p.moving:
                _paste(rgba, self.trail[k], x, y)
            _paste(rgba, self.van[k], x, y)
        img.paste(rgba.convert("RGB"))

    # -- delivered: a box on the doorstep --------------------------------------------------------------------------
    def doorstep_card(self, p: view.Shown, now, into, corner, still) -> Image.Image:
        w, h = self.ctx.width, self.ctx.height
        img = self.ctx.canvas()
        top = max(0, (h - 32) // 2) if h > 32 else 0
        self.name_row(img, p, now, corner, top, still)
        tall = h >= 32
        step_y = top + 9 if tall else h - 20            # the doorstep's top row
        k = into if not still else 9.0
        drop = min(1.0, k / 0.5)
        rgba = img.convert("RGBA")
        _paste(rgba, self.doorstep, 1, step_y)
        _paste(rgba, self.box, 11, step_y + 1 + round(12 * drop))
        img.paste(rgba.convert("RGB"))
        if k > 0.8:
            x = 21
            first = top + 14 if tall else top + 12
            self.font.draw(img, x, first, "DELIVERED", p.ink)
            self.ticked(img, x, first + 3, k - 0.8)
            when = p.when
            if when:
                self.font.draw(img, x + 9, first + 8, when, WHITE)
            said = p.where or (f"BY {p.courier}" if p.courier else "")
            if said:
                self.text(img, x, first + 15 if tall else first + 13, w - x - 1, said, GREY, now, ("where", p.number), still)
        return img


def _paste(rgba: Image.Image, picture: Image.Image, x: int, y: int) -> None:
    """``alpha_composite`` that may hang over the edges (a van driving in, a narrow panel)."""
    if picture is None:
        return
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(picture.width, rgba.width - x), min(picture.height, rgba.height - y)
    if right <= left or bottom <= top:
        return
    rgba.alpha_composite(picture.crop((left, top, right, bottom)), (x + left, y + top))
