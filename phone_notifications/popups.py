"""The pop-up's own look (module API 3), as in the mockup: a card slides down over whatever was playing, tinted in
the kind's colour, with the kind's icon (an Animator drawing in ``art/``), who it's from, the kind and how long ago,
then a line under (the text, with "Who and the text"; otherwise "SEE YOUR PHONE"), and a line along the bottom that
shrinks as its time runs out. Several at once (those that waited out the gap, or quiet hours) are one card with the
bell: "3 NEW", since when (or "WHILE QUIET"), and each name in its kind's colour. It slides back up at the end.

The background task hands it what to draw in ``self.ctx.popup`` (desk.popup_data), which never holds more than the
"On the panel, show" setting allows; the words it gives too ("Mum: New message") are what the panel shows instead
if this look ever fails."""
from __future__ import annotations

import datetime as dt

from PIL import Image

from bongo.module import Style

from . import kinds, look
from .listen import ago

CARD = 32                       # rows of the card on a panel this tall or taller (in the middle of a taller one)
SMALL = 16                      # rows of it on a shorter panel: the icon, who and the kind, nothing under
POP_SPEED = 20                  # px/s a long line slides: one dot a frame, so it moves evenly
NAME_INK = {"calendar": (255, 90, 90)}   # a name in a kind's colour, where that colour is too near the text's white
TALL = 48                       # a panel this tall gets a card of its own height: the icon twice the size, and the
#                                 text (when it may be shown) or each of several on lines of their own
SLIDE, RISE, GONE = 0.35, 0.5, 0.2   # s it takes to slide down, to go back up, and empty at the very end
BELL = (255, 212, 107)          # several at once: the bell's colour
SAMPLE = {"show": "who", "quiet": False, "count": 1, "notes": [{"kind": "message", "who": "Mum"}]}   # (the test screen)


