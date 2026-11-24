"""The Sports screen: which frame to show now, and whether to ask to keep the panel.

What is known comes from feed.py (``feed.view``); the frames are drawn by draw.py. Nothing here waits for the
internet: a frame is drawn from whatever is known at that moment, and says so when that is nothing.

The ticked views take turns on the one screen (Result, Next, Table). While a match is in play there is only the
live view. Kick-off times are in the Matrix's own time zone: ``now`` arrives in it.

One screen follows one thing (sports.py): a team (football and the other team sports, here), the Formula 1
championship or a tennis or golf tour (racing.py).
"""
import datetime as dt

from bongo.module import Style

from . import art, draw, example
from .feed import feed_for
from .racing import Racing
from .sources import IN_PLAY, SOURCES, as_known, plain, source_for
from .sports import SPORTS, TOURS, tour_for

try:                                   # a later Matrix: views take turns the way its own screens do
    from bongo.scroll import Scrolls
except ImportError:                    # an older one: by the clock
    class Scrolls:
        pass

VIEW_SECONDS = 8.0
FIRST_WORD = 15 * 60.0                 # after kick-off, the screen waits this long at most for the first live word
RESULT_DAYS = 7                        # a result is shown for a week (or until the next match kicks off)
FULL_TIME_HOLD = 120.0                 # seconds the final score keeps the panel after the whistle
LIVE_GONE = 10 * 60.0                  # no fresh score for this long: stop saying LIVE, stop keeping the panel
STALE = 86400.0                        # fixtures older than a day (no connection): say so
SETTINGS = ("IN ITS SETTINGS", "IN SETTINGS")
PLAN = ("NOT IN PLAN", "NO PLAN")
NO_ANSWER = ("NO ANSWER YET", "NO ANSWER", "OFFLINE")
AGAIN = ("TRYING AGAIN", "RETRYING")
PREMIUM = ("THESPORTSDB PREMIUM", "PREMIUM KEY")
FREE_KEY = ("FOOTBALL-DATA.ORG KEY", "FREE KEY")
VIEWS = ("next", "live", "result", "table")
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def ordinal(n):
    return f"{n}{'TH' if 10 <= n % 100 <= 20 else {1: 'ST', 2: 'ND', 3: 'RD'}.get(n % 10, 'TH')}"


