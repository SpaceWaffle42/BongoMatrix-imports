"""The background task: follows each parcel politely (one question a tick, each parcel every "Check every"
minutes, DHL's within its 250 a day), keeps count of Ship24's free parcels this month, says how things stand on
the card's status line, and puts up a pop-up when a parcel is out for delivery or delivered."""
from __future__ import annotations

import datetime as dt
import time

from bongo.module import Background

from . import couriers, parse, popups, store, view

TICK = 10                  # s between ticks: never more than one question to anyone in a tick
DHL_A_DAY = 200            # of DHL's 250 calls a day on a free key: room to spare
KEEP_GONE = 60 * 86400     # s a parcel taken off the card is remembered (put back, it doesn't cost a new one)
NEWS = 12 * 3600           # s a delivered pop-up held through the sleep hours is still news
GAP = 8                    # s between two pop-ups (the Matrix allows one every 5)
NEVER = 1e15               # "next": a delivered parcel isn't asked about again
RETRY_REFUSED = 86400      # s: Ship24 said this month's are used before our own count did (its month may start on
#                            another day than the 1st): ask again once a day, which costs nothing when refused


WORDS_MOST = 32            # letters of a pop-up's words, so the Matrix's banner (shown if the look fails) reads them
#                            through well inside the 20 s it gives them


def pop_up(panel, kind: str, shown: view.Shown) -> None:
    """The one place a pop-up is put up, in the module's own look (popups.Parcel). ``kind``: "out" or "delivered".
    Its words say it all on their own, shortly: they are what the panel shows if the look ever fails."""
    title, text = pop_up_words(kind, shown)
    data = pop_up_data(kind, shown)
    panel.message(text, title=title, seconds=popups.seconds_for(data), look="parcel", data=data)


def pop_up_words(kind: str, shown: view.Shown) -> tuple[str, str]:
    """(title, words): "Out today", "New Boots (DPD), 12:15–13:15"; "Delivered", "Birthday Gift: porch 11:42, UPS".
    The nickname is cut short with "…" so the whole is at most WORDS_MOST letters."""
    courier = (shown.courier.title() if len(shown.courier) > 3 else shown.courier) if shown.courier else ""
    if kind == "out":
        title = "Out today"                       # (fits the banner's title without scrolling, as "Delivered" does)
        rest = f" ({courier})" if courier else ""
        slot = shown.when
        if slot[:1].isdigit():
            rest += f", {slot.replace('-', '–')}"
        elif slot.startswith("BY "):
            rest += f", by {slot[3:]}"
    else:
        title = "Delivered"
        where = shown.where.lower() if shown.where else ""
        at = shown.delivered_at.strftime("%H:%M") if shown.delivered_at is not None and \
            (shown.delivered_at.hour, shown.delivered_at.minute) != (0, 0) else ""
        for said in ((where, at), (where,), (where.split(" ")[-1],)):      # too long: the time goes, then where shortens
            rest = (": " + " ".join(w for w in said if w) if any(said) else "") + (f", {courier}" if courier else "")
            if len(rest) <= WORDS_MOST - 6:                                  # (room for some of the nickname)
                break
        rest = rest[:WORDS_MOST - 6]
    return title, _cut(shown.nickname.title(), WORDS_MOST - len(rest)) + rest


