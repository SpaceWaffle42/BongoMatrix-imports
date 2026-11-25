"""The background task: hears every phone that has the drawing page open, keeps the wall (shared.STATE) and tells
the other phones each dot as it comes, cuts in on the panel when someone starts drawing, pops a sent drawing up if
the owner wants that, clears the wall by itself if asked to, and says how things stand on the card's status line.

What a page sends (JSON, at most 2 KB each; checked here, whatever the page is):
    {"t": "d", "id": 7, "c": 0-9, "w": 1 or 2, "p": [x, y, x, y...], "e": 1 at a line's end}   dots of one line
    {"t": "text", "s": "GONE TO THE SHOPS", "c": 1-9}                                          words, in the Matrix's letters
    {"t": "undo"}  {"t": "clear"}  {"t": "send"}  {"t": "back", "id": 12}                      (back: put one up again)
What it hears back (at most 8 KB each, 10 a second from the Matrix, so this keeps to 8):
    {"t": "all", "w", "h", "y", "n", "g", "pop", "me"}   the wall from row y, n rows (``wall.encode``); y 0 starts afresh
    {"t": "d", "l": [{"by", "who", "pc", "c", "w", "p"}]}  dots as they come, from every phone (its own too)
    {"t": "hist", "from", "of", "items": [{"id", "who", "when", "w", "h", "g"}]}
    {"t": "here", "names": [...]}   {"t": "said", "s": "..."} (to one phone)
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import time

from bongo.module import Background

from . import letters, shared
from . import wall as walls

TICK = 1
CHUNK = 6000           # characters of picture in one message to the pages (each is at most 8 KB)
MOST_NUMBERS = 1400    # numbers (x, y, ...) in one message of dots to the pages
FLUSH = 0.15           # s between messages of dots to the pages, while someone draws
CUT_IN = 30            # s a cut-in shows for (the most a pop-up may)
FOLLOW_ON = 24         # s into a cut-in that the next is asked for, if the drawing is still going on
REST = 60              # s before trying to cut in again after the Matrix said no (10 pop-ups in ten minutes)
SAVE_EVERY = 5         # s at most between saves of the wall while it changes


class Outbox:
    """What is to go to the pages, sent at the pace the Matrix allows (10 a second, 20 at once), a little under it.
    A message with a ``key`` replaces one with the same key still waiting (a newer picture of the whole wall)."""
    RATE, BURST = 8.0, 16.0

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.tokens, self.at = self.BURST, clock()
        self.queue: collections.deque = collections.deque()

    def add(self, data: dict, to: str | None = None, key=None) -> None:
        if key is not None:
            self.queue = collections.deque(m for m in self.queue if m[2] != key)
        self.queue.append((data, to, key))

    def room(self) -> float:
        now = self.clock()
        self.tokens = min(self.BURST, self.tokens + (now - self.at) * self.RATE)
        self.at = now
        return self.tokens

    def flush(self, page, most: int = 30) -> int:
        sent = 0
        while self.queue and sent < most and self.room() >= 1:
            data, to, _ = self.queue.popleft()
            page.send(data, to=to)
            self.tokens -= 1
            sent += 1
        return sent


def quiet_panel(status: dict | None) -> bool:
    """Whether the wall may cut in or pop up: never in the sleep hours, and never while someone has the panel
    paused (the council: a pause is respected). ``status`` is the Matrix's (the "status" control)."""
    status = status or {}
    return not status.get("asleep") and not status.get("paused")


def _int(v, low, high) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not low <= v <= high:
        raise ValueError("a number out of range")
    return v


