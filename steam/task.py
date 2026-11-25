"""The background task: asks Steam what's going on, a little at a time, and shares it with the screens.

A tick has 5 seconds, so each does at most one call to Steam (3 seconds at most), whichever is due first:
look up a custom profile link, the friend list (every half hour), who's on and what they're playing (every
minute), the games of the last two weeks (every 10 minutes), the newest achievement (every 15 minutes, one game
a tick), and pictures (one a tick, each fetched once). That is about 2,000 calls a day, against the free key's
100,000. When Steam asks us to slow down, or can't be reached, it rests and tries again later, longer each time."""
from __future__ import annotations

import time

from bongo.module import Background

from . import api, pictures, seen
from .seen import SEEN
from .words import ago, pop_up_seconds
from .words import pop_up_words as words_for

EVERY = {"friend_list": 1800, "summaries": 60, "recent": 600, "achievements": 900, "percent": 86400}
REST = {"busy": (300, 3600), "network": (60, 600), "steam": (60, 600), "key": (600, 600)}   # first rest, longest
CHUNK = 100                     # players GetPlayerSummaries takes at once
ACHIEVEMENT_GAMES = 4           # recent games looked at for the newest achievement
POP_UP_GAP = 6                  # s between pop-ups (the Matrix allows one every 5)
POP_UP_MOST = 9                 # in ten minutes (the Matrix allows 10)
WAITING = 3                     # pop-ups kept waiting at most: a whole party starting at once isn't 20 messages

PRIVATE = {"profile": "Your Steam profile is private: set it to Public in Steam",
           "friends": "Your friends list is private: set it to Public in Steam",
           "games": "Your profile's game details are private (Steam › Privacy settings)"}