def mix(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


class Note(Style):
    """Notifications from the phone. Only ever a pop-up: never in Add a module or the playlist."""
    popup_only = True
    fps = 20

    def setup(self):
        self.font = self.ctx.fonts(look.FONT)
        self.private = True                     # who it's from, or what it says: on the panel only, never on the web
        given = self.ctx.popup if isinstance(self.ctx.popup, dict) else SAMPLE
        self.show = given.get("show") if given.get("show") in ("who", "all", "kind") else "who"
        self.quiet = given.get("quiet") is True
        self.notes = [n for n in given.get("notes") or [] if isinstance(n, dict)][-8:] or SAMPLE["notes"]
        count = given.get("count")
        self.count = count if isinstance(count, int) and not isinstance(count, bool) and count >= len(self.notes) else len(self.notes)
        self.began = None

    # -- each frame ---------------------------------------------------------------------------------------------
    def render(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        if self.began is None:
            self.began = now.timestamp()
        t = now.timestamp() - self.began
        left = self.left(now)
        shown = min(1.0, t / SLIDE, (left - GONE) / RISE)               # 0: up out of sight, 1: in place
        if self.ctx.popup is None:
            shown, t = 1.0, 0.5                 # (the import's test screen draws it once: in place, not on its way)
        if shown <= 0:
            return img
        rows = h if h >= TALL else CARD if h >= CARD - 2 else SMALL
        top = max(0, (h - rows) // 2)
        total = None if self.hand_over_at is None else self.hand_over_at - self.began
        draw = self.tall_card if rows >= TALL else self.card
        card = draw(w, min(rows, h), max(0.0, t - SLIDE), now, None if total is None else left / max(0.1, total))
        if h > rows or rows >= TALL:                                    # (a taller panel: an edge along its bottom too)
            card.paste(self.ink, (0, rows - 1, w, rows))
        img.paste(card, (0, round(top - (1 - shown) * (top + rows))))
        return img

    def left(self, now) -> float:
        """Seconds until the pop-up hands over (the player says when); as good as for ever if it hasn't said."""
        ends = self.hand_over_at
        return 1e9 if ends is None else max(0.0, ends - now.timestamp())

    # -- the card -----------------------------------------------------------------------------------------------
    def card(self, w: int, rows: int, t: float, now, left: float | None) -> Image.Image:
        one = self.count == 1 and not self.quiet
        note = self.notes[-1]
        kind = note.get("kind") if note.get("kind") in kinds.KINDS else "other"
        ink = self.ink = look.colour(kind) if one else BELL
        bg = mix((0, 0, 0), ink, 0.10)
        card = Image.new("RGB", (w, rows), bg)
        card.paste(ink, (0, 0, w, 1))
        layer = card.convert("RGBA")
        layer.alpha_composite(look.kind_icon(kind if one else "other", True), (2, 3))
        card.paste(layer.convert("RGB"))
        f = self.font
        if one:
            who = look.caps(kinds.NEW[kind] if self.show == "kind" else note.get("who") or kinds.KINDS[kind][0])
            under = "" if self.show == "kind" else look.caps(kinds.KINDS[kind][0])
            age = ago(now.timestamp() - _when(note, now.timestamp()))
        else:
            who = f"{self.count} NEW"
            under = "WHILE QUIET" if self.quiet else self.since()
            age = ""
        room = w - 15
        offset, _ = look.slide(f.width(who) - 1, room, t, speed=POP_SPEED)   # (its ink: no gap after it)
        look.parts_at(card, f, 14, 3, room, [(who, look.WHITE)], offset, bg)
        if age:
            f.draw(card, w - f.width(age), 14, age, look.GREY)
        room = w - 14 - (f.width(age) + 2 if age else 1)
        if under and f.width(under) - 1 <= room:                        # (left out on a panel too narrow for it)
            look.parts_at(card, f, 14, 9, room, [(under, mix((0, 0, 0), ink, 0.85) if one else look.GREY)], 0, bg)
        if rows < CARD:
            card.paste(mix(bg, ink, 0.35), (0, rows - 1, w, rows))
            return card
        card.paste(mix(bg, ink, 0.35), (0, 15, w, 16))
        parts = self.line(one, w - 4)
        offset, _ = look.slide(look.width(f, parts) - 1, w - 4, t, speed=POP_SPEED)
        look.parts_at(card, f, 2, 19, w - 4, parts, offset, bg)
        card.paste(mix(bg, look.DARK, 0.6), (2, 28, w - 2, 29))            # the time left, as a shrinking line
        if left is not None:
            card.paste(mix((0, 0, 0), ink, 0.7), (2, 28, 2 + round((w - 4) * max(0.0, min(1.0, left))), 29))
        return card

    def tall_card(self, w: int, rows: int, t: float, now, left: float | None) -> Image.Image:
        """The card on a tall panel (64 x 64): the kind's icon at twice its size, who, the kind and how long ago, a rule,
        then the text wrapped over the lines below (with "Who and the text"; otherwise SEE YOUR PHONE), or for several
        one line each, and the time left along the bottom."""
        one = self.count == 1 and not self.quiet
        note = self.notes[-1]
        kind = note.get("kind") if note.get("kind") in kinds.KINDS else "other"
        ink = self.ink = look.colour(kind) if one else BELL
        bg = mix((0, 0, 0), ink, 0.10)
        card = Image.new("RGB", (w, rows), bg)
        card.paste(ink, (0, 0, w, 1))
        icon = look.kind_icon(kind if one else "other", True)
        icon = icon.resize((icon.width * 2, icon.height * 2), Image.NEAREST)   # (the Animator's drawing, twice the size)
        layer = card.convert("RGBA")
        layer.alpha_composite(icon, (1, 3))
        card.paste(layer.convert("RGB"))
        f = self.font
        x = 2 + icon.width                                                           # (a clear dot after the icon)
        if one:
            who = look.caps(kinds.NEW[kind] if self.show == "kind" else note.get("who") or kinds.KINDS[kind][0])
            under = "" if self.show == "kind" else look.caps(kinds.KINDS[kind][0])
            age = ago(now.timestamp() - _when(note, now.timestamp()))
        else:
            who, under, age = f"{self.count} NEW", ("WHILE QUIET" if self.quiet else self.since()), ""
        room = w - x - 1
        offset, _ = look.slide(f.width(who) - 1, room, t, speed=POP_SPEED)   # (its ink: no gap after it)
        look.parts_at(card, f, x, 3, room, [(who, look.WHITE)], offset, bg)       # three rows of words by the icon:
        if under and f.width(under) - 1 <= w - x - 1:                                # who, the kind (or since when),
            f.draw(card, x, 15, under, mix((0, 0, 0), ink, 0.85) if one else look.GREY)
        if age:                                                                      # and how long ago
            f.draw(card, w - f.width(age), 21, age, look.GREY)
        card.paste(mix(bg, ink, 0.35), (0, 23, w, 24))
        room, top, most = w - 4, 26, max(1, (rows - 6 - 26) // look.ROW)
        for k, parts in enumerate(self.lines(one, room, most)):
            look.parts_at(card, f, 2, top + k * look.ROW, room, parts, 0, bg)
        card.paste(mix(bg, look.DARK, 0.6), (2, rows - 4, w - 2, rows - 3))      # the time left, as a shrinking line
        if left is not None:
            card.paste(mix((0, 0, 0), ink, 0.7), (2, rows - 4, 2 + round((w - 4) * max(0.0, min(1.0, left))), rows - 3))
        return card

    def lines(self, one: bool, room: int, most: int) -> list[list[tuple[str, tuple]]]:
        """The lines under the rule on a tall card, at most ``most``, each fitting ``room`` (cut with "…")."""
        f = self.font

        def fit(text, ink):
            while text and f.width(text) - 1 > room:
                text = text.rstrip("…")[:-1].rstrip() + "…"
            return (text, ink)
        if one:
            text = self.notes[-1].get("text") if self.show == "all" else ""
            if not text:
                return [[("SEE YOUR PHONE", look.GREY)]]
            wrapped = look.wrap(f, look.caps(text), room)
            if len(wrapped) > most:
                wrapped = wrapped[:most - 1] + [fit(wrapped[most - 1] + "…", look.WHITE)[0]]
            return [[(line, look.WHITE)] for line in wrapped]
        entries = []                            # several: each one's lines, its name in its kind's colour
        for note in self.notes:
            kind = note.get("kind") if note.get("kind") in kinds.KINDS else "other"
            ink = NAME_INK.get(kind, look.colour(kind))
            name = look.caps(kinds.KINDS[kind][0] if self.show == "kind" else note.get("who") or kinds.KINDS[kind][0])
            text = look.caps(note.get("text") or "") if self.show == "all" else ""
            if not text:
                entries.append([[fit(name, ink)]])
                continue
            wrapped = look.wrap(f, f"{name}: {text}", room)
            head = name + ":"
            if wrapped[0].startswith(head):
                entry = [[(head, ink), (wrapped[0][len(head):], look.WHITE)]]
            else:
                entry = [[(wrapped[0], ink)]]
            entries.append(entry + [[(line, look.WHITE)] for line in wrapped[1:]])
        more = self.count - len(entries)
        if len(entries) + (1 if more > 0 else 0) > most:                # more than there are lines: the newest
            keep = most - 1
            more, entries = more + len(entries) - keep, entries[-keep:]
        room_left = most - (1 if more > 0 else 0)
        while sum(len(e) for e in entries) > room_left:                 # too many lines: the longest gives way first
            longest = max(entries, key=len)
            del longest[-1]
            line = longest[-1]
            text, ink = line[-1]
            text += "…"
            while text != "…" and look.width(f, line[:-1] + [(text, ink)]) - 1 > room:
                text = text[:-2].rstrip() + "…"
            line[-1] = (text, ink)
        out = [line for entry in entries for line in entry]
        if more > 0:
            out.append([(f"AND {more} MORE", look.GREY)])
        return out[:most]

    def line(self, one: bool, room: int) -> list[tuple[str, tuple]]:
        """The line under the rule: the text, or SEE YOUR PHONE; for several, each one in its kind's colour, as far
        apart as ``room`` lets them all be seen at once (three spaces between, or two, or one; three if it must
        slide anyway)."""
        if one:
            text = self.notes[-1].get("text") if self.show == "all" else ""
            return [(look.caps(text), look.WHITE)] if text else [("SEE YOUR PHONE", look.GREY)]
        for gap in ("   ", "  ", " ", "   "):
            parts = self.several(gap)
            if look.width(self.font, parts) - 1 <= room:
                break
        return parts

    def several(self, gap: str) -> list[tuple[str, tuple]]:
        parts = []
        for k, note in enumerate(self.notes):
            kind = note.get("kind") if note.get("kind") in kinds.KINDS else "other"
            name = kinds.KINDS[kind][0] if self.show == "kind" else note.get("who") or kinds.KINDS[kind][0]
            text = note.get("text") if self.show == "all" else ""
            parts.append(((gap if k else "") + look.caps(name) + (":" if text else ""), NAME_INK.get(kind, look.colour(kind))))
            if text:
                parts.append((" " + look.caps(text), look.WHITE))
        more = self.count - len(self.notes)
        if more > 0:
            parts.append((f"{gap}AND {more} MORE", look.GREY))
        return parts

    def since(self) -> str:
        """SINCE 14:01: when the first of several came."""
        at = _when(self.notes[0], None)
        if at is None:
            return ""
        first = dt.datetime.fromtimestamp(at, self.ctx.tz)
        return f"SINCE {first:%H:%M}"


def _when(note: dict, otherwise):
    """When a notification came (a timestamp), or ``otherwise`` if it doesn't say properly."""
    at = note.get("at")
    if isinstance(at, (int, float)) and not isinstance(at, bool) and 0 < at < 1e11:
        return float(at)
    return otherwise
