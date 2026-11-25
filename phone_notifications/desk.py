"""What the module keeps (``Book``: the last few notifications, in a file in its working folder) and when a
pop-up may go up (``Desk``: the gap between pop-ups, quiet hours and the sleep hours). Plain Python, with the
time passed in, so all of it can be tested without a Matrix or a network."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path

from . import kinds, ntfy

FILE = "notifications.json"     # in the module's working folder (the only place it may write); never in a backup
DAY = 24 * 3600                 # a notification is forgotten a day after it came
STALE = 15 * 60                 # one heard this late (catching up after a long drop) goes in the list, but never pops up
MOST_SEEN = 300                 # ids remembered, so one heard again on catching up isn't shown twice

WHO, WHO_TEXT, KIND = "Only who it's from", "Who and the text", "Only the kind of app"
SHOWS = [WHO, WHO_TEXT, KIND]
GAPS = {"2 minutes": 120, "5 minutes": 300, "15 minutes": 900, "30 minutes": 1800}
MOST_TEXT, MOST_TITLE = 120, 40  # what the Matrix takes in a short message


# -- the notifications kept ----------------------------------------------------------------------------------
def _key(topic: str) -> str:
    """A topic as the book files it: never the name itself, which is a secret."""
    return hashlib.sha256(topic.encode()).hexdigest()[:16]


def _number(value) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else 0.0


class Book:
    def __init__(self, path: Path | str = FILE):
        self.path = Path(path)
        self.data = self._read()
        self.dirty = False

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            data = {}
        data = data if isinstance(data, dict) else {}
        notes = [n for n in data.get("notes", []) if isinstance(n, dict) and isinstance(n.get("id"), str)]
        return {"made": data.get("made") if isinstance(data.get("made"), str) else "",
                "heard_made": data.get("heard_made") is True,
                "since": data.get("since") if isinstance(data.get("since"), dict) else {},
                "seen": [s for s in data.get("seen", []) if isinstance(s, str)][-MOST_SEEN:],
                "notes": notes, "last_pop": _number(data.get("last_pop")),
                "day": str(data.get("day") or ""), "today": int(_number(data.get("today")))}

    def save(self) -> None:
        if not self.dirty:
            return
        part = self.path.with_name(self.path.name + ".part")
        part.write_text(json.dumps(self.data))
        os.replace(part, self.path)                 # (all or nothing, even if the process is stopped half way)
        self.dirty = False

    def _changed(self):
        self.dirty = True

    # the topic the module made itself, when the owner hasn't typed one
    def made_topic(self) -> str:
        if not ntfy.TOPIC.match(self.data["made"]):
            self.data["made"], self.data["heard_made"] = ntfy.make_topic(), False
            self._changed()
            self.save()                             # (at once: it is what the phone will be told)
        return self.data["made"]

    def since(self, topic: str) -> str | None:
        return self.data["since"].get(_key(topic))

    def heard(self, topic: str, event_id: str, made: bool) -> None:
        self.data["since"] = {_key(topic): event_id}   # (one topic at a time: another's place is no use)
        if made and not self.data["heard_made"]:
            self.data["heard_made"] = True
        self._changed()

    def seen(self, event_id: str) -> bool:
        return event_id in self.data["seen"] or any(n["id"] == event_id for n in self.data["notes"])

    def remember(self, event_id: str) -> None:
        self.data["seen"] = (self.data["seen"] + [event_id])[-MOST_SEEN:]
        self._changed()

    def count(self, day: str) -> int:
        """One more today; how many today."""
        if self.data["day"] != day:
            self.data["day"], self.data["today"] = day, 0
        self.data["today"] += 1
        self._changed()
        return self.data["today"]

    def today(self, day: str) -> int:
        return self.data["today"] if self.data["day"] == day else 0

    def add(self, note: dict, keep: int) -> None:
        self.data["notes"] = sorted([note] + self.data["notes"], key=lambda n: -n.get("at", 0))[:max(1, keep)]
        self.remember(note["id"])

    def forget(self, now: float, keep: int) -> None:
        """Only the last ``keep``, and none older than a day."""
        notes = [n for n in self.data["notes"] if now - n.get("at", 0) < DAY][:max(1, keep)]
        if notes != self.data["notes"]:
            self.data["notes"] = notes
            self._changed()

    def clear(self) -> None:
        if self.data["notes"]:
            self.data["notes"] = []
            self._changed()

    @property
    def notes(self) -> list[dict]:
        return list(self.data["notes"])


def note_from(event: dict) -> dict:
    """A notification as the module keeps it, from what ntfy sent."""
    tags = [str(t) for t in event.get("tags") or [] if isinstance(t, (str, int))][:5]
    app = next((kinds.plain(t, 30) for t in tags if t.strip().lower().replace(" ", "_") not in kinds.WORDS), "")
    kind = kinds.kind_of(tags, app)
    who = kinds.plain(event.get("title") or "", MOST_TITLE)
    try:
        at = float(event.get("time"))
    except (TypeError, ValueError):
        at = 0.0
    return {"id": event["id"], "at": at, "kind": kind, "app": app, "who": who or app or kinds.KINDS[kind][0],
            "text": kinds.text_of(event.get("message"))}


# -- quiet hours --------------------------------------------------------------------------------------------
_TIME = r"\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\s*"


def _minutes(match) -> int:
    hour, minute, half = int(match[0]), int(match[1] or 0), (match[2] or "").lower()
    if half:
        if not 1 <= hour <= 12:
            raise ValueError
        hour = hour % 12 + (12 if half == "pm" else 0)
    if not (0 <= hour <= 24 and 0 <= minute < 60) or (hour == 24 and minute):
        raise ValueError
    return (hour * 60 + minute) % (24 * 60)


def quiet_hours(text) -> tuple[int, int] | None:
    """"21:30-07:00" (or "9.30pm to 7am") as minutes after midnight (from, to); None for none. Raises
    ValueError for anything else."""
    text = str(text or "").strip().lower()
    if not text:
        return None
    match = re.fullmatch(_TIME + r"(?:-|–|to|until)" + _TIME, text)
    if not match:
        raise ValueError(text)
    start, end = _minutes(match.groups()[:3]), _minutes(match.groups()[3:])
    return None if start == end else (start, end)


def in_quiet(minute: int, span) -> bool:
    if not span:
        return False
    start, end = span
    return start <= minute < end if start < end else (minute >= start or minute < end)


# -- pop-ups ------------------------------------------------------------------------------------------------
class Desk:
    """Notifications waiting to pop up. ``due`` says when some may, and which: at most one pop-up every
    ``gap`` seconds (those in between wait and go up together), none while ``hushed`` (quiet or sleep hours),
    and when those end, one summary of what came meanwhile (or nothing, if the owner said so)."""

    def __init__(self, last_pop: float = 0.0):
        self.waiting: list[dict] = []
        self.last_pop = last_pop
        self.hushed = False

    def add(self, note: dict) -> None:
        self.waiting.append({**note, "quiet": False})

    def due(self, now: float, hushed: bool, gap: float, summary: bool):
        """(notes, while_quiet) to pop up now, or None."""
        if now < self.last_pop:                     # (the clock went back)
            self.last_pop = 0.0
        if hushed:
            for note in self.waiting:
                note["quiet"] = True
            self.hushed = True
            return None
        if self.hushed:                             # quiet (or sleep) has just ended
            self.hushed = False
            if not summary:
                self.waiting = [n for n in self.waiting if not n["quiet"]]
        if not self.waiting or now - self.last_pop < gap:
            return None
        notes, self.waiting, self.last_pop = self.waiting, [], now
        return notes, any(n["quiet"] for n in notes)

    def refused(self, notes: list[dict], now: float) -> None:
        """The Matrix didn't show them (too many messages just now): they wait for the next gap."""
        self.waiting = notes + self.waiting
        self.last_pop = now


