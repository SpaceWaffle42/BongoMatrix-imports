"""Drawing the frames. Every function takes a canvas and plain data and draws one frame: nothing here knows
where the data came from, or what time it is.

Everything is placed from the canvas's own width and height (the panel's safe area can be smaller than 64x32).
At 64x32 the frames are the agreed design, pixel for pixel. As the canvas shrinks, the kit stripes give way first
(2 px, 1 px, none), then the type steps down (big, small, tiny), then the top and bottom lines go, so a line is
never drawn over another and nothing is clipped.

Words are never cut: each line comes with shorter ways of saying it, and if none fits it is left out.

No badge or crest is ever drawn: a team is its three letters and two stripes of its kit colours.
"""
from PIL import ImageDraw

TEXT, GREY, AMBER, RED, GREEN = (240, 236, 228), (175, 181, 190), (255, 181, 71), (255, 80, 80), (110, 220, 150)
INK = {"6x13B": 9, "5x7": 6, "tom-thumb": 5}      # rows a capital really fills, above its baseline


def rgb(colour, default=(120, 126, 134)):
    try:
        return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return default


class Page:
    """One frame being drawn: the canvas, the three typefaces, and where its rows go."""

    def __init__(self, ctx):
        self.img = ctx.canvas()
        self.W, self.H = self.img.size
        self.d = ImageDraw.Draw(self.img)
        self.fonts = [(name, ctx.fonts(name), INK[name]) for name in ("6x13B", "5x7", "tom-thumb")]
        self.tiny = self.fonts[2][1]
        H = self.H
        if H >= 24:                    # three rows: a line at the top, the big row, a line at the bottom
            self.top, self.bottom, self.centre, room = 6, H - 2, H // 2, H // 2 - 3
        elif H >= 17:                  # two: the big row and a line under it
            self.top, self.bottom, self.centre, room = None, H - 2, (H - 6) // 2, H - 9
        else:                          # one
            self.top, self.bottom, self.centre, room = None, None, (H - 1) // 2, H - 2
        self.mids = [f for f in self.fonts if f[2] <= room] or self.fonts[-1:]

    # -- text -------------------------------------------------------------------------------------------------
    def fit(self, words, fonts, width):
        """(font, text) for a line. ``words`` is the text, or several ways of saying it, longest first: the first
        that fits ``width`` in one of ``fonts`` (biggest first) is used, so a narrow panel gets fewer words, never
        cut ones. If none fits, the line is left out ("")."""
        options = [words] if isinstance(words, str) else list(words)
        for text in options:
            for font in fonts:
                if font.width(text) <= width:
                    return font, text
        return fonts[-1], ""

    def line(self, baseline, words, colour):
        """Words centred on a row of small type (see ``fit``)."""
        if baseline is None or not words:
            return
        font, text = self.fit(words, [self.tiny], self.W)
        font.draw(self.img, max(0, (self.W - font.width(text) + 1) // 2), baseline, text, colour)

    def base(self, ink):
        """The baseline that centres a row of this height in the big row's band."""
        return self.centre + ink // 2

    # -- the two kits -----------------------------------------------------------------------------------------
    def kits(self, width, home, away):
        if width <= 0:
            return
        top, mid, end = max(0, self.centre - 6), max(0, min(self.H, self.centre)), min(self.H - 1, self.centre + 5)
        for x, cols in ((0, home), (self.W - width, away)):
            if mid - 1 >= top:
                self.d.rectangle([x, top, x + width - 1, mid - 1], fill=rgb(cols[0]))
            if end >= mid:
                self.d.rectangle([x, mid, x + width - 1, end], fill=rgb(cols[-1]))

    # -- the big row ------------------------------------------------------------------------------------------
    def names(self, home, away, colour=TEXT):
        """NTH v STH between the kits, as big as fits."""
        text = f"{home['code']} v {away['code']}"
        for _, font, ink in self.mids:
            for stripe in (2, 1):
                if font.width(text) <= self.W - 2 * stripe - 4:
                    self.kits(stripe, home["colours"], away["colours"])
                    font.draw(self.img, (self.W - font.width(text) + 1) // 2, self.base(ink), text, colour)
                    return
        font, text = self.fit((text, f"{home['code']}-{away['code']}"), [f for _, f, _ in self.mids], self.W)
        if text:
            ink = next(i for _, f, i in self.fonts if f is font)
            font.draw(self.img, (self.W - font.width(text) + 1) // 2, self.base(ink), text, colour)

    def score(self, home, away, a, b, colour):
        """NTH 2-1 STH: the codes at the edges, the score in the middle in the biggest digits that fit, with a
        short dash of its own (the typeface's ran into a 3)."""
        a, b = str(a), str(b)
        small, tiny = self.fonts[1], self.fonts[2]
        tries = [(2, 3, small, f) for f in self.mids[:1]] + [(1, g, small, f) for f in self.mids[:1] for g in (2, 1)] + \
                [(1, 1, tiny, f) for f in self.mids] + [(0, 0, tiny, f) for f in self.mids[1:] or self.mids]
        for stripe, gap, (_, code, code_ink), (_, digits, ink) in tries:
            if code_ink > ink:
                continue
            dash = 4 if ink >= 9 else 3
            wide = digits.width(a) + 2 + dash + 2 + digits.width(b)
            sides = max(code.width(home["code"]), code.width(away["code"]))
            if 2 * (stripe + gap + sides) + 4 + wide <= self.W:
                self.kits(stripe, home["colours"], away["colours"])
                at = self.centre + 2 if ink >= 9 else self.base(ink)
                code.draw(self.img, stripe + gap, at, home["code"], TEXT)
                code.draw(self.img, self.W - code.width(away["code"]) - stripe - gap, at, away["code"], TEXT)
                self.digits(digits, ink, a, b, colour)
                return
        for _, digits, ink in self.mids:          # no room for the codes: the score alone (if even that fits)
            if digits.width(a) + 4 + (4 if ink >= 9 else 3) + digits.width(b) <= self.W:
                self.digits(digits, ink, a, b, colour)
                return

    def digits(self, font, ink, a, b, colour):
        dash = 4 if ink >= 9 else 3
        wa, y = font.width(a), self.base(ink)
        x = max(0, (self.W - (wa + 2 + dash + 2 + font.width(b)) + 1) // 2)
        font.draw(self.img, x, y, a, colour)
        font.draw(self.img, x + wa + 4 + dash, y, b, colour)
        up = 6 if ink >= 9 else ink // 2 + 1
        self.d.rectangle([x + wa + 2, y - up, x + wa + 1 + dash, y - up + (1 if ink >= 9 else 0)], fill=colour)


# -- the frames ---------------------------------------------------------------------------------------------------
def fixture(ctx, home, away, top, bottom, bottom_colour=AMBER):
    """Next match, and Postponed: the date, NTH v STH, and a line under it (KO 15:00, POSTPONED)."""
    p = Page(ctx)
    p.line(p.top, top, GREY)
    p.names(home, away)
    p.line(p.bottom - 1 if p.bottom and p.H >= 30 else p.bottom, bottom, bottom_colour)
    return p.img


def scoreline(ctx, home, away, score, top, top_colour, bottom="", score_colour=TEXT, minute="", dot=False):
    """Live, half time and full time. ``top`` centred (HALF TIME), or with ``minute``: LIVE at the left with its
    dot and the minute at the right."""
    p = Page(ctx)
    if p.top is not None and minute:
        tiny = p.tiny
        _, minute = p.fit(minute, [tiny], p.W - 1)
        room = p.W - tiny.width(minute) - 1
        _, top = p.fit(top, [tiny], room - 7)
        if top:
            if dot:
                p.d.rectangle([1, 2, 2, 3], fill=top_colour)
            tiny.draw(p.img, 5, p.top, top, top_colour)
        if minute:
            tiny.draw(p.img, room, p.top, minute, AMBER)
    else:
        p.line(p.top, top, top_colour)
    p.score(home, away, score[0], score[1], score_colour)
    p.line(p.bottom, bottom, GREY)
    return p.img


def table(ctx, rows, mine):
    """The rows of the league table around ``mine`` (a team id): place, code, points."""
    p = Page(ctx)
    if not rows:
        return p.img
    count = max(1, min(len(rows), (p.H + 1) // 8))
    index = next((i for i, r in enumerate(rows) if r["id"] == mine), 0)
    start = max(0, min(index - 1, len(rows) - count))
    shown = rows[start:start + count]
    for _, font, ink in p.fonts[1:]:
        place = max(font.width(str(r["pos"])) for r in shown)
        points = max(font.width(str(r["points"])) for r in shown)
        if 1 + place + 3 + max(font.width(r["code"]) for r in shown) + 2 + points + 1 <= p.W or ink == 5:
            break
    pitch = 8 if p.H >= count * 8 - 1 else max(ink + 1, p.H // count)
    first = ink + max(0, (p.H - ((count - 1) * pitch + ink)) // 2) if p.H != 32 else 7
    for i, row in enumerate(shown):
        y, colour = first + i * pitch, AMBER if row["id"] == mine else TEXT
        if place + points + 4 <= p.W:            # (too narrow even for those: the row is left out)
            font.draw(p.img, 1, y, str(row["pos"]), GREY)
            font.draw(p.img, p.W - font.width(str(row["points"])) - 1, y, str(row["points"]), colour)
            if 1 + place + 3 + font.width(row["code"]) + 2 + points + 1 <= p.W:
                font.draw(p.img, 1 + place + 3, y, row["code"], colour)
    return p.img


def card(ctx, top, middle, bottom, top_colour=GREY, middle_colour=TEXT, bottom_colour=GREY, kit=None):
    """Three lines of words: what the screen needs (ADD YOUR KEY), or the team it found."""
    p = Page(ctx)
    p.line(p.top, top, top_colour)
    if kit:
        p.kits(2 if p.W >= 40 else 1, kit, kit)
    fonts = [f for _, f, ink in p.mids if ink <= 6] or [p.tiny]
    font, middle = p.fit(middle, fonts, p.W - (6 if kit else 0))
    ink = next(i for _, f, i in p.fonts if f is font)
    if middle:
        font.draw(p.img, (p.W - font.width(middle) + 1) // 2, p.base(ink), middle, middle_colour)
    p.line(p.bottom, bottom, bottom_colour)
    return p.img