class Watch(Background):
    every = 5

    def start(self):
        seen.load()
        self.fresh()

    def fresh(self):
        """From the beginning: at the start, and after the key or the profile changes."""
        self.due: dict[str, float] = {}
        self.rest_until, self.rests = 0.0, 0
        self.round: list[dict] = []           # players gathered so far in this round of summaries
        self.chunk = 0
        self.first_round = True               # no pop-ups for whoever is in a game when we first look
        self.games_to_ask: list[int] = []     # recent games still to ask about achievements, this round
        self.newest: dict | None = None
        self.missing: dict[str, float] = {}   # pictures Steam didn't have, and when we asked
        self.tries: dict[str, list[str]] = {}
        self.waiting: list[dict] = []
        self.popped: list[float] = []
        self.asked = (self.settings.get("api_key", ""), self.settings.get("profile", ""))
        if SEEN.get("typed") != self.asked[1]:
            seen.forget()
            SEEN["typed"] = self.asked[1]

    def settings_changed(self):
        if (self.settings.get("api_key", ""), self.settings.get("profile", "")) != self.asked:
            self.fresh()
            seen.save()
        elif not self.settings.get("pop_up"):
            self.waiting.clear()

    # -- each tick ---------------------------------------------------------------------------------------
    def tick(self, now):
        t = time.time()
        if self.ready(t):
            job = self.next_job(t)
            if job is not None:
                try:
                    job(t)
                except api.Trouble as trouble:
                    self.trouble(trouble, t)
                else:
                    self.rests = 0
                    if (SEEN["problem"] or {}).get("kind") in REST:
                        SEEN["problem"] = None
                seen.save()
            self.pop_up_next(t)
        self.report(*self.status(t))

    def ready(self, t) -> bool:
        """Whether there's a key and a profile to ask about, and we aren't resting."""
        key, typed = self.settings.get("api_key", ""), self.settings.get("profile", "")
        if not key:
            return self.stuck("no_key")
        if not typed.strip():
            return self.stuck("no_profile")
        try:
            api.profile(typed)
        except ValueError:
            return self.stuck("bad_profile")
        if SEEN["problem"] and SEEN["problem"]["kind"] in ("no_key", "no_profile", "bad_profile"):
            SEEN["problem"] = None
        return t >= self.rest_until

    def stuck(self, kind) -> bool:
        if (SEEN["problem"] or {}).get("kind") != kind:
            SEEN["problem"] = {"kind": kind}
            seen.save()
        return False

    def next_job(self, t):
        if SEEN["steamid"] is None:
            return None if t < self.due.get("resolve", 0) else self.resolve
        for name in ("friend_list", "summaries", "recent", "achievements", "percent"):
            if name == "percent" and not SEEN["achievement"]:
                continue
            if t >= self.due.get(name, 0):
                return getattr(self, name)
        return self.picture if self.wanted_picture(t) else None

    def later(self, name, t, seconds=None):
        self.due[name] = t + (EVERY[name] if seconds is None else seconds)

    def trouble(self, trouble: api.Trouble, t):
        """A call that didn't work: rest a while (longer each time) and say why, plainly."""
        if trouble.kind in REST:
            first, most = REST[trouble.kind]
            self.rest_until = t + min(most, first * 2 ** self.rests)
            self.rests += 1
            SEEN["problem"] = {"kind": trouble.kind, "until": self.rest_until}
        elif trouble.kind == "private":     # (said where it was asked: see each job)
            pass
        else:                               # "missing" where nothing could be missing: Steam's odd answer
            self.rest_until = t + 60
            SEEN["problem"] = {"kind": "steam", "until": self.rest_until}

    # -- the jobs ----------------------------------------------------------------------------------------
    def key(self) -> str:
        return self.settings["api_key"].strip()

    def resolve(self, t):
        kind, value = api.profile(self.settings["profile"])
        if kind == "id":
            SEEN["steamid"] = value
            return
        found = api.get_json("ISteamUser/ResolveVanityURL/v1", {"vanityurl": value}, self.key()).get("response") or {}
        if found.get("success") == 1 and api.STEAMID.match(str(found.get("steamid", ""))):
            SEEN["steamid"] = str(found["steamid"])
            if SEEN["problem"] and SEEN["problem"]["kind"] == "no_such_profile":
                SEEN["problem"] = None
        else:
            SEEN["problem"] = {"kind": "no_such_profile", "name": value[:32]}
            self.later("resolve", t, 600)

    def friend_list(self, t):
        self.later("friend_list", t)
        try:
            answer = api.get_json("ISteamUser/GetFriendList/v1", {"steamid": SEEN["steamid"], "relationship": "friend"}, self.key())
        except api.Trouble as trouble:
            if trouble.kind != "private":
                raise
            self.private("friends", True)
            SEEN["friend_ids"] = []
            return
        self.private("friends", False)
        friends = (answer.get("friendslist") or {}).get("friends") or []
        SEEN["friend_ids"] = [str(f["steamid"]) for f in friends if api.STEAMID.match(str(f.get("steamid", "")))][:2000]
        SEEN["friends"] = {k: v for k, v in SEEN["friends"].items() if k in SEEN["friend_ids"]}

    def summaries(self, t):
        everyone = [SEEN["steamid"], *SEEN["friend_ids"]]
        part = everyone[self.chunk * CHUNK:(self.chunk + 1) * CHUNK]
        answer = api.get_json("ISteamUser/GetPlayerSummaries/v2", {"steamids": ",".join(part)}, self.key())
        self.round += [p for p in (answer.get("response") or {}).get("players") or [] if isinstance(p, dict)]
        self.chunk += 1
        if self.chunk * CHUNK < len(everyone):
            return                                     # the rest next tick
        self.chunk, players, self.round = 0, self.round, []
        self.later("summaries", t)
        mine = next((p for p in players if str(p.get("steamid")) == SEEN["steamid"]), None)
        if mine is None:                               # a SteamID64 nobody has
            SEEN["problem"] = {"kind": "no_such_profile", "name": SEEN["steamid"]}
            return
        if (SEEN["problem"] or {}).get("kind") in ("no_such_profile", "key"):
            SEEN["problem"] = None
        self.private("profile", mine.get("communityvisibilitystate") != 3)
        before = SEEN["friends"]
        SEEN["me"] = seen.person(mine)
        SEEN["friends"] = {p["steamid"]: p for p in (seen.person(s) for s in players if str(s.get("steamid")) != SEEN["steamid"])}
        seen.note_games([SEEN["me"], *SEEN["friends"].values()], self.first_round, t)
        if not self.first_round:
            self.started_games(before)
        self.first_round = False
        SEEN["checked"] = t

    def recent(self, t):
        self.later("recent", t)
        answer = api.get_json("IPlayerService/GetRecentlyPlayedGames/v1", {"steamid": SEEN["steamid"], "count": 0}, self.key())
        response = answer.get("response") or {}
        if "total_count" not in response:              # Steam says nothing at all when game details are private
            self.private("games", True)
            SEEN["recent"] = []
            return
        self.private("games", False)
        games = [g for g in response.get("games") or [] if isinstance(g, dict) and g.get("appid")]
        games.sort(key=lambda g: -int(g.get("playtime_2weeks") or 0))
        SEEN["recent"] = [{"appid": int(g["appid"]), "name": str(g.get("name") or "?")[:128],
                           "minutes": int(g.get("playtime_2weeks") or 0), "icon": str(g.get("img_icon_url") or "")[:64]}
                          for g in games[:8]]

    def achievements(self, t):
        """One recent game a tick; when they've all been asked, the newest of their achievements is kept."""
        if not self.games_to_ask:
            self.games_to_ask = [g["appid"] for g in SEEN["recent"][:ACHIEVEMENT_GAMES]]
            self.newest = None
            if not self.games_to_ask:
                self.later("achievements", t)
                return
        appid = self.games_to_ask.pop(0)
        try:
            answer = api.get_json("ISteamUserStats/GetPlayerAchievements/v1",
                                  {"steamid": SEEN["steamid"], "appid": appid, "l": "english"}, self.key())
        except api.Trouble as trouble:
            if trouble.kind == "private":
                self.private("games", True)
                self.games_to_ask = []
                self.later("achievements", t)
                return
            if trouble.kind != "missing":              # (a game with no achievements: on to the next)
                self.games_to_ask.insert(0, appid)
                raise
            answer = {}
        stats = answer.get("playerstats") or {}
        for a in stats.get("achievements") or []:
            when = int(a.get("unlocktime") or 0)
            if a.get("achieved") and when and (self.newest is None or when > self.newest["when"]):
                self.newest = {"appid": appid, "game": str(stats.get("gameName") or self.game_name(appid))[:128],
                               "apiname": str(a.get("apiname", ""))[:128], "name": str(a.get("name") or a.get("apiname") or "?")[:128],
                               "when": when}
        if self.games_to_ask:
            return
        self.later("achievements", t)
        old = SEEN["achievement"] or {}
        if self.newest and (old.get("appid"), old.get("apiname")) != (self.newest["appid"], self.newest["apiname"]):
            SEEN["achievement"] = {**self.newest, "percent": None, "icon": ""}
            self.due["percent"] = 0                    # its rarity, and its icon, next
            self.due["schema"] = 0

    def percent(self, t):
        a = SEEN["achievement"]
        self.later("percent", t)
        answer = api.get_json("ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2", {"gameid": a["appid"]}, self.key())
        for one in (answer.get("achievementpercentages") or {}).get("achievements") or []:
            if one.get("name") == a["apiname"]:
                try:
                    a["percent"] = max(0.0, min(100.0, float(one.get("percent"))))
                except (TypeError, ValueError):
                    pass

    def schema(self, t):
        """Where the newest achievement's icon is: in the game's schema (asked once for each newest one)."""
        a = SEEN["achievement"]
        self.due["schema"] = float("inf")
        try:
            answer = api.get_json("ISteamUserStats/GetSchemaForGame/v2", {"appid": a["appid"], "l": "english"}, self.key())
        except api.Trouble as trouble:
            if trouble.kind == "missing":
                return
            self.due["schema"] = 0
            raise
        listed = ((answer.get("game") or {}).get("availableGameStats") or {}).get("achievements") or []
        one = next((x for x in listed if x.get("name") == a["apiname"]), None)
        a["icon"] = (pictures.on_cdn(one.get("icon", ""), a["appid"]) or "") if one else ""

    def game_name(self, appid) -> str:
        return next((g["name"] for g in SEEN["recent"] if g["appid"] == appid), "")

    def private(self, part: str, private: bool):
        parts = set(SEEN["private"])
        parts.add(part) if private else parts.discard(part)
        SEEN["private"] = sorted(parts)

    # -- pictures ----------------------------------------------------------------------------------------
    def wanted_picture(self, t) -> str | None:
        """The first picture a screen could use that we haven't got (and haven't been told is missing lately)."""
        if self.due.get("schema", float("inf")) <= t and SEEN["achievement"]:
            return "schema"
        for key, urls in want(SEEN):
            if not pictures.have(key) and pictures.missing_again(self.missing, key, t):
                self.tries.setdefault(key, list(urls))
                return key
        return None

    def picture(self, t):
        key = self.wanted_picture(t)
        if key == "schema":
            return self.schema(t)
        urls = self.tries[key]
        url = urls.pop(0)
        try:
            if url.startswith("store:"):               # where the store says its capsule is (newer games' have a hash in it)
                found = api.store_json("api/appdetails", {"appids": url[6:], "filters": "basic"})
                data = (found.get(url[6:]) or {}).get("data") or {}
                better = pictures.on_cdn(data.get("capsule_image") or data.get("header_image") or "")
                if better:
                    urls.insert(0, better)
            elif not pictures.keep(key, api.get_bytes(url)):
                raise api.Trouble("missing", "not a picture")
        except api.Trouble as trouble:
            if trouble.kind != "missing":
                urls.insert(0, url)
                raise
        if not pictures.have(key) and not urls:        # nowhere left to look: not again for a day
            self.missing[key] = t
            self.tries.pop(key, None)

    # -- pop-ups -----------------------------------------------------------------------------------------
    def started_games(self, before: dict):
        if not self.settings.get("pop_up"):
            return
        shown = {f["steamid"] for f in seen.friends_shown({**self.settings, "show_away": True})}
        for sid, now in SEEN["friends"].items():
            then = before.get(sid) or {}
            if sid in shown and now["state"] == seen.IN_GAME and (then.get("state") != seen.IN_GAME or
                                                                   (then.get("gameid") or then.get("game")) != (now["gameid"] or now["game"])):
                self.waiting.append(now)
        del self.waiting[:-WAITING]

    def pop_up_next(self, t):
        self.popped = [p for p in self.popped if t - p < 600]
        status = self.panel.status or {}
        if not self.settings.get("pop_up") or status.get("asleep") or len(self.popped) >= POP_UP_MOST:
            self.waiting.clear()                       # (never in the sleep hours, and none saved up for later)
            return
        if self.waiting and (not self.popped or t - self.popped[-1] >= POP_UP_GAP):
            self.pop_up(self.waiting.pop(0))
            self.popped.append(t)

    def pop_up(self, friend: dict):
        """A friend has just started a game: a short pop-up on the panel in the module's own look (popups.Started),
        with who and which game for it to draw. Its words are what the panel shows if the look ever fails, so they
        say it all on their own."""
        data = pop_up_data(friend)
        self.panel.message(pop_up_words(friend), title="Steam", seconds=pop_up_seconds(data["name"], data["game"] or "A GAME"),
                           look="started", data=data)

    # -- the status line ---------------------------------------------------------------------------------
    def status(self, t) -> tuple[str, bool]:
        problem = SEEN["problem"] or {}
        kind = problem.get("kind")
        if kind:
            return problem_words(problem, t), False
        for part in ("profile", "games", "friends"):
            if part in SEEN["private"]:
                return PRIVATE[part], False
        if not SEEN["me"]:
            return "Asking Steam…", True
        name = SEEN["me"]["name"][:24]
        online = sum(1 for f in SEEN["friends"].values() if f.get("state"))      # (in a game, online or away)
        line = f"Signed in as {name} · {online} friend{'' if online == 1 else 's'} online"
        return line + (f" · checked {ago(t - SEEN['checked'])}" if SEEN["checked"] else ""), True