PLURAL = {"message": ("message", "messages"), "call": ("missed call", "missed calls"),
          "delivery": ("delivery update", "delivery updates"), "email": ("email", "emails"),
          "calendar": ("reminder", "reminders"), "other": ("notification", "notifications")}


WORDS_MOST, TITLE_MOST = 32, 10  # letters of a pop-up's words and title, so the Matrix's banner (shown if the look
#                                  fails) reads them through well inside 20 s, the title without sliding


def _cut(text: str, most: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= most else text[:max(1, most - 1)].rstrip() + "…"


def _names(names: list[str], most: int = WORDS_MOST) -> str:
    """"Mum, Jo and Sam", or as many as fit in ``most`` letters and how many more: "Mum, Jo +1"."""
    names = list(dict.fromkeys(names))              # (each once, in the order they came)
    if len(names) == 1:
        return _cut(names[0], most)
    whole = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    if len(whole) <= most:
        return whole
    for k in range(len(names) - 1, 0, -1):
        said = ", ".join(_cut(n, 12) for n in names[:k]) + f" +{len(names) - k}"
        if len(said) <= most:
            return said
    return _cut(names[0], most - 4) + f" +{len(names) - 1}"


def _counts(counts: dict, most: int = WORDS_MOST) -> str:
    """"2 messages, 1 missed call", or as many kinds as fit and how many more."""
    parts = [f"{n} {PLURAL[k][n != 1]}" for k, n in counts.items()]
    for k in range(len(parts), 0, -1):
        rest = sum(counts.values()) - sum(int(p.split(" ")[0]) for p in parts[:k])
        said = ", ".join(parts[:k]) + (f" +{rest}" if rest else "")
        if len(said) <= most:
            return said
    return _cut(parts[0], most)


def compose(notes: list[dict], show: str, quiet: bool = False, size=(64, 32)) -> tuple[str, str, float]:
    """A pop-up's (title, text, seconds) for some notifications, saying only what ``show`` allows. The words are what
    the Matrix's banner shows if the look fails, so they are short: a title of at most 10 letters and words of at
    most 32, cut with "…", read well inside the 20 s the Matrix gives them. The seconds are the look's."""
    notes = sorted(notes, key=lambda n: n.get("at", 0))
    if len(notes) == 1 and not quiet:
        note = notes[0]
        kind = note.get("kind", "other")
        if show == KIND:
            title, text = "Phone", kinds.NEW[kind]
        elif show == WHO_TEXT:
            title, text = note["who"], note.get("text") or kinds.NEW[kind]
        else:
            title, text = note["who"], kinds.NEW[kind]
    else:
        n = len(notes)
        title = (f"{n} in quiet" if n < 10 else f"{n} quiet") if quiet else f"{n} new"
        if show == KIND:
            counts: dict[str, int] = {}
            for note in notes:
                counts[note.get("kind", "other")] = counts.get(note.get("kind", "other"), 0) + 1
            text = _counts(counts)
        elif show == WHO_TEXT:
            text = _each_said([(n["who"], n.get("text") or "") for n in notes])
        else:
            text = "From " + _names([n["who"] for n in notes], WORDS_MOST - 5)
    title, text = _cut(title, TITLE_MOST), _cut(text or "New", WORDS_MOST)
    return title, text, look_seconds(popup_data(notes, show, quiet), size)


def _each_said(said: list[tuple[str, str]], most: int = WORDS_MOST) -> str:
    """"Mum: Home at 6. Jo: Missed call", every name kept: the longest text is cut first (with "…"), and a text
    cut to nothing goes; only if the names alone are too long, as many as fit and how many more."""
    said = [[who, text] for who, text in said]

    def joined():
        parts = [f"{who}: {text}" if text else who for who, text in said]
        return "".join(p + ("" if k == len(parts) - 1 else " " if p.endswith("…") else ". ") for k, p in enumerate(parts))
    while len(joined()) > most:
        longest = max(said, key=lambda p: len(p[1]))
        if not longest[1]:
            return _names([who for who, _ in said], most)
        longest[1] = "" if len(longest[1]) <= 3 else longest[1].rstrip("…")[:-2].rstrip() + "…"
    return joined()


LETTER, HOLD, SPEED = 4, 1.5, 20   # the look's small font, and how its line slides (held, then 20 px/s)


def look_seconds(data: dict, size=(64, 32)) -> float:
    """How long the pop-up is up: what its look (popups.Note) needs on a panel of ``size`` (the module area: the
    background task's ``panel.size``) to slide in, let its line under be read once, and go; at least 6 s, never more
    than 19 (a second's slack under 20). On a tall panel (48 dots or more) nothing slides: the text is wrapped over
    lines of its own, so the time follows how much there is to read. Only what the look needs: if it fails, the Matrix gives its words the time
    they need to be read (module API 3)."""
    width, height = size
    notes = data.get("notes") or [{}]
    one = data.get("count", 1) == 1 and not data.get("quiet")
    if one:
        line = notes[-1].get("text") or "SEE YOUR PHONE"
    else:
        line = "  ".join(f"{n.get('who') or n.get('kind', '')}: {n.get('text', '')}" if n.get("text")
                         else (n.get("who") or n.get("kind", "")) for n in notes)
    if height >= 48:
        need = 6.0 + 0.08 * max(0, len(line) - 30)                     # (about a word a second, past the first few)
    else:
        room, wide = width - 4, len(line) * LETTER - 1
        need = 0.35 + (0 if wide <= room else HOLD * 2 + (wide - room) / SPEED) + 0.5 + 0.2 + 1.0
    return min(19.0, max(6.0, math.ceil(need * 10) / 10))   # (a second's slack under the Matrix's 20)


MOST_DATA = 2000                 # bytes of JSON a pop-up's look may be given (the Matrix allows 2 KB)
MOST_NOTES = 8                   # notifications a pop-up's look lists at most (a bundle: the newest)


def popup_data(notes: list[dict], show: str, quiet: bool = False) -> dict:
    """What the pop-up's look draws (popups.Note), saying no more than ``show`` allows, just as ``compose`` does:
    the kind and when of each, who (unless only the kind is shown) and the text (only with "Who and the text").
    The newest few, cut until it is well inside the 2 KB a pop-up may be given."""
    notes = sorted(notes, key=lambda n: n.get("at", 0))
    way = {WHO: "who", WHO_TEXT: "all", KIND: "kind"}.get(show, "who")
    items = []
    for note in notes[-MOST_NOTES:]:
        item = {"kind": note.get("kind", "other") if note.get("kind") in kinds.KINDS else "other", "at": round(_number(note.get("at")))}
        if way != "kind":
            item["who"] = str(note.get("who") or "")[:MOST_TITLE]
        if way == "all" and note.get("text"):
            item["text"] = str(note["text"])[:MOST_TEXT]
        items.append(item)
    data = {"show": way, "quiet": bool(quiet), "count": len(notes), "notes": items}
    while len(json.dumps(data).encode()) > MOST_DATA:
        longest = max(items, key=lambda i: len(i.get("text", "")))
        if len(items) > 1 and not longest.get("text"):
            items.pop(0)                            # (the oldest goes first)
        elif longest.get("text"):
            longest["text"] = longest["text"][:len(longest["text"]) // 2]
        else:
            break
    return data

