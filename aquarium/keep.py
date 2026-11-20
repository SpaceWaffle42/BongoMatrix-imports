"""What the tank remembers between restarts: which fish live in each look, and when food last dropped in by itself.

It is one small file, ``tank.json``, in the module's working folder (the only place a module may write).
It is written only when something changes (a fish added or removed, food dropped in), never every frame,
and a missing or damaged file just means starting again from the settings.
"""
import json
import os

FILE = "tank.json"


def load() -> dict:
    try:
        with open(FILE, encoding="utf-8") as f:
            kept = json.load(f)
        return kept if isinstance(kept, dict) else {}
    except (OSError, ValueError, RecursionError):
        return {}


def look(name: str) -> dict:
    """What is kept for one tank: {"kinds": [the kind of each fish], "count": the ``fish``
    setting it last went by, "fed": the feeding time last dealt with, "dropped": when food last dropped in}."""
    section = load().get(name)
    return section if isinstance(section, dict) else {}


def save(name: str, **values) -> None:
    kept = load()
    section = kept.get(name) if isinstance(kept.get(name), dict) else {}
    kept[name] = {**section, **values}
    try:
        with open(FILE + ".new", "w", encoding="utf-8") as f:
            json.dump(kept, f)
        os.replace(FILE + ".new", FILE)        # swapped in whole: a power cut can't leave half a file
    except OSError:
        pass                                   # nowhere to write: the tank just starts afresh next time