def ago(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 86400}D" if seconds >= 86400 else f"{seconds // 3600}H" if seconds >= 3600 else f"{max(1, seconds // 60)}M"


def key_for(source, settings, sport):
    """The key a screen's source uses, from the module's two keys (each entered once, for every Sports screen):
    Key is only ever football-data.org's, Premium key only ever TheSportsDB's. Nothing is guessed and nothing falls
    back from one to the other, so a key never reaches another service. (Sports 1.x kept one key, for whichever
    source its screens used: a 1.x TheSportsDB user pastes it again under Premium key, and until then those screens
    say NEEDS A KEY, THESPORTSDB PREMIUM and fetch nothing.)"""
    if not source.needs_key:
        return ""
    if source.id == "football_data":
        return str(settings.get("key") or "").strip()
    return str(settings.get("premium_key") or "").strip()


class Board(Racing, Scrolls, Style):
    fps = 5
    defaults = {"sport": "football", "team": "", "tour": "atp", "highlight": "", "show": list(VIEWS), "take_over": False,
                "source": "football_data"}
    choices = {"sport": list(SPORTS), "tour": list(TOURS), "show": list(VIEWS), "source": list(SOURCES)}

    def setup(self):
        s = self.settings
        self.sport = s.get("sport") if s.get("sport") in SPORTS else "football"
        self.kind = SPORTS[self.sport]["kind"]
        self.tour = tour_for(self.sport, s.get("tour"))
        self.source = source_for(self.sport, s.get("source"), self.tour)
        self.key = key_for(self.source, s, self.sport)
        self.team_text = {"team": str(s.get("team") or "").strip(), "championship": "championship"}.get(self.kind, self.tour or "")
        self.highlight = str(s.get("highlight") or "").strip()
        self.show = [v for v in ("result", "next", "table", "live") if v in (s.get("show") or [])]
        self.icon = art.icon(self.sport)
        self.match_icon = self.icon
        ready = self.team_text and (self.key or not self.source.needs_key)
        self.feed = feed_for(self.source, self.team_text) if ready else None

    def sport_words(self):
        return SPORTS[self.sport]["words"]

    # -- the time, in the Matrix's zone -----------------------------------------------------------------------
    def local(self, epoch, now):
        return dt.datetime.fromtimestamp(epoch, now.tzinfo) if now.tzinfo else dt.datetime.fromtimestamp(epoch)

    def day(self, epoch, now):
        when = self.local(epoch, now)
        days = (when.date() - now.date()).days
        date = f"{when.day} {MONTHS[when.month - 1]}"
        return "TODAY" if days == 0 else ("TOMORROW", date) if days == 1 else (f"{DAYS[when.weekday()]} {date}", date)

    # -- one frame ----------------------------------------------------------------------------------------------
    @property
    def busy(self):
        """The player's ``busy``: a moment longer, please (kick-off has passed and the first word is on its way),
        or a view that hasn't had its turn (``Scrolls``)."""
        try:
            return bool(self.__dict__.get("waiting")) or bool(getattr(super(), "busy", False))
        except Exception:
            return False

    def render(self, now):
        self.stay = False
        self.waiting = False
        draw.tick(now)
        preview = bool(getattr(self.ctx, "preview", False))
        football = self.sport == "football"
        top = self.sport_words()
        if not self.show:
            return draw.card(self.ctx, top, ("NOTHING TICKED", "NO VIEWS"), ("TICK WHAT TO SHOW", "IN SETTINGS"), icon=self.icon)
        if football and preview and not self.team_text and not self.key:      # not set up yet: what it will look like
            frames = example.frames(self.ctx)
            return frames[self.turn(list(range(len(frames))), now, example.SECONDS)]()
        if self.source.needs_key and not self.key:                            # the same words for every sport
            which = PREMIUM if self.source.id == "thesportsdb" else FREE_KEY
            return draw.card(self.ctx, top, ("NEEDS A KEY", "NO KEY"), which, middle_colour=draw.AMBER, icon=self.icon)
        if not self.team_text:
            return draw.card(self.ctx, top, ("TYPE YOUR TEAM", "ADD YOUR TEAM", "NO TEAM"), SETTINGS, middle_colour=draw.AMBER, icon=self.icon)
        wants = [v for v in ("table",) if "table" in self.show or "result" in self.show]
        view = self.feed.ask(self.key, wants, preview)
        if self.kind == "championship":
            return self.f1(view, now, now.timestamp())
        if self.kind == "tour":
            return self.tours(view, now, now.timestamp())
        return self.frame(view, now, now.timestamp(), preview)

    def frame(self, view, now, t, preview):
        team, problem = view["team"], view["problem"]
        if team is None:
            if problem == "refused":
                return draw.card(self.ctx, self.source.short, ("KEY REFUSED", "BAD KEY"), ("CHECK THE KEY", "CHECK IT"), middle_colour=draw.RED, icon=self.icon)
            if problem == "missing":
                return draw.card(self.ctx, ("NO TEAM CALLED", "NO TEAM"), (self.team_text.upper(), "NOT FOUND", "NO TEAM"), (f"ON {self.source.short}", self.source.short, ""), middle_colour=draw.RED, icon=self.icon)
            if problem == "plan":
                return draw.card(self.ctx, self.source.short, PLAN, (self.team_text.upper(), ""), middle_colour=draw.RED, icon=self.icon)
            if problem in ("offline", "limit"):
                return draw.card(self.ctx, self.sport_words(), NO_ANSWER, AGAIN, icon=self.icon)
            return draw.card(self.ctx, self.sport_words(), ("FINDING TEAM", "LOOKING"), (self.team_text.upper(), ""), icon=self.icon)
        matches = [as_known(m, t) for m in view["matches"]]
        if not view["at"].get("matches"):
            if problem == "refused":
                return draw.card(self.ctx, self.source.short, ("KEY REFUSED", "BAD KEY"), ("CHECK THE KEY", "CHECK IT"), middle_colour=draw.RED, icon=self.icon)
            if problem == "plan":
                return draw.card(self.ctx, self.source.short, PLAN, (team["name"].upper(), team["code"]), middle_colour=draw.RED, icon=self.icon)
            if preview:
                return self.found(team)
            return draw.card(self.ctx, team["code"], NO_ANSWER if problem else ("GETTING FIXTURES", "LOADING"), AGAIN if problem else "", icon=self.icon)

        live_age = t - view["at"].get("live", 0)
        playing = next((m for m in matches if m["state"] in IN_PLAY), None)
        due = next((m for m in matches if m["state"] == "scheduled" and m["timed"] and 0 <= t - m["kickoff"] < 4 * 3600), None)
        last = next((m for m in reversed(matches) if m["state"] == "finished" and (m["score"] or m.get("said"))), None)   # (no score read: no result)
        upcoming = due or next((m for m in matches if (m["state"] == "scheduled" and m["kickoff"] > t)
                                or (m["state"] in ("postponed", "suspended") and m["kickoff"] > t - 86400)), None)
        ended = view["ended"].get(last["id"], last["kickoff"] + 7200) if last else None
        just_ended = last is not None and 0 <= t - ended < FULL_TIME_HOLD
        take_over = bool(self.settings.get("take_over")) and not preview and bool(self.source.live_every)   # (only where there are live scores)

        if playing and "live" in self.show:
            if preview and int(t // VIEW_SECONDS) % 2 == 0:
                return self.found(team)                          # in the editor: the team it found, turn about with the score
            fresh = live_age < LIVE_GONE
            self.stay = take_over and fresh                      # (Style.stay: a later Matrix keeps the panel for it)
            return self.live(playing, t, live_age, fresh)
        if just_ended and ("live" in self.show or "result" in self.show):
            self.stay = take_over                                # the final score, for a moment, then back to the playlist
            return self.result(last, view, now, t)
        if due and "live" in self.show and take_over and t - due["kickoff"] < FIRST_WORD:
            self.waiting = True                                  # kick-off has passed: a moment longer, for the first word of it

        views = []
        if preview:
            views.append(("team", None))                         # in the editor: the team it found, so a wrong one shows
        if "result" in self.show and last and t - ended < RESULT_DAYS * 86400:
            views.append(("result", last))
        if playing and "next" in self.show:                      # (in play, with Live score unticked)
            views.append(("next", playing))
        elif upcoming and "next" in self.show:
            views.append(("next", upcoming))
        if "table" in self.show and any(r["id"] == team["id"] for r in view["table"]):
            views.append(("table", None))
        if not views:
            return draw.card(self.ctx, (team["name"].upper(), team["code"]), ("NO FIXTURES", "NO GAMES"), "" if matches else ("NOTHING TO SHOW YET", "NOTHING YET"), icon=self.icon)
        kind, match = self.turn(views, now, VIEW_SECONDS)
        if kind == "team":
            return self.found(team)
        if kind == "table":
            return draw.table(self.ctx, view["table"], team["id"])
        if kind == "result":
            return self.result(match, view, now, t)
        return self.next(match, view, now, t)

    def turn(self, views, now, seconds):
        """The view whose turn it is. On a Matrix with ``bongo.scroll`` each gets its time and the screen hands
        over between two of them; on an older one, by the clock."""
        if len(views) == 1:
            return views[0]
        if hasattr(self, "turns"):
            try:
                names = [f"view{i}" for i in range(len(views))]
                picked, _ = self.turns(("sports", self.team_text.lower(), len(views)), names, now, lambda _: seconds)
                return views[names.index(picked)]
            except Exception:                                    # (a Matrix whose ``turns`` isn't the one we know)
                pass
        return views[int(now.timestamp() // seconds) % len(views)]

    # -- the views ----------------------------------------------------------------------------------------------
    def found(self, team):
        league = (team.get("league") or {}).get("name") or team.get("country") or ""
        return draw.card(self.ctx, "YOUR TEAM", (team["name"].upper(), team["code"]), league.upper(), bottom_colour=draw.AMBER, kit=team["colours"], icon=self.icon)

    def next(self, match, view, now, t):
        top, icon = self.day(match["kickoff"], now), self.match_icon
        if match["state"] == "postponed":
            return draw.fixture(self.ctx, match["home"], match["away"], top, ("POSTPONED", "OFF"), draw.RED, icon=icon)
        if match["state"] == "suspended":
            return draw.fixture(self.ctx, match["home"], match["away"], top, ("SUSPENDED", "STOPPED"), draw.RED, icon=icon)
        if match["state"] in IN_PLAY:
            return draw.fixture(self.ctx, match["home"], match["away"], top, "IN PLAY", icon=icon)
        old = t - max(view["at"].get("matches", 0), view["at"].get("live", 0))
        if match["kickoff"] + 300 <= t and not self.source.live_every:   # no live scores for this sport: say so, plainly
            return draw.fixture(self.ctx, match["home"], match["away"], top, ("STARTED, NO LIVE SCORES", "STARTED"), draw.GREY, icon=icon)
        if match["kickoff"] + 300 <= t:                          # well past kick-off and nothing has been heard since
            return draw.fixture(self.ctx, match["home"], match["away"], top, (f"NO NEWS FOR {ago(old)}", f"NO NEWS {ago(old)}"), draw.GREY, icon=icon)
        if old > STALE and int(t // 4) % 2:                      # a day without an answer: it may have moved
            return draw.fixture(self.ctx, match["home"], match["away"], top, (f"CHECKED {ago(old)} AGO", f"OLD: {ago(old)}"), draw.GREY, icon=icon)
        start = "KO" if self.sport in ("football", "rugby_union", "american_football") else "AT"
        kick = self.local(match["kickoff"], now).strftime(f"{start} %H:%M") if match["timed"] else f"{start} TBC"
        return draw.fixture(self.ctx, match["home"], match["away"], top, kick, icon=icon)

    def live(self, match, t, age, fresh):
        state, score = match["state"], match["score"] or ["?", "?"]   # (a score that couldn't be read: not a made-up 0-0)
        minute = ""
        if match["minute"] is not None:
            minute = f"{match['minute']}+{match['added']}'" if match["added"] else f"{match['minute']}'"
        goal = match.get("goal")
        bottom = (f"GOAL {goal['minute']}' {goal['name']}".strip(), f"GOAL {goal['minute']}'") if goal and goal.get("minute") is not None else ""
        if match.get("pens") and state == "penalties":
            bottom = f"PENS {match['pens'][0]}-{match['pens'][1]}"
        if not fresh:                                            # the score is from a while ago: say how long, claim nothing
            return draw.scoreline(self.ctx, match["home"], match["away"], score, (f"NO NEWS FOR {ago(age)}", f"NO NEWS {ago(age)}"), draw.GREY, "", draw.GREY)
        if state == "half_time":
            return draw.scoreline(self.ctx, match["home"], match["away"], score, ("HALF TIME", "HT"), draw.AMBER, "")
        if state == "break":
            return draw.scoreline(self.ctx, match["home"], match["away"], score, "BREAK", draw.AMBER, bottom)
        if state == "penalties":
            return draw.scoreline(self.ctx, match["home"], match["away"], score, ("PENALTIES", "PENS"), draw.RED, bottom, draw.AMBER)
        if state == "extra_time":
            minute = (f"ET {minute}", minute) if minute else "ET"
        if not minute and match.get("period"):                   # Q3, P2: the period, as the source says it
            minute = match["period"]
        blink = int(t * 2) % 2 == 0
        return draw.scoreline(self.ctx, match["home"], match["away"], score, "LIVE", draw.RED, bottom, draw.AMBER,
                              minute=minute or " ", dot=blink)

    def result(self, match, view, now, t):
        score = match["score"]
        when = self.local(match["kickoff"], now)
        full = "FULL TIME" if self.sport in ("football", "rugby_union") else "RESULT"   # (FINAL is a tournament's final)
        ft = "FT " if full == "FULL TIME" else ""
        top = full if when.date() == now.date() or 0 <= t - match["kickoff"] < 12 * 3600 else tuple(dict.fromkeys(
            (f"{ft}{DAYS[when.weekday()]} {when.day} {MONTHS[when.month - 1]}", f"{ft}{when.day} {MONTHS[when.month - 1]}", ft.strip() or full)))
        bottom = ""
        place = next((r["pos"] for r in view["table"] if r["id"] == (view["team"] or {}).get("id")), None)
        if match.get("after") == "penalties":
            bottom = (f"{match['pens'][0]}-{match['pens'][1]} ON PENS", f"PENS {match['pens'][0]}-{match['pens'][1]}") if match.get("pens") else ("ON PENALTIES", "ON PENS")
        elif match.get("after") == "extra_time":
            bottom = ("AFTER EXTRA TIME", "AFTER ET", "AET")
        elif match.get("after") == "overtime":
            bottom = ("AFTER OVERTIME", "AFTER OT", "OT")
        elif place and view["at"].get("table", 0) >= view["ended"].get(match["id"], 0) - 60:
            bottom = (f"{ordinal(place)} IN TABLE", ordinal(place))  # (only from a table fetched since the whistle)
        elif match.get("said"):                                  # cricket: "Scorchers won by 6 wickets", as the source says it
            bottom = said_words(match["said"], match["home"], match["away"])
        if score is None:                                        # (a result in words only: the two teams, and the words)
            return draw.fixture(self.ctx, match["home"], match["away"], top, bottom, draw.GREEN, icon=self.match_icon)
        return draw.scoreline(self.ctx, match["home"], match["away"], score, top, draw.GREEN, bottom, icon=self.match_icon)


SHORTER = (("WICKETS", "WKTS"), ("WICKET", "WKT"), ("RUNS", "RUNS"))


def said_words(said, home=None, away=None):
    """A result in words, longest first: the whole; without what's in brackets; with the winner's three letters
    (PER WON BY 6 WICKETS); with WKTS for wickets. Every wording names who won where it can."""
    said = said.upper().strip()
    plain_said = said.split(" (")[0].strip()
    out = [said, plain_said]
    if " WON " in f" {plain_said} ":
        who, rest = plain_said.split(" WON ", 1)
        code = next((side["code"] for side in (home, away) if side and plain(who) and (
            plain(who) in plain(side.get("name", "")) or plain(side.get("name", "")) in plain(who))), None)
        if code:
            out += [f"{code} WON {rest}"]
        short = rest
        for long, brief in SHORTER:
            short = short.replace(long, brief)
        out += [f"{code} WON {short}"] if code else []
        if code and short.startswith("BY "):
            out += [f"{code} WON, {short[3:]}"]          # (PER WON, 6 WKTS: who won, where the longer won't fit)
        out += [f"WON {short}"]                        # (the score above says who: the bigger number)
    return tuple(dict.fromkeys(w for w in out if w))
