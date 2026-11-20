"""Two looks: Card (the word big, its meaning scrolling underneath) and Pages (the meaning in lines you can read still)."""
from PIL import ImageColor

from bongo.module import Style

from .words import today, wrap

WHITE, GREY = (255, 255, 255), (150, 156, 166)
PAUSE = 2.0          # seconds the scrolling line waits before it sets off
PAGE_SECONDS = 5     # seconds each page of the meaning stays up


class _Look(Style):
    fps = 20

    def setup(self):
        self.small = self.ctx.fonts("4x6")
        self.text = self.ctx.fonts("5x7")
        self.colour = ImageColor.getrgb(self.settings["colour"])
        self.showing, self.since = None, 0.0             # the word on screen, and when this screen first drew it

    def biggest(self, word, names):
        """The first of these fonts in which ``word`` fits across the canvas."""
        for name in names:
            font = self.ctx.fonts(name)
            if font.width(word) <= self.ctx.width - 2:
                return font
        return self.small


class Card(_Look):
    """The kind of word on top, the word as big as fits, and the meaning scrolling along the bottom."""

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        entry = today(now)
        word = entry["word"].upper()
        if h >= 22:
            self.small.draw(img, 1, 6, entry["kind"].upper(), GREY)
        font = self.biggest(word, ("9x15B", "7x13B", "6x10", "5x7") if h >= 30 else ("6x10", "5x7"))
        top, bottom = (8 if h >= 22 else 0), h - 9                    # the band the word sits in
        baseline = top + (bottom - top + font.cap) // 2
        font.draw(img, max(1, (w - font.width(word)) // 2), baseline, word, self.colour)
        # the meaning: still if it fits, otherwise it waits a moment, scrolls off, and comes round again
        meaning = entry["meaning"]
        wide = self.text.width(meaning)
        if wide <= w - 2:
            x = (w - wide) // 2
        else:
            if self.showing != entry["word"]:                          # a new screen, or a new day: start at the start
                self.showing, self.since = entry["word"], now.timestamp()
            lap = PAUSE + (wide + 8) / self.settings["speed"]
            into = (now.timestamp() - self.since) % lap                # from the clock: no counting frames
            x = 1 - max(0, round((into - PAUSE) * self.settings["speed"]))
        self.text.draw(img, x, h - 2, meaning, WHITE)
        return img


class Pages(_Look):
    """The word small on top, and the meaning in lines underneath, a page at a time."""
    fps = 4

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        entry = today(now)
        word = entry["word"].upper()
        head = self.biggest(word, ("6x10", "5x7"))
        drop = 0 if head.cap >= self.ctx.fonts("6x10").cap else 1     # (the smaller fonts would touch the top edge)
        head.draw(img, 1, head.cap + drop, word, self.colour)
        step = 7
        first = head.cap + drop + 3
        room = max(1, (h - first) // step)                             # lines of meaning that fit under the word
        lines = wrap(entry["meaning"], lambda line: self.small.width(line.upper()) <= w - 2)
        pages = [lines[k:k + room] for k in range(0, len(lines), room)] or [[]]
        page = pages[int(now.timestamp() // PAGE_SECONDS) % len(pages)]
        for k, line in enumerate(page):
            self.small.draw(img, 1, first + 5 + k * step, line.upper(), WHITE)
        if len(pages) > 1:                                             # dots in the corner: which page this is
            at = int(now.timestamp() // PAGE_SECONDS) % len(pages)
            for k in range(len(pages)):
                x = w - 2 - (len(pages) - 1 - k) * 2
                if x >= 0:
                    img.putpixel((x, h - 1), self.colour if k == at else (90, 96, 106))
        return img
