"""Drawing the frames. Every function takes a canvas and plain data and draws one frame: nothing here knows
where the data came from (the time only to take turns on a one-line panel, ``tick``).

Everything is placed from the canvas's own width and height (the panel's safe area can be smaller than 64x32).
As the canvas shrinks, the kit stripes give way first (2 px, 1 px, none), then the type steps down (big, small,
tiny), then the top and bottom lines go, so a line is never drawn over another and nothing is clipped. On a panel
with room for one line only, that line takes turns between what the lines above and below it would have said.

Words are never cut: each line comes with shorter ways of saying it, and if none fits it is left out. Every word is
kept at least one LED in from each edge (a frame round the panel can hide its outermost LEDs), and every letter has
a dark column between it and the next (``Type``), whatever the typeface's own spacing.

No badge or crest is ever drawn: a team is its three letters and two stripes of its kit colours. A sport's own
small icon (art.py, made in the Animator) sits at the left of the top line, where the words still fit beside it.
"""
import unicodedata

from PIL import Image, ImageDraw

TEXT, GREY, AMBER, RED, GREEN = (240, 236, 228), (175, 181, 190), (255, 181, 71), (255, 80, 80), (110, 220, 150)
HIGHLIGHT = (90, 200, 255)       # the driver or player picked out: its own colour (amber is for times and states), with a
#                                  marker that isn't colour as well (a ">" before the name, or the row drawn reversed)
INK = {"6x13B": 9, "5x7": 6, "tom-thumb": 5}      # rows a capital really fills, above its baseline
SPACE = {"6x13B": 3, "5x7": 2, "tom-thumb": 2}    # a word space, on top of the dark column after the letter before it
MARGIN = 1                                        # LEDs kept dark at each side of every line of words
SCORE_GAP = 3                                     # dark LEDs at least between a score and the teams' letters
NARROW = 40                                       # below this width a word that needs every LED may use them all
_tick = [0]


def tick(now):
    """The turn of a one-line panel (every two seconds), from the frame's time."""
    try:
        _tick[0] = int(now.timestamp() // 2)
    except (AttributeError, OverflowError, ValueError, OSError):
        _tick[0] = 0


def rgb(colour, default=(120, 126, 134)):
    try:
        return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return default


def plain_letters(text):
    """``text`` in the letters the panel's typefaces have: accents taken off (MÜLLER: MULLER), anything else left out."""
    text = unicodedata.normalize("NFKD", "".join(UNFOLDED.get(c, c) for c in str(text)))
    return "".join(c for c in text.encode("ascii", "ignore").decode() if c.isprintable())


# Letters of the Matrix's own typefaces that read as other letters from across a room, drawn here instead (the
# typefaces aren't changed, only these letters replaced when this module draws): tom-thumb's Q, N and W (3 LEDs
# wide: they read as 4, n and H; M too), 5x7's W and M and 6x13B's M and W (all read as H).
LETTERS = {
    "tom-thumb": {
        "Q": (".##.", "#..#", "#..#", "#.#.", ".#.#"),
        "N": ("#..#", "##.#", "#.##", "#..#", "#..#"),
        "W": ("#...#", "#...#", "#.#.#", "#.#.#", ".#.#."),
        "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#"),
        "I": ("#", "#", "#", "#", "#"),      # (one LED wide, so the wider M still lets OLYMPICS fit 32 LEDs)
    },
    "5x7": {
        "W": ("#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
        "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#"),
    },
    "6x13B": {
        "M": ("##...##", "###.###", "#######", "##.#.##", "##.#.##", "##...##", "##...##", "##...##", "##...##"),
        "W": ("##...##", "##...##", "##...##", "##...##", "##.#.##", "##.#.##", "#######", "###.###", "##...##"),
    },
}
UNFOLDED = {"Ø": "O", "ø": "o", "Æ": "AE", "æ": "ae", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "ß": "SS", "ẞ": "SS",
            "Œ": "OE", "œ": "oe", "Þ": "TH", "þ": "th", "Ð": "D", "ð": "d", "Ħ": "H", "ħ": "h", "ı": "i", "Ŋ": "NG",
            "ŋ": "ng", "Ŧ": "T", "ŧ": "t", "ĸ": "k", "ſ": "s", "Ə": "E", "ə": "e", "’": "'", "‘": "'", "–": "-", "—": "-"}
