"""The scenery behind and in front of the fish, put together once for each size from the drawings in
``art/scenery`` (Animator projects, drawn on the 64 x 32 panel: see ``art.py``).

Each look is three layers: the back (water, seabed, rocks, weed: behind the fish), the fish, and the front
(the bubbles, and a few weeds in front of them, darker so the fish stay the brightest thing). The scenery's drawings all loop
in step (each look's water sets the clock, 48 or 64 frames of 125 ms), so the back and the front are put
together whole for each frame, once, when the look first shows at a size; on the panel each frame is then
a copy of the back, the fish, and the front laid on top. (The same scenery is shared by every screen of the
look at that size and colour.)

How a 64 x 32 drawing fits other sizes (48 x 20, 64 x 64, 128 x 64...). Nothing crisp is ever stretched:
- The water is soft light with no edges (a gradient, blurred sunbeams), so it is the one thing resized: to
  the height, smoothly; and it is drawn so its left and right edges meet, so it repeats across a wider panel.
- The seabed strips (sand, silt) repeat across and sit on the bottom row.
- Rocks, coral and weed are placed at their size, from one of two arrangements: one for the 64-wide panel
  and one for the 128-wide one (more pieces, none of them side by side with its twin). Up to 95 wide the
  64-wide one is squeezed or spread to the width; from 96 the 128-wide one is (and repeated side by side
  on a panel wider still). The pieces themselves never change size.
- On a short panel (under 24 tall) the scenery keeps low, so the fish have clear water above it: the anemone
  and the sea fan are left out, and a piece too tall gives way to a shorter one (tall kelp, then weed, then
  grass) or, with nothing shorter to stand in, is set deeper into the seabed.
- Specks in the water (the Deep's marine snow, its Glow) are repeated down a taller panel, not resized.
"""
import colorsys

from PIL import Image, ImageChops

from . import art

REF_WATER = (0x2A, 0x8A, 0xC8)    # the colour the Reef's water is drawn in (at the surface): the default ``water``

# The arrangements: (drawing, its left edge) on the 64-wide panel and on the 128-wide one. Back to front; the
# front pieces go over the fish. Bubbles: (the middle of a column, how many seconds it is ahead of the others).
LOOKS = {
    "reef": {
        "water": "reef_water", "bed": "reef_sand", "sits": 2, "bubble": "reef_bubbles",   # back pieces stand 2 LEDs into the sand
        64: {"back": [("reef_kelp", 1), ("reef_rock", 5), ("reef_weed", 22), ("reef_anemone", 31), ("reef_fan", 52),
                      ("reef_coral", 44), ("reef_kelp", 58)],
             "front": [("reef_front", 13)],
             "bubbles": [(11, 0.0), (41, 2.1), (56, 4.3)]},
        128: {"back": [("reef_kelp", 1), ("reef_rock", 6), ("reef_grass", 22), ("reef_weed", 33), ("reef_anemone", 42),
                       ("reef_kelp", 58), ("reef_coral", 68), ("reef_grass", 82), ("reef_fan", 92), ("reef_weed", 104),
                       ("reef_kelp", 118)],
              "front": [("reef_front", 15), ("reef_front", 96)],
              "bubbles": [(12, 0.0), (38, 2.1), (77, 4.3), (111, 1.2)]},
    },
    "deep": {
        "water": "deep_water", "bed": "deep_floor", "sits": 1, "bubble": "deep_bubbles",
        64: {"back": [("deep_rocks", 0), ("deep_worms", 21), ("deep_anemone", 28), ("deep_vent", 43), ("deep_worms", 56)],
             "front": [("deep_pen", 15)],
             "bubbles": [(48, 0.0), (12, 3.0)]},                    # (one rises from the vent)
        128: {"back": [("deep_rocks", 0), ("deep_worms", 22), ("deep_anemone", 31), ("deep_vent", 50), ("deep_worms", 66),
                       ("deep_anemone", 82), ("deep_rocks", 104)],
              "front": [("deep_pen", 16), ("deep_pen", 92)],
              "bubbles": [(55, 0.0), (12, 3.0), (95, 5.1)]},
    },
}
SHORTER = {"reef_kelp": "reef_weed", "reef_weed": "reef_grass"}   # what stands in for a piece too tall for the panel
LOW = 24                                                          # under this tall, the scenery keeps low...
LEFT_OUT = {"reef_anemone", "reef_fan"}                           # ...and these are left out

