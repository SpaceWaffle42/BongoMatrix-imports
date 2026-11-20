"""This module's pictures.

Each one is an Animator project: the same small text file the dashboard's Animator opens and saves.
They are in the ``art`` folder, and the module draws straight from them, so there are no exported
images to keep in step. To change a picture: Animator > More > "Open a drawing file...", choose the
file from ``art``, change it, download the project file back over the old one, and import the module again.

Pure magenta (#FF00FF) in a picture stands for "a colour the module chooses": see ``tinted``.
"""
from pathlib import Path

from bongo import sprites          # the Matrix's own reader of Animator projects

FOLDER = Path(__file__).parent / "art"      # a module may read its own folder; it can't write there
MAGENTA = (255, 0, 255, 255)


def load(name: str) -> list:
    """The frames of ``art/<name>.json``, as RGBA pictures (see-through where nothing is drawn)."""
    read = getattr(sprites, "read", None) or sprites._read     # (``read`` came with a later Matrix)
    return list(read(FOLDER / f"{name}.json").frames)


def tinted(picture, colour):
    """A copy of ``picture`` with every pure-magenta LED turned ``colour`` (r, g, b)."""
    out = picture.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            if px[x, y] == MAGENTA:
                px[x, y] = (*colour[:3], 255)
    return out
