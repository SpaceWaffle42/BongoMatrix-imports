"""The two places the scores can come from, each turned into the same plain shapes the screen draws.

A source only says what to ask for and how to read the answer. It never touches the network itself: it is
handed ``get(path, keep=0)``, which fetches one of its addresses (feed.py does that, politely) and returns the
parsed JSON. Everything read from an answer is checked: a field that is missing or odd is left out, never trusted.

The shapes (all plain JSON, so they can be kept in the cache file):

    team   {"id": "57", "name": "Northtown FC", "code": "NTH", "colours": ["#C81E28", "#FFFFFF"],
            "league": {"id": "EL1", "name": "League One"}, "country": "England"}
    match  {"id": "9001", "kickoff": 1795273200, "timed": True, "state": "scheduled",
            "home": {"id", "name", "code", "colours"}, "away": {...}, "league": {"id", "name"},
            "score": [2, 1] | None, "pens": [4, 3] | None, "after": "extra_time" | "penalties" | None,
            "minute": 67 | None, "added": 3 | None, "goal": {"minute": 64, "name": "SMITH"} | None}
    table  [{"pos": 4, "id": "57", "code": "NTH", "points": 29}, ...]

``state`` is one of STATES. What each service really offers, and on which plan, is in README.md with the
addresses of the pages it was read from.
"""
import datetime as dt
import re
import unicodedata

STATES = ("scheduled", "live", "half_time", "break", "extra_time", "penalties", "finished", "postponed", "suspended", "cancelled")
IN_PLAY = ("live", "half_time", "break", "extra_time", "penalties")
EARLY, LATE = 15 * 60, 8 * 3600       # a match is only believed in play from 15 minutes before its kick-off to 8 hours after


def playing(match, now):
    """Whether ``match`` is in play at ``now`` (seconds since 1970). One the service calls in play with a kick-off
    far off (a mistake there, or the Matrix's clock wrong) is taken as scheduled, so it isn't watched for ever."""
    return match["state"] in IN_PLAY and -EARLY <= now - match["kickoff"] < LATE


def as_known(match, now):
    """``match`` as the screen should take it at ``now``: in play only inside its believable hours (``playing``)."""
    if match["state"] in IN_PLAY and not playing(match, now):
        return {**match, "state": "scheduled", "score": None, "pens": None, "minute": None, "added": None, "goal": None}
    return match
GREY = "#787E86"                      # a kit we don't know the colours of


class Trouble(Exception):
    """Why a request didn't give an answer. ``kind``: "refused" (the key), "plan" (not in the key's plan),
    "missing" (no such thing), "limit" (asked too often; ``wait`` seconds), "offline", "answer" (not what was
    expected). Never carries an address or a key."""

    MOST_WAIT = 3600.0       # a service asking us to wait longer than an hour is asked again in an hour

    def __init__(self, kind, wait=0.0):
        super().__init__(kind)
        try:
            wait = float(wait)
        except (TypeError, ValueError):
            wait = 0.0
        self.kind, self.wait = kind, max(0.0, min(self.MOST_WAIT, wait if wait == wait else 0.0))


def header(headers, name):
    """A response header, whatever case the service wrote its name in."""
    want = name.lower()
    return next((v for k, v in (headers or {}).items() if str(k).lower() == want), None)


# -- small readers --------------------------------------------------------------------------------------------
def text(value, most=60):
    """A string from an answer, at most ``most`` characters, shortened at a space so no word is ever cut."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if len(value) <= most:
        return value
    cut = value[:most + 1].rsplit(" ", 1)[0].rstrip(" ,;:-(")
    return cut if " " in value[:most + 1] else value[:most]


def whole(value):
    """A whole number from an answer (5, "5", 5.0), or None. Never True/False, never negative."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value and abs(value) < 1e12:
        value = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\d{1,12}", value.strip()):
        value = int(value)
    else:
        return None
    return value if value >= 0 else None


def plain(name):
    """A team's name as it is compared: no accents, capitals or punctuation, and without "FC" and the like."""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", name).split() if w not in ("fc", "afc", "cf", "sc", "ac", "the", "club", "ssc", "as", "fk")]
    return " ".join(words)


