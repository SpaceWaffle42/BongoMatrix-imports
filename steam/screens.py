"""The four screens: friends online, now playing, recent games and the newest achievement. They draw what the
background task last found (``seen.SEEN``); its pictures come from Steam and its fixed art (the dots, the trophy,
the controller...) from the Animator drawings in ``art/``."""
from __future__ import annotations

import math
import time
from functools import lru_cache
from pathlib import Path

from PIL import Image

from bongo import sprites
from bongo.module import Style
from bongo.scroll import HOLD, Scrolls

from . import pictures, seen
from .seen import SEEN
from .task import steam_app
from .words import drawable, hours, percent, since

ART = Path(__file__).parent / "art"
WHITE, GREY, DIM, LINE = (242, 238, 230), (180, 186, 194), (110, 116, 124), (40, 44, 50)
GOLD, PURPLE, AMBER = (255, 201, 74), (195, 140, 255), (255, 181, 71)
SPEED, GAP = 14, 16              # px a second a long line scrolls, and the gap before it comes round again
GAP_BEFORE_HOURS = 4            # clear dots between a recent game's name and its hours
RARE = 10.0                      # % of players or fewer: said to be rare
EMPTY_FOR = 0.0                  # s a screen with nothing to show says so before handing over: none, it skips its
#                                  turn at once (the words are still drawn for the dashboard's picture of it)
TROUBLE_FOR = 6.0                # ... and one that can't show anything (no key, a private profile)


@lru_cache(maxsize=None)
def art(name: str):
    """One of the module's Animator drawings (read once in this process)."""
    return sprites.read(ART / f"{name}.json")


@lru_cache(maxsize=None)
def dot(state: str) -> Image.Image:
    """The status dot for in game, online or away: one layer each of the drawing ``dot``."""
    return art("dot").layer({seen.IN_GAME: "In game", seen.ONLINE: "Online", seen.AWAY: "Away"}[state])


@lru_cache(maxsize=None)
def ink(state: str) -> tuple:
    """The colour words about someone are written in: the middle of their dot, so the drawing decides it."""
    return dot(state).getpixel((1, 1))[:3]