def _cut(text: str, most: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= most else text[:max(1, most - 1)].rstrip() + "…"


def pop_up_data(kind: str, shown: view.Shown) -> dict:
    """What the pop-up's look draws: the news, the nickname, and the line under it. Out for delivery: the time slot
    and the courier (12:15-13:15 DPD); delivered: when, where and who (11:42 PORCH UPS), short enough to fit a
    64-dot line whole when it can. Well inside the 2 KB a pop-up may be given."""
    if kind == "out":
        under = shown.line
    else:
        when = shown.when or (shown.delivered_at.strftime("%H:%M") if shown.delivered_at is not None else "")
        under = " ".join(w for w in (when, shown.where, shown.courier) if w)
    return {"kind": kind, "name": shown.nickname[:60], "under": under[:80]}


class Tracker(Background):
    every = TICK

    def start(self):
        self.state = store.load()
        self.token, self.token_until = None, 0.0
        self.next_pop = 0.0
        self.dirty = False
        self.asking = None

    def settings_changed(self):
        self.state["keys"] = {}                        # a key may have been put right: try them all again
        for p in self.state["parcels"].values():
            if p.get("error") in ("needs_key", "key"):
                p["error"], p["next"] = None, 0
        self.token, self.token_until = None, 0.0
        self.dirty = True

    # -- every tick -------------------------------------------------------------------------------------------
    def tick(self, now):
        clock = now.timestamp()
        listed = self.listed(now, clock)
        self.new_month(now)
        due = sorted((p for n, p in self.state["parcels"].items() if n in listed and p.get("next", 0) <= clock),
                     key=lambda p: p.get("next", 0))
        if due:
            self.check(due[0], listed[due[0]["number"]], now, clock)
        self.pop(now, clock)                            # (after the check: a pop-up says what's true now)
        self.report(*self.line(listed, now))
        if self.dirty:
            store.save(self.state)
            self.dirty = False

    def listed(self, now, clock) -> dict:
        """The parcels on the card now ({number: (slot, typed)}), each with an entry in the state."""
        out = {}
        for slot, t in view.typed(self.settings):
            if not t.number or t.number in out:
                continue
            out[t.number] = (slot, t)
            p = self.state["parcels"].get(t.number)
            if p is None:
                p = self.state["parcels"][t.number] = {"number": t.number, "provider": None, "tracker": None, "result": None,
                                                       "next": 0, "error": None, "told": [], "tried": [], "waiting": False}
                self.dirty = True
            p["hint"], p["seen"] = t.hint, clock
        for number, p in list(self.state["parcels"].items()):   # gone from the card a long while: forgotten
            if number not in out and clock - p.get("seen", clock) > KEEP_GONE:
                del self.state["parcels"][number]
                self.dirty = True
        return out

    def new_month(self, now):
        month = now.strftime("%Y-%m")
        if self.state.get("month") != month:
            self.state.update(month=month, used=0, refused_until=None)
            for p in self.state["parcels"].values():
                if p.get("waiting"):
                    p["waiting"], p["next"] = False, 0
            self.dirty = True

    # -- asking about one parcel ----------------------------------------------------------------------------------
    def check(self, p, slot_typed, now, clock):
        slot, t = slot_typed
        self.dirty = True
        before = (p.get("result") or {}).get("state")
        try:
            found = self.ask(p, t, now, clock)
        except couriers.Refused as no:
            self.refused(p, no, clock, now)
            return
        if found is None:                              # nothing asked this time (waiting, a key missing, a token got)
            return
        p["result"], p["error"], p["checked"] = found, None, clock
        p["next"] = NEVER if found["state"] == "delivered" else clock + self.interval(p)
        self.news(p, slot, t, before, now, clock)

    def ask(self, p, t, now, clock):
        """Asks whoever follows this parcel (one question), or starts following it. None: nothing was asked of
        anyone about it this time (it waits, a key is missing, or the tick went on a UPS token)."""
        tz = now.tzinfo
        settings = self.settings
        provider = p.get("provider")
        self.asking = provider
        if provider is None:                           # first: the courier's own free key, if it's theirs and there is one
            guess = parse.looks_like(t.number, t.hint)
            if guess == "dhl" and settings.get("dhl_key") and "dhl" not in p["tried"] and not self.state["keys"].get("dhl"):
                self.asking = "dhl"
                found = couriers.dhl(settings["dhl_key"], t.number, tz)
                p["provider"] = "dhl"
                return found
            if guess == "ups" and self.ups_ready() and "ups" not in p["tried"] and not self.state["keys"].get("ups"):
                if self.token is None or time.time() >= self.token_until:
                    return self.new_token()
                self.asking = "ups"
                found = couriers.ups(self.token, t.number, tz)
                p["provider"] = "ups"
                return found
            self.asking = "ship24"
            return self.ship24_start(p, t, now, clock)
        if provider == "dhl":
            return couriers.dhl(settings["dhl_key"], t.number, tz) if settings.get("dhl_key") else self.lost_key(p, clock)
        if provider == "ups":
            if not self.ups_ready():
                return self.lost_key(p, clock)
            if self.token is None or time.time() >= self.token_until:
                return self.new_token()
            return couriers.ups(self.token, t.number, tz)
        if not settings.get("ship24_key"):
            p["error"], p["next"] = "needs_key", clock + 3600
            return None
        return couriers.ship24_check(settings["ship24_key"], p["tracker"], tz)

    def ship24_start(self, p, t, now, clock):
        key = self.settings.get("ship24_key")
        if not key:
            p["error"], p["next"] = "needs_key", clock + 3600   # (checked again at once when the card is saved)
            return None
        refused = self.state.get("refused_until")
        if refused and clock < refused:                # Ship24 said this month's are used: asked again at most daily
            p["waiting"], p["next"] = True, refused
            return None
        if not refused and self.state["used"] >= view.ALLOWANCE:
            p["waiting"], p["next"] = True, self.first_of_next_month(now)   # past this month's 10: waits for the 1st
            return None
        tracker, found = couriers.ship24_start(key, t.number, now.tzinfo)
        if refused:                                    # its month started again on a day of its own: count afresh
            self.state.update(used=0, refused_until=None)
            for q in self.state["parcels"].values():
                if q.get("waiting"):
                    q["waiting"], q["next"] = False, 0
        self.state["used"] += 1
        p.update(provider="ship24", tracker=tracker, waiting=False)
        return found

    def refused(self, p, no, clock, now):
        who = self.asking or "ship24"
        if no.why == "not_found" and who in ("dhl", "ups") and p.get("result") is None:
            p["tried"].append(who)                     # not theirs after all: Ship24 next
            p["provider"], p["next"] = None, 0
            return
        if no.why == "token":
            self.token, p["next"] = None, 0
            return
        if no.why in ("key", "plan"):
            self.state["keys"][who] = no.why
            if who in ("dhl", "ups") and p.get("result") is None:
                p["provider"], p["next"] = None, 0     # a courier's key that doesn't work: Ship24 instead
            else:
                p["error"], p["next"] = "key", clock + 6 * 3600   # (tried again at once when the card is saved)
            return
        if no.why == "quota":
            self.state["used"] = max(self.state["used"], view.ALLOWANCE)
            self.state["refused_until"] = min(clock + RETRY_REFUSED, self.first_of_next_month(now))
            p["waiting"], p["next"] = True, self.state["refused_until"]
            return
        if no.why == "busy":
            p["next"] = clock + (no.wait or 900)
            return
        p["error"], p["next"] = str(no)[:60], clock + self.interval(p)   # no answer, or a tracker Ship24 has lost

    def lost_key(self, p, clock):
        """Followed with a courier's key that has since been cleared: on to Ship24."""
        p["provider"], p["next"] = None, clock
        return None

    def ups_ready(self) -> bool:
        return bool(self.settings.get("ups_client_id") and self.settings.get("ups_secret"))

    def new_token(self):
        try:
            self.token, lasts = couriers.ups_token(self.settings["ups_client_id"], self.settings["ups_secret"])
        except couriers.Refused as no:
            if no.why == "key":
                self.state["keys"]["ups"] = "key"
                self.dirty = True
            return None
        self.token_until = time.time() + max(60.0, lasts - 120)
        return None

    def interval(self, p) -> float:
        every = 60.0 * max(5, int(self.settings.get("every") or 15))
        if p.get("provider") == "dhl":               # DHL's free 250 a day, shared by every DHL parcel
            on_dhl = sum(1 for q in self.state["parcels"].values()
                         if q.get("provider") == "dhl" and (q.get("result") or {}).get("state") != "delivered")
            every = max(every, 86400.0 * max(1, on_dhl) / DHL_A_DAY)
        return every

    @staticmethod
    def first_of_next_month(now) -> float:
        year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

    # -- pop-ups ---------------------------------------------------------------------------------------------------
    def news(self, p, slot, t, before, now, clock):
        """Out for delivery or delivered, for the first time: a pop-up is due (held through the sleep hours)."""
        state = p["result"]["state"]
        for kind in ("out", "delivered"):
            if state != kind or kind in p["told"]:
                continue
            p["told"].append(kind)
            if kind == "delivered":
                self.state["queue"] = [q for q in self.state["queue"] if q["number"] != p["number"]]
                shown = view.describe(slot, t, p, now)
                if before is None and shown.delivered_at is not None and (now - shown.delivered_at).total_seconds() > NEWS:
                    continue                           # added already delivered, long ago: not news
            self.state["queue"].append({"kind": kind, "number": p["number"], "at": clock})

    def pop(self, now, clock):
        queue = self.state.get("queue") or []
        if not queue or clock < self.next_pop:
            return
        status = self.panel.status or {}
        if status.get("asleep"):
            return                                     # never in the sleep hours: it waits until they end
        typed = {t.number: (slot, t) for slot, t in view.typed(self.settings)}
        while queue:
            q = queue.pop(0)
            self.dirty = True
            p = self.state["parcels"].get(q["number"])
            if p is None or q["number"] not in typed or not self.settings.get(f"popup_{q['kind']}", True):
                continue
            shown = view.describe(*typed[q["number"]], p, now)
            if q["kind"] == "out" and (shown.state != "out" or dt.datetime.fromtimestamp(q["at"], now.tzinfo).date() != now.date()):
                continue                               # no longer news: it came, or it was yesterday
            if q["kind"] == "delivered" and clock - q["at"] > NEWS:
                continue
            pop_up(self.panel, q["kind"], shown)
            self.next_pop = clock + GAP
            return

    # -- the status line -------------------------------------------------------------------------------------------
    def line(self, listed, now) -> tuple[str, bool]:
        problems = [f"Parcel {slot}: {t.problem}" for slot, t in view.typed(self.settings) if t.problem]
        keys = self.state.get("keys") or {}
        parcels = [self.state["parcels"][n] for n in listed]
        if keys.get("ship24") == "key":
            problems.insert(0, "Ship24 didn't accept the key")
        elif keys.get("ship24") == "plan":
            problems.insert(0, "Ship24: choose its free Tracking API plan")
        if any(p.get("error") == "needs_key" for p in parcels):
            problems.insert(0, "Add your free Ship24 key")
        for who, name in (("dhl", "DHL key"), ("ups", "UPS client ID or secret")):
            if keys.get(who) == "key":
                problems.append(f"{name} not accepted: Ship24 used")
        if not listed:
            return (problems[0] if problems else "No parcels yet: add a tracking number above"), not problems
        n = len(listed)
        words = [f"{n} parcel{'s' if n != 1 else ''}", f"{min(self.state['used'], view.ALLOWANCE)} of {view.ALLOWANCE} used this month"]
        waiting = sum(1 for p in parcels if p.get("waiting"))
        if waiting:
            words.append(f"{waiting} wait{'s' if waiting == 1 else ''} until {view.first_of_next_month(now).title()}")
        said = " · ".join(words)
        if problems:
            said = f"{problems[0]} · {said}"
        return said[:80], not problems and not waiting
