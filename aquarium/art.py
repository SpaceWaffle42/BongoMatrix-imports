"""This module's pictures.

Each one is an Animator project: the same small text file the dashboard's Animator opens and saves.
They are in the ``art`` folder (the fish) and ``art/scenery`` (the water, sand, rocks, weed and bubbles),
and the module draws straight from them, so there are no exported images to keep in step. To change a
picture: Animator > More > "Open a drawing file...", choose the file, change it, download the project file
back over the old one, and import the module again.

Two kinds of colour mean "a colour the module chooses":
- Pure magenta (#FF00FF), and darker shades of it (#800080, #400040: red and blue the same, no green), is the
  Deep look's ``glow`` colour at that strength (see ``tinted``).
- A layer called **Glow** that adds light (Layers > mode "Adds light") is light in the ``glow`` colour: drawn
  in shades of magenta, added onto whatever is under it. Other layers that add light (sunbeams, the plume
  from a vent) are added as light too, in their own colours. So a glow brightens the water round it rather
  than painting a dark square there.

Reading: a drawing is taken apart layer by layer (``clip``), so its glow can be coloured and its light added.
That needs the layers, which the Matrix's ``bongo.sprites`` puts together into one picture, so ``clip`` reads
the project's text itself (the format is in the Animator's js/animator-project.js and bongo/animator.py: a
palette, and each layer's pixels as runs). Should a file ever not read that way, it falls back to the
Matrix's own ``bongo.sprites`` picture, drawn as it is.
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageChops

from bongo import sprites          # the Matrix's own reader of Animator projects

FOLDER = Path(__file__).parent / "art"      # a module may read its own folder; it can't write there
MAGENTA = (255, 0, 255, 255)
_RUN = re.compile(r"(?:([1-9][0-9]{0,5})\*)?(\.|[0-9a-z]{1,4})")   # "12*a", "a" or "." (as bongo/animator.py reads them)
_CLEAR = b"\0\0\0\0"


def load(name: str) -> list:
    """The frames of ``art/<name>.json`` as the Matrix puts them together: RGBA pictures (see-through where
    nothing is drawn)."""
    read = getattr(sprites, "read", None) or sprites._read     # (``read`` came with a later Matrix)
    return list(read(FOLDER / f"{name}.json").frames)


class Clip:
    """A drawing taken apart: for each frame, what is drawn (``solid``, RGBA), the light it adds in its own
    colours (``light``, RGB on black, or None) and its Glow (``glow``, RGB on black in shades of magenta, or
    None); and how long each frame shows (``ms``) and how it loops. ``flat``: the drawing couldn't be taken
    apart, so its light and glow are in ``solid`` as they were drawn. ``magenta``: False when it has none
    (its colours say so), so there is nothing to tint."""

    def __init__(self, solid, light, glow, ms, loop="loop", flat=False, magenta=True):
        self.solid, self.light, self.glow, self.ms, self.loop, self.flat = solid, light, glow, list(ms), loop, flat
        self.magenta = magenta          # False: no magenta anywhere in it, so nothing to tint
        self.size = solid[0].size

    def index(self, seconds: float) -> int:
        return index(self.ms, self.loop, seconds)


def index(ms: list, loop: str, seconds: float) -> int:
    """Which frame shows ``seconds`` in, for frames of ``ms`` each (the same sums as ``bongo.sprites.Sprite.at``)."""
    order = list(range(len(ms)))
    if loop == "pingpong" and len(order) > 2:
        order += order[-2:0:-1]
    total = sum(ms[i] for i in order) or 1
    t = seconds * 1000
    t = min(t, total - 1) if loop == "once" else t % total
    for i in order:
        if t < ms[i]:
            return i
        t -= ms[i]
    return order[-1]


def _picture(text, colours, size, seen):
    """One layer's pixels in one frame (its runs) as an RGBA picture. ``seen``: pictures already made, by text."""
    if text not in seen:
        out = []
        for run in text.split():
            match = _RUN.fullmatch(run)
            if match is None:
                raise ValueError(f"a layer has pixels the file doesn't describe ({run[:12]})")
            out.append((_CLEAR if match[2] == "." else colours[int(match[2], 36)]) * int(match[1] or 1))
        data = b"".join(out)
        if len(data) != size[0] * size[1] * 4:
            raise ValueError("a layer has the wrong number of pixels")
        seen[text] = Image.frombytes("RGBA", size, data)
    return seen[text]


