"""The background task: keeps the one connection to ntfy, files what comes in, and asks for a pop-up when one
is allowed. Every tick only looks at what the connection's own thread has heard, so it is over in a moment."""
from __future__ import annotations

from bongo.module import Background

from . import desk, kinds, ntfy

STATE: dict = {"ready": False}   # what the screens draw (they run in this same process): filled at every tick


class Listen(Background):
    every = 1

    def start(self):
        self.book = desk.Book()
        self.desk = desk.Desk(self.book.data["last_pop"])
        self.listener, self.link, self.trouble, self.asked = None, "connecting", "", None
        self.topic, self.made, self.joined = "", False, None
        self._connect()

    def settings_changed(self):
        if (self._topic()[0], self.settings.get("token") or "") != self.joined:
            self._connect()                       # another topic or token: listen there instead

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
        self.book.save()

    # -- the connection -----------------------------------------------------------------------------------
    def _topic(self) -> tuple[str, bool]:
        """The topic listened to, and whether the module made it (the owner hasn't typed one)."""
        typed = (self.settings.get("topic") or "").strip()
        return (typed, False) if typed else (self.book.made_topic(), True)

    def _connect(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        self.topic, self.made = self._topic()
        token = (self.settings.get("token") or "").strip()
        self.joined = (self.topic, self.settings.get("token") or "")
        if not ntfy.TOPIC.match(self.topic):
            self.link = "bad topic"
            return
        self.link, self.trouble = "connecting", ""
        self.listener = ntfy.Listener(self.topic, token, since=self.book.since(self.topic))
        self.listener.start()

    # -- every second -------------------------------------------------------------------------------------
    def tick(self, now):
        at = now.timestamp()
        if self.asked is not None and any(r.get("do") == "message" for r in self.panel.refused or []):
            self.desk.refused(self.asked, at)     # not shown (the Matrix's own limit): they wait for the next gap
        self.asked = None
        for item in ntfy.drain(self.listener.inbox) if self.listener is not None else []:
            if item[0] == "up":
                self.link, self.trouble = "up", ""
            elif item[0] == "down":
                self.link, self.trouble = "down", item[1]
            elif item[0] == "message":
                self._heard(item[1], now)
        if STATE.pop("clear", False):             # (the screens' Clear the list button)
            self.book.clear()
        keep = int(self.settings.get("keep") or 8)
        self.book.forget(at, keep)
        due = self.desk.due(at, self._hushed(now), desk.GAPS.get(self.settings.get("gap"), 120),
                            bool(self.settings.get("summary", True)))
        if due:
            self._pop_up(*due)
        if self.book.data["last_pop"] != self.desk.last_pop:
            self.book.data["last_pop"] = self.desk.last_pop
            self.book.dirty = True
        self.book.save()
        STATE.update(ready=True, notes=self.book.notes, link=self.link, trouble=self.trouble, topic=self.topic)
        self.report(*self.status_line(now))

    def _heard(self, event: dict, now):
        self.book.heard(self.topic, event["id"], self.made)
        if self.book.seen(event["id"]):
            return                                # (heard again on catching up)
        note = desk.note_from(event)
        handling = kinds.handling(note["kind"], self.settings)
        if handling == kinds.IGNORE:
            self.book.remember(note["id"])
            return
        self.book.count(now.date().isoformat())
        self.book.add(note, int(self.settings.get("keep") or 8))
        if handling == kinds.POP and now.timestamp() - note["at"] < desk.STALE:
            self.desk.add(note)

    def _hushed(self, now) -> bool:
        """No pop-ups now: the panel is asleep (its sleep hours, or put to sleep) or it's the owner's quiet hours."""
        if (self.panel.status or {}).get("asleep"):
            return True
        try:
            span = desk.quiet_hours(self.settings.get("quiet_hours"))
        except ValueError:
            return False
        return desk.in_quiet(now.hour * 60 + now.minute, span)

    def _pop_up(self, notes, quiet):
        show = self.settings.get("show") or desk.WHO
        title, text, seconds = desk.compose(notes, show, quiet, tuple(getattr(self.panel, "size", None) or (64, 32)))
        self.say(title, text, seconds, desk.popup_data(notes, show, quiet))
        self.asked = notes

    def say(self, title: str, text: str, seconds: float, data: dict) -> None:
        """The one place a pop-up is asked for: in the module's own look (popups.Note: the kind's icon, who, and
        the time left), given ``data`` (desk.popup_data). The words say the same on their own: they are what the
        panel shows if the look ever fails."""
        self.panel.message(text, title=title, seconds=seconds, look="note", data=data)

    # -- the line in the module's card ---------------------------------------------------------------------
    def status_line(self, now) -> tuple[str, bool]:
        if self.link == "bad topic":
            return "Topic name: only letters, numbers, - and _ (up to 64)", False
        # (the topic itself is never said here, nor anywhere else on the dashboard: only on the panel, as the Setup
        # code screen's QR code, when the owner adds that screen)
        waiting = self.made and not self.book.data["heard_made"]  # a topic made for the owner, not used by a phone yet
        if self.link == "down":
            return (f"Can't reach {ntfy.NAME} yet · your topic is on the Setup code screen" if waiting
                    else f"Can't reach {ntfy.NAME}: {self.trouble}"), False
        if waiting:
            return "Topic made: add the Setup code screen and scan it with your phone", True
        try:
            desk.quiet_hours(self.settings.get("quiet_hours"))
        except ValueError:
            return "Quiet hours: write them like 21:30-07:00", False
        if self.link == "connecting":
            return f"Connecting to {ntfy.NAME}...", True
        today = self.book.today(now.date().isoformat())
        notes = self.book.notes
        said = f"Listening on {ntfy.NAME} · {today} today" if today else f"Listening on {ntfy.NAME} · none yet today"
        if notes:
            said += f" · the last one {ago(now.timestamp() - notes[0]['at'], long=True)}"
        return said, True


def ago(seconds: float, long: bool = False) -> str:
    """How long ago, the panel's way ("NOW", "4M", "2H", "1D") or the card's ("4 min ago")."""
    minutes = max(0, int(seconds // 60))
    if long:
        return ("just now" if minutes < 1 else f"{minutes} min ago" if minutes < 60
                else f"{minutes // 60} h ago" if minutes < 1440 else f"{minutes // 1440} days ago")
    return "NOW" if minutes < 1 else f"{minutes}M" if minutes < 60 else f"{minutes // 60}H" if minutes < 1440 else f"{minutes // 1440}D"