class Base(Scrolls, Style):
    fps = 20
    PROBLEM_PARTS = ()          # the private parts of a profile that stop this screen (seen.SEEN["private"])

    def setup(self):
        seen.load()
        self.font = self.ctx.fonts("tom-thumb")
        self.began = None
        if not self.ctx.preview and not self.problem()[1] and self.empty():
            self.finished = True        # nothing to show: skipped before its first frame (the dashboard's picture
            #                             of it still says so)

    def empty(self) -> bool:
        """Whether there's nothing of this screen's to show just now (nobody on, no recent games...)."""
        return False

    # -- writing ---------------------------------------------------------------------------------------
    def words(self, text: str) -> str:
        return drawable(text, self.font)

    def width(self, text: str) -> int:
        return max(0, self.font.width(text) - 1)          # (the last letter's spacing isn't drawn)

    def text(self, img, x, top, text, colour):
        self.font.draw(img, x, top + self.font.cap, text, colour)

    def ink_left(self, text: str) -> int:
        """Blank columns before ``text``'s first lit dot (a "1" is drawn at the right of its cell)."""
        probe = Image.new("L", (self.font.width(text) + 2, self.font.cap + 2))
        self.font.draw(probe, 0, self.font.cap, text, 255)
        box = probe.getbbox()
        return box[0] if box else 0

    def need(self, text, w) -> float:
        """Seconds for ``text`` to be read through once in ``w`` px (0: it fits)."""
        tw = self.width(text)
        return 0.0 if tw <= w else HOLD + (tw + 1 + GAP) / SPEED

    def marquee(self, img, x, top, w, text, colour, t):
        """``text`` in ``w`` px from ``x``: still if it fits; otherwise held at its start, then round (``t``: seconds
        since it came on), as every scrolling line on the Matrix does."""
        if w <= 0:
            return
        if self.width(text) <= w:
            return self.text(img, x, top, text, colour)
        period = self.font.width(text) + GAP
        off = int(max(0.0, t - HOLD) * SPEED) % period
        lane = Image.new("RGB", (w, img.height))
        for k in (0, 1):
            self.font.draw(lane, -off + k * period, top + self.font.cap, text, colour)
        img.paste(lane, (x, 0), lane.convert("L").point(lambda v: 255 if v else 0))

    def centred(self, img, lines, top, colour):
        for k, line in enumerate(lines):
            line = self.words(line)
            self.text(img, max(0, (img.width - self.width(line)) // 2), top + k * 6, line, colour)

    # -- when there's nothing to draw ------------------------------------------------------------------
    def clock(self, now) -> float:
        if self.began is None:
            self.began = now.timestamp()
        return now.timestamp() - self.began

    def hand_over_after(self, t, seconds):
        if t >= seconds and not self.ctx.preview:
            self.finished = True

    def problem(self) -> tuple[str | None, list[str], tuple]:
        """What stops this screen showing anything: (an icon drawing or None, the words, their colour), or (None, [], ())."""
        p = SEEN.get("problem") or {}
        kind = p.get("kind")
        if not kind and not SEEN.get("me"):                 # the background task hasn't said yet (or isn't running:
            given = self.ctx.module_settings or {}          # the import's test screen): go by the settings
            kind = "no_key" if not given.get("api_key") else "no_profile" if not str(given.get("profile", "")).strip() else "asking"
        if kind == "no_key":
            return "key", ["ADD A STEAM", "KEY IN SETTINGS"], AMBER
        if kind in ("no_profile", "bad_profile"):
            return "key", ["ADD YOUR STEAM", "PROFILE IN", "SETTINGS"], AMBER
        if kind == "no_such_profile":
            return None, ["NO SUCH", "STEAM PROFILE"], AMBER
        if kind == "key":
            return "key", ["STEAM DIDN'T", "ACCEPT THE KEY"], AMBER
        private = [part for part in ("profile", *self.PROBLEM_PARTS) if part in SEEN.get("private", [])]
        if private and not self.has_news():
            return "lock", {"profile": ["PROFILE IS", "PRIVATE"], "friends": ["FRIENDS LIST", "IS PRIVATE"],
                            "games": ["GAME DETAILS", "ARE PRIVATE"]}[private[0]], GREY
        if self.has_news():
            return None, [], ()
        if kind == "network":
            return None, ["CAN'T REACH", "STEAM"], GREY
        if kind in ("busy", "steam"):
            return None, ["STEAM IS BUSY:", "TRYING AGAIN", "SOON"], GREY
        return None, ["ASKING STEAM…"], DIM

    def has_news(self) -> bool:
        """Whether there's anything of this screen's to show (even from a while ago)."""
        return bool(SEEN.get("me"))

    def say_problem(self, now, icon, lines, colour):
        img = self.ctx.canvas()
        sprite = art(icon).frame(0) if icon else None
        block = len(lines) * 6 - 1 + (sprite.height + 3 if sprite else 0)
        top = max(0, (img.height - block) // 2)
        if sprite:
            img.paste(sprite, ((img.width - sprite.width) // 2, top), sprite)
            top += sprite.height + 3
        self.centred(img, lines, top, colour)
        self.hand_over_after(self.clock(now), TROUBLE_FOR)
        return img

    def render(self, now):
        icon, lines, colour = self.problem()
        if lines:
            return self.say_problem(now, icon, lines, colour)
        return self.draw(now)

    def draw(self, now) -> Image.Image:
        raise NotImplementedError


class Friends(Base):
    """Friends online: who's on and what they're playing, those in a game first. A page of four on a 32-dot-high
    panel (more on a taller one); the pages take turns, each on until its long names have gone round once."""
    PROBLEM_PARTS = ("friends",)
    PAGE = 5.0

    def has_news(self):
        return bool(SEEN.get("me")) and "friends" not in SEEN.get("private", [])

    def empty(self):
        return not seen.friends_shown(self.ctx.module_settings or {})

    def draw(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        shown = seen.friends_shown(self.ctx.module_settings or {})
        self.text(img, 1, 0, "FRIENDS", GREY)
        count = f"{len(shown)} ON"
        self.text(img, w - self.width(count) - 1, 0, count, ink(seen.ONLINE))
        img.paste(LINE, (0, 6, w, 7))
        if not shown:
            self.centred(img, ["NOBODY'S ON"], 7 + (h - 7) // 2 - 3, DIM)
            self.hand_over_after(self.clock(now), EMPTY_FOR)
            return img
        rows = max(1, (h - 7) // 6)
        pages = [tuple(shown[k:k + rows]) for k in range(0, len(shown), rows)]
        name_w, label_x = 18, 26
        page, t = self.turns("steam friends", pages, now, lambda p: self.page_time(p, name_w, w - label_x - 1),
                             name=lambda p: tuple(f["steamid"] for f in p))
        for i, friend in enumerate(page):
            y = 8 + i * 6
            img.paste(dot(friend["state"]), (1, y + 1), dot(friend["state"]))
            self.marquee(img, 6, y, name_w, self.words(friend["name"]), WHITE, t)
            label = (friend["game"] or "IN A GAME") if friend["state"] == seen.IN_GAME else friend["state"].upper()
            self.marquee(img, label_x, y, w - label_x - 1, self.words(label), ink(friend["state"]), t)
        return img

    def page_time(self, page, name_w, label_w):
        longest = max(max(self.need(self.words(f["name"]), name_w), self.need(self.words(f["game"] or ""), label_w)) for f in page)
        return max(self.PAGE, longest)


class NowPlaying(Base):
    """Now playing: you or a friend in a game, with the game's capsule art from Steam across the top, who, the game,
    and how long they've been in it (when we saw them start). Several take turns."""
    TURN = 8.0

    def empty(self):
        return not seen.players(self.ctx.module_settings or {})

    def draw(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        people = seen.players(self.ctx.module_settings or {})
        if not people:
            self.centred(img, ["NOBODY'S", "PLAYING"], (h - 11) // 2, DIM)
            self.hand_over_after(self.clock(now), EMPTY_FOR)
            return img
        band = h - 19 if h - 19 >= 6 else 0                  # the picture: what the three lines of words leave
        p, t = self.turns("steam now playing", people, now, lambda p: self.turn_time(p, w), name=lambda p: p["steamid"])
        if band:
            self.banner(img, p, w, band)
        top = band + 2 if band else max(0, (h - 17) // 2)
        mine = p is people[0] and SEEN.get("me") and p["steamid"] == SEEN["me"]["steamid"]
        who, rest = ("YOU", "'RE PLAYING") if mine else (self.words(p["name"]), " IS PLAYING")
        green = ink(seen.IN_GAME)
        if self.width(who + rest) <= w - 2:
            self.text(img, 1, top, who, green)
            self.text(img, 1 + self.font.width(who), top, rest, GREY)
        else:
            self.marquee(img, 1, top, w - 2 - self.width(rest) - 1, who, green, t)
            self.text(img, w - self.width(rest) - 1, top, rest, GREY)
        self.marquee(img, 1, top + 6, w - 2, self.words(p["game"] or "A GAME"), WHITE, t)
        if top + 17 <= h:
            begun = seen.started(p["steamid"])
            if begun:
                length = since(time.time() - begun)
                self.text(img, w - self.width(length) - 1, top + 12, length, GREY)
            for i in range(3):                               # a little "live" pulse
                k = (1 + math.sin(now.timestamp() * 3 - i)) / 2
                img.putpixel((2 + i * 2, top + 14), tuple(int(a + (b - a) * k) for a, b in zip((58, 63, 71), green)))
        return img

    def turn_time(self, p, w):
        return max(self.TURN, self.need(self.words(p["game"] or ""), w - 2), self.need(self.words(p["name"]), w - 50))

    def banner(self, img, p, w, band):
        appid = steam_app(p.get("gameid"))
        picture = pictures.picture(f"capsule:{appid}", w, band) if appid else None
        if picture is not None:
            img.paste(picture, (0, 0))
            return
        img.paste((22, 26, 34), (0, 0, w, band))                # no picture (yet, or a game Steam has none for)
        pad = art("controller").frame(0)
        img.paste(pad, ((w - pad.width) // 2, (band - pad.height) // 2), pad)


class Recent(Base):
    """Recent games: your games of the last two weeks, most played first, with the hours and a bar each."""
    PROBLEM_PARTS = ("games",)

    def has_news(self):
        return bool(SEEN.get("me")) and "games" not in SEEN.get("private", [])

    def empty(self):
        return not SEEN.get("recent")

    def draw(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        self.text(img, 1, 1, "LAST 2 WEEKS", GREY)
        games = SEEN.get("recent") or []
        t = self.clock(now)
        if not games:
            self.centred(img, ["NO GAMES IN", "TWO WEEKS"], 7 + (h - 7 - 11) // 2, DIM)
            self.hand_over_after(t, EMPTY_FOR)
            return img
        rows = games[:max(1, (h - 5) // 8)]
        most = max(1, rows[0]["minutes"])
        grow = min(1.0, t / 1.2)                               # the bars grow as the screen comes on
        for i, g in enumerate(rows):
            y = 7 + i * 8
            icon = pictures.picture(f"icon:{g['appid']}", 6, 6)
            img.paste(icon if icon is not None else art("tile").frame(0), (1, y),
                      None if icon is not None else art("tile").frame(0))
            spent = hours(g["minutes"])
            hx = w - self.width(spent) - 1
            self.text(img, hx, y, spent, WHITE)
            lane = hx + self.ink_left(spent) - GAP_BEFORE_HOURS - 9      # the name's window stops well short of the hours
            name = self.words(g["name"])
            self.marquee(img, 9, y, lane, name, WHITE, self.scrolled(("recent", i, name), now, self.need(name, lane)))
            img.paste(LINE, (9, y + 6, w - 1, y + 7))
            length = round((w - 10) * g["minutes"] / most * grow)
            if length > 0:
                img.paste(pictures.accent(icon), (9, y + 6, 9 + length, y + 7))
        return img


class Achievement(Base):
    """Newest achievement: its icon from Steam (a trophy when there's none), its name, the game, and how many players
    have it. It slides in as the screen comes on, and a glint crosses the icon now and then."""
    PROBLEM_PARTS = ("games",)

    def has_news(self):
        return bool(SEEN.get("me")) and "games" not in SEEN.get("private", [])

    def empty(self):
        return not SEEN.get("achievement")

    def draw(self, now):
        img = self.ctx.canvas()
        w, h = img.size
        a = SEEN.get("achievement")
        t = self.clock(now)
        if not a:
            self.centred(img, ["NO NEW", "ACHIEVEMENTS"], (h - 11) // 2, DIM)
            self.hand_over_after(t, EMPTY_FOR)
            return img
        dx = round(max(0.0, 1 - t / 0.6) * w)                  # slides in from the right
        top = max(0, (h - 29) // 2)
        icon = pictures.picture(f"achievement:{a['appid']}:{a['apiname']}", 12, 12) if a.get("icon") else None
        icon = icon.convert("RGBA") if icon is not None else art("trophy").frame(0)
        icon = self.glint(icon, t)
        img.paste(icon, (1 + (12 - icon.width) // 2 + dx, top + 7 + (12 - icon.height) // 2), icon)
        x = 15
        self.text(img, x + dx, top + 1, "UNLOCKED", GOLD)
        if dx:
            return img
        name = self.words(a["name"])
        self.marquee(img, x, top + 9, w - x - 1, name, WHITE, self.scrolled(("name", a["apiname"]), now, self.need(name, w - x - 1)))
        game = self.words(a["game"] or "")
        self.marquee(img, x, top + 16, w - x - 1, game, GREY, self.scrolled(("game", a["apiname"]), now, self.need(game, w - x - 1)))
        if a.get("percent") is not None:
            rare = a["percent"] <= RARE
            share = percent(a["percent"])
            if rare:
                self.text(img, x, top + 24, "RARE", PURPLE)
            self.text(img, w - self.width(share) - 1, top + 24, share, PURPLE if rare else GREY)
        return img

    def glint(self, icon: Image.Image, t: float) -> Image.Image:
        """A diagonal of light crossing the icon, once every few seconds."""
        k = (t % 4.0) / 0.8
        if k >= 1:
            return icon
        lit = icon.copy()
        px = lit.load()
        line = -4 + k * (icon.width + icon.height + 8)
        for y in range(icon.height):
            for x in range(icon.width):
                r, g, b, al = px[x, y]
                if al and abs(x + y - line) < 1.5:
                    px[x, y] = ((r + 255) // 2, (g + 255) // 2, (b + 255) // 2, al)
        return lit
