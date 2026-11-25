"""What the module knows about each parcel, kept in a file in its working folder (the only place it may write), so
a restart neither forgets where parcels were nor starts following them again (which would use more of Ship24's
free parcels). The background task and the screens run in one process and share ``STATE``."""
from __future__ import annotations

import json
import os

FILE = "parcels.json"
STATE: dict = {}          # the background task fills it; the screens read it


def empty() -> dict:
    return {"month": None, "used": 0, "refused_until": None, "keys": {}, "parcels": {}, "queue": []}


def load(path: str = FILE) -> dict:
    """The kept state (an empty one if there's none, or it can't be read), now also ``STATE``."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("parcels"), dict):
            raise ValueError("not ours")
        state = {**empty(), **data}
    except (OSError, ValueError):
        state = empty()
    STATE.clear()
    STATE.update(state)
    return STATE


def save(state: dict, path: str = FILE) -> None:
    """Written whole, then swapped in, so a stop half-way never leaves half a file."""
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as f:
        json.dump(state, f, separators=(",", ":"))
    os.replace(part, path)


def shared() -> dict:
    """For a screen: what the background task knows, read from the file the first time (a screen can come on
    before the first tick, and a preview has no background task at all)."""
    return STATE if STATE else load()
