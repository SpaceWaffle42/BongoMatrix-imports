"""What the panel says about each parcel: the words, the colour, the line under them and where the van is along
the route. Worked out from the module's settings (the parcels and their nicknames, read afresh so a new nickname
shows at once) and what the background task has found out (``store``)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import parse

ALLOWANCE = 10          # new parcels a month on Ship24's free plan
SLOTS = 4               # Parcel 1 to Parcel 4 on the card

# the Matrix's own colours, none of them a courier's
INK = {"transit": (0x9f, 0xc2, 0xff), "today": (0xff, 0xb5, 0x47), "out": (0xff, 0xd8, 0x4a), "delivered": (0x4a, 0xde, 0x80),
       "problem": (0xff, 0x7a, 0x6b), "quiet": (0x9a, 0xa1, 0xac)}
WORDS = {"pending": "NOT FOUND YET", "info": "NOT SENT YET", "transit": "ON ITS WAY", "today": "ARRIVES TODAY",
         "out": "OUT FOR DELIVERY", "failed": "MISSED DELIVERY", "pickup": "READY TO COLLECT", "problem": "HELD UP",
         "delivered": "DELIVERED", "checking": "CHECKING", "waiting": "WAITING", "needs_key": "NEEDS A KEY"}
# along the route bar: 0 posted, 1 at the depot, 2 out for delivery, 3 home
PLACE = {"pending": 0, "info": 0, "transit": 1, "today": 1.5, "out": 2, "failed": 2.5, "pickup": 2.5, "problem": 1,
         "delivered": 3, "checking": 0, "waiting": 0, "needs_key": 0}
FIRST = {"out": 0, "today": 1, "failed": 2, "pickup": 3, "problem": 4, "transit": 5, "info": 6, "pending": 7,
         "checking": 8, "waiting": 9, "needs_key": 10, "delivered": 11}   # the order they take turns in


@dataclass
class Shown:
    number: str
    nickname: str
    state: str           # a key of WORDS
    words: str
    ink: tuple
    line: str            # the line under: a time slot or a day, and the courier
    when: str            # just the time slot or day (12:15-13:15, BY 21:00, THU 27 NOV, 11:42)
    place: float         # along the route, 0 to 3
    moving: bool         # the van drives (or creeps) on
    courier: str | None
    delivered_at: dt.datetime | None
    where: str | None


def typed(settings: dict) -> list[tuple[int, parse.Typed]]:
    """(slot, what was typed) for each Parcel box with something in it, in order."""
    out = []
    for k in range(1, SLOTS + 1):
        found = parse.read(str(settings.get(f"parcel_{k}") or ""))
        if found is not None:
            out.append((k, found))
    return out


def shown(settings: dict, state: dict, now: dt.datetime) -> list[Shown]:
    """The parcels to show now, in the order they take turns: out for delivery first, then arriving today, then the
    rest by when they're due; delivered ones last, until they're older than "Keep delivered" days."""
    keep = dt.timedelta(days=_number(settings.get("keep_days"), 2))
    out = []
    for slot, t in typed(settings):
        if not t.number:
            continue
        kept = (state.get("parcels") or {}).get(t.number) or {}
        one = describe(slot, t, kept, now)
        if one.state == "delivered" and one.delivered_at is not None and now - one.delivered_at > keep:
            continue                                   # delivered a while ago: dropped
        out.append(one)
    return sorted(out, key=lambda s: (FIRST[s.state], _eta_key(state, s), s.number))


def _eta_key(state, s) -> str:
    return ((state.get("parcels") or {}).get(s.number, {}).get("result") or {}).get("eta") or "9999"


def describe(slot: int, t: parse.Typed, kept: dict, now: dt.datetime) -> Shown:
    nickname = (t.nickname or f"Parcel {slot}").upper()
    found = kept.get("result")
    if not found:
        state = "needs_key" if kept.get("error") == "needs_key" else "waiting" if kept.get("waiting") else "checking"
        line = f"FROM {first_of_next_month(now)}" if state == "waiting" else "SEE SETTINGS" if state == "needs_key" else ""
        return Shown(t.number, nickname, state, WORDS[state], INK["quiet"], line, line, PLACE[state], False, None, None, None)
    state = found["state"]
    today = now.date().isoformat()
    if state in ("info", "transit") and found.get("eta") == today:
        state = "today"
    done = _local(found.get("delivered_at"), now) if state == "delivered" else None
    ink = INK["delivered"] if state == "delivered" else INK["out"] if state == "out" else INK["today"] if state == "today" \
        else INK["problem"] if state in ("failed", "problem") else INK["quiet"] if state == "pending" else INK["transit"]
    when = _when(state, found, now, done)
    courier = (found.get("courier") or "").upper() or None
    line = " ".join(w for w in (when, courier) if w)
    return Shown(t.number, nickname, state, WORDS[state], ink, line, when, PLACE[state],
                 state in ("transit", "today", "out", "info"), courier, done, found.get("where"))


def _when(state: str, found: dict, now: dt.datetime, done) -> str:
    """The time slot (12:15-13:15, BY 21:00), or the day it's due (THU 27 NOV), or when it came."""
    if state == "delivered":
        return _day_and_time(done, now) if done else ""
    slot = found.get("slot")
    if state in ("out", "today", "failed") or (found.get("eta") == now.date().isoformat()):
        if slot and slot[0] and slot[1]:
            return f"{slot[0]}-{slot[1]}"
        if slot and slot[1]:
            return f"BY {slot[1]}"
        return "TODAY" if state in ("out", "today") else ""
    if state == "pickup":
        return found.get("where") or ""
    eta = found.get("eta")
    if eta and state in ("info", "transit", "problem"):
        try:
            day = dt.date.fromisoformat(eta)
        except ValueError:
            return ""
        if day == now.date() + dt.timedelta(days=1):
            return "TOMORROW"
        if day >= now.date():
            return day.strftime("%a %-d %b").upper()
    return ""


def _day_and_time(done: dt.datetime, now: dt.datetime) -> str:
    """11:42 today; YESTERDAY or THU 11:42 before that."""
    hm = done.strftime("%H:%M") if (done.hour, done.minute) != (0, 0) else ""
    if done.date() == now.date():
        return hm or "TODAY"
    if done.date() == now.date() - dt.timedelta(days=1):
        return "YESTERDAY" if not hm else f"YDAY {hm}"
    return done.strftime("%a").upper() + (f" {hm}" if hm else "")


def _local(text, now: dt.datetime) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return when.replace(tzinfo=now.tzinfo) if when.tzinfo is None else when.astimezone(now.tzinfo)


def first_of_next_month(now: dt.datetime) -> str:
    """1 DEC: when this month's free parcels start again."""
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return dt.date(year, month, 1).strftime("%-d %b").upper()


def _number(value, default):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default