def code_of(name, short=None):
    """Three letters for a team: the service's own if it has one, else the first three of its name."""
    short = re.sub(r"[^A-Za-z0-9]", "", short or "")
    if 2 <= len(short) <= 4:
        return short.upper()[:3]
    letters = re.sub(r"[^a-z0-9]", "", plain(name)) or "???"
    return letters[:3].upper()


COLOUR_WORDS = {
    "red": "#D21E28", "white": "#FFFFFF", "blue": "#1E5AC8", "black": "#5A5A64", "yellow": "#FAD228", "green": "#1E9646",
    "orange": "#F58220", "purple": "#6E3CB4", "claret": "#7A1F3D", "maroon": "#7A1F3D", "burgundy": "#7A1F3D", "garnet": "#7A1F3D",
    "navy": "#1F2F6E", "sky": "#6CB4EE", "gold": "#D4AF37", "amber": "#FFB547", "pink": "#F06EAA", "grey": "#9AA0A8", "gray": "#9AA0A8",
    "silver": "#C0C4CC", "brown": "#7B4A1E", "violet": "#6E3CB4", "crimson": "#B4142D", "scarlet": "#D21E28", "royal": "#1E5AC8",
    "turquoise": "#28B4AA", "lime": "#96D228", "cyan": "#28B4D2", "cream": "#F0E6C8",
}


