"""Fetching, in the background, politely: ``render`` never waits for the internet.

A screen calls ``feed_for(source, team)`` once and then ``feed.ask(key, wants, preview)`` every frame. Both
return at once. What is known is in ``feed.view``, a plain dict swapped whole when something arrives:

    {"problem": None | "refused" | "missing" | "plan" | "offline" | "limit",
     "team": {...} | None, "matches": [...], "table": [...],            (the shapes in sources.py)
     "at": {"team", "matches", "live", "table"},                        (when each was last fetched, by the clock)
     "ended": {match id: when it was first seen finished}}

Being polite to a service someone else pays for is the point of this file:
- one thread for the whole module, one request at a time, never closer together than the source's ``gap``
  (football-data.org's free plan allows 10 a minute: 7 seconds apart keeps under it);
- fixtures every 3 hours, every 30 minutes in the 3 hours before kick-off, and a match in play no faster
  than the source's ``live_every``; the table every 3 hours and once more after full time;
- after "too many requests" nothing is asked for as long as the service says (a minute if it doesn't);
  after any other failure the wait doubles, from 30 seconds up to 30 minutes;
- a key the service refused isn't tried again for 15 minutes (unless the key changes);
- team lists and lookups are kept for days in ``cache.json`` in the module's working folder, with the last
  fixtures and table, so a restart shows something at once and asks for little;
- a feed nobody has asked for 5 minutes is forgotten, and the thread stops when there are none.

The key is held in memory only. It is never written to the cache, and no message printed here carries an
address or a key: only the source's name and what kind of trouble it was.
"""
import datetime as dt
import json
import os
import threading
import time
import urllib.error
import urllib.request

from .sources import SOURCES, Trouble, playing

AGENT = "bongo-sports/1.0 (a Bongo Matrix module)"
KEEP = "cache.json"
IDLE_AFTER = 300.0          # s since any screen asked: the feed is forgotten
PREVIEW_SETTLE = 2.0        # s a preview must have been asking before anything is fetched for it (someone typing)
FIXTURES_EVERY = 3 * 3600.0
SOON = 3 * 3600.0           # this long before kick-off...
SOON_EVERY = 30 * 60.0      # ...fixtures are looked at this often (a postponement, a moved kick-off)
DUE_FOR = 4 * 3600.0        # after kick-off with no word of full time, a match is still looked at as if in play
TABLE_EVERY = 3 * 3600.0
AFTER_FULL_TIME = 5 * 60.0  # then the fixtures and the table once more, when the result has settled
REFUSED_REST = 15 * 60.0
MISSING_REST = 6 * 3600.0
MOST_BYTES = 2_000_000
MOST_LISTS = 60             # answers kept in the cache file (team lists, lookups)


def http(url, headers):
    """(status, headers, parsed JSON or None). The one place this module touches the network."""
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            status, got, raw = answer.status, dict(answer.headers), answer.read(MOST_BYTES + 1)
    except urllib.error.HTTPError as error:
        status, got = error.code, dict(error.headers or {})
        try:
            raw = error.read(MOST_BYTES + 1)
        except OSError:
            raw = b""
    if len(raw) > MOST_BYTES:
        return status, got, None
    try:
        return status, got, json.loads(raw)
    except ValueError:
        return status, got, None


HTTP = http                 # (the tests put a pretend one here)