def pop_up_words(friend: dict) -> str:
    return words_for(friend["name"], friend["game"])


def pop_up_data(friend: dict) -> dict:
    """What the pop-up's look draws: who, the game, and its appid for the game's picture (well inside the 2 KB a
    pop-up may be given)."""
    return {"name": friend["name"][:64], "game": friend["game"][:128], "appid": steam_app(friend.get("gameid"))}


def problem_words(problem: dict, t: float) -> str:
    kind = problem["kind"]
    wait = max(1, round((problem.get("until", t) - t) / 60))
    return {
        "no_key": "Add your Steam Web API key above (free from steamcommunity.com/dev/apikey)",
        "no_profile": "Type your Steam profile link or SteamID64 above",
        "bad_profile": "That isn't a Steam profile link or SteamID64",
        "no_such_profile": f"Steam has no profile called {problem.get('name', '')[:32]}",
        "key": "Steam didn't accept the API key: check it's typed right",
        "busy": f"Steam asked us to slow down: trying again in {wait} min",
        "network": f"Can't reach Steam just now: trying again in {wait} min",
        "steam": f"Steam isn't answering properly just now: trying again in {wait} min",
    }.get(kind, "Something went wrong talking to Steam")


def want(s: dict):
    """(key, where to fetch it) for each picture the screens could draw now: the games being played, the recent
    games' icons, the newest achievement's icon."""
    for p in seen.players({"show_away": True}, s):
        appid = steam_app(p.get("gameid"))
        if appid:
            yield f"capsule:{appid}", [*pictures.capsule_urls(appid), f"store:{appid}"]
    for g in s["recent"][:6]:
        url = pictures.icon_url(g["appid"], g.get("icon", ""))
        if url:
            yield f"icon:{g['appid']}", [url]
    a = s.get("achievement") or {}
    if a.get("icon"):
        yield f"achievement:{a['appid']}:{a['apiname']}", [a["icon"]]


def steam_app(gameid) -> int | None:
    """A Steam game's appid from a player's gameid (a game added to Steam from elsewhere has a huge one: no art)."""
    try:
        n = int(gameid)
    except (TypeError, ValueError):
        return None
    return n if 0 < n < 1 << 32 else None
