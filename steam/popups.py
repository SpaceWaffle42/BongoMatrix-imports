"""The pop-up's own look (module API 3): when a friend starts a game, a band drops in from the top with their dot,
their name and "STARTED", and the game sliding along under it, then goes back up just before the pop-up's time is
over. On a taller panel the game's capsule art from Steam sits above the band, and on a wide one (128 x 32) to its
right (the controller drawing until Steam's picture has come). The background task hands it who and what in ``self.ctx.popup``; the words it also gives
("Jess started Iron Tide") are what the panel shows instead if this look ever fails."""
from __future__ import annotations

from PIL import Image

from . import pictures, seen
from .screens import GREY, WHITE, Base, art, dot, ink
from .words import POP_DROP, POP_GONE, POP_RISE, slide_offset, slide_time

BAND = 15                       # rows of the band: a line above, two lines of words, a line below
SHADE = (36, 56, 74)            # the band's colour, a dark Steam blue (the mockup's)
PICTURE_FROM = 48               # a panel this tall or taller has room for the game's picture above the band
GAP = 2                         # rows between the picture and the band
SIDE_FROM, SIDE_BAND = 96, 64   # a panel this wide or wider has the picture on the right, the band in the left 64


class Started(Base):
    """A friend has started a game. Only ever a pop-up: never in Add a module or the playlist."""
    popup_only = True
    fps = 20

    def empty(self):
        return False                            # (a pop-up always has something to show)

    def problem(self):
        return None, [], ()                     # (nor is it stopped by what stops the screens: the task asked for it)

    def setup(self):
        super().setup()
        given = self.ctx.popup or {}            # (None on the import's test screen: something sensible anyway)
        self.name = self.words(str(given.get("name") or "FRIEND")[:64])
        self.game = self.words(str(given.get("game") or "A GAME")[:128])
        appid = given.get("appid")
        self.appid = appid if isinstance(appid, int) and not isinstance(appid, bool) and appid > 0 else None

    def render(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        t = self.clock(now)
        shown = min(1.0, t / POP_DROP, (self.left(now) - POP_GONE) / POP_RISE)   # 0: up out of sight, 1: in place
        if self.ctx.popup is None:
            shown = 1.0                         # (the import's test screen draws it once: in place, not on its way)
        if shown <= 0:
            return img
        block = self.block(w, h, max(0.0, t - POP_DROP))   # the picture (on a tall panel) and the band, as one
        top = max(0, (h - block.height) // 2)
        img.paste(block, (0, round(top - (1 - shown) * (top + block.height))))
        return img

    def left(self, now) -> float:
        """Seconds until the pop-up hands over (the player says when); as good as for ever if it hasn't said."""
        ends = self.hand_over_at
        return 1e9 if ends is None else max(0.0, ends - now.timestamp())

    def block(self, w: int, h: int, t: float) -> Image.Image:
        """The band, with the game's picture above it when there's room (a tall panel) or beside it on the right (a
        wide one: the band then keeps to the left 64 dots). They come and go together."""
        picture_h = self.picture_height(w, h)
        if picture_h:
            block = Image.new("RGB", (w, picture_h + GAP + BAND))
            block.paste(self.picture(w, picture_h), (0, 0))
            block.paste(self.band(w, t), (0, picture_h + GAP))
            return block
        if w >= SIDE_FROM:
            pw = w - SIDE_BAND
            ph = min(h, round(pw * 87 / 231))                       # (a capsule is 231 x 87)
            block = Image.new("RGB", (w, max(BAND, ph)))
            block.paste(self.band(SIDE_BAND, t), (0, (block.height - BAND) // 2))
            block.paste(self.picture(pw, ph), (SIDE_BAND, (block.height - ph) // 2))
            return block
        return self.band(w, t)

    def band(self, w: int, t: float) -> Image.Image:
        """The band: its lines, the dot, who and STARTED, then the game. A line too long for its room is held,
        slid through to its end, and held; who goes first, then the game (never both at once)."""
        band = Image.new("RGB", (w, BAND), SHADE)
        line = ink(seen.ONLINE)
        band.paste(line, (0, 0, w, 1))
        band.paste(line, (0, BAND - 1, w, BAND))
        green = dot(seen.IN_GAME)
        band.paste(green, (1, 3), green)
        word = "STARTED"
        room = w - 6 - self.width(word) - 5                        # who, then a clear 4 dots, then STARTED
        if room < 12:                                              # (a very narrow panel: who, and the game under)
            room = w - 7
        else:                                                      # STARTED after who, or at the right if who slides
            fits = self.width(self.name) <= room
            self.text(band, 6 + self.width(self.name) + 5 if fits else w - self.width(word) - 1, 2, word, GREY)
        self.slid(band, 6, 2, room, self.name, ink(seen.IN_GAME), t)
        self.slid(band, 1, 8, w - 2, self.game, WHITE, t - slide_time(self.width(self.name), room))
        return band

    def slid(self, img, x, top, room, text, colour, t):
        """``text`` in ``room`` px from ``x``: still if it fits, otherwise held, slid to its end and held."""
        lane = Image.new("RGB", (max(1, room), img.height))
        stops = [self.font.width(text[:k]) for k in range(len(text))]           # (where each letter begins)
        self.font.draw(lane, -slide_offset(self.width(text), room, t, stops), top + self.font.cap, text, colour)
        img.paste(lane, (x, 0), lane.convert("L").point(lambda v: 255 if v else 0))

    def picture_height(self, w: int, h: int) -> int:
        """Rows for the game's picture above the band: none on a panel shorter than PICTURE_FROM."""
        if h < PICTURE_FROM:
            return 0
        return min(h - BAND - GAP - 2, round(w * 87 / 231))            # (a capsule is 231 x 87: never taller than that)

    def picture(self, w: int, ph: int) -> Image.Image:
        """The game's capsule art from Steam, or the controller on a dark tile until it has come."""
        found = pictures.picture(f"capsule:{self.appid}", w, ph) if self.appid else None
        if found is not None:
            return found.convert("RGB")
        tile = Image.new("RGB", (w, ph), (22, 26, 34))
        pad = art("controller").frame(0)
        tile.paste(pad, ((w - pad.width) // 2, (ph - pad.height) // 2), pad)
        return tile
