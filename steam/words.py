"""Words for the panel: names and games made drawable in the panel's small font, and times said shortly."""
from __future__ import annotations

import math
import unicodedata

SWAPS = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u00a0": " ",
         "\u0141": "L", "\u0110": "D", "\u0126": "H", "\u0130": "I", "\u0131": "I"}   # (letters Unicode has no plain form of)
DROP = "\u2122\u00ae\u00a9"     # TM, (R), (C): in many games' names, and only noise on 64 dots


def drawable(text: str, font) -> str:
    """``text`` in capitals, with what ``font`` can't draw folded to plain letters (É stays, Ł becomes L) or left
    out (emoji, other scripts). Never empty: "?" if nothing is left."""
    out = []
    for ch in str(text).upper():
        ch = SWAPS.get(ch, ch)
        if ch in DROP or not ch.isprintable():
            continue
        if ord(ch) in font.glyphs:
            out.append(ch)
            continue
        plain = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
        out.append("".join(c for c in plain if ord(c) in font.glyphs))
    text = " ".join("".join(out).split())
    return text or "?"


def hours(minutes: int) -> str:
    """Playtime as the recent games screen says it: 40M, 9H, 14.5H, 120H."""
    if minutes < 60:
        return f"{max(0, int(minutes))}M"
    h = minutes / 60
    if h >= 100:
        return f"{round(h)}H"
    h = round(h * 2) / 2
    return f"{h:g}H"


def since(seconds: float) -> str:
    """How long someone has been in a game: 23M, 1H 05M."""
    m = max(0, int(seconds // 60))
    return f"{m}M" if m < 60 else f"{m // 60}H {m % 60:02d}M"


def ago(seconds: float) -> str:
    """For the status line: 20 s ago, 3 min ago, 2 h ago."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} s ago"
    if s < 3600:
        return f"{s // 60} min ago"
    return f"{s // 3600} h ago"


def percent(value: float) -> str:
    """A rarity: 4.2%, 0.3%, 61%."""
    if value >= 10:
        return f"{round(value)}%"
    return f"{value:.1f}%"


# -- the pop-up's timing (shared by the background task, which asks for the seconds, and the look) -------------
POP_DROP, POP_RISE, POP_GONE = 0.4, 0.5, 0.2   # s the band takes to drop in, to go back up, and empty at the very end
POP_HOLD, POP_SPEED = 1.0, 20                  # s a long line is held at its start and at its end; px/s between
#                                                (20: one dot a frame at the player's 20 frames a second, so it moves evenly)
POP_SHORTEST, POP_LONGEST = 8.0, 20.0          # s a pop-up is up: never more than 20 (the Matrix allows 3 to 30)
WORDS_MOST = 32                                # letters of its words (the banner shown if the look fails), so the
#                                                banner reads them through well inside the 20 s the Matrix gives them
LETTER = 4                                     # px a letter of the panel's small font takes (tom-thumb)
NAME_ROOM, GAME_ROOM = 26, 62                  # px for who and for the game on a 64-dot-wide panel


def slide_time(width: int, room: int) -> float:
    """Seconds a line ``width`` px wide takes to be read in ``room`` px: held, slid to its end, held (0: it fits)."""
    return 0.0 if width <= room else POP_HOLD * 2 + (width - room) / POP_SPEED


def slide_offset(width: int, room: int, t: float, stops=()) -> int:
    """How far such a line has slid ``t`` seconds after its turn began (held at its start, then at its end). With
    ``stops`` (where each letter begins, in px), it ends on the first letter that shows the whole end of the line,
    so a letter is never left cut in half at the start of the room."""
    if width <= room:
        return 0
    end = min((s for s in stops if s >= width - room), default=width - room)
    return min(end, round(max(0.0, t - POP_HOLD) * POP_SPEED))   # (rounded: one dot each frame, never 0 then 2)


def cut(text: str, most: int) -> str:
    """``text`` in at most ``most`` letters, ending "…" if it had to be cut."""
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:max(1, most - 1)].rstrip() + "…"


def pop_up_words(name: str, game: str) -> str:
    """The pop-up's words: "Jess started Iron Tide", a long name or game cut short with "…" so the Matrix's own
    banner (shown if the look fails) reads them through well inside the 20 s it gives them."""
    who = cut(name, 9)                               # (a long name gives way to more of the game)
    return f"{who} started {cut(game or 'a game', WORDS_MOST - len(who) - len(' started '))}"


def pop_up_seconds(name: str, game: str) -> float:
    """How long the pop-up is up: long enough for who and then the game to be read through once each on a
    64-dot-wide panel (they take turns sliding, never both at once), between POP_SHORTEST and POP_LONGEST. Only what
    the look needs: if it fails, the Matrix gives its words the time they need to be read (module API 3)."""
    def wide(text):
        return max(0, len(text) * LETTER - 1)
    need = POP_DROP + slide_time(wide(name), NAME_ROOM) + slide_time(wide(game), GAME_ROOM) + POP_RISE + POP_GONE + 1.0
    return min(POP_LONGEST, max(POP_SHORTEST, math.ceil(need * 10) / 10))   # (rounded up: never a moment short)
