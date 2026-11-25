"""What the background task and the screens share: they run in one process (the module's own), so the task fills
these as the phones draw and the screens draw from them, frame by frame."""
from __future__ import annotations

import datetime as dt

from . import wall as walls

QUIET = 8.0          # s after the last dot that someone counts as still drawing (the wall stays on, cut in, till then)
PEN_SHOWS = 1.5      # s a phone's pen shows on the panel after its last dot
NAME_SHOWS = 2.5     # s the names of who's drawing show, from when they start

STRAIGHT_AWAY, WAIT = "Show it straight away", "Wait for its turn"
NEVER, MIDNIGHT, A_DAY = "Never", "Every night at midnight", "A day after the last drawing"
SKIP, DRAW_ON_ME = "Skip its screen", 'Show "Draw on me"'
POPUP_OFF = "Off"
POPUPS = (POPUP_OFF, "On, for 5 seconds", "On, for 10 seconds", "On, for 15 seconds", "On, for 20 seconds", "On, for 30 seconds")
DEFAULTS = {"start": STRAIGHT_AWAY, "popup": POPUP_OFF, "keep": 5, "clear_by_itself": NEVER, "when_empty": SKIP,
            "show_who": True}
ADDRESS = "MATRIX.LOCAL"   # where to draw, on an empty wall, until the Matrix has said its own name

STATE: dict = {"wall": None}
# device -> {"who": "MUM", "c": colour of the line, "x", "y": where the pen is, "at": time of its last dot,
#            "since": when this spell of drawing started, "colour": that person's own colour}
PENS: dict[str, dict] = {}
# the live cut-in: when it was asked for, when its look first drew (so the next can follow on), when it ended,
# and when a drawing was last sent (the cut-in gives way to the sent pop-up)
LIVE: dict = {"asked": None, "shown": None, "ended": None, "sent": 0.0}
SEEN: dict = {"size": None, "address": ""}   # the panel's size as a screen last drew it; the Matrix's address
TAGS: dict = {}               # where the names of who's drawing are on the panel, and since when (screens.names)   # the panel's size, as a screen of the module last drew it


def wall() -> walls.Wall:
    """The wall: the task's, or, for a screen drawn before the task's first tick (or a preview, where there is no
    task), whatever was kept in the working folder."""
    if STATE["wall"] is None:
        STATE["wall"] = walls.load()
    return STATE["wall"]


def setting(settings: dict | None, name: str):
    value = (settings or {}).get(name, DEFAULTS[name])
    return DEFAULTS[name] if value is None else value


def address() -> str:
    """Where people draw: the name the Matrix is reached by (the task hears it from the Matrix), in capitals, or
    MATRIX.LOCAL until it has said."""
    return (SEEN.get("address") or ADDRESS).upper()


def popup_seconds(settings: dict | None) -> int:
    """How long a sent drawing pops up for: 0 when the owner hasn't switched the pop-up on."""
    value = str(setting(settings, "popup"))
    digits = "".join(c for c in value if c.isdigit())
    return int(digits) if value in POPUPS and digits else 0


def when(at: float, now: dt.datetime) -> str:
    """When something was drawn, as the panel says it: 10:42 today, YESTERDAY, MON within the week, else 12 NOV.
    ``now`` carries the Matrix's time zone."""
    then = dt.datetime.fromtimestamp(at, now.tzinfo)
    days = (now.date() - then.date()).days
    if days <= 0:
        return then.strftime("%H:%M")
    if days == 1:
        return "YESTERDAY"
    if days < 7:
        return then.strftime("%a").upper()
    return f"{then.day} {then.strftime('%b').upper()}"


def drawing_now(at: float) -> list[tuple[str, dict]]:
    """The pens that have drawn in the last QUIET seconds, first to start first."""
    return sorted(((d, p) for d, p in PENS.items() if at - p["at"] < QUIET), key=lambda dp: dp[1]["since"])