def lift(colour):
    """A colour the panel can show: one too dark to see (a black kit) becomes a dark grey."""
    try:
        r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return GREY
    if max(r, g, b) < 70:
        return "#5A5A64"
    light = 0.3 * r + 0.59 * g + 0.11 * b
    if light < DIM:                                     # a very dark colour (navy): brightened, keeping its hue
        k = DIM / max(1.0, light)
        r, g, b = (min(255, round(v * k)) for v in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


DIM = 75                                                # the least brightness a kit colour is shown at


def colours_from_words(words):
    """["#..", "#.."] from "Red / White" (football-data.org's clubColors): the first two colours named."""
    found = []
    for part in re.split(r"[/,&]| and ", str(words or "").lower()):
        tokens = [t for t in re.split(r"[^a-z]+", part) if t]
        named = [COLOUR_WORDS[t] for t in tokens if t in COLOUR_WORDS]
        if "sky" in tokens or "light" in tokens and "blue" in tokens:
            named = [COLOUR_WORDS["sky"]]
        elif ("navy" in tokens or "dark" in tokens) and "blue" in tokens:
            named = [COLOUR_WORDS["navy"]]
        if named:
            found.append(named[0])
    found = [lift(c) for c in found[:2]]
    return [found[0], found[-1]] if found else [GREY, GREY]


def colours_from_hex(*values):
    found = [lift(v.strip()) for v in values if isinstance(v, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", v.strip())][:2]
    return [found[0], found[-1]] if found else [GREY, GREY]


def best(query, teams):
    """The team in ``teams`` ([(names it goes by, team)]) that ``query`` means, or None. An exact name wins,
    then a name that starts with it, then one that contains it."""
    want = plain(query)
    if not want:
        return None
    scored = []
    for order, (names, team) in enumerate(teams):
        known = [plain(n) for n in names if n]
        raw = [str(n).lower() for n in names if n]
        if want in known or query.strip().lower() in raw:
            score = 3
        elif any(k.startswith(want + " ") or want.startswith(k + " ") for k in known if k):
            score = 2
        elif len(want) >= 3 and any(want in k for k in known):
            score = 1
        else:
            continue
        scored.append((-score, order, team))
    return min(scored)[2] if scored else None


def epoch(stamp):
    """Seconds since 1970 from "2026-11-21T15:00:00Z" (a time with no zone is UTC), or None."""
    if not isinstance(stamp, str):
        return None
    try:
        when = dt.datetime.fromisoformat(stamp.strip().replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    try:
        seconds = int(when.timestamp())
    except (OverflowError, ValueError, OSError):
        return None
    return seconds if FIRST <= seconds < LAST else None      # (a date far off is a mistake: never shown, never an overflow)


FIRST, LAST = 631152000, 4102444800                          # 1990 to 2100


def minutes(value):
    """(minute, added time) from 67, "67", "45+2" or "90+4'": (None, None) if it can't be read."""
    if isinstance(value, str):
        found = re.fullmatch(r"\s*(\d{1,3})\s*(?:\+\s*(\d{1,2}))?\s*'?\s*", value)
        return (int(found[1]), int(found[2]) if found[2] else None) if found else (None, None)
    return whole(value), None


def surname(name):
    return text(name, 120).split(" ")[-1].upper() if text(name) else ""


# -- football-data.org ----------------------------------------------------------------------------------------
class FootballData:
    """football-data.org, API v4 (https://docs.football-data.org/general/v4/index.html). The key goes in the X-Auth-Token header. The free plan: 12 competitions,
    10 requests a minute, fixtures and tables, scores "delayed"; live scores are a paid plan."""
    id = feed_id = "football_data"
    name = "football-data.org"
    short = "FOOTBALL-DATA"
    host = "api.football-data.org"
    base = "https://api.football-data.org/v4"
    gap = 7.0               # seconds between requests: under the free plan's 10 a minute
    live_every = 60.0       # seconds between looks at a match in play
    has_table = True
    needs_key = True
    LEAGUES = ("PL", "ELC", "BL1", "SA", "PD", "FL1", "DED", "PPL", "BSA")   # the free plan's leagues (it also has CL, WC, EC)

    def headers(self, key):
        return {"X-Auth-Token": key}

    def trouble(self, status, body, headers):
        said = text(body.get("message") if isinstance(body, dict) else "", 200).lower()
        if status == 429:
            return Trouble("limit", whole(header(headers, "X-RequestCounter-Reset")) or 60)
        if status == 401 or (status in (400, 403) and "token" in said):
            return Trouble("refused")
        if status == 403:
            return Trouble("plan")
        if status == 404:
            return Trouble("missing")
        return Trouble("answer")

    def _team(self, raw, league=None):
        if not isinstance(raw, dict) or whole(raw.get("id")) is None or not text(raw.get("name")):
            return None
        if league is None:
            running = [c for c in raw.get("runningCompetitions") or [] if isinstance(c, dict) and c.get("type") == "LEAGUE" and text(c.get("code"))]
            pick = next((c for c in running if c["code"] in self.LEAGUES), running[0] if running else None)
            league = {"id": pick["code"], "name": text(pick.get("name"))} if pick else None
        area = raw.get("area") if isinstance(raw.get("area"), dict) else {}
        return {"id": str(whole(raw["id"])), "name": text(raw["name"]), "code": code_of(raw.get("shortName") or raw["name"], raw.get("tla")),
                "colours": colours_from_words(raw.get("clubColors")), "league": league, "country": text(area.get("name"))}

    def league_teams(self, get, code):
        answer = get(f"/competitions/{code}/teams", keep=7 * 86400)
        name = text((answer.get("competition") or {}).get("name")) if isinstance(answer.get("competition"), dict) else ""
        listed = []
        for raw in answer.get("teams") or [] if isinstance(answer.get("teams"), list) else []:
            team = self._team(raw, {"id": code, "name": name or code})
            if team:
                listed.append((team, raw))
        return listed

    def find_team(self, get, query):
        """The team typed in Settings: its number here, or its name looked for in each free league in turn."""
        if query.strip().isdigit():
            team = self._team(get(f"/teams/{int(query)}", keep=30 * 86400))
            if team is None:
                raise Trouble("missing")
            return team
        for code in self.LEAGUES:
            listed = self.league_teams(get, code)
            found = best(query, [((raw.get("name"), raw.get("shortName"), raw.get("tla")), team) for team, raw in listed])
            if found:
                return found
        raise Trouble("missing")

    def side(self, get, raw, known):
        if not isinstance(raw, dict) or whole(raw.get("id")) is None:
            return {"id": "", "name": "", "code": "???", "colours": [GREY, GREY]}
        ident = str(whole(raw["id"]))
        name = text(raw.get("name")) or text(raw.get("shortName"))
        return {"id": ident, "name": name, "code": code_of(raw.get("shortName") or name, raw.get("tla")),
                "colours": known.get(ident, [GREY, GREY])}

    def match(self, get, raw, known):
        if not isinstance(raw, dict) or whole(raw.get("id")) is None or epoch(raw.get("utcDate")) is None:
            return None
        status = text(raw.get("status")).upper()
        score = raw.get("score") if isinstance(raw.get("score"), dict) else {}
        duration = text(score.get("duration")).upper()
        minute, added = minutes(raw.get("minute"))
        state = {"SCHEDULED": "scheduled", "TIMED": "scheduled", "IN_PLAY": "live", "LIVE": "live", "PAUSED": "half_time",
                 "EXTRA_TIME": "extra_time", "PENALTY_SHOOTOUT": "penalties", "FINISHED": "finished", "AWARDED": "finished",
                 "POSTPONED": "postponed", "SUSPENDED": "suspended", "CANCELLED": "cancelled"}.get(status)
        if state is None:
            return None
        if state == "live" and duration == "EXTRA_TIME":
            state = "extra_time"
        if state == "half_time" and (duration in ("EXTRA_TIME", "PENALTY_SHOOTOUT") or (minute or 0) > 60):
            state = "break"                     # a pause that isn't half time (before extra time, or before penalties)

        def pair(part):
            part = score.get(part) if isinstance(score.get(part), dict) else {}
            home, away = whole(part.get("home")), whole(part.get("away"))
            return None if home is None or away is None else [home, away]
        full, pens = pair("fullTime"), pair("penalties")
        played = full
        if pens and full:
            regular, extra = pair("regularTime"), pair("extraTime")
            if regular and extra:               # the goals scored in play, without the shoot-out's
                played = [regular[0] + extra[0], regular[1] + extra[1]]
            elif full[0] >= pens[0] and full[1] >= pens[1]:
                played = [full[0] - pens[0], full[1] - pens[1]]
        if state in ("scheduled", "postponed", "cancelled"):
            played = pens = None
        elif played is None and state in IN_PLAY and not any(isinstance(score.get(k), dict) and any(
                v is not None for v in score[k].values()) for k in ("fullTime", "halfTime")):
            played = [0, 0]                     # (no score at all yet: 0-0. One that can't be read: None, so the last one stays)
        home, away = self.side(get, raw.get("homeTeam"), known), self.side(get, raw.get("awayTeam"), known)
        goal = None
        goals = [g for g in raw.get("goals") or [] if isinstance(g, dict) and whole(g.get("minute")) is not None] if isinstance(raw.get("goals"), list) else []
        if goals and state in IN_PLAY:
            last = goals[-1]
            scorer = last.get("scorer") if isinstance(last.get("scorer"), dict) else {}
            goal = {"minute": whole(last["minute"]), "name": surname(scorer.get("name"))}
        competition = raw.get("competition") if isinstance(raw.get("competition"), dict) else {}
        return {"id": str(whole(raw["id"])), "kickoff": epoch(raw["utcDate"]), "timed": status != "SCHEDULED", "state": state,
                "home": home, "away": away, "league": {"id": text(competition.get("code")), "name": text(competition.get("name"))},
                "score": played, "pens": pens if state in ("penalties", "finished") else None,
                "after": {"EXTRA_TIME": "extra_time", "PENALTY_SHOOTOUT": "penalties"}.get(duration) if state == "finished" else None,
                "minute": minute if state in IN_PLAY else None, "added": (whole(raw.get("injuryTime")) or added) if state in IN_PLAY else None, "goal": goal}

    def known_colours(self, get, team):
        """Kit colours of the teams in our league, from its team list (kept a week): no request per opponent."""
        known = {team["id"]: team["colours"]}
        league = (team.get("league") or {}).get("id")
        if league:
            try:
                known.update({t["id"]: t["colours"] for t, _ in self.league_teams(get, league)})
            except Trouble:
                pass
        return known

    def fixtures(self, get, team, today):
        """Our matches from ten days back to sixty ahead, soonest first: the last result, any in play, the next."""
        window = f"dateFrom={(today - dt.timedelta(days=10)).isoformat()}&dateTo={(today + dt.timedelta(days=60)).isoformat()}"
        answer = get(f"/teams/{team['id']}/matches?{window}")
        known = self.known_colours(get, team)
        found = [m for m in (self.match(get, raw, known) for raw in answer.get("matches") or []) if m]
        return sorted(found, key=lambda m: m["kickoff"])

    def live(self, get, team, match):
        """One match in play, looked at again: its own address has the minute and the goals."""
        return self.match(get, get(f"/matches/{match['id']}"), {match["home"]["id"]: match["home"]["colours"], match["away"]["id"]: match["away"]["colours"]})

    def table(self, get, team):
        league = (team.get("league") or {}).get("id")
        if not league:
            return []
        answer = get(f"/competitions/{league}/standings")
        tables = [s for s in answer.get("standings") or [] if isinstance(s, dict) and isinstance(s.get("table"), list)]
        tables.sort(key=lambda s: s.get("type") != "TOTAL")       # the whole season's table, not home or away only
        for standing in tables:
            rows = []
            for row in standing["table"]:
                side = row.get("team") if isinstance(row, dict) and isinstance(row.get("team"), dict) else None
                if side is None or whole(row.get("position")) is None or whole(side.get("id")) is None or whole(row.get("points")) is None:
                    continue
                rows.append({"pos": whole(row["position"]), "id": str(whole(side["id"])), "points": whole(row["points"]),
                             "code": code_of(side.get("shortName") or side.get("name") or "", side.get("tla"))})
            if any(r["id"] == team["id"] for r in rows):
                return sorted(rows, key=lambda r: r["pos"])
        return []


# -- TheSportsDB ----------------------------------------------------------------------------------------------
class TheSportsDB:
    """TheSportsDB, API v2, which is for its Premium subscribers only: the key goes in the X-API-KEY header.
    https://www.thesportsdb.com/documentation (read 23 Nov 2026): "V2 ... only for premium subscribers"; search,
    lookup, schedule (next/previous for a team or a league, 10 an answer) and livescore (by sport or league).
    Its free key ("123") is a test key everyone shares, on the old v1 API only, with one fixture an answer: too
    little for any of these screens, and v1 wants the key in the address. So this needs the Premium key, and the
    free one is never offered. Its league table is only on v1, so there is no table from here.

    One of these for each team sport (``sport``, a key of sports.SPORTS). They share one key and one limit
    (``id``); a feed is named by ``feed_id``, so a cricket team and a football team of the same name don't mix."""
    id = "thesportsdb"
    name = "TheSportsDB"
    short = "THESPORTSDB"
    host = "www.thesportsdb.com"
    base = "https://www.thesportsdb.com/api/v2/json"
    gap = 2.0               # seconds between requests: far under Premium's 100 a minute
    has_table = False
    needs_key = True
    STATUS = {"NS": "scheduled", "TBD": "scheduled", "1H": "live", "2H": "live", "LIVE": "live", "HT": "half_time", "ET": "extra_time",
              "BT": "break", "P": "penalties", "FT": "finished", "AET": "finished", "PEN": "finished", "AWD": "finished", "WO": "finished",
              "PST": "postponed", "CANC": "cancelled", "ABD": "cancelled", "SUSP": "suspended", "INT": "suspended",
              "NOT STARTED": "scheduled", "MATCH FINISHED": "finished", "POSTPONED": "postponed", "CANCELLED": "cancelled",
              "AOT": "finished", "AP": "finished", "FT/OT": "finished", "AFTER OT": "finished", "FINAL": "finished", "F/OT": "finished"}
    # Periods of the other sports' live scores (quarters, periods, innings, overtime): in play.
    PLAYING = re.compile(r"(Q[1-4]|[1-4]Q|OT\d?|P[1-3]|[1-3]P|SO|PT|BT|IN\d{1,2}|T\d{1,2}|B\d{1,2}|TOP \d{1,2}|BOT \d{1,2}|"
                         r"[1-9](ST|ND|RD|TH)( (HALF|QUARTER|PERIOD|INNING))?)")
    OVERTIME = ("AOT", "FT/OT", "AFTER OT", "F/OT")

    def __init__(self, sport="football"):
        from .sports import SPORTS
        self.sport = sport if sport in SPORTS and SPORTS[sport]["kind"] == "team" else "football"
        self.strsport = SPORTS[self.sport]["tsdb"].lower()
        self.feed_id = self.id if self.sport == "football" else f"{self.id}:{self.sport}"   # (football's: as in 1.x, so its cache still counts)
        self.live_every = 120.0 if SPORTS[self.sport]["live"] else None   # its live scores are "2 min livescore": asking sooner gets the same answer

    def ours(self, raw):
        """Whether a row is of this screen's sport (a row that doesn't say is taken as ours)."""
        return text(raw.get("strSport")).lower() in (self.strsport, "")

    def headers(self, key):
        return {"X-API-KEY": key}

    def trouble(self, status, body, headers):
        if status == 429:
            return Trouble("limit", 60)
        if status in (401, 403):
            return Trouble("refused")
        if status == 404:
            return Trouble("missing")
        return Trouble("answer")

    @staticmethod
    def rows(answer):
        """The list in an answer, whatever it is filed under ("search", "lookup", "schedule", "livescore")."""
        if isinstance(answer, dict):
            for value in answer.values():
                if isinstance(value, list):
                    return [r for r in value if isinstance(r, dict)]
        return []

    def _team(self, raw):
        if whole(raw.get("idTeam")) is None or not text(raw.get("strTeam")):
            return None
        league = {"id": str(whole(raw.get("idLeague"))), "name": text(raw.get("strLeague"))} if whole(raw.get("idLeague")) is not None else None
        return {"id": str(whole(raw["idTeam"])), "name": text(raw["strTeam"]), "code": code_of(raw["strTeam"], raw.get("strTeamShort")),
                "colours": colours_from_hex(raw.get("strColour1"), raw.get("strColour2")), "league": league, "country": text(raw.get("strCountry"))}

    def find_team(self, get, query):
        if query.strip().isdigit():
            found = [self._team(r) for r in self.rows(get(f"/lookup/team/{int(query)}", keep=30 * 86400))]
        else:
            slug = re.sub(r"[^a-z0-9]+", "_", plain(query) or query.lower()).strip("_")
            if not slug:
                raise Trouble("missing")
            rows = [r for r in self.rows(get(f"/search/team/{slug}", keep=30 * 86400)) if self.ours(r)]
            teams = [(r, self._team(r)) for r in rows]
            one = best(query, [((r.get("strTeam"), r.get("strTeamShort"), r.get("strTeamAlternate")), t) for r, t in teams if t])
            found = [one] if one else [t for _, t in teams[:1]]
        found = [t for t in found if t]
        if not found:
            raise Trouble("missing")
        return found[0]

    def side(self, get, ident, name, known):
        ident = str(whole(ident)) if whole(ident) is not None else ""
        if ident and ident not in known:
            try:                                # an opponent's kit colours: asked for once, kept a month
                rows = [self._team(r) for r in self.rows(get(f"/lookup/team/{ident}", keep=30 * 86400))]
                known[ident] = next((t["colours"] for t in rows if t), [GREY, GREY])
                short = next((t["code"] for t in rows if t), None)
                if short:
                    known[ident + ":code"] = short
            except Trouble:
                known[ident] = [GREY, GREY]
        return {"id": ident, "name": text(name), "code": known.get(ident + ":code") or code_of(text(name) or "???"),
                "colours": known.get(ident, [GREY, GREY])}

    def state_of(self, status, live=False):
        """A state of STATES from TheSportsDB's strStatus, or None. ``live``: the row is from its live scores, where
        a period we don't know the name of is still a game in play."""
        state = self.STATUS.get(status)
        if state is None and status and (self.PLAYING.fullmatch(status) or live):
            state = "live"
        return state

    def match(self, get, raw, known, live=False):
        kickoff = epoch(raw.get("strTimestamp")) or epoch(f"{text(raw.get('dateEvent'))}T{text(raw.get('strTime')) or '00:00:00'}")
        if whole(raw.get("idEvent")) is None or kickoff is None:
            return None
        status = text(raw.get("strStatus")).upper()
        state = self.state_of(status, live)
        home, away = whole(raw.get("intHomeScore")), whole(raw.get("intAwayScore"))
        if text(raw.get("strPostponed")).lower() == "yes":
            state = "postponed"
        if not self.live_every and state in IN_PLAY:   # no live scores for this sport: a schedule saying "in play" is
            state = "scheduled"                        # only "started"; nothing is drawn as LIVE and it isn't watched
        if state is None:                       # a status we don't know: by its score, if it has one
            state = "finished" if home is not None and away is not None else "scheduled"
        score = None
        if state in IN_PLAY or state == "finished":
            if home is not None and away is not None:
                score = [home, away]
            elif raw.get("intHomeScore") in (None, "") and raw.get("intAwayScore") in (None, ""):
                score = [0, 0]                  # (no score at all yet: 0-0. One that can't be read: None, so the last one stays)
        minute, added = minutes(raw.get("strProgress")) if state in IN_PLAY else (None, None)
        period = None
        if state in IN_PLAY and minute is None and self.sport != "football":       # Q3, P2, TOP 5TH: said as it is
            period = text(raw.get("strProgress"), 8).upper() or (status if self.PLAYING.fullmatch(status) else None)
        after = {"AET": "extra_time", "PEN": "penalties"}.get(status) if self.sport == "football" else ("overtime" if status in self.OVERTIME else None)
        said = text(text(raw.get("strResult"), 400).split("\n")[0], 120) if state == "finished" else ""
        return {"id": str(whole(raw["idEvent"])), "kickoff": kickoff, "timed": status != "TBD" and bool(text(raw.get("strTime")) or raw.get("strTimestamp")),
                "state": state, "home": self.side(get, raw.get("idHomeTeam"), raw.get("strHomeTeam"), known),
                "away": self.side(get, raw.get("idAwayTeam"), raw.get("strAwayTeam"), known),
                "league": {"id": str(whole(raw.get("idLeague")) or ""), "name": text(raw.get("strLeague"))},
                "score": score, "pens": None, "after": after if state == "finished" else None,
                "minute": minute, "added": added, "goal": None, **({"period": period} if period else {}), **({"said": said} if said else {})}

    def fixtures(self, get, team, today):
        known = {team["id"]: team["colours"], team["id"] + ":code": team["code"]}
        found = {}
        for path in (f"/schedule/previous/team/{team['id']}", f"/schedule/next/team/{team['id']}"):
            for raw in self.rows(get(path)):
                if not self.ours(raw):
                    continue
                match = self.match(get, raw, known)
                if match:
                    found[match["id"]] = match
        return sorted(found.values(), key=lambda m: m["kickoff"])

    def live(self, get, team, match):
        """The league's live scores, and our match among them (None: it isn't listed, so nothing new is known)."""
        league = match["league"]["id"] or (team.get("league") or {}).get("id")
        if not league:
            return None
        known = {match["home"]["id"]: match["home"]["colours"], match["away"]["id"]: match["away"]["colours"],
                 match["home"]["id"] + ":code": match["home"]["code"], match["away"]["id"] + ":code": match["away"]["code"]}
        for raw in self.rows(get(f"/livescore/{league}")):
            if str(whole(raw.get("idEvent"))) == match["id"]:
                now = self.match(get, {**raw, "strTimestamp": dt.datetime.fromtimestamp(match["kickoff"], dt.timezone.utc).isoformat()}, known, live=True)
                if now:
                    return {**now, "kickoff": match["kickoff"], "timed": match["timed"], "league": match["league"]}
        return None

    def table(self, get, team):
        return []


SOURCES = {s.id: s for s in (FootballData(), TheSportsDB())}      # (football's two: the Source setting's choices)


def source_for(sport, source="football_data", tour=None):
    """The source a screen of ``sport`` uses: for football the one chosen, for the other team sports TheSportsDB,
    for Formula 1 Jolpica-F1, for tennis and golf the tour on TheSportsDB."""
    from .sports import SPORTS, tour_for
    kind = SPORTS.get(sport, SPORTS["football"])["kind"]
    if kind == "championship":
        from .f1 import JOLPICA
        return JOLPICA
    if kind == "tour":
        from .tours import tour_source
        return tour_source(tour_for(sport, tour))
    if sport in (None, "football") or sport not in SPORTS:
        return SOURCES.get(source) or SOURCES["football_data"]
    return _TEAMS.setdefault(sport, TheSportsDB(sport))


_TEAMS = {}
