"""The views of the screens that don't follow a team: Formula 1 (the championship) and tennis and golf (a tour).

A part of the Sports screen (board.py's ``Board`` has these methods). Formula 1: the next race with a countdown,
the last race's podium and the drivers' standings, with one driver picked out if one is named. A tour: its current
or next tournament, then the winner, with one player picked out where they appear. No live timing or scores for
any of these: the sources have none, and the screen says so rather than pretend.
"""
import re

from . import draw
from .f1 import RACE_HOURS
from .sources import plain
from .sports import TOURS

VIEW_SECONDS = 8.0
PENDING_DAYS = 3               # a race run with no result yet says RESULT TO COME for this long
RESULT_DAYS = 14               # a tour's last winner is shown for this long


def fewer_words(name, most=4):
    """Ways of saying a name, longest first, by whole words: BNP PARIBAS OPEN, BNP PARIBAS, BNP."""
    words = name.upper().split()[:8]
    out = [" ".join(words[:n]) for n in range(len(words), 0, -1)]
    if len(words) > 1 and words[0] == "THE":                       # THE RSM CLASSIC, RSM CLASSIC, RSM: never THE RSM
        out = [out[0]] + [" ".join(words[1:n]) for n in range(len(words), 1, -1)]
    return tuple(out[:most]) or ("",)


def countdown(seconds):
    """IN 13 DAYS, IN 5H 20M, IN 12 MIN, with shorter ways of saying each."""
    seconds = int(seconds)
    if seconds >= 2 * 86400:
        days = seconds // 86400
        return (f"IN {days} DAYS", f"{days} DAYS", f"{days}D")
    if seconds >= 3600:
        return (f"IN {seconds // 3600}H {seconds % 3600 // 60:02d}M", f"{seconds // 3600}H {seconds % 3600 // 60:02d}M")
    return (f"IN {max(1, seconds // 60)} MIN", f"{max(1, seconds // 60)} MIN")


