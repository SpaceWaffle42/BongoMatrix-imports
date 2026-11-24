"""Formula 1, from Jolpica-F1 (https://api.jolpi.ca/ergast/f1/): free, open source, no key.

What was read, and where (23 Nov 2026):
- The endpoints: https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md ("All endpoints should either end
  with a / or .json"; ``limit`` defaults to 30, at most 100).
- Races, the calendar: ``/{season}/races/``, season a year or ``current``; each race has ``round``, ``raceName``,
  ``date``, ``time`` (UTC, not always there) and a ``Sprint`` when it is a sprint weekend.
  https://github.com/jolpica/jolpica-f1/blob/main/docs/endpoints/races.md
- Results: ``/{season}/last/results/``: ``Results[]`` with ``position``, ``Driver`` (``driverId``, ``code``,
  ``familyName``). https://github.com/jolpica/jolpica-f1/blob/main/docs/endpoints/results.md
- Driver standings: ``/{season}/driverstandings/``: ``StandingsLists[].DriverStandings[]`` with ``position``,
  ``points``, ``Driver``. https://github.com/jolpica/jolpica-f1/blob/main/docs/endpoints/driverStandings.md
- Limits: "4 requests per second" and "500 requests per hour", "subject to change, and will decrease in the
  future"; HTTP 429 when throttled; "Implement a cache". It asks for a User-Agent with the app's name and version.
  https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md

So this asks rarely: the calendar is kept 12 hours, the last result and the standings are asked for every 3 hours
(every 30 minutes in the hours after a race, until its result is in). No live timing: Jolpica has none.
"""
import datetime as dt
import re

from .sources import GREY, Trouble, epoch, header, text, whole

RACE_HOURS = 3 * 3600          # a race is taken as under way for this long after its start


def short_names(race_name):
    """Ways of saying a race's name, longest first: ABU DHABI GRAND PRIX, ABU DHABI GP, ABU DHABI."""
    name = text(race_name).upper()
    place = re.sub(r"\s+GRAND PRIX$", "", name).strip()
    out = [name, f"{place} GP", place] if place != name else [name]
    return tuple(dict.fromkeys(w for w in out if w))