class Feed:
    def __init__(self, book, source, team_text):
        self.book, self.source, self.team_text = book, source, team_text.strip()
        self.name = f"{source.id}|{self.team_text.lower()}"
        self.key = ""
        self.asked = time.monotonic()        # when a screen last asked
        self.since = None                    # when a screen that isn't a preview first asked, or a preview began asking
        self.on_panel = False                # a screen on the panel has asked (not only previews in the dashboard)
        self.wants = set()                   # "table", "live": what the screens asking show
        self.view = {"problem": None, "team": None, "matches": [], "table": [], "at": {}, "ended": {}}
        self.retry = 0.0                     # by the clock: nothing for this feed before then
        self.fails = 0
        self.failed_key = None               # the key in use when something last failed (a new one is tried at once)

    def ask(self, key, wants=(), preview=False):
        now = time.monotonic()
        if self.since is None or (preview and now - self.asked > PREVIEW_SETTLE):
            self.since = now if preview else now - PREVIEW_SETTLE
        elif not preview:
            self.since = min(self.since, now - PREVIEW_SETTLE)
        self.on_panel = self.on_panel or not preview
        self.asked, self.key = now, key or ""
        self.wants = set(wants)
        self.book.wake()
        return self.view

    # -- what is due --------------------------------------------------------------------------------------
    def live_match(self, now):
        """The match to watch closely: one in play, or one whose kick-off has passed with no word of full time."""
        for match in self.view["matches"]:
            if playing(match, now):
                return match
            if match["state"] == "scheduled" and match["timed"] and 0 <= now - match["kickoff"] < DUE_FOR:
                return match
        return None

    def job(self, now):
        """What to fetch next, or None: "team", "matches", "live" or "table"."""
        if self.failed_key is not None and self.failed_key != self.key:
            self.failed_key, self.retry, self.fails = None, 0.0, 0     # a new key: whatever was wrong may not be now
        if not self.key or not self.team_text or now < self.retry:
            return None
        at, view = self.view["at"], self.view
        if view["team"] is None:
            return "team"
        latest_end = max(view["ended"].values(), default=0)
        settle = latest_end and now - latest_end >= AFTER_FULL_TIME and at.get("matches", 0) < latest_end + AFTER_FULL_TIME
        soon = any(m["state"] == "scheduled" and 0 < m["kickoff"] - now <= SOON for m in view["matches"])
        if settle or now - at.get("matches", 0) >= (SOON_EVERY if soon else FIXTURES_EVERY):
            return "matches"
        if self.live_match(now) and now - max(at.get("live", 0), at.get("tried", 0)) >= self.source.live_every:
            return "live"
        if "table" in self.wants and self.source.has_table:
            settle = latest_end and now - latest_end >= AFTER_FULL_TIME and at.get("table", 0) < latest_end + AFTER_FULL_TIME
            if settle or now - at.get("table", 0) >= TABLE_EVERY:
                return "table"
        return None

    # -- doing it --------------------------------------------------------------------------------------------
    def do(self, job, now):
        get, source, view = self.book.getter(self), self.source, dict(self.view)
        at, ended = dict(view["at"]), dict(view["ended"])
        try:
            if job == "team":
                view["team"], at["team"] = source.find_team(get, self.team_text), now
            elif job == "matches":
                matches = source.fixtures(get, view["team"], dt.datetime.fromtimestamp(now, dt.timezone.utc).date())
                view["matches"], at["matches"], at["live"] = matches, now, now
            elif job == "live":
                at["tried"] = now                            # asked, whatever comes of it: not again before the source allows
                watched = self.live_match(now)
                fresh = source.live(get, view["team"], watched)
                if fresh:
                    old = next((m for m in view["matches"] if m["id"] == fresh["id"]), {})
                    if fresh["score"] is None and old.get("score"):   # a score that couldn't be read: the last one stays
                        fresh = {**fresh, "score": old["score"]}
                    view["matches"] = [fresh if m["id"] == fresh["id"] else m for m in view["matches"]]
                    at["live"] = now
                elif now - at.get("matches", 0) >= 600:      # it isn't listed: the fixtures say why (postponed?)
                    matches = source.fixtures(get, view["team"], dt.datetime.fromtimestamp(now, dt.timezone.utc).date())
                    view["matches"], at["matches"] = matches, now
            elif job == "table":
                view["table"], at["table"] = source.table(get, view["team"]), now
            for match in view["matches"]:
                if match["state"] == "finished" and match["id"] not in ended:
                    known = any(m["id"] == match["id"] for m in self.view["matches"])
                    ended[match["id"]] = now if known and now - match["kickoff"] < DUE_FOR * 2 else match["kickoff"] + 7200
            ended = {k: v for k, v in ended.items() if any(m["id"] == k for m in view["matches"])}
            view.update(problem=None, at=at, ended=ended)
            self.fails, self.retry = 0, 0.0
            self.view = view
            if job != "live":
                self.book.save()
        except Trouble as trouble:
            self.failed(job, trouble, now)
        except Exception as error:   # an answer of a shape nobody expected: keep what we have, try later
            print(f"sports: couldn't read {source.name}'s answer ({type(error).__name__})", flush=True)
            self.failed(job, Trouble("answer"), now)

    def failed(self, job, trouble, now):
        kind = trouble.kind
        self.fails += 1
        wait = min(1800.0, 30.0 * 2 ** min(self.fails - 1, 6))
        self.failed_key = self.key
        if kind == "refused":
            wait = REFUSED_REST
        elif kind == "limit":
            wait = max(60.0, trouble.wait)
        elif kind == "missing" and job == "team":
            wait = MISSING_REST
        elif kind == "plan":
            wait = MISSING_REST
        if kind == "missing" and job != "team":
            kind = "answer"
        self.retry = now + wait
        if kind == "answer":
            kind = "offline"
        if self.view["problem"] != kind:
            print(f"sports: {self.source.name}: {WORDS.get(kind, kind)} (trying again in {int(wait // 60) or 1} min)", flush=True)
        self.view = {**self.view, "problem": kind, "at": {**self.view["at"], **({"tried": now} if job == "live" else {})}}


WORDS = {"refused": "the key was refused", "missing": "no such team", "plan": "not in this key's plan",
         "limit": "asked too often", "offline": "no answer"}


