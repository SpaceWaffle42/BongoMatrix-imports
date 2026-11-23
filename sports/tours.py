"""Tennis and golf: a tour's current or next tournament, then its winner, from TheSportsDB Premium (API v2).

What was read, and where (23 Nov 2026):
- ``/schedule/next/league/{id}`` and ``/schedule/previous/league/{id}``: a league's next and last events (10 an
  answer), and ``/lookup/event_results/{id}``: an event's results, a row a player with ``intPosition`` and
  ``strPlayer``. https://www.thesportsdb.com/documentation
- What a tour's events look like there (its free v1 answers, which have the same fields): a tennis event is one
  match, usually a final, named "Nordic Open Fritz vs Tirante", with the tournament and round in its description
  ("Nordic Open - Stockholm - The Final") and the result in words ("Fritz beat Tirante 2-1"). A golf event is a
  tournament ("The RSM Classic"), now and then one event a round ("The Open Championship Round 3"), with the
  places in its results once someone has filled them in.

So this is honest about what it has: tournaments and winners, as TheSportsDB records them, when it records them.
No live scores (none for tennis or golf on any plan) and no world rankings (no documented source for them).
"""
import datetime as dt
import re

from .sources import TheSportsDB, Trouble, epoch, plain, text, whole
from .sports import TOURS

GOLF_DAYS = 4                  # a golf tournament's four rounds, Thursday to Sunday, when only its start is known


def winner_of(line):
    """FRITZ from "Fritz beat Tirante 2-1" (also "beats", "def.", "defeated"), or ""."""
    found = re.match(r"\s*(.+?)\s+(?:beat|beats|def\.?|defeated|defeats)\s+(.+?)(?:\s+\d.*)?$", line or "", re.I)
    return text(found[1]).upper() if found else ""


class TsdbTour(TheSportsDB):
    """One tour on TheSportsDB (``tour``, a key of sports.TOURS). The same key, address and limit as the team
    sports; its own feed."""

    def __init__(self, tour):
        super().__init__("football")
        self.tour = tour
        self.info = TOURS[tour]
        self.sport = self.info["sport"]
        self.strsport = "tennis" if self.sport == "tennis" else "golf"
        self.feed_id = f"{self.id}:{tour}"
        self.live_every = None

    def find_team(self, get, query):
        return {"id": self.info["league"], "name": self.info["name"], "code": self.info["words"][-1], "colours": ["#787E86", "#787E86"],
                "league": {"id": self.info["league"], "name": self.info["name"]}, "country": ""}

    # -- one event ------------------------------------------------------------------------------------------------
    def event(self, raw, now):
        start = epoch(raw.get("strTimestamp")) or epoch(f"{text(raw.get('dateEvent'))}T{text(raw.get('strTime')) or '00:00:00'}")
        if whole(raw.get("idEvent")) is None or start is None or not text(raw.get("strEvent")):
            return None
        title = text(raw.get("strEvent"), 120)
        about = [p.strip() for p in text(raw.get("strDescriptionEN"), 400).split("\n")[0].split(" - ") if p.strip()]
        players = []
        found = re.match(r"(.*?)\s*\b([\w'.-]+)\s+vs\.?\s+(.+)$", title)
        lines = text(raw.get("strDescriptionEN"), 400).split("\n")
        pair = re.match(r"\s*(.+?)\s*(?:\(\d+\))?\s+vs\.?\s+(.+?)\s*(?:\(\d+\))?\s*$", lines[1]) if len(lines) > 1 else None
        if self.sport == "tennis" and pair:                     # "Draper (8) vs Fritz (6)": the players as the description has them
            players = [text(pair[1]).upper(), text(pair[2]).upper()]
        elif self.sport == "tennis" and found:                  # (else the word either side of "vs" in the event's name)
            players = [text(found[2]).upper(), text(found[3]).upper()]
        if self.sport == "tennis" and len(about) >= 2:
            name, stage = about[0], about[-1]
        elif self.sport == "tennis" and found and found[1]:
            name, stage = found[1], ""
        else:
            name, stage = re.sub(r"\s+Round\s+\d+$", "", title, flags=re.I), ""
        stage = re.sub(r"^THE\s+", "", stage.upper())
        line = text(text(raw.get("strResult"), 400).split("\n")[0], 120)
        status = text(raw.get("strStatus")).upper()
        postponed = text(raw.get("strPostponed")).lower() == "yes" or status in ("PST", "POSTPONED", "CANC", "CANCELLED")
        end = start + (GOLF_DAYS * 86400 - 3600 if self.sport == "golf" else 6 * 3600)
        done = bool(line) or status in ("FT", "MATCH FINISHED", "FINISHED", "AET") or (self.sport == "golf" and now >= end)
        return {"id": str(whole(raw["idEvent"])), "kickoff": start, "end": end, "timed": text(raw.get("strTime")) not in ("", "00:00:00"),
                "state": "postponed" if postponed else "finished" if done else "scheduled", "name": text(name, 60), "stage": text(stage, 24),
                "players": players, "line": line.upper(), "winner": winner_of(line) if self.sport == "tennis" else ""}

    def fixtures(self, get, team, today):
        """The tour's tournaments around now, soonest first. A golf tournament filed as one event a round is put
        back together; its winner is looked up in its results."""
        now = dt.datetime.combine(today, dt.time(12), dt.timezone.utc).timestamp()
        league = self.info["league"]
        events = {}
        for path in (f"/schedule/previous/league/{league}", f"/schedule/next/league/{league}"):
            for raw in self.rows(get(path)):
                if self.ours(raw):
                    ev = self.event(raw, now)
                    if ev:
                        events[ev["id"]] = ev
        found = sorted(events.values(), key=lambda e: e["kickoff"])
        if self.sport == "golf":
            found = self.together(found)
            last = next((e for e in reversed(found) if e["state"] == "finished"), None)
            if last and not last["winner"]:
                try:
                    last["winner"] = self.golf_winner(get, last)
                except Trouble:
                    pass
        return found

    @staticmethod
    def together(events):
        """Golf: the rounds of one tournament (the same name within a week) as one event, from the first round's
        start to the last round's end, with the last round's id (its results are the final ones)."""
        out = []
        for ev in events:
            same = next((o for o in out if plain(o["name"]) == plain(ev["name"]) and 0 <= ev["kickoff"] - o["kickoff"] < 7 * 86400), None)
            if same is None:
                out.append(dict(ev))
                continue
            same.update(id=ev["id"], end=ev["kickoff"] + 86400 - 3600, line=ev["line"] or same["line"],
                        state=ev["state"] if ev["kickoff"] >= same["kickoff"] else same["state"])
        return out

    def golf_winner(self, get, event):
        rows = self.rows(get(f"/lookup/event_results/{event['id']}", keep=6 * 3600))
        first = [r for r in rows if whole(r.get("intPosition")) == 1 and text(r.get("strPlayer"))]
        return text(first[0]["strPlayer"]).upper() if len(first) == 1 else ""     # (a tie for first: no winner said yet)

    def live(self, get, team, match):
        return None

    def table(self, get, team):
        return []


_TOURS = {}


def tour_source(tour):
    return _TOURS.setdefault(tour, TsdbTour(tour))