def _apart(path):
    """The project at ``path`` taken apart (see ``clip``), read from its text."""
    project = json.loads(path.read_text(encoding="utf-8"))
    if project.get("format") != "bongo-animation" or project.get("version") != 1:
        raise ValueError("not an Animator project this module knows")
    size = (int(project["width"]), int(project["height"]))
    colours = [bytes.fromhex(c[1:7]) + b"\xff" for c in project["palette"]]
    magenta = any(c[0] == c[2] and c[0] and not c[1] for c in colours)
    layers = project["layers"]
    glowing = [layer.get("mode") == "light" and str(layer.get("name", "")).strip().lower() == "glow" for layer in layers]
    lighting = [layer.get("mode") == "light" and not g for layer, g in zip(layers, glowing)]
    shown = [layer.get("on", True) is not False and layer.get("opacity", 1) > 0 for layer in layers]
    seen, before, ms = {}, None, []
    solid, light, glow = [], [], []
    made = {}                                   # frames whose layers are all the same as an earlier one's
    for k, frame in enumerate(project["frames"]):
        cels = [before[j] if before and (cel == "=" or layer.get("shared")) else cel
                for j, (cel, layer) in enumerate(zip(frame["cels"], layers))]
        before = cels
        ms.append(max(20, min(5000, int(frame.get("ms", 90)))))
        key = tuple(cels)
        if key not in made:
            parts = {"solid": Image.new("RGBA", size), "light": None, "glow": None}
            for j, cel in enumerate(cels):
                if not shown[j]:
                    continue
                picture = _picture(cel, colours, size, seen)
                opacity = layers[j].get("opacity", 1)
                if lighting[j] or glowing[j]:
                    rgb = picture.convert("RGB")       # (clear = black: adds nothing)
                    if opacity < 1:
                        rgb = rgb.point(lambda v, o=opacity: round(v * o))
                    which = "glow" if glowing[j] else "light"
                    parts[which] = rgb if parts[which] is None else ImageChops.add(parts[which], rgb)
                else:
                    if opacity < 1:
                        picture = picture.copy()
                        picture.putalpha(picture.getchannel("A").point(lambda v, o=opacity: round(v * o)))
                    parts["solid"].alpha_composite(picture)
            made[key] = parts
        parts = made[key]
        solid.append(parts["solid"])
        light.append(parts["light"])
        glow.append(parts["glow"])
    blank = Image.new("RGB", size)
    fill = lambda pictures: None if all(p is None for p in pictures) else [p or blank for p in pictures]
    return Clip(solid, fill(light), fill(glow), ms, project.get("loop", "loop"), magenta=magenta)


def clip(name: str) -> Clip:
    """``art/<name>.json`` taken apart into what is drawn, its light and its glow (see ``Clip``)."""
    path = FOLDER / f"{name}.json"
    try:
        return _apart(path)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):   # not as expected: the Matrix's own picture
        read = getattr(sprites, "read", None) or sprites._read
        sprite = read(path)
        frames = list(sprite.frames)
        return Clip(frames, None, None, getattr(sprite, "ms", None) or [90] * len(frames), getattr(sprite, "loop", "loop"), flat=True)


def timeline(name: str, pictures: list, ms: list, loop: str = "loop"):
    """Pictures shown by time: ``.at(seconds)`` gives the one showing then. A ``bongo.sprites.Sprite`` where the
    Matrix has one that can (so the panel times them as it times every sprite), else the same sums here."""
    kind = getattr(sprites, "Sprite", None)
    if kind is not None and hasattr(kind, "at"):
        try:
            return kind(name, tuple(pictures), tuple(ms), loop)
        except TypeError:       # a Sprite made differently
            pass
    return _Timeline(pictures, ms, loop)


class _Timeline:
    def __init__(self, pictures, ms, loop):
        self.frames, self.ms, self.loop = tuple(pictures), list(ms), loop

    def at(self, seconds):
        return self.frames[index(self.ms, self.loop, seconds)]


_ZERO = [255] + [0] * 255      # lookup tables: 255 where a value is 0, and where it isn't
_SOME = [0] + [255] * 255
_LOOSE = [0] * 40 + [255] * 216     # (tinted, loose: far more red and blue than green...)
_NEAR = [255] * 40 + [0] * 216      # (...and red and blue near each other)


def tinted(picture, colour, loose=False):
    """A copy of ``picture`` with every magenta LED turned ``colour`` (r, g, b): pure magenta exactly, a darker
    shade of magenta (red and blue the same, no green) the colour that much darker.

    ``loose``: for a drawing that couldn't be taken apart (``Clip.flat``), where glow was added onto what was
    under it: any LED much more red and blue than green, and about as red as blue, is taken for glow."""
    r, g, b, a = picture.split()
    if loose:
        strength = ImageChops.subtract(ImageChops.darker(r, b), g)
        mask = ImageChops.multiply(strength.point(_LOOSE), ImageChops.difference(r, b).point(_NEAR))
        if not mask.getbbox():
            return picture
        out = picture.copy()
        out.paste(_dye(strength, colour).convert("RGBA"), (0, 0), mask)
        return out
    same = ImageChops.difference(r, b).point(_ZERO)                                    # red and blue the same...
    mask = ImageChops.multiply(ImageChops.multiply(same, g.point(_ZERO)),              # ...no green, and some red
                               ImageChops.multiply(r.point(_SOME), a.point(_SOME)))
    if not mask.getbbox():
        return picture
    out = picture.copy()
    out.paste(_dye(r, colour), (0, 0), mask)
    return out


def glowing(light, colour):
    """A Glow layer's light (shades of magenta on black) in ``colour``: as bright as the magenta was."""
    return _dye(light.getchannel("R"), colour)


def _dye(strength, colour):
    """``colour`` (RGB) as bright as ``strength`` (an L picture) says, LED by LED."""
    return ImageChops.multiply(Image.merge("RGB", (strength,) * 3), Image.new("RGB", strength.size, tuple(colour[:3])))


def add(img, light, xy=(0, 0)):
    """Adds ``light`` (RGB, black for none) onto ``img`` (RGB) with its top-left at ``xy``, in place."""
    x, y = xy
    box = (x, y, x + light.width, y + light.height)
    img.paste(ImageChops.add(img.crop(box), light), box)    # (the part off the edge is dropped)
