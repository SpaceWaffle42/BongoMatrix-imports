"""Word of the Day for Bongo Matrix: a new word each day, with what it means.

The words live in ``words.json`` beside this file, so this is the module to read if yours ships its
own data. Add to that file (or swap it for your own list) and the module picks them up: each entry is
{"word": ..., "kind": "noun", "meaning": ...}. Keep to plain letters: the panel's small fonts have no
accents worth reading.

Also shows two ways of fitting words of any length on a small panel: picking the biggest font that
fits, and scrolling what doesn't.
"""
from bongo.module import Module

from .styles import Card, Pages

__version__ = "1.0.0"

MODULE = Module(
    id="word_of_the_day",
    name="Word of the Day",
    description="A new word every day, with what it means.",
    styles={"card": Card, "pages": Pages},
    defaults={"colour": "#FFD166", "speed": 20},        # speed: how fast the meaning scrolls, in LEDs a second
    limits={"speed": (6, 60)},
    basic=("colour",),
)
