"""This module's pictures: a small icon for each sport and the Games tracker's torch, sun and snowflake.

Each one is an Animator project, the same small text file the dashboard's Animator opens and saves. They are in
the ``art`` folder and the module draws straight from them, so there are no exported images to keep in step. To
change one: Animator > More > "Open a drawing file...", choose the file from ``art``, change it, download the
project file back over the old one, and import the module again.

No club badge, league logo, Olympic rings, Paralympic Agitos or Games emblem is drawn, here or anywhere else in
this module: those belong to others.
"""
from pathlib import Path

FOLDER = Path(__file__).parent / "art"      # a module may read its own folder; it can't write there
_kept = {}


def frames(name):
    """The frames of ``art/<name>.json`` as RGBA pictures, read once. A picture that can't be read is simply
    not drawn (an empty list): the words still are."""
    if name not in _kept:
        try:
            from bongo import sprites      # the Matrix's own reader of Animator projects
            read = getattr(sprites, "read", None) or sprites._read      # (``read`` came with a later Matrix)
            _kept[name] = list(read(FOLDER / f"{name}.json").frames)
        except Exception:                   # (an older Matrix, or a damaged file)
            _kept[name] = []
    return _kept[name]


def icon_named(name):
    """The first frame of ``art/<name>.json``, or None."""
    pictures = frames(name) if name else []
    return pictures[0] if pictures else None


def icon(sport):
    """The 7x7 icon of a sport (a key of sports.SPORTS), or None."""
    return icon_named(f"icon_{sport}") if sport else None


def at(name, seconds):
    """The frame of an animated picture showing ``seconds`` in (each frame 0.18 s), or None."""
    pictures = frames(name)
    return pictures[int(seconds / 0.18) % len(pictures)] if pictures else None
