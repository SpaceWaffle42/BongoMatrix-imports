"""Three looks of the same timer. Each ``render`` draws one frame from ``now`` and returns it."""
from PIL import ImageColor, ImageDraw

from bongo.module import Style

from .timer import phase

WHITE, GREY = (255, 255, 255), (120, 126, 136)


def dim(colour, by):
    return tuple(int(c * by) for c in colour)


class _Look(Style):
    """What the three looks share: the fonts, the colours and the phase."""
    fps = 5    # a timer needs few frames a second; lower is kinder to the Matrix

    def setup(self):                     # runs once, when the screen starts
        self.small = self.ctx.fonts("4x6")
        self.work = ImageColor.getrgb(self.settings["work_colour"])
        self.rest = ImageColor.getrgb(self.settings["rest_colour"])

    def now_phase(self, now):
        p = phase(now, self.settings["work"], self.settings["rest"])
        colour = self.work if p.working else self.rest
        self.ink = WHITE                                # the colour of the digits
        if p.ending and now.microsecond >= 500_000:     # the last ten seconds: the colours swap, twice a second
            colour, self.ink = WHITE, colour
        return p, colour, "FOCUS" if p.working else "BREAK"

    def digits(self, room):
        """The biggest font whose MM:SS fits ``room`` pixels across."""
        for name in ("10x20", "9x15B", "7x13B", "5x7"):
            font = self.ctx.fonts(name)
            if font.width("00:00") <= room:
                return font
        return self.small


class Countdown(_Look):
    """Big digits, what you're doing above them, and a bar underneath that runs down."""

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height           # never assume 64x32: the safe area can be smaller
        p, colour, label = self.now_phase(now)
        self.small.draw(img, 1, 6, label, colour)
        font = self.digits(w - 2) if h >= 30 else self.ctx.fonts("7x13B" if h >= 22 and w >= 40 else "5x7")
        baseline = (h + font.cap) // 2 + 2
        font.draw(img, (w - font.width(p.clock)) // 2, min(baseline, h - 4), p.clock, self.ink)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, h - 2, w - 1, h - 1], fill=dim(colour, 0.25))
        filled = round(w * p.part_left)
        if filled:
            draw.rectangle([0, h - 2, filled - 1, h - 1], fill=colour)
        return img


class Tomato(_Look):
    """A tomato that empties as you work, and ripens again over the break."""

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        p, colour, label = self.now_phase(now)
        size = max(4, min(h - 8, w // 2 - 10))           # the tomato's width and height
        left, top = 2, (h - size) // 2 + 2
        draw = ImageDraw.Draw(img)
        draw.ellipse([left, top, left + size, top + size], fill=dim(colour, 0.22))
        # how much is full: all of it at the start of work, none at the end; the break fills it again
        full = p.part_left if p.working else 1 - p.part_left
        level = top + round(size * (1 - full))
        body = img.copy()
        ImageDraw.Draw(body).ellipse([left, top, left + size, top + size], fill=colour)
        img.paste(body.crop((left, level, left + size + 1, top + size + 1)), (left, level))
        stalk = (70, 170, 80)
        mid = left + size // 2
        draw.line([mid, top - 3, mid, top], fill=stalk)
        draw.line([mid - 2, top, mid + 2, top], fill=stalk)
        room = w - (left + size + 4)
        font = self.digits(room)
        x = left + size + 4 + max(0, (room - font.width(p.clock)) // 2)
        self.small.draw(img, x, h // 2 - 4, label, colour)
        font.draw(img, x, h // 2 + font.cap + 1, p.clock, self.ink)
        return img


class Minutes(_Look):
    """One dot for every minute of this part: they go out one by one, and the last one lit blinks."""

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        p, colour, label = self.now_phase(now)
        if w >= self.small.width(label + " " + p.clock) + 2:
            self.small.draw(img, 1, 6, label, colour)
            self.small.draw(img, w - self.small.width(p.clock) - 1, 6, p.clock, self.ink)
        else:                                             # too narrow for both: the time, in the part's colour
            self.small.draw(img, max(0, (w - self.small.width(p.clock)) // 2), 6, p.clock, colour)
        room_w, room_h = max(2, w - 2), max(2, h - 10)   # the room under the heading
        minutes = p.length // 60
        each = -(-minutes // ((room_w // 2) * (room_h // 2)))    # minutes a dot stands for: 1, unless they can't all fit
        total = -(-minutes // each)
        left = -(-p.left // (60 * each))                 # dots left, rounded up: 61 seconds is 2 dots
        # the layout with the biggest dots (up to 3 LEDs and a gap); between equals, the one with no short last row
        gap, _, per_row = max((min(4, room_w // cols, room_h // -(-total // cols)), total % cols == 0, cols)
                              for cols in range(1, total + 1))
        rows = -(-total // per_row)
        x0 = (w - min(total, per_row) * gap + 1) // 2
        y0 = 9 + max(0, (h - 9 - rows * gap) // 2)
        px = img.load()
        for k in range(total):
            x, y = x0 + (k % per_row) * gap, y0 + (k // per_row) * gap
            if not (0 <= x < w - 1 and 0 <= y < h - 1):
                continue                                  # a very small canvas shows the dots that fit
            lit = k < left
            blink = k == left - 1 and now.microsecond >= 500_000
            c = dim(colour, 0.18) if not lit or blink else colour
            for dx in range(gap - 1):
                for dy in range(gap - 1):
                    px[x + dx, y + dy] = c
        return img