#                                  (letters with no plain form in Unicode's own decomposition, mapped by hand)


def _mask(rows):
    img = Image.new("1", (len(rows[0]), len(rows)), 0)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "#":
                img.putpixel((x, y), 1)
    return img


class Type:
    """A typeface drawn with exactly one dark column between letters: each letter's own ink, then a gap. (The
    typefaces' own spacing lets some letters touch, NTH, DAYS, 108, and leaves false gaps round I and T.)"""
    _made = {}

    def __new__(cls, font, name):
        key = (id(font), name)
        if key not in cls._made:
            self = super().__new__(cls)
            self.font, self.name, self.space, self.glyphs = font, name, SPACE.get(name, 2), {}
            cls._made[key] = self
        return cls._made[key]

    def __init__(self, font, name):
        pass

    def glyph(self, c):
        """(mask or None, first ink column, ink width, rows above the baseline) of one letter."""
        if c not in self.glyphs:
            own = LETTERS.get(self.name, {}).get(c)
            if own:
                mask = _mask(own)
                cap = self.font.glyphs.get(ord("H"))
                base = (cap[2] - cap[3].getbbox()[1]) if cap and cap[3] is not None and cap[3].getbbox() else len(own)
                self.glyphs[c] = (mask, 0, mask.width, base)       # (its top row where the H's is)
            else:
                got = self.font.glyphs.get(ord(c)) or self.font.glyphs.get(ord("?"))
                _, _, top, mask = got if got else (0, 0, 0, None)
                box = mask.getbbox() if mask is not None else None
                #  (where its ink starts in its own picture: the typeface's offset is left out, so ":" and "'" get a dark
                #   column on each side like every other letter)
                self.glyphs[c] = (mask, box[0], box[2] - box[0], top) if box else (None, 0, 0, 0)
        return self.glyphs[c]

    def width(self, text):
        x, last = 0, False
        for c in plain_letters(text):
            mask, _, ink, _ = self.glyph(c)
            if c == " " or mask is None:
                x, last = x + self.space, False
            else:
                x, last = x + ink + 1, True
        return x - 1 if last else x

    def draw(self, img, x, baseline, text, fill):
        start = x
        for c in plain_letters(text):
            mask, left, ink, top = self.glyph(c)
            if c == " " or mask is None:
                x += self.space
                continue
            img.paste(fill, (x - left, baseline - top), mask)
            x += ink + 1
        return x - start