class Book:
    """Every feed, the one thread that fetches for them, and what is kept between runs."""

    def __init__(self, folder="."):
        self.path = os.path.join(folder, KEEP)
        self.feeds = {}
        self.lists = {}                      # an address's answer, kept: {"source|path": {"at", "data"}}
        self.not_before = {}                 # source id -> monotonic time of its next request
        self.rest = {}                       # source id -> clock time until which it asked us to stop
        self.thread = None
        self.lock = threading.Lock()
        self.kept = {}
        self.clock = time.time
        self.load()

    def feed(self, source_id, team_text):
        source = SOURCES.get(source_id) or next(iter(SOURCES.values()))
        name = f"{source.id}|{team_text.strip().lower()}"
        with self.lock:
            feed = self.feeds.get(name)
            if feed is None:
                feed = self.feeds[name] = Feed(self, source, team_text)
                kept = self.kept.get(name)
                if kept:                     # from the last run: shown at once, refreshed when due
                    feed.view = {**feed.view, **kept}
            return feed

    def wake(self):
        if os.environ.get("BONGO_OFFLINE") == "1":
            return
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.run, name="sports-feed", daemon=True)
                self.thread.start()

    def run(self):
        while self.step():
            time.sleep(1.0)

    def step(self):
        """One look round: at most one fetching job. False when there is nothing left to look after."""
        mono, now = time.monotonic(), self.clock()
        with self.lock:
            for name in [n for n, f in self.feeds.items() if mono - f.asked > IDLE_AFTER]:
                del self.feeds[name]
            feeds = sorted(self.feeds.values(), key=lambda f: f.asked, reverse=True)
        if not feeds:
            return False
        for feed in feeds:
            if mono - feed.asked > (30 if feed.on_panel else 1.5) or feed.since is None or mono - feed.since < PREVIEW_SETTLE:
                continue                     # nobody is looking at it just now (or someone is still typing: a preview
                #                              that is no longer drawn was a name half typed)
            if now < self.rest.get(feed.source.id, 0):
                continue
            job = feed.job(now)
            if job:
                feed.do(job, now)
                break
        return True

    # -- one request ------------------------------------------------------------------------------------------
    def getter(self, feed):
        source, key = feed.source, feed.key

        def get(path, keep=0):
            name = f"{source.id}|{path}"
            now = self.clock()
            if keep and name in self.lists and 0 <= now - self.lists[name]["at"] < keep:
                return self.lists[name]["data"]
            wait = self.not_before.get(source.id, 0) - time.monotonic()
            if wait > 0:
                time.sleep(min(wait, source.gap))
            self.not_before[source.id] = time.monotonic() + source.gap
            try:
                status, headers, body = HTTP(source.base + path, source.headers(key))
            except (urllib.error.URLError, OSError, ValueError):
                raise Trouble("offline") from None
            if status != 200:
                trouble = source.trouble(status, body, headers)
                if trouble.kind == "limit":
                    self.rest[source.id] = now + max(60.0, trouble.wait)
                raise trouble
            if not isinstance(body, dict):
                raise Trouble("answer")
            if keep:
                self.lists[name] = {"at": now, "data": body}
                self.save()
            return body
        return get

    # -- between runs -----------------------------------------------------------------------------------------
    def save(self):
        with self.lock:
            feeds = {name: {k: f.view[k] for k in ("team", "matches", "table", "at", "ended")} for name, f in self.feeds.items() if f.view["team"]}
            kept = {**{n: v for n, v in self.kept.items() if n not in feeds}, **feeds}
            self.kept = dict(sorted(kept.items(), key=lambda kv: kv[1]["at"].get("matches", 0), reverse=True)[:12])
            lists = dict(sorted(self.lists.items(), key=lambda kv: kv[1]["at"], reverse=True)[:MOST_LISTS])
            self.lists = lists
            out = {"v": 1, "feeds": self.kept, "lists": lists}
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(out, f, separators=(",", ":"))
            os.replace(tmp, self.path)
        except OSError:
            pass                             # nowhere to write: there's just nothing to show after a restart

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                kept = json.load(f)
            if kept.get("v") != 1:
                return
            now = time.time()
            for name, view in kept.get("feeds", {}).items():
                if isinstance(view, dict) and isinstance(view.get("team"), dict) and isinstance(view.get("matches"), list) \
                        and isinstance(view.get("at"), dict) and now - float(view["at"].get("matches", 0)) < 30 * 86400:
                    self.kept[name] = {"team": view["team"], "matches": view["matches"], "table": view.get("table") or [],
                                       "at": {k: float(v) for k, v in view["at"].items() if isinstance(v, (int, float))},
                                       "ended": {str(k): float(v) for k, v in (view.get("ended") or {}).items() if isinstance(v, (int, float))}}
            for name, entry in kept.get("lists", {}).items():
                if isinstance(entry, dict) and isinstance(entry.get("data"), dict) and isinstance(entry.get("at"), (int, float)):
                    self.lists[name] = {"at": float(entry["at"]), "data": entry["data"]}
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            self.kept, self.lists = {}, {}   # no file, or a damaged one: start with nothing


BOOK = Book()


def feed_for(source_id, team_text):
    return BOOK.feed(source_id, team_text)
