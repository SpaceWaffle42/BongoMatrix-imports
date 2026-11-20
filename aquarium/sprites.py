"""The fish, ready to draw: each kind's pictures facing both ways.

The pictures themselves are Animator projects in the ``art`` folder (see ``art.py``): two frames each
(the tail in two positions), drawn facing right. To add a fish, draw one in the Animator and put its
project file in ``art``: a name starting ``reef_`` joins the Reef, ``deep_`` the Deep.

A fish can have a second picture for when it is startled (the puffer puffs up): a project of the same
name in ``art/scared``. It may be a different size. Without one, the fish just looks as it always does.

A Deep fish can carry light: magenta in it is the ``glow`` colour, and a layer called Glow that adds light
is added onto the water round it (the angler's lure, the jellyfish's bell).
"""
from PIL import ImageOps

from . import art


class Sprite:
    def __init__(self, frames: list, scared: "Sprite | None" = None, light: "list | None" = None):
        self.frames = {1: frames, -1: [ImageOps.mirror(f) for f in frames]}     # by direction
        self.light = light and {1: light, -1: [ImageOps.mirror(f) for f in light]}   # light it adds round it, or None
        self.width, self.height = frames[0].size
        self.scared = scared

    def draw(self, img, x, y, direction, frame, scared=False):
        if scared and self.scared:              # drawn about the same middle, whatever its size
            other = self.scared
            return other.draw(img, x + (self.width - other.width) // 2, y + (self.height - other.height) // 2, direction, frame)
        pictures = self.frames[direction]
        picture = pictures[frame % len(pictures)]
        img.paste(picture, (x, y), picture)     # the picture is its own mask: clear LEDs stay clear
        if self.light:
            lights = self.light[direction]
            art.add(img, lights[frame % len(lights)], (x, y))


def _sprite(name, glow, scared=None):
    clip = art.clip(name)
    frames = [art.tinted(f, glow, loose=clip.flat) for f in clip.solid] if glow and clip.magenta else clip.solid
    light = None
    if clip.light or clip.glow:
        light = []
        for k in range(len(frames)):
            parts = ([clip.light[k]] if clip.light else []) + ([art.glowing(clip.glow[k], glow or (255, 0, 255))] if clip.glow else [])
            light.append(parts[0] if len(parts) == 1 else art.ImageChops.add(*parts))
    return Sprite(frames, scared, light)


def load(prefix: str, glow=None) -> dict:
    """Every fish whose file name starts with ``prefix``: {name: Sprite}, in name order. ``glow``: the colour
    that takes the place of magenta (the Deep look's light)."""
    out = {}
    for path in sorted(art.FOLDER.glob(f"{prefix}*.json")):
        other = art.FOLDER / "scared" / path.name
        scared = _sprite(f"scared/{path.stem}", glow) if other.is_file() else None
        out[path.stem] = _sprite(path.stem, glow, scared)
    return out