class Page:
    """One frame being drawn: the canvas, the three typefaces, and where its rows go."""

    def __init__(self, ctx):
        self.img = ctx.canvas()
        self.W, self.H = self.img.size
        self.d = ImageDraw.Draw(self.img)
        self.fonts = [(name, Type(ctx.fonts(name), name), INK[name]) for name in ("6x13B", "5x7", "tom-thumb")]
        self.tiny = self.fonts[2][1]
        self.room = self.W - 2 * MARGIN       # the width a line of words may use
        H = self.H
        if H >= 24:                    # three rows: a line at the top, the big row, a line at the bottom
            self.top, self.bottom, self.centre, room = 6, H - 2, H // 2, H // 2 - 3
        elif H >= 17:                  # two: the big row and a line under it
            self.top, self.bottom, self.centre, room = None, H - 2, (H - 6) // 2, H - 9
        else:                          # one
            self.top, self.bottom, self.centre, room = None, None, (H - 1) // 2, H - 2
        self.mids = [f for f in self.fonts if f[2] <= room] or self.fonts[-1:]
        self.one_line = self.top is None and self.bottom is None

    # -- text -------------------------------------------------------------------------------------------------
    def fit(self, words, fonts, width=None):
        """(font, text) for a line. ``words`` is the text, or several ways of saying it, longest first: the first
        that fits ``width`` (the line's room, inside the margins) in one of ``fonts`` (biggest first) is used, so a
        narrow panel gets fewer words, never cut ones. If none fits, the line is left out ("")."""
        width = self.room if width is None else width
        options = [words] if isinstance(words, str) else list(words)
        for room in (width, width + 2 * MARGIN) if self.W < NARROW and width == self.room else (width,):
            for text in options:             # (a narrow panel: first every wording inside the margins, then to the edges)
                for font in fonts:
                    if font.width(text) <= room:
                        return font, text
        return fonts[-1], ""

    def centred(self, font, text, baseline, colour, left=0, mark=None):
        """Draw ``text`` centred in the room right of ``left`` (inside the margins). ``mark``: a colour for the one
        word of it that starts with ">" (a player picked out), the rest staying ``colour``."""
        x0, x1 = MARGIN + left, self.W - MARGIN
        if font.width(text) > x1 - x0:       # (only on a narrow panel: see ``fit``)
            x0, x1 = left, self.W
        x = x0 + max(0, (x1 - x0 - font.width(text) + 1) // 2)
        font.draw(self.img, x, baseline, text, colour)
        if mark is not None and ">" in text:
            at = text.index(">")
            end = text.find(" ", at)
            word = text[at:] if end < 0 else text[at:end]
            font.draw(self.img, x + font.width(text[:at]), baseline, word, mark)
        return x

    def line(self, baseline, words, colour, icon=None, mark=None):
        """Words centred on a row of small type (see ``fit``). ``icon`` (an RGBA picture): at the left of the top
        line, with the words centred in the room beside it; if no wording fits beside it, the icon is left out
        (unless no wording fits at all: then the icon alone)."""
        if baseline is None or (not words and icon is None):
            return
        if icon is not None and baseline == self.top and icon.height <= baseline + 1 and self.H >= 26:   # (a dark row under it)
            beside = icon.width + 2
            font, text = self.fit(words or "", [self.tiny], self.room - beside)
            if text or not words or not self.fit(words, [self.tiny])[1]:
                self.img.paste(icon, (MARGIN, max(0, baseline - icon.height + 1)), icon)
                if text:
                    self.centred(font, text, baseline, colour, beside, mark)
                return
        if not words:
            return
        font, text = self.fit(words, [self.tiny])
        if text:
            self.centred(font, text, baseline, colour, mark=mark)

    def base(self, ink):
        """The baseline that centres a row of this height in the big row's band."""
        return self.centre + ink // 2

    def turn(self, *lines):
        """On a one-line panel: which of several lines (each words and a colour) has the line now. Empty ones,
        and ones with no wording short enough for the panel, are skipped."""
        lines = [(w, c) for w, c in lines if w and self.fit(w, [f for _, f, _ in self.mids])[1]]
        return lines[_tick[0] % len(lines)] if lines else ("", TEXT)

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
        font, text = self.fit((text, f"{home['code']}v{away['code']}"), [f for _, f, _ in self.mids])
        if text:
            ink = next(i for _, f, i in self.fonts if f is font)
            self.centred(font, text, self.base(ink), colour)
        else:                                      # (no room for the letters at all: the two kits, at least)
            self.kits(1, home["colours"], away["colours"])

    def score(self, home, away, a, b, colour):
        """NTH 2-1 STH: the codes at the edges, the score in the middle in the biggest digits that fit, with a
        short dash of its own (the typeface's ran into a 3)."""
        a, b = str(a), str(b)
        small, tiny = self.fonts[1], self.fonts[2]
        tries = [(2, 3, small, f) for f in self.mids[:1]] + [(1, g, small, f) for f in self.mids[:1] for g in (2, 1)] + \
                [(1, 1, tiny, f) for f in self.mids] + [(0, MARGIN, tiny, f) for f in self.mids[1:] or self.mids]
        for stripe, gap, (_, code, code_ink), (_, digits, ink) in tries:
            if code_ink > ink:
                continue
            dash = 4 if ink >= 9 else 3
            wide = digits.width(a) + 2 + dash + 2 + digits.width(b)
            sides = max(code.width(home["code"]), code.width(away["code"]))
            if 2 * (stripe + gap + sides) + 2 * SCORE_GAP + wide <= self.W:   # (a clear gap between the score and the codes)
                self.kits(stripe, home["colours"], away["colours"])
                at = self.centre + 2 if ink >= 9 else self.base(ink)
                code.draw(self.img, stripe + gap, at, home["code"], TEXT)
                code.draw(self.img, self.W - code.width(away["code"]) - stripe - gap, at, away["code"], TEXT)
                self.digits(digits, ink, a, b, colour)
                return
        for _, digits, ink in self.mids:          # no room for the codes: the score alone (if even that fits)
            if digits.width(a) + 4 + (4 if ink >= 9 else 3) + digits.width(b) <= self.room:
                self.digits(digits, ink, a, b, colour)
                return

    def digits(self, font, ink, a, b, colour):
        dash = 4 if ink >= 9 else 3
        wa, y = font.width(a), self.base(ink)
        x = max(MARGIN, (self.W - (wa + 2 + dash + 2 + font.width(b)) + 1) // 2)
        font.draw(self.img, x, y, a, colour)
        font.draw(self.img, x + wa + 4 + dash, y, b, colour)
        up = 6 if ink >= 9 else ink // 2 + 1
        self.d.rectangle([x + wa + 2, y - up, x + wa + 1 + dash, y - up + (1 if ink >= 9 else 0)], fill=colour)

    def one(self, words, colour, mark=None, icon=None, kits=None):
        """A panel's one line: ``words`` as big as fits, centred. ``icon``: the sport's, at the left, where the words
        still fit beside it. ``kits``: the two kits' stripes at the edges, only where the words keep a dark column
        from them. Returns the words drawn."""
        fonts = [f for _, f, _ in self.mids]
        left = 0
        if icon is not None and icon.height <= self.H:
            font, text = self.fit(words, fonts, self.room - icon.width - 2)
            if text:
                self.img.paste(icon, (MARGIN, max(0, (self.H - icon.height) // 2)), icon)
                left = icon.width + 2                # (two dark LEDs between the icon and the words)
        if not left:
            font, text = self.fit(words, fonts)
        if text:
            ink = next(i for _, f, i in self.fonts if f is font)
            x = self.centred(font, text, self.base(ink), colour, left, mark)
            if kits and x >= 3 and x + font.width(text) <= self.W - 3:
                self.kits(1, *kits)
        elif kits:
            self.kits(1, *kits)
        return text


# -- the frames ---------------------------------------------------------------------------------------------------
def fixture(ctx, home, away, top, bottom, bottom_colour=AMBER, icon=None):
    """Next match, and Postponed: the date, NTH v STH, and a line under it (KO 15:00, POSTPONED)."""
    p = Page(ctx)
    if p.one_line:                                 # the teams, the day, the time, in turn
        teams = f"{home['code']} v {away['code']}"
        teams = teams if p.tiny.width(teams) <= p.W else f"{home['code']}v{away['code']}"   # (spaced wherever it fits at all)
        p.one(*p.turn(((teams,), TEXT), (top, GREY), (bottom, bottom_colour)),
              kits=(home["colours"], away["colours"]))
        return p.img
    p.line(p.top, top, GREY, icon)
    p.names(home, away)
    p.line(p.bottom - 1 if p.bottom and p.H >= 30 else p.bottom, bottom, bottom_colour)
    return p.img


def scoreline(ctx, home, away, score, top, top_colour, bottom="", score_colour=TEXT, minute="", dot=False, icon=None):
    """Live, half time and full time. ``top`` centred (HALF TIME), or with ``minute``: LIVE at the left with its
    dot and the minute at the right."""
    p = Page(ctx)
    if p.one_line:                                 # the score, and what it is (LIVE 67', FULL TIME), in turn
        said = top if not minute or not isinstance(top, str) else (f"{top} {minute if isinstance(minute, str) else minute[-1]}".strip(), top)
        if _tick[0] % 2:
            p.one(said, top_colour)
        else:
            p.score(home, away, score[0], score[1], score_colour)
        return p.img
    if p.top is not None and minute:
        tiny = p.tiny
        _, minute = p.fit(minute, [tiny], p.room)
        room = p.W - MARGIN - tiny.width(minute)
        _, top = p.fit(top, [tiny], room - 7)
        if top:
            if dot:
                p.d.rectangle([1, 2, 2, 3], fill=top_colour)
            tiny.draw(p.img, 5, p.top, top, top_colour)
        if minute:
            tiny.draw(p.img, room, p.top, minute, AMBER)
    else:
        p.line(p.top, top, top_colour, icon)
    p.score(home, away, score[0], score[1], score_colour)
    p.line(p.bottom, bottom, GREY)
    return p.img


def table(ctx, rows, mine, reverse=True, band=AMBER):
    """The rows of the table around ``mine`` (a team or driver id): place, code, points. The row of ``mine`` is drawn
    dark on a band of ``band`` (amber for your team, HIGHLIGHT for a driver picked out), not by colour alone."""
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
