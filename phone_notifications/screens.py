"""The looks for the playlist: Recent (the last few), Latest one (the newest in full) and Setup code (the topic
as a QR code, for the owner to add while setting up a phone and take out again). Recent and Latest one say
"Nothing new" when there's nothing (or skip their turn, as their setting says) and "Can't reach ntfy.sh" when
the connection is down."""
from __future__ import annotations

import os

from PIL import Image

from bongo.module import Style
from bongo.scroll import Scrolls

from . import desk, kinds, look, ntfy, qr
from .listen import STATE, ago

SKIP, SAY = "Skip this screen", "Say nothing new"
_file = {"at": None, "book": None}


def kept() -> tuple[list[dict], str | None, str]:
    """(notifications newest first, the connection: "up", "down", "connecting" or None, the topic) as the background
    task last left them; when it isn't running in this process (a test screen), as its file has them."""
    if STATE.get("ready"):
        return STATE["notes"], STATE["link"], STATE["topic"]
    try:
        at = os.stat(desk.FILE).st_mtime_ns
    except OSError:
        return [], None, ""
    if _file["at"] != at:
        _file["at"], _file["book"] = at, desk.Book()
    book = _file["book"]
    return book.notes, None, book.data["made"]


class Listing(Scrolls, Style):
    """What Recent and Latest one share: where the notifications come from, and the two states with none."""
    fps = 10
    defaults = {"when_empty": SKIP}
    choices = {"when_empty": [SKIP, SAY]}

    def setup(self):
        self.font = self.ctx.fonts(look.FONT)

    def act(self, name):
        if name == "clear":                       # the background task empties the list at its next tick
            STATE["clear"] = True
            STATE["notes"] = []

    def show(self) -> str:
        return (self.ctx.module_settings or {}).get("show") or desk.WHO

    def render(self, now):
        img = Image.new("RGB", (self.ctx.width, self.ctx.height))
        notes, link, _ = kept()
        notes = [n for n in notes if now.timestamp() - n.get("at", 0) < desk.DAY]
        self.private = bool(notes)                # who sent what: on the panel only, never in a picture on the web (the
        #                                           hub's, the Now page's show a padlocked stand-in); "nothing new" isn't
        if notes:
            self.draw(img, notes, link, now)
        elif link == "down":
            self.offline(img)
        else:
            if self.settings["when_empty"] == SKIP and not self.ctx.preview:
                self.finished = True              # nothing to say: the playlist moves on
            self.nothing(img, now)
        return img

    def nothing(self, img, now):
        bell = look.dimmed(look.icon("other_9"), 0.55)
        sway = (1 if int(now.timestamp() * 2) % 2 else -1) if int(now.timestamp()) % 6 < 2 else 0   # a little ring now and then
        top = 3 if img.height >= 28 else 1
        layer = img.convert("RGBA")
        layer.alpha_composite(bell, ((img.width - bell.width) // 2 + sway, top))
        img.paste(layer.convert("RGB"))
        look.centred(img, self.font, top + 12, "NOTHING NEW", look.GREY)

    def offline(self, img):
        top = 3 if img.height >= 28 else 1
        layer = img.convert("RGBA")
        art = look.icon("offline_9")
        layer.alpha_composite(art, ((img.width - art.width) // 2, top))
        img.paste(layer.convert("RGB"))
        look.centred(img, self.font, top + 12, "CAN'T REACH", look.WARN)
        look.centred(img, self.font, top + 19, ntfy.NAME.upper(), look.WARN)


class Recent(Listing):
    """The last few, newest first: each kind's icon, who (in the kind's colour) and how long ago."""

    def draw(self, img, notes, link, now):
        f, show = self.font, self.show()
        top = 0
        if img.height >= 20:                      # a heading, if there's room for it
            f.draw(img, 1, 5, "RECENT", look.GREY)
            top = 8
        per = max(1, (img.height - top + 1) // look.ROW)
        pages = [notes[i:i + per] for i in range(0, len(notes), per)]
        rows = {id(p): [self.parts(n, show) for n in p] for p in pages}

        def page_time(page):
            room = img.width - 8 - 16
            return max(6.0, max(look.slide(look.width(f, parts), room, 0)[1] for parts in rows[id(page)]))

        page, t = self.turns("recent", pages, now, page_time, name=lambda p: p[0]["id"])
        if top:
            right = "OFFLINE" if link == "down" else f"{pages.index(page) + 1}/{len(pages)}" if len(pages) > 1 else str(len(notes))
            f.draw(img, img.width - f.width(right), 5, right, look.WARN if link == "down" else look.GREY)
            img.paste(look.DARK, (0, 6, img.width, 7))
        layer = img.convert("RGBA")
        for i, note in enumerate(page):
            layer.alpha_composite(look.kind_icon(note.get("kind"), False), (1, top + i * look.ROW))
        img.paste(layer.convert("RGB"))
        for i, note in enumerate(page):
            y = top + i * look.ROW
            age = ago(now.timestamp() - note.get("at", 0))
            f.draw(img, img.width - f.width(age), y + 5, age, look.DIM)
            room = img.width - 8 - f.width(age) - 4
            parts = rows[id(page)][i]
            offset, _ = look.slide(look.width(f, parts), room, t)
            look.parts_at(img, f, 8, y, room, parts, offset)

    @staticmethod
    def parts(note, show):
        kind, ink = note.get("kind", "other"), look.colour(note.get("kind", "other"))
        if show == desk.KIND:
            return [(look.caps(kinds.KINDS[kind][0]), ink)]
        who = [(look.caps(note.get("who") or kinds.KINDS[kind][0]), ink)]
        if show == desk.WHO_TEXT and note.get("text"):
            return who + [(" " + look.caps(note["text"]), look.WHITE)]
        return who


class Latest(Listing):
    """The newest one in full: its icon, who, its kind and how long ago, and the text over the lines below
    (longer text turns over like pages)."""

    def draw(self, img, notes, link, now):
        f, show, note = self.font, self.show(), notes[0]
        kind = note.get("kind", "other")
        layer = img.convert("RGBA")
        layer.alpha_composite(look.kind_icon(kind, True), (1, 1))
        img.paste(layer.convert("RGB"))
        who = look.caps(kinds.KINDS[kind][0] if show == desk.KIND else note.get("who") or kinds.KINDS[kind][0])
        room = img.width - 13
        t = self.scrolled(("who", note["id"], who), now, look.slide(f.width(who), room, 0)[1])
        look.parts_at(img, f, 12, 1, room, [(who, look.WHITE)], look.slide(f.width(who), room, t)[0])
        age = "OFFLINE" if link == "down" else ago(now.timestamp() - note.get("at", 0))
        f.draw(img, img.width - f.width(age), 12, age, look.WARN if link == "down" else look.GREY)
        if show != desk.KIND:
            label = look.caps(kinds.KINDS[kind][0])
            f.draw(img, 12, 12, label, tuple(int(c * 0.85) for c in look.colour(kind)))
        img.paste(look.DARK, (0, 13, img.width, 14))
        per = (img.height - 15 + 1) // look.ROW
        if per < 1:
            return
        if show == desk.WHO_TEXT and note.get("text"):
            lines, ink = look.wrap(f, look.caps(note["text"]), img.width - 4), look.WHITE
        else:
            lines, ink = ["SEE YOUR PHONE"], look.GREY
        pages = [lines[i:i + per] for i in range(0, len(lines), per)]
        page, _ = self.turns(("latest", note["id"]), pages, now, lambda p: 5.0, name=lambda p: "\n".join(p))
        for i, line in enumerate(page):
            f.draw(img, 1, 15 + i * look.ROW + 5, line, ink)
        if len(pages) > 1:                        # which page this is, as dots down the right
            for k in range(min(len(pages), (img.height - 16) // 3)):
                img.putpixel((img.width - 2, 16 + k * 3), look.WHITE if page is pages[k] else look.DARK)


class SetupCode(Style):
    """The topic's address as a QR code, so a phone can scan it while it's being set up. Add this screen when
    you set up a phone and take it out afterwards: anyone who can see the panel can scan it."""
    fps = 2
    LIGHT, INK = (235, 235, 235), (0, 0, 0)

    def setup(self):
        self.font = self.ctx.fonts(look.FONT)

    def render(self, now):
        img = Image.new("RGB", (self.ctx.width, self.ctx.height))
        f = self.font
        self.private = False                      # (True only while the code itself is drawn: see below)
        _, _, topic = kept()
        topic = (self.ctx.module_settings or {}).get("topic") or topic
        if self.ctx.preview:                      # a picture for the dashboard: never the code itself
            return self.words(img, ["SETUP", "CODE:", "SHOWN ON", "THE PANEL", "ONLY"])
        if not topic or not ntfy.TOPIC.match(topic):
            return self.words(img, ["NO TOPIC", "YET: SEE", "SETTINGS"])
        dots = qr.matrix(ntfy.address(topic))       # always the full https:// address, so a phone opens it as it is
        if not dots or len(dots) + 2 > min(img.height, img.width):
            return self.words(img, ["NO ROOM", "FOR THE", "CODE"] if dots else ["TOPIC TOO", "LONG FOR", "A CODE"])
        self.private = True                       # the topic: on the panel only, never in a picture on the web (the
        #                                           hub's, the Now page's): those show the Matrix's padlocked stand-in
        side = len(dots) + 2                      # a light border round it, one dot wide: scanners need it
        y0 = (img.height - side) // 2
        img.paste(self.LIGHT, (0, y0, side, y0 + side))
        for y, row in enumerate(dots):
            for x, dark in enumerate(row):
                if dark:
                    img.putpixel((1 + x, y0 + 1 + y), self.INK)
        lines = ["SCAN", "WITH", "YOUR", "PHONE"]
        room = img.width - side - 2
        if room >= f.width("PHONE"):
            top = max(0, (img.height - len(lines) * look.ROW) // 2)
            for i, line in enumerate(lines):
                f.draw(img, side + 2 + (room - f.width(line)) // 2, top + i * look.ROW + 5, line, look.GREY)
        return img

    def words(self, img, lines):
        top = max(0, (img.height - len(lines) * look.ROW) // 2)
        for i, line in enumerate(lines):
            look.centred(img, self.font, top + i * look.ROW, line, look.GREY)
        return img