class Task(Background):
    every = TICK

    def start(self):
        shared.STATE["wall"] = walls.load()
        shared.PENS.clear()
        shared.LIVE.update(asked=None, shown=None, ended=None, sent=0.0)
        self.out = Outbox()
        self.pending: dict[tuple, dict] = {}     # dots not yet told to the pages, by (device, line)
        self.flushed = 0.0
        self.here: dict[str, list] = {}          # device -> [its name, how many pages it has open]
        self.now = dt.datetime.now().astimezone()
        self.day = self.now.date()
        self.saved, self.saved_at = self.wall.changed, time.monotonic()
        self.rest_until = 0.0
        self.sent_last: dict | None = None       # the last drawing sent: who and when, for the status line

    @property
    def wall(self) -> walls.Wall:
        return shared.wall()

    # -- the pages ----------------------------------------------------------------------------------------------
    def page_opened(self, sender):
        device = sender["device"]
        self.here.setdefault(device, [sender["name"], 0])[1] += 1
        self.whole(to=device)
        self.history(to=device)
        self.out.add({"t": "here", "names": self.names()}, key="here")
        self.out.flush(self.page)

    def page_closed(self, sender):
        seen = self.here.get(sender["device"])
        if seen:
            seen[1] -= 1
            if seen[1] <= 0:
                del self.here[sender["device"]]
        self.out.add({"t": "here", "names": self.names()}, key="here")
        self.out.flush(self.page)

    def names(self) -> list[str]:
        return sorted(name for name, _ in self.here.values())

    def page_message(self, sender, data):
        try:
            self.hear(sender, data)
        except (ValueError, TypeError, KeyError):
            pass                                  # not something this page sends: dropped, as the Matrix drops the too-big
        self.tell()

    def hear(self, sender, data) -> None:
        if not isinstance(data, dict) or not isinstance(data.get("t"), str):
            raise ValueError("not a message")
        device, who, kind, at = sender["device"], walls.short_name(sender["name"]), data["t"], time.time()
        wall = self.wall
        if kind == "d":
            line, c, width = _int(data["id"], -10 ** 9, 10 ** 9), _int(data["c"], 0, 9), _int(data["w"], 1, 2)
            points = data["p"]
            if not isinstance(points, list) or len(points) % 2 or len(points) > 1000:
                raise ValueError("not dots")
            kept = wall.dots(device, who, line, c, width, [_int(v, -10 ** 6, 10 ** 6) for v in points], at)
            if kept:
                self.drew(device, who, line, c, width, kept, at)
            if data.get("e"):
                self.flushed = 0.0                # a line's end: the other phones hear its last dots at once
        elif kind == "text":
            c = _int(data.get("c", 1), 1, 9)
            text = data["s"]
            if not isinstance(text, str):
                raise ValueError("not words")
            words = letters.clear_of(letters.dots(text[:letters.MOST], wall.w, wall.h), wall.grid, wall.w, wall.h)
            kept = wall.stamp(device, who, c, words, at)
            if kept:
                self.drew(device, who, None, c, 1, kept, at)
                self.flushed = 0.0
        elif kind == "undo":
            if wall.undo(device):
                self.whole()
            else:
                self.said(device, "Nothing of yours to undo.")
        elif kind == "clear":
            if wall.clear(device):
                self.whole()
                self.said(device, "Cleared for everyone.")
        elif kind == "back":
            if wall.put_back(device, _int(data["id"], 0, 10 ** 9)):
                self.whole()
                self.said(device, "Put back on the wall. Undo takes it down again.")
        elif kind == "send":
            self.send(device, who, at)
        else:
            raise ValueError("not a message")

    def drew(self, device, who, line, c, width, kept, at) -> None:
        """Dots kept on the wall: the pen moves on the panel, the other phones will hear, and the wall may cut in."""
        pen = shared.PENS.get(device)
        since = pen["since"] if pen and at - pen["at"] < shared.QUIET else at
        shared.PENS[device] = {"who": who, "c": c, "x": kept[-2], "y": kept[-1], "at": at, "since": since,
                               "colour": self.wall.colour_of(device)}
        key = (device, line if line is not None else f"words {at}", c, width)
        part = self.pending.setdefault(key, {"by": device, "who": who, "pc": self.wall.colour_of(device), "c": c, "w": width, "p": []})
        part["p"].extend(kept)
        self.cut_in(at)

    def send(self, device, who, at) -> None:
        wall = self.wall
        item = wall.send(device, who, at, int(shared.setting(self.settings, "keep")))
        if item is None:
            return self.said(device, "The wall is empty: draw something first.")
        self.sent_last = {"who": self.here.get(device, [who])[0], "at": at}
        shared.LIVE["sent"] = at                  # a cut-in showing gives way to the pop-up
        self.history()
        popup = shared.popup_seconds(self.settings)
        if popup and quiet_panel(self.panel.status):
            show_who = bool(shared.setting(self.settings, "show_who"))
            self.panel.message(f"{who.title()} sent a drawing" if show_who else "A drawing was sent", title="Drawing wall",
                               seconds=popup, look="sent",
                               data={"id": item["id"], "who": who, "pc": wall.colour_of(device)})
            self.said(device, "Sent. It's popping up on the panel, and kept in the history.")
        else:
            self.said(device, "Sent. Kept in the history." + ("" if popup else " (The pop-up is off in its settings.)"))

    def said(self, device, text) -> None:
        self.out.add({"t": "said", "s": text}, to=device)

    # -- what goes to the pages ---------------------------------------------------------------------------------
    def whole(self, to: str | None = None) -> None:
        """The whole wall, in as many messages as it takes (y 0 tells the page to start afresh)."""
        wall = self.wall
        self.dots_out()                           # (dots already heard go first, so nothing newer is painted over)
        rows = max(1, CHUNK // wall.w)
        pop = bool(shared.popup_seconds(self.settings))
        for y in range(0, wall.h, rows):
            n = min(rows, wall.h - y)
            msg = {"t": "all", "w": wall.w, "h": wall.h, "y": y, "n": n, "g": walls.encode(wall.grid[y * wall.w:(y + n) * wall.w]),
                   "pop": pop}
            if to is not None:
                msg["me"] = {"pc": wall.colour_of(to)}
            self.out.add(msg, to=to, key=("all", to, y) if to is None else None)

    def history(self, to: str | None = None) -> None:
        wall, items, size = self.wall, [], 0
        told = [{"id": i["id"], "who": i["who"], "when": shared.when(i["at"], self.now), "w": i["w"], "h": i["h"],
                 "g": walls.encode(i["g"])} for i in wall.history]
        start = 0
        for k, item in enumerate(told):
            n = len(json.dumps(item))
            if items and size + n > CHUNK:
                self.out.add({"t": "hist", "from": start, "of": len(told), "items": items}, to=to,
                             key=("hist", start) if to is None else None)
                items, size, start = [], 0, k
            items.append(item)
            size += n
        self.out.add({"t": "hist", "from": start, "of": len(told), "items": items}, to=to,
                     key=("hist", start) if to is None else None)

    def dots_out(self) -> None:
        """The dots heard since last time, to every page, in messages under 8 KB."""
        parts, numbers = [], 0
        for part in self.pending.values():
            p = part["p"]
            for k in range(0, len(p), MOST_NUMBERS):
                piece = {**part, "p": p[k:k + MOST_NUMBERS]}
                if numbers + len(piece["p"]) > MOST_NUMBERS and parts:
                    self.out.add({"t": "d", "l": parts})
                    parts, numbers = [], 0
                parts.append(piece)
                numbers += len(piece["p"])
        if parts:
            self.out.add({"t": "d", "l": parts})
        self.pending.clear()
        self.flushed = time.monotonic()

    def tell(self) -> None:
        if self.pending and time.monotonic() - self.flushed >= FLUSH:
            self.dots_out()
        self.out.flush(self.page)

    # -- the panel ----------------------------------------------------------------------------------------------
    def cut_in(self, at: float) -> None:
        """Someone is drawing: the wall cuts in on the panel at once (in its look "live", as a pop-up of 30 s that
        ends itself after a quiet spell), and another follows on if they're still drawing when it's nearly over.
        Not when the owner chose to wait for its turn, never in the sleep hours or while the panel is paused, and not
        when the wall is on."""
        if shared.setting(self.settings, "start") != shared.STRAIGHT_AWAY or at < self.rest_until:
            return
        status = self.panel.status or {}
        if not quiet_panel(status) or (status.get("module") == "drawing_wall" and status.get("style") == "wall"):
            return
        if not shared.drawing_now(at):
            return
        live = shared.LIVE
        if live["asked"] is not None and not (live["ended"] and live["ended"] >= live["asked"]):
            started = live["shown"] if live["shown"] and live["shown"] >= live["asked"] else None
            if started is None and at - live["asked"] < 15:
                return                            # asked for, not on yet (something else may be showing first)
            if started is not None and at - started < FOLLOW_ON:
                return                            # on, and not nearly over
        names = [p["who"].title() for _, p in shared.drawing_now(at)]
        self.panel.message(f"{' and '.join(names[:2])} {'is' if len(names) == 1 else 'are'} drawing on the wall",
                           title="Drawing wall", seconds=CUT_IN, look="live", data={"who": names[:2]})
        live["asked"] = at

    def tick(self, now):
        self.now = now
        at = time.time()
        for refused in self.panel.refused or []:
            if refused.get("do") == "message":   # (10 pop-ups in ten minutes, say): it shows on its turn instead
                shared.LIVE["asked"] = None
                self.rest_until = at + REST
        # The module area's size, as the Matrix says (module API 3 with K4); on a Matrix before that, as the
        # wall's own screens found it. And the name the Matrix is reached by, for an empty wall to show (K5).
        told = getattr(self.panel, "size", None)
        size = tuple(told) if isinstance(told, (tuple, list)) and len(told) == 2 else shared.SEEN["size"]
        shared.SEEN["address"] = str(getattr(self.panel, "address", "") or "")
        if size and size != (self.wall.w, self.wall.h) and self.wall.resize(*size):
            self.whole()
        self.clear_by_itself(now, at)
        if self.wall.trim(int(shared.setting(self.settings, "keep"))):
            self.history()
        self.cut_in(at)
        for device in [d for d, p in shared.PENS.items() if at - p["at"] > 60]:
            del shared.PENS[device]
        self.keep()
        self.report(self.status_line(at))
        if self.pending:
            self.dots_out()
        self.out.flush(self.page)

    def settings_changed(self):
        self.whole()                              # (the pages' Send button says whether it pops up)
        if self.wall.trim(int(shared.setting(self.settings, "keep"))):
            self.history()

    def clear_by_itself(self, now, at) -> None:
        how, wall = shared.setting(self.settings, "clear_by_itself"), self.wall
        day, self.day = self.day, now.date()
        due = (how == shared.MIDNIGHT and now.date() != day) or \
              (how == shared.A_DAY and wall.last is not None and at - wall.last["at"] >= 86400)
        if due and not wall.empty() and not shared.drawing_now(at):
            wall.keep_unsent(at, int(shared.setting(self.settings, "keep")))
            wall.clear("")
            self.whole()
            self.history()

    def keep(self) -> None:
        wall = self.wall
        if wall.changed != self.saved and (time.monotonic() - self.saved_at >= SAVE_EVERY or not shared.drawing_now(time.time())):
            try:
                walls.save(wall)
            except OSError as error:
                print(f"couldn't keep the wall: {error}")
            self.saved, self.saved_at = wall.changed, time.monotonic()

    def stop(self):
        self.keep_now()

    def keep_now(self) -> None:
        try:
            walls.save(self.wall)
        except OSError:
            pass

    def status_line(self, at: float) -> str:
        bits = []
        drawing = len(shared.drawing_now(at))
        if drawing:
            bits.append(f"{drawing} {'person' if drawing == 1 else 'people'} drawing now")
        elif self.here:
            n = len(self.here)
            bits.append(f"Open on {n} {'phone or computer' if n == 1 else 'phones or computers'}")
        if self.sent_last:
            bits.append(f"last sent {shared.when(self.sent_last['at'], self.now).title()} from {self.sent_last['who']}")
        n = len(self.wall.history)
        bits.append(f"{n} in the history" if n else "Nothing sent yet")
        line = " · ".join(bits)
        return line if len(line) <= 80 else line[:79] + "…"
