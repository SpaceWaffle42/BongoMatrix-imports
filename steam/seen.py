"""What the background task has found out, shared with the screens (they run in the same process: docs/MODULES.md)
and kept in a file in the module's working folder, so a restart starts from the last news rather than from nothing."""
from __future__ import annotations

import json
import os
import time

FILE = "steam.json"

IN_GAME, ONLINE, AWAY = "in_game", "online", "away"
STATES = {1: ONLINE, 2: ONLINE, 3: AWAY, 4: AWAY, 5: ONLINE, 6: ONLINE}   # Steam's personastate (0 is offline)


def empty() -> dict:
    return {
        "steamid": None,           # whose this is (the profile in the settings, looked up)
        "typed": None,             # ... as it was typed: another profile typed in starts afresh
        "me": None,                # {"steamid", "name", "state", "game", "gameid"}
        "friends": {},             # steamid -> the same, for every friend Steam told us about
        "friend_ids": [],
        "since": {},               # steamid -> [gameid, when we first saw them in it, or None if already in it]
        "recent": [],              # [{"appid", "name", "minutes", "icon"}], most played first
        "achievement": None,       # the newest: {"appid", "game", "apiname", "name", "when", "percent", "icon"}
        "private": [],             # the parts of the profile Steam won't show: "profile", "friends", "games"
        "problem": None,           # what stops everything: {"kind", "status"} (kinds as api.Trouble, and "setup")
        "checked": None,           # when the friends were last checked (time.time())
    }


SEEN = empty()
_loaded = False


def load() -> dict:
    """``SEEN``, read from the working folder the first time it is asked for in this process."""
    global _loaded
    if not _loaded:
        _loaded = True
        try:
            with open(FILE) as f:
                kept = json.load(f)
            if isinstance(kept, dict):
                SEEN.update({k: v for k, v in kept.items() if k in SEEN})
        except (OSError, ValueError):
            pass
    return SEEN


def save() -> None:
    try:
        with open(FILE + ".new", "w") as f:
            json.dump(SEEN, f)
        os.replace(FILE + ".new", FILE)
    except OSError as error:            # (its folder full: it carries on from memory)
        print(f"couldn't keep what it found: {error.strerror}")


def forget() -> None:
    """Another profile, or another key: nothing of the old one is shown."""
    SEEN.clear()
    SEEN.update(empty())


def person(summary: dict) -> dict:
    """One of GetPlayerSummaries' players as the screens want it."""
    game = summary.get("gameextrainfo") or ""
    gameid = str(summary.get("gameid") or "")
    state = STATES.get(summary.get("personastate"))
    if state and (game or gameid):
        state = IN_GAME
    return {"steamid": str(summary.get("steamid", "")), "name": str(summary.get("personaname") or "?")[:64],
            "state": state, "game": str(game)[:128], "gameid": gameid}


def names(settings: dict) -> set[str]:
    """"Only these friends", as names to match (any case); empty: everyone."""
    return {n.strip().casefold() for n in str(settings.get("only_friends") or "").split(",") if n.strip()}


def friends_shown(settings: dict, seen: dict | None = None) -> list[dict]:
    """The friends the friends screen shows: on Steam now (away ones only if asked for), only the ones listed if
    any are, in a game first, then online, then away, each lot in name order."""
    seen = SEEN if seen is None else seen
    only = names(settings)
    order = {IN_GAME: 0, ONLINE: 1, AWAY: 2}
    out = [f for f in seen["friends"].values()
           if f.get("state") in order and (f["state"] != AWAY or settings.get("show_away"))
           and (not only or f["name"].strip().casefold() in only)]
    return sorted(out, key=lambda f: (order[f["state"]], f["name"].casefold()))


def players(settings: dict, seen: dict | None = None) -> list[dict]:
    """Who the now playing screen shows: you first if you're in a game, then the friends shown who are."""
    seen = SEEN if seen is None else seen
    me = [seen["me"]] if seen.get("me") and seen["me"].get("state") == IN_GAME else []
    return me + [f for f in friends_shown(settings, seen) if f["state"] == IN_GAME]


def started(steamid: str, seen: dict | None = None) -> float | None:
    """When we first saw them in the game they're in (None: they were already in it when we first looked)."""
    seen = SEEN if seen is None else seen
    entry = seen["since"].get(steamid)
    return entry[1] if entry else None


def note_games(people: list[dict], first: bool, now: float | None = None) -> None:
    """Keep, for each person in a game, when they started it as far as we know."""
    now = time.time() if now is None else now
    for p in people:
        sid, game = p["steamid"], p["gameid"] or p["game"]
        if p["state"] != IN_GAME:
            SEEN["since"].pop(sid, None)
        elif SEEN["since"].get(sid, [None])[0] != game:
            SEEN["since"][sid] = [game, None if first else now]