class Racing:
    """Formula 1 and the tours. Mixed into board.Board, which has ``ctx``, ``settings``, ``show``, ``icon``,
    ``highlight``, ``source``, ``turn``, ``local`` and ``day``."""

    def waiting_card(self, view, words):
        problem = view["problem"]
        if problem == "refused":
            return draw.card(self.ctx, self.source.short, ("KEY REFUSED", "BAD KEY"), ("CHECK THE KEY", "CHECK IT"), middle_colour=draw.RED, icon=self.icon)
        if problem == "plan":
            return draw.card(self.ctx, self.source.short, ("NOT IN PLAN", "NO PLAN"), ("NEEDS PREMIUM", ""), middle_colour=draw.RED, icon=self.icon)
        if problem in ("offline", "limit", "missing"):
            return draw.card(self.ctx, words, ("NO ANSWER YET", "NO ANSWER", "OFFLINE"), ("TRYING AGAIN", "RETRYING"), icon=self.icon)
        return draw.card(self.ctx, words, ("GETTING DATES", "LOADING"), "", icon=self.icon)

    def mine(self, rows):
        """The id of the row (a driver) whose code, name or id is the one named to pick out, or None."""
        want = plain(self.highlight)
        if not want:
            return None
        return next((r["id"] for r in rows if want in (plain(r.get("code", "")), plain(r.get("name", "")), plain(r.get("id", "")))), None)

    def named(self, *names):
        """Whether the player named to pick out is one of ``names`` (or in one: a surname in a full name)."""
        want = plain(self.highlight)
        return bool(want) and any(f" {want} " in f" {plain(n)} " for n in names if n)

    # -- Formula 1 --------------------------------------------------------------------------------------------
    def f1(self, view, now, t):
        words = ("FORMULA 1", "F1")
        if view["team"] is None or not view["at"].get("matches"):
            return self.waiting_card(view, words)
        races = view["matches"]
        upcoming = next((r for r in races if r["state"] != "finished" and t < r["kickoff"] + RACE_HOURS), None)
        last = next((r for r in reversed(races) if r["state"] == "finished" and r.get("podium")), None)
        pending = next((r for r in reversed(races) if r["state"] != "finished" and r["kickoff"] + RACE_HOURS <= t < r["kickoff"] + PENDING_DAYS * 86400), None)
        views = []
        if "result" in self.show and pending:
            views.append(("pending", pending))
        elif "result" in self.show and last:
            views.append(("podium", last))
        if "next" in self.show:
            views.append(("race", upcoming))
        if "table" in self.show and view["table"]:
            views.append(("standings", None))
        if not views:
            return draw.card(self.ctx, words, ("NO RACES YET", "NOTHING YET"), "", icon=self.icon)
        kind, race = self.turn(views, now, VIEW_SECONDS)
        if kind == "standings":
            return draw.table(self.ctx, view["table"], self.mine(view["table"]), band=draw.HIGHLIGHT)
        if kind == "podium":
            return draw.podium(self.ctx, race["words"], race["podium"], self.mine(race["podium"]), icon=self.icon)
        if kind == "pending":
            return draw.card(self.ctx, race["words"], ("RESULT TO COME", "RESULT SOON", "NO RESULT", "RESULT"), ("NO LIVE TIMING", "NOT YET"), middle_colour=draw.AMBER, icon=self.icon)
        if race is None:                                          # the season is over, and next season's dates aren't out
            season = max((r.get("season") or 0 for r in races), default=0)
            return draw.card(self.ctx, words[:1], ("SEASON OVER", "F1 OVER"), (f"{season + 1} DATES TO COME", "DATES TO COME") if season else "",
                             icon=self.icon)
        return self.race(race, now, t)

    def race(self, race, now, t):
        day = self.day(race["kickoff"], now)
        day = (day,) if isinstance(day, str) else day
        if race["timed"]:
            clock = self.local(race["kickoff"], now).strftime("%H:%M")
            top = tuple(f"{d} {clock}" for d in day) + day
        else:
            top = day
        if t >= race["kickoff"]:
            return draw.card(self.ctx, top, race["words"], ("UNDER WAY, NO LIVE TIMING", "UNDER WAY", "ON NOW"), bottom_colour=draw.GREY, icon=self.icon)
        bottom = countdown(race["kickoff"] - t)
        if race.get("sprint") and race["kickoff"] - t >= 2 * 86400:
            bottom = (f"{bottom[0]}, SPRINT", *bottom)
        return draw.card(self.ctx, top, race["words"], bottom, bottom_colour=draw.AMBER, icon=self.icon)

    # -- tennis and golf ----------------------------------------------------------------------------------------
    def tours(self, view, now, t):
        words = TOURS[self.tour]["words"]
        if view["team"] is None or not view["at"].get("matches"):
            return self.waiting_card(view, words)
        events = view["matches"]
        current = next((e for e in events if e["state"] == "scheduled" and e["kickoff"] <= t <= e["end"]), None)
        upcoming = current or next((e for e in events if e["state"] in ("scheduled", "postponed") and e["kickoff"] > t), None)
        last = next((e for e in reversed(events) if e["state"] == "finished" and e["kickoff"] <= t and t - e["end"] < RESULT_DAYS * 86400), None)
        views = []
        if "result" in self.show and last:
            views.append(("result", last))
        if "next" in self.show and upcoming:
            views.append(("next", upcoming))
        if not views:
            return draw.card(self.ctx, words, ("NO TOURNAMENTS", "NOTHING YET"), ("ON THESPORTSDB YET", ""), icon=self.icon)
        kind, event = self.turn(views, now, VIEW_SECONDS)
        if kind == "result":
            return self.winner(event, words)
        return self.tournament(event, now, t, words, event is current)

    def tournament(self, event, now, t, words, on_now):
        name = fewer_words(event["name"])
        day = self.day(event["kickoff"], now)
        day = (day,) if isinstance(day, str) else day
        stage = event.get("stage") or ""
        if event["state"] == "postponed":
            return draw.card(self.ctx, words, name, ("POSTPONED", "OFF"), bottom_colour=draw.RED, icon=self.icon)
        if len(event.get("players") or []) == 2 and self.named(*event["players"]):
            a, b = event["players"]
            picked, other = (a, b) if self.named(a) else (b, a)
            when = tuple(f"{stage} {d}".strip() for d in day) + day
            versus = other.split()[-1]
            return draw.card(self.ctx, name, (f">{picked}", f">{picked.split()[-1]}"),
                             (*(f"v {versus}, {w}" for w in when), *when, f"v {versus}"),   # (the date before the opponent)
                             middle_colour=draw.HIGHLIGHT, bottom_colour=draw.AMBER, icon=self.icon)
        if on_now and self.sport == "golf":
            ends = self.day(event["end"], now)
            ends = ends[0] if isinstance(ends, tuple) else ends
            bottom = (f"ON NOW, ENDS {ends}", "ON NOW")
        elif on_now:
            bottom = (f"{stage} TODAY".strip(), "TODAY")
        elif self.sport == "golf":
            bottom = tuple(f"STARTS {d}" for d in day) + day
        else:
            bottom = tuple(f"{stage} {d}".strip() for d in day) + day
        return draw.card(self.ctx, words, name, bottom, bottom_colour=draw.AMBER, icon=self.icon)

    def winner(self, event, words):
        name = fewer_words(event["name"])
        who = event.get("winner") or ""
        if not who:
            if event.get("line"):                                # a result in words we couldn't read a winner from
                return draw.card(self.ctx, name, ("RESULT", ), event["line"], middle_colour=draw.GREEN, icon=self.icon)
            return draw.card(self.ctx, name, ("NO RESULT YET", "NO RESULT"), ("NOT ON THESPORTSDB YET", "NOT IN YET"), icon=self.icon)
        surname = who.split()[-1]
        picked = self.named(who)
        middle = (f">{who}", f">{surname}") if picked else (who, surname)
        line = event.get("line") or ""
        rest = line[len(who):].strip() if line.upper().startswith(who) else ""
        found = re.match(r"(?:BEAT|BEATS|DEF\.?|DEFEATED|DEFEATS)\s+(.+?)\s*((?:\d[\d()\-]*\s*)*)$", rest)
        bottom, lost = ("WINNER",), False
        if found:
            others = [p for p in event.get("players") or [] if p and not self.same(p, who)]
            beaten = (found[1] or (others[0] if others else "")).split()[-1]  # the beaten player's surname: the result line's,
            others = [p for p in others if self.same(p, found[1])] or [found[1]]  # (the player list only where it has none)
            score = found[2].strip()
            lost = not picked and (self.named(beaten) or any(self.named(p) for p in others))
            name_ = f">{beaten}" if lost else beaten         # (the one picked out was beaten: marked, not by colour alone)
            bottom = tuple(dict.fromkeys(w for w in (f"BEAT {name_} {score}".strip(), f"v {name_} {score}".strip(), f"BEAT {name_}", name_ if lost else "WINNER") if w))
        return draw.card(self.ctx, name, middle, bottom, middle_colour=draw.HIGHLIGHT if picked else draw.GREEN,
                         bottom_colour=draw.GREY, icon=self.icon, mark=draw.HIGHLIGHT)

    @staticmethod
    def same(player, who):
        """Whether ``player`` (from the event) is ``who`` (from the result line): the same surname."""
        return plain(player).split()[-1:] == plain(who).split()[-1:]
