"""The Olympics and Paralympics tracker: a Sports screen that needs no key and fetches nothing.

It counts down to the next Games, then says DAY n OF m while they are on, then moves on to the next. The
Games after that take turns with it, so you can see what is coming next too. There is no live medal table: no
free, documented source for one exists (the ones that do exist are paid feeds, or scrape web pages).

The dates are bundled here, read on the official pages on 23 Nov 2026:
- LA 2028 Olympic Games, 14 to 30 July 2028; Paralympic Games, 15 to 27 August 2028.
  https://olympics.com/en/news/la-2028-olympic-paralympic-games-dates-confirmed
  (Some events start on 13 July, the day before the opening: the council's reading of LA28's schedule,
  https://la28.org/en/newsroom/la28-reveals-comprehensive-olympic-competition-schedule.html)
- French Alps 2030 Olympic Winter Games, 1 to 17 February 2030, and Paralympic Winter Games, 1 to 10 March 2030.
  olympics.com still says these dates are "proposed" and the Paralympics "would follow":
  https://olympics.com/en/news/olympic-winter-games-french-alps-2030-top-facts-you-need-to-know-about-the-host,
  https://www.paralympic.org/french-alps-2030. So they are marked ``proposed`` until confirmed.
Later Games are added with later versions of this module. Days are counted in the Matrix's own time zone.

No Olympic rings, Paralympic Agitos or Games emblem is drawn: the torch, sun and snowflake are this module's own
(art/, made in the Animator).
"""
import datetime as dt

from bongo.module import Style

from . import art, draw

try:
    from zoneinfo import ZoneInfo
except ImportError:                    # (no time zones: the Matrix's own day)
    ZoneInfo = None

D = dt.date
GAMES = (
    {"id": "la28_olympics", "where": ("LA 2028",), "kind": "olympics", "season": "summer", "start": D(2028, 7, 14), "end": D(2028, 7, 30),
     "early": D(2028, 7, 13), "zone": "America/Los_Angeles"},
    {"id": "la28_paralympics", "where": ("LA 2028",), "kind": "paralympics", "season": "summer", "start": D(2028, 8, 15), "end": D(2028, 8, 27),
     "zone": "America/Los_Angeles"},
    {"id": "alps30_olympics", "where": ("FRENCH ALPS 2030", "ALPS 2030"), "kind": "olympics", "season": "winter", "start": D(2030, 2, 1),
     "end": D(2030, 2, 17), "proposed": True, "zone": "Europe/Paris"},
    {"id": "alps30_paralympics", "where": ("FRENCH ALPS 2030", "ALPS 2030"), "kind": "paralympics", "season": "winter", "start": D(2030, 3, 1),
     "end": D(2030, 3, 10), "proposed": True, "zone": "Europe/Paris"},
)
KINDS = {"olympics": ("OLYMPICS",), "paralympics": ("PARALYMPICS", "PARA")}
VIEW_SECONDS = 8.0
EARLY_SECONDS = 4.0                    # on the day of the first events, the two things said take turns this fast


def day_of(games, when):
    """The date at the Games' own home at ``when`` (a datetime): DAY 1 is the opening day there, not here. A date
    given instead is taken as it is."""
    if not isinstance(when, dt.datetime):
        return when
    try:
        return when.astimezone(ZoneInfo(games["zone"])).date() if ZoneInfo and when.tzinfo else when.date()
    except Exception:                  # (a Matrix without that zone)
        return when.date()


def chosen(which="both", season="both"):
    """The bundled Games a screen with these settings follows, in date order."""
    return [g for g in GAMES if which in ("both", g["kind"]) and season in ("both", g["season"])]


def ahead(when, which="both", season="both"):
    """The Games on now or still to come at ``when`` (a date, or a datetime: each Games' own day is used): the
    first is the one to show, the second the one after."""
    return [g for g in chosen(which, season) if g["end"] >= day_of(g, when)]


def lines(games, today, phase=0):
    """(top, middle, bottom, middle colour) for one Games on ``today`` (its own date): each a wording or several,
    longest first. ``phase``: on the day of the first events, which of its two things is said."""
    kind = KINDS[games["kind"]]
    where = games["where"]
    if games["start"] <= today <= games["end"]:
        n, m = (today - games["start"]).days + 1, (games["end"] - games["start"]).days + 1
        bottom = (f"{kind[0]}, FINAL DAY", *kind) if n == m else kind
        said = (f"DAY {n} OF {m}", "LAST DAY") if n == m else (f"DAY {n} OF {m}", f"DAY {n}/{m}")
        return where, said, bottom, draw.GREEN
    days = (games["start"] - today).days
    if games.get("early") == today:    # the first events are today, the opening tomorrow: said one at a time
        if phase % 2 == 0:
            return where, ("TODAY",), (f"{kind[0]} FIRST EVENTS", "FIRST EVENTS", "EVENTS"), draw.GREEN
        return where, ("TOMORROW",), (f"{kind[0]} OPEN", "OPENING"), draw.TEXT
    count = ("TOMORROW",) if days == 1 else (f"{days} DAYS", f"{days}D")
    return where, count, kind, draw.TEXT


class Games(Style):
    """The tracker's screen: no key, nothing fetched, drawn from the dates above."""
    fps = 5
    defaults = {"games": "both", "season": "both"}
    choices = {"games": ["both", "olympics", "paralympics"], "season": ["both", "summer", "winter"]}

    def setup(self):
        self.which = self.settings.get("games") if self.settings.get("games") in self.choices["games"] else "both"
        self.season = self.settings.get("season") if self.settings.get("season") in self.choices["season"] else "both"

    def render(self, now):
        draw.tick(now)
        coming = ahead(now, self.which, self.season)[:2]
        if not coming:
            return draw.card(self.ctx, "NEXT GAMES", ("DATES TO COME", "NO DATES YET", "NO DATES"), ("UPDATE SPORTS", ""))
        try:
            seconds = now.timestamp()
        except (OverflowError, ValueError, OSError):
            seconds = 0.0
        games = coming[int(seconds // VIEW_SECONDS) % len(coming)]   # (by the clock, so every panel is in step)
        one_line = self.ctx.height < 17
        top, middle, bottom, colour = lines(games, day_of(games, now), 0 if one_line else int(seconds // EARLY_SECONDS))
        if one_line and games.get("early") == day_of(games, now):
            top = KINDS[games["kind"]]                 # (one line: TODAY, EVENTS, OLYMPICS in turn; the opening is tomorrow's)
        torch = art.at("games_torch", seconds)
        mark = art.icon_named(f"games_{games['season']}")
        return draw.games(self.ctx, torch, top, middle, bottom, middle_colour=colour, icon=mark)