class Jolpica:
    id = feed_id = "jolpica"
    name = "Jolpica-F1"
    short = "JOLPICA-F1"
    host = "api.jolpi.ca"
    base = "https://api.jolpi.ca/ergast/f1"
    gap = 2.0               # seconds between requests: well under 4 a second (and a few an hour in all)
    live_every = None       # no live timing
    has_table = True        # the drivers' standings
    needs_key = False

    def headers(self, key):
        return {}           # no key: none is ever sent here

    def trouble(self, status, body, headers):
        if status == 429:
            return Trouble("limit", whole(header(headers, "Retry-After")) or 60)
        if status == 404:
            return Trouble("missing")
        return Trouble("answer")

    def find_team(self, get, query):
        """What a Formula 1 screen follows: the championship (no request)."""
        return {"id": "f1", "name": "Formula 1", "code": "F1", "colours": [GREY, GREY], "league": {"id": "f1", "name": "Formula 1"}, "country": ""}

    @staticmethod
    def table_of(answer, name):
        data = answer.get("MRData") if isinstance(answer, dict) and isinstance(answer.get("MRData"), dict) else {}
        table = data.get(name) if isinstance(data.get(name), dict) else {}
        return table

    def races(self, answer):
        out = []
        for raw in self.table_of(answer, "RaceTable").get("Races") or []:
            if not isinstance(raw, dict) or whole(raw.get("round")) is None or whole(raw.get("season")) is None:
                continue
            date, time = text(raw.get("date")), text(raw.get("time"))
            start = epoch(f"{date}T{time}") if time else epoch(f"{date}T12:00:00Z")
            if start is None or not text(raw.get("raceName")):
                continue
            season, round_ = whole(raw["season"]), whole(raw["round"])
            out.append({"id": f"{season}-{round_}", "kickoff": start, "timed": bool(time), "state": "scheduled", "season": season,
                        "round": round_, "name": text(raw["raceName"]), "words": short_names(raw["raceName"]),
                        "sprint": isinstance(raw.get("Sprint"), dict)})
        return out

    @staticmethod
    def driver(raw):
        d = raw.get("Driver") if isinstance(raw.get("Driver"), dict) else {}
        family = text(d.get("familyName")).upper()
        code = re.sub(r"[^A-Z]", "", text(d.get("code")).upper())[:3] or re.sub(r"[^A-Z]", "", family)[:3] or "???"
        return {"id": text(d.get("driverId")) or code.lower(), "code": code, "name": family}

    def podium(self, answer):
        """(season, round, the first three) of the last race with results, or None."""
        for raw in self.table_of(answer, "RaceTable").get("Races") or []:
            if not isinstance(raw, dict):
                continue
            rows = []
            for r in raw.get("Results") or []:
                if isinstance(r, dict) and whole(r.get("position")) in (1, 2, 3):
                    rows.append({"pos": whole(r["position"]), **self.driver(r)})
            rows.sort(key=lambda r: r["pos"])
            if rows and whole(raw.get("season")) is not None and whole(raw.get("round")) is not None:
                return whole(raw["season"]), whole(raw["round"]), rows
        return None

    def fixtures(self, get, team, today):
        """The season's races, soonest first, the last one with results carrying its ``podium``. When the season is
        over, next season's calendar as soon as Jolpica has it."""
        races = self.races(get("/current/races/?limit=100", keep=12 * 3600))
        last = self.podium(get("/current/last/results/"))
        if last is None and races:              # a new season with no race run yet: last season's last race
            last = self.podium(get(f"/{races[0]['season'] - 1}/last/results/", keep=12 * 3600))
        now = dt.datetime.combine(today, dt.time(), dt.timezone.utc).timestamp()
        if not any(r["kickoff"] > now - 86400 for r in races):
            season = (races[-1]["season"] if races else today.year) + 1
            try:
                races += self.races(get(f"/{season}/races/?limit=100", keep=12 * 3600))
            except Trouble:
                pass
        if last:
            season, round_, rows = last
            for race in races:
                if (race["season"], race["round"]) <= (season, round_):
                    race["state"] = "finished"
                if (race["season"], race["round"]) == (season, round_):
                    race["podium"] = rows
            if not any((r["season"], r["round"]) == (season, round_) for r in races):
                races.insert(0, {"id": f"{season}-{round_}", "kickoff": 0, "timed": False, "state": "finished", "season": season,
                                 "round": round_, "name": "", "words": ("LAST RACE",), "sprint": False, "podium": rows})
        return sorted(races, key=lambda r: r["kickoff"])

    def live(self, get, team, match):
        return None

    def table(self, get, team):
        """The drivers' standings: [{"pos", "id", "code", "points", "name"}]. Early in a season, before its first
        race, last season's final standings."""
        rows = self.standings(get("/current/driverstandings/"))
        if not rows:
            table = self.table_of(get("/current/races/?limit=100", keep=12 * 3600), "RaceTable")
            season = whole(table.get("season"))
            if season:
                rows = self.standings(get(f"/{season - 1}/driverstandings/", keep=12 * 3600))
        return rows

    def standings(self, answer):
        lists = [s for s in self.table_of(answer, "StandingsTable").get("StandingsLists") or [] if isinstance(s, dict)]
        rows = []
        for raw in (lists[-1].get("DriverStandings") or []) if lists else []:
            if not isinstance(raw, dict) or whole(raw.get("position")) is None:
                continue
            points = raw.get("points")
            try:
                points = float(points)
            except (TypeError, ValueError):
                continue
            rows.append({"pos": whole(raw["position"]), "points": int(points) if points == int(points) else points, **self.driver(raw)})
        return sorted(rows, key=lambda r: r["pos"])


JOLPICA = Jolpica()
