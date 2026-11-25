"""Talking to Steam's Web API (https://steamcommunity.com/dev): one call at a time, with a short timeout, so the
background task never waits long. Every way a call can go wrong becomes a ``Trouble`` with a plain reason; the
API key is in the address of every call, so neither an address nor anything Steam sends back is ever put in one."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.steampowered.com"
STORE = "https://store.steampowered.com"
WAIT = 3.0                   # s: a tick has 5 in all, and does one call
MOST_JSON = 4 << 20          # a friend list of 2,000 is under 200 kB; anything this big is not an answer
MOST_PICTURE = 2 << 20
AGENT = "BongoMatrix-Steam/1.0"


class Trouble(Exception):
    """A call that didn't work. ``kind`` says what to do about it:
    "key" (Steam refused the key), "private" (that part of the profile isn't public), "missing" (no such thing,
    or no stats for that game), "busy" (Steam asked us to slow down), "network" (couldn't reach Steam), "steam"
    (Steam answered, but not properly)."""

    def __init__(self, kind: str, why: str = ""):
        super().__init__(why or kind)
        self.kind = kind


def _open(url: str, most: int, wait: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(request, timeout=wait) as answer:
            data = answer.read(most + 1)
    except urllib.error.HTTPError as error:
        try:
            body = error.read(4096)
        except OSError:
            body = b""
        finally:
            error.close()
        raise _refused(error.code, body) from None
    except (urllib.error.URLError, OSError, ValueError) as error:   # no network, a timeout, a dropped connection
        raise Trouble("network", type(error).__name__) from None
    if len(data) > most:
        raise Trouble("steam", "the answer was far too big")
    return data


def _refused(code: int, body: bytes) -> Trouble:
    if code == 429:
        return Trouble("busy", "429")
    text = body.decode("utf-8", "replace")
    if "not public" in text.lower() or code == 401:           # a private friend list is a 401; private stats say so
        return Trouble("private", str(code))
    if code == 403:
        return Trouble("key", "403")
    if code in (400, 404):                                    # a game with no achievements, a picture that isn't there
        return Trouble("missing", str(code))
    return Trouble("steam", str(code))


def get_json(path: str, params: dict, key: str, wait: float = WAIT) -> dict:
    """``path`` of the Web API (``ISteamUser/GetPlayerSummaries/v2``) with ``params`` and the key."""
    query = urllib.parse.urlencode({"key": key, "format": "json", **params})
    return _decoded(_open(f"{API}/{path}/?{query}", MOST_JSON, wait))


def store_json(path: str, params: dict, wait: float = WAIT) -> dict:
    """The store's own little API (no key): only for where a game's picture is."""
    return _decoded(_open(f"{STORE}/{path}?{urllib.parse.urlencode(params)}", MOST_JSON, wait))


def get_bytes(url: str, wait: float = WAIT) -> bytes:
    """A picture from Steam's CDN."""
    return _open(url, MOST_PICTURE, wait)


def _decoded(data: bytes) -> dict:
    try:
        out = json.loads(data)
    except ValueError:
        raise Trouble("steam", "not JSON") from None
    if not isinstance(out, dict):
        raise Trouble("steam", "not an object")
    return out


# -- the profile a person types ----------------------------------------------------------------------------
STEAMID = re.compile(r"7656119\d{10}\Z")
VANITY = re.compile(r"[A-Za-z0-9_-]{2,32}\Z")
LINK = re.compile(r"(?:https?://)?(?:www\.)?steamcommunity\.com/(profiles|id)/([^/?#\s]+)/?(?:[?#].*)?\Z", re.I)


def profile(typed: str) -> tuple[str, str]:
    """What was typed into "Your Steam profile": ("id", a SteamID64) or ("vanity", the name in a custom profile
    link, which Steam has to look up). Raises ValueError, in words for the card, if it is neither."""
    text = (typed or "").strip()
    if STEAMID.match(text):
        return "id", text
    link = LINK.match(text)
    if link:
        kind, value = link.group(1).lower(), urllib.parse.unquote(link.group(2))
        if kind == "profiles" and STEAMID.match(value):
            return "id", value
        if kind == "id" and VANITY.match(value):
            return "vanity", value
    elif VANITY.match(text) and not text.isdigit():
        return "vanity", text                                 # just the custom name, as in steamcommunity.com/id/<name>
    raise ValueError("That isn't a Steam profile link or SteamID64")