_clips = {}      # drawing -> art.Clip (read once: a drawing doesn't change while the module runs)
_dyed = {}       # (drawing, frame, glow) -> (what is drawn with its magenta in the glow colour, the light it adds)
_scenes = {}     # (look, width, height, water, glow, bubbles) -> Scene
KEEP = 6         # scenes kept: the panel's sizes and colours in use, and a few previews


def _clip(name):
    if name not in _clips:
        _clips[name] = art.clip(f"scenery/{name}")
    return _clips[name]


def _frame(name, i, glow):
    """Frame ``i`` of a drawing: what is drawn (magenta in ``glow``) and the light it adds (or None). Worked out
    once for each colour, however many times the piece is placed."""
    key = (name, i, glow)
    if key not in _dyed:
        piece = _clip(name)
        solid = art.tinted(piece.solid[i], glow, loose=piece.flat) if glow and piece.magenta else piece.solid[i]
        parts = ([piece.light[i]] if piece.light else []) + ([art.glowing(piece.glow[i], glow or (255, 0, 255))] if piece.glow else [])
        light = None if not parts else parts[0] if len(parts) == 1 else ImageChops.add(*parts)
        if len(_dyed) > 6000:                      # (colours changed many times over: start again)
            _dyed.clear()
        _dyed[key] = (solid, light)
    return _dyed[key]


def shifted(picture, colour):
    """``picture`` (drawn in the reference blue) moved to ``colour``: its hue turned by the difference, its
    colourfulness and brightness scaled by the ratio, so the default colour changes nothing."""
    h0, s0, v0 = colorsys.rgb_to_hsv(*(c / 255 for c in REF_WATER))
    h1, s1, v1 = colorsys.rgb_to_hsv(*(c / 255 for c in colour[:3]))
    if (h1, s1, v1) == (h0, s0, v0):
        return picture
    turn = round((h1 - h0) * 256)
    h, s, v = picture.convert("HSV").split()
    h = h.point(lambda x: (x + turn) % 256)
    s = s.point(lambda x: min(255, round(x * s1 / s0)))
    v = v.point(lambda x: min(255, round(x * v1 / v0)))
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def _across(strip, w, h, y):
    """``strip`` repeated across a ``w`` x ``h`` see-through canvas, its top at row ``y``."""
    out = Image.new(strip.mode, (w, h))
    for x in range(0, w, strip.width):
        out.paste(strip, (x, y))
    return out


def _arrangement(look, w):
    """The arrangement for a panel ``w`` wide, how wide it was drawn, and how many copies go side by side."""
    drawn = 128 if w >= 96 else 64
    return LOOKS[look][drawn], drawn, max(1, round(w / drawn))


def _layout(pieces, drawn, copies, w, h, sits):
    """Where each piece goes on a ``w`` x ``h`` panel: [(drawing, x, y, set deeper in)], back to front (see the
    top of this file). A piece set deeper in goes under the seabed, which covers the part of it that is buried."""
    low = h < LOW
    room = max(4, round((h - 7) * (0.5 if low else 0.8)))   # the most a piece may rise from the bottom
    bay = w / copies
    out = []
    for b in range(copies):
        for name, x0 in pieces:
            if low and name in LEFT_OUT:
                continue
            middle = (x0 + _clip(name).size[0] / 2) / drawn   # where its middle is, across the panel it was placed on...
            while _clip(name).size[1] > room and name in SHORTER:
                name = SHORTER[name]
            pw, ph = _clip(name).size
            x = round(b * bay + middle * bay - pw / 2)         # ...at the same place across this one
            drawn_box = _clip(name).solid[0].getbbox()         # (a vent's plume rises above what is drawn)
            tall = drawn_box[3] - drawn_box[1] if drawn_box else ph
            sunk = max(0, tall - room)                         # still too tall, with nothing shorter: set deeper in
            out.append((name, max(-(pw // 3), min(x, w - pw + pw // 3)), h - sits - ph + sunk, sunk > 0))   # at most a third off the panel
    return out


class Scene:
    """One look's scenery at one size and colour: ``back.at(t)`` (RGB), ``front.at(t)`` (RGBA, or None) and
    ``front_light.at(t)`` (RGB, or None), each the picture showing ``t`` seconds in; and ``rows``, the water's
    colour row by row (for the dive between the looks)."""

    def __init__(self, look, w, h, water=None, glow=None, bubbles=True):
        spec = LOOKS[look]
        glow = tuple(glow[:3]) if glow else None
        sea = _clip(spec["water"])
        times, t = [], 0
        for ms in sea.ms:                          # the water's frames set the clock for the scenery
            times.append(t / 1000)
            t += ms
        plan, drawn, copies = _arrangement(look, w)
        back = _layout(plan["back"], drawn, copies, w, h, spec["sits"])
        front = _layout(plan["front"], drawn, copies, w, h, 1)
        bed = _clip(spec["bed"])
        floor = [(spec["bed"], x, h - bed.size[1], False) for x in range(0, w, bed.size[0])]
        buried = [p for p in back if p[3]]
        back = buried + floor + [p for p in back if not p[3]]   # (the buried pieces under the seabed, the rest on it)
        bubble = spec["bubble"] + ("_tall" if h > 40 else "")   # (on a tall panel, a column a bubble rises the whole way up)
        columns = []
        if bubbles:                                # columns of bubbles, rising from just above the seabed
            bw, bh = _clip(bubble).size
            for b in range(copies):
                for x0, ahead in plan["bubbles"]:
                    x = round((b + x0 / drawn) * w / copies) - bw // 2
                    columns += [(x, y, ahead) for y in range(h - 3 - bh, -bh, -bh)]
        backs, fronts, lights = [], [], []
        for k, at in enumerate(times):
            img = self._water(sea, k, w, h, water, glow)
            if k == 0:
                column = img.resize((1, h), Image.BOX)
                self.rows = [column.getpixel((0, y)) for y in range(h)]
            self._lay(img, at, back, glow)
            backs.append(img)
            if front or columns:
                over = Image.new("RGBA", (w, h))
                light = Image.new("RGB", (w, h))
                for x, y, ahead in columns:
                    solid, _ = _frame(bubble, _clip(bubble).index(at + ahead), glow)
                    over.paste(solid, (x, y), solid)
                self._lay(over, at, front, glow, light)
                fronts.append(over)
                lights.append(light if light.getbbox() else None)
        self.back = art.timeline(f"{look} back", backs, sea.ms, sea.loop)
        self.front = art.timeline(f"{look} front", fronts, sea.ms, sea.loop) if fronts else None
        self.front_light = art.timeline(f"{look} front light", lights, sea.ms, sea.loop) if any(lights) else None

    def _water(self, sea, k, w, h, water, glow):
        """The water in frame ``k``, at ``w`` x ``h``: resized to the height (it is soft light, no edges),
        repeated across, and turned to the ``water`` colour (the Reef)."""
        img = sea.solid[k].convert("RGB")
        if sea.flat and glow:                      # (a drawing that couldn't be taken apart: its magenta at least)
            img = art.tinted(sea.solid[k], glow, loose=True).convert("RGB")
        if sea.light:
            img = ImageChops.add(img, sea.light[k])
        if water:
            img = shifted(img, water)
        if img.height != h:
            img = img.resize((img.width, h), Image.BILINEAR)
        img = _across(img, w, h, 0) if img.width != w else img
        if sea.glow:                               # specks, not soft light: repeated, never resized (each copy
            specks = art.glowing(sea.glow[k], glow or (255, 0, 255))    # moved along, so no pattern shows)
            sw, sh = specks.size
            for row, y in enumerate(range(0, h, sh)):
                for x in range(-sw, w, sw):
                    art.add(img, specks, (x + (row * 23) % sw, y))
        return img

    @staticmethod
    def _lay(img, at, placed, glow, light=None):
        """The pieces ``placed`` [(drawing, x, y, buried)], each at its frame for ``at`` seconds, onto ``img`` in place;
        the light they give is added to ``light`` if given, else onto ``img``."""
        for name, x, y, _ in placed:
            solid, shine = _frame(name, _clip(name).index(at), glow)
            img.paste(solid, (x, y), solid)
            if shine is not None:
                art.add(img if light is None else light, shine, (x, y))


def scene(look, w, h, water=None, glow=None, bubbles=True):
    """The scenery for ``look`` at ``w`` x ``h`` (made on first use, and kept)."""
    key = (look, w, h, tuple(water or ()), tuple(glow or ()), bool(bubbles))
    if key not in _scenes:
        while len(_scenes) >= KEEP:
            _scenes.pop(next(iter(_scenes)))       # the oldest goes
        _scenes[key] = Scene(look, w, h, water, glow, bubbles)
    return _scenes[key]
