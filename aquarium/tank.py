"""The tank on the panel: the two looks, and what the dashboard's buttons do.

The fish themselves live in ``world.py`` (how they move) and are remembered by ``keep.py`` (which ones
there are). This file draws them, and passes on what a person asks for.

The water, the weed and the bubbles are worked out from the time alone. The fish are different: they
turn and chase food, so they have places of their own that move on a little each frame. One tank is
shared by every screen of the same look, size and starting number of fish, and it lasts as long as
the module is running, so the fish are where you left them when the Aquarium's turn comes round again.

A preview in the dashboard (``ctx.preview``) can be of a made-up moment, and several can be drawn at
once. Each gets a tank of its own, so looking at a preview never disturbs the one on the panel.
"""
import datetime as dt
import math
import random

from PIL import ImageColor

from bongo.module import Style

from . import keep, sprites
from .world import FLAKE_LIFE, World

WORLDS = {}             # (tank's name, width, height) -> the tank on the panel
FEEDS, APART = 8, 45    # food drops in by itself 8 times a day, at random times at least 45 minutes apart
SETTLE = 0.7            # s between one fish and the next when the number of fish is changed
DIVE = 4.0              # s to sink from the Reef down to the Deep (or rise back up) when one follows the other
LAST = {}               # the Aquarium screen last on the panel: {"tank": that screen, "at": when it last drew}
CREAM, CORAL, AMBER = (255, 210, 110), (255, 120, 90), (255, 190, 80)


def shade(colour, by):
    return tuple(max(0, min(255, int(c * by))) for c in colour)


def blend(a, b, by):
    return tuple(round(x + (y - x) * by) for x, y in zip(a, b))


def feeding_times(day, name):
    """The minutes of ``day`` when food drops in by itself: ``FEEDS`` of them at random, each at least
    ``APART`` minutes from the next, the last of one day and the first of the next too. Worked out
    from the date alone, so a restart doesn't change them."""
    rng = random.Random(f"{day.isoformat()} {name}")
    room = 24 * 60 - FEEDS * APART                     # the minutes left to share out at random
    spare = sorted(rng.uniform(0, room) for _ in range(FEEDS))
    return [APART / 2 + spare[k] + k * APART for k in range(FEEDS)]


def last_feeding(now, name):
    """When the most recent of these times was (a timestamp), today's or else yesterday's last."""
    for day in (now.date(), now.date() - dt.timedelta(days=1)):
        midnight = dt.datetime.combine(day, dt.time(), tzinfo=now.tzinfo)
        due = [m for m in feeding_times(day, name) if midnight + dt.timedelta(minutes=m) <= now]
        if due:
            return (midnight + dt.timedelta(minutes=due[-1])).timestamp()
    return None


class _Tank(Style):
    fps = 12
    prefix = ""            # which sprites this look uses
    ignores = ()           # kinds that take no notice of food
    jets = ()              # kinds that shoot upwards when startled
    sink = 3.0             # how fast food falls, LEDs a second

    def setup(self):
        rng = self.ctx.rng                       # the Matrix's own random numbers: a seed redraws the same tank
        w = self.ctx.width
        self.kinds = sprites.load(self.prefix, self.glow())
        self.sizes = {name: (s.width, s.height) for name, s in self.kinds.items()}
        self.own = None                          # a tank of this screen's own, for previews at made-up times
        self.seed = rng.getrandbits(32)
        self.streams = [(rng.randrange(2, max(3, w - 2)), rng.uniform(4, 9), rng.uniform(0, 40)) for _ in range(3)]
        self.passing = [(rng.randrange(w), rng.random()) for _ in range(10)]   # what drifts past on the way down
        self.came_from = None                    # (the other look's screen, when this one came on): diving or rising
        self.first = True
        self.prepare(rng)

    # -- for a look to fill in -----------------------------------------------------------------
    def glow(self):
        return None

    def floor(self):
        return 0

    def prepare(self, rng):
        pass

    def water(self, img, t):
        pass

    def front(self, img, t):
        pass

    def flake(self, img, flake, t, fade):
        pass

    def ripple(self, img, x, age):
        pass

    # -- the tank -------------------------------------------------------------------------------
    def name(self):
        """What this tank is kept under: one tank for each look."""
        return self.prefix

    def _new(self, rng):
        """A tank with the fish that were in it last time, or as many as the ``fish`` setting says."""
        names, count = list(self.kinds), self.settings["fish"]
        kept = keep.look(self.name()) or keep.look(f"{self.name()}{count}")   # (2.2 and before: a tank for each number)
        kinds = kept.get("kinds")
        if not isinstance(kinds, list) or not 1 <= len(kinds) <= 10 or not all(isinstance(k, str) and k in self.kinds for k in kinds):
            kinds = [names[k % len(names)] for k in range(count)] if names else []     # nothing kept (or nonsense): the setting
            kept = {}
        world = World(self.ctx.width, self.ctx.height, self.floor(), self.sizes, kinds, rng, self.ignores, self.jets, self.sink)
        number = lambda v: v if type(v) in (int, float) and math.isfinite(v) else None   # (not true/false, NaN, Infinity)
        world.count = kept.get("count") if type(kept.get("count")) is int else count   # the setting it last went by
        world.fed, world.dropped = number(kept.get("fed")), number(kept.get("dropped"))
        world.changed = -math.inf                           # when a fish last came or went for a change of setting
        return world

    def shared(self):
        """The tank on the panel for this look and size (made on first use)."""
        key = (self.name(), self.ctx.width, self.ctx.height)
        if key not in WORLDS:
            WORLDS[key] = self._new(random.Random())
        return WORLDS[key]

    def world(self, now):
        if not getattr(self.ctx, "preview", True):          # the screen on the panel: the tank that lasts
            world = self.shared()                           # (a Matrix too old to say which it is: always its own)
            self.recount(world, now.timestamp())
            self.feed_by_itself(world, now)
            return world
        if self.own is None:                                # a preview: a tank of its own
            self.own = self._new(random.Random(self.seed))
        return self.own

    def recount(self, world, t):
        """The ``fish`` setting was changed: fish drop in, or swim off the side, one at a time, until there
        are that many. (The buttons add and remove fish too; only a change to the setting does this.)"""
        want = self.settings["fish"]
        if world.count == want or 0 <= t - world.changed < SETTLE:   # (one at a time, a moment apart)
            return
        have = len(world.kinds())
        if have == want or not (world.add(t) if have < want else world.remove()):   # there (or full, or down to one)
            world.count = want
        world.changed = t
        keep.save(self.name(), kinds=world.kinds(), count=world.count)   # (part way: a restart carries on)

    def feed_by_itself(self, world, now):
        """Food drops in at the day's ``feeding_times`` while this screen is on. One missed while another
        screen was on comes when the Aquarium next is, but never sooner than ``APART`` minutes after the last."""
        t = now.timestamp()
        if world.fed is not None and world.fed > t + 60:    # remembered from a clock that was once ahead (set wrong,
            world.fed = None                                 # since put right): start again, rather than wait for that day
        if world.dropped is not None and world.dropped > t + 60:
            world.dropped = None
        due = last_feeding(now, self.name())
        if due is None or (world.fed is not None and due <= world.fed):
            return
        if world.fed is None:                               # the very first time: nothing to catch up on
            world.fed = due
        elif world.dropped is not None and 0 <= t - world.dropped < APART * 60:
            return                                          # too soon after the last: it waits
        else:
            world.feed(t)
            world.fed, world.dropped = due, t
        keep.save(self.name(), fed=world.fed, dropped=world.dropped)

    def act(self, name):
        """A button in the dashboard. It is only noted here; the next frame does it, at that frame's moment."""
        self.shared().asked.append(name)

    def do(self, world, name, t):
        if name == "feed":
            world.feed(t)
        elif name == "tap":
            world.tap(t)
        elif name in ("add", "remove") and (world.add(t) if name == "add" else world.remove()):
            keep.save(self.name(), kinds=world.kinds())           # the same fish next time

    # -- drawing --------------------------------------------------------------------------------
    def swim(self, img, world, t):
        for flake in world.flakes:
            if flake.y >= 0:
                left = FLAKE_LIFE - (t - flake.born)
                self.flake(img, flake, t, min(1.0, left / 2))        # it fades over its last two seconds
        for f in world.fish:
            x, y = round(f.x), round(f.y)
            if f.close and int(t * 4) % 2:                           # a nibble: one LED towards the food and back
                x += f.direction
            self.kinds[f.kind].draw(img, x, y, f.direction, int(t * 3 + f.phase), scared=t < f.scared_until)

    def bubbles(self, img, t, colour):
        if not self.settings["bubbles"]:
            return
        w, h = self.ctx.width, self.ctx.height
        for x0, speed, offset in self.streams:
            for n in range(3):                                                # three bubbles to a stream
                up = (t * speed + offset + n * (h + 6) / 3) % (h + 6)
                x, y = x0 + round(math.sin(up / 3 + n)), h - self.floor() - round(up)
                if 0 <= x < w and 0 <= y < h:
                    img.putpixel((x, y), colour)

    def scene(self, now):
        """This look at ``now``, fish and all."""
        img = self.ctx.canvas()
        t = now.timestamp()
        world = self.world(now)
        world.step(t)
        while world.asked:                                       # buttons pressed since the last frame
            self.do(world, world.asked.pop(0), t)
        self.water(img, t)
        self.swim(img, world, t)
        self.front(img, t)
        for x, when in world.ripples:
            self.ripple(img, x, t - when)
        return img

    def render(self, now):
        t = now.timestamp()
        if not getattr(self.ctx, "preview", True):               # (the panel: previews never dive)
            if self.first:                                       # the other look was on just before this one: go there
                last = LAST.get("tank")
                if (last is not None and last.prefix != self.prefix and 0 <= t - LAST["at"] < 3
                        and (last.ctx.width, last.ctx.height) == (self.ctx.width, self.ctx.height)):
                    self.came_from = (last, t)
            LAST.update(tank=self, at=t)
        self.first = False
        img = self.scene(now)
        if self.came_from is not None:
            last, start = self.came_from
            gone = t - start
            if 0 <= gone < DIVE:
                self.busy = True                                 # (a screen shorter than the dive still finishes it)
                return self.dive(last.scene(now), img, gone / DIVE)
            self.came_from, self.busy = None, False              # (there, or the clock jumped: just this look now)
        return img

    def dive(self, before, after, p):
        """Part ``p`` (0 to 1) of the way from the look that was on to this one, as if the tank were one tall
        column of water with the Reef at the top and the Deep below: it sinks from one to the other (or
        rises), through water that darkens, with specks streaming past the other way."""
        w, h = self.ctx.width, self.ctx.height
        p = p * p * (3 - 2 * p)                                  # gently away, gently to a stop
        reef, deep = (before, after) if isinstance(self, Deep) else (after, before)
        down = isinstance(self, Deep)
        gap = h                                                  # the water between the two
        travel = h + gap
        y = round((p if down else 1 - p) * travel)               # how far down the column the view is
        shallow = (self if isinstance(self, Reef) else self.came_from[0]).rows[-1]   # the reef's deepest water...
        top = (0, 8, 22)                                         # ...to the very top of the Deep (Deep.water, row 0)
        img = self.ctx.canvas()
        img.paste(reef, (0, -y))
        for row in range(gap):                                   # the reef's water fading into the deep's
            yy = h - y + row
            if 0 <= yy < h:
                colour = blend(shallow, top, (row + 1) / gap)
                for x in range(w):
                    img.putpixel((x, yy), colour)
        img.paste(deep, (0, h + gap - y))
        moving = math.sin(math.pi * p)                           # specks show while it moves
        if moving > 0.15:
            ink = blend(top, (190, 220, 255), 0.35 * moving)
            for x, at in self.passing:                            # rising past as it sinks, falling as it rises
                img.putpixel((x, int((at * h - y * 1.6) % h)), ink)
        return img


class Reef(_Tank):
    """Sunlit water, sand, swaying weed and bright fish."""
    prefix = "reef_"
    defaults = {"water": "#0A3A66"}

    def floor(self):
        return 2 if self.ctx.height >= 12 else 0

    def prepare(self, rng):
        w, h = self.ctx.width, self.ctx.height
        top = ImageColor.getrgb(self.settings["water"])
        self.rows = [shade(top, 1.0 - 0.75 * y / max(1, h - 1)) for y in range(h)]     # lighter near the surface
        self.speckles = {rng.randrange(w) for _ in range(w // 4)}
        self.weed = [(rng.randrange(1, max(2, w - 1)), rng.randrange(4, max(5, h // 2)), rng.uniform(0, 6)) for _ in range(max(2, w // 14))]

    def water(self, img, t):
        w, h = self.ctx.width, self.ctx.height
        px = img.load()
        for y in range(h):
            for x in range(w):
                px[x, y] = self.rows[y]
        for x, tall, phase in self.weed:                     # weed first: the fish swim in front of it
            for k in range(tall):
                sway = round(math.sin(t * 1.1 + phase + k * 0.6) * min(1.5, k / 3))
                y = h - self.floor() - 1 - k
                if 0 <= x + sway < w and y >= 0:
                    px[x + sway, y] = (30, 150, 70) if k % 2 else (40, 185, 90)
        for y in range(h - self.floor(), h):
            for x in range(w):
                px[x, y] = (214, 190, 120) if (x in self.speckles) == (y == h - 1) else (190, 164, 100)

    def front(self, img, t):
        self.bubbles(img, t, (190, 225, 255))

    def flake(self, img, flake, t, fade):
        """A flake of food: two LEDs wide while it flutters down (a bubble is one), one once it has settled."""
        x, y = round(flake.x), round(flake.y)
        colour = CREAM if flake.settled or not flake.coral else CORAL      # (coral is lost against the sand)
        wide = not flake.settled
        for dx in range(2 if wide else 1):
            if 0 <= x + dx < self.ctx.width and 0 <= y < self.ctx.height:
                img.putpixel((x + dx, y), blend(img.getpixel((x + dx, y)), colour, fade))

    def ripple(self, img, x, age):
        """Something went in at the surface: a short bright line on the top row that spreads apart and fades."""
        if not 0 <= age < 1.5:
            return
        reach, strength = round(age * 5), 0.9 * (1 - age / 1.5)
        for px in {round(x) - reach - 1, round(x) - reach, round(x) + reach, round(x) + reach + 1}:
            if 0 <= px < self.ctx.width:
                img.putpixel((px, 0), blend(self.rows[0], (200, 230, 255), strength))


class Deep(_Tank):
    """Dark water where the only light is what lives there. ``glow`` is its colour."""
    prefix = "deep_"
    defaults = {"glow": "#7FFFD4"}
    ignores = ("deep_jelly", "deep_angler")      # jellyfish don't care; the angler waits for food to come to it
    jets = ("deep_jelly",)                       # startled, a jellyfish shoots upwards
    sink = 1.5                                   # "marine snow" drifts down slowly

    def glow(self):
        return ImageColor.getrgb(self.settings["glow"])

    def prepare(self, rng):
        w, h = self.ctx.width, self.ctx.height
        self.specks = [(rng.randrange(w), rng.randrange(h), rng.uniform(0, 6), rng.uniform(0.4, 1.2)) for _ in range(max(3, w * h // 170))]

    def water(self, img, t):
        w, h = self.ctx.width, self.ctx.height
        px = img.load()
        for y in range(h):
            row = (0, 2 + 6 * (h - y) // h, 8 + 14 * (h - y) // h)
            for x in range(w):
                px[x, y] = row
        glow = self.glow()
        for x, y, phase, beat in self.specks:                # specks that brighten and fade where they are
            px[x, y] = shade(glow, 0.12 + 0.3 * (0.5 + 0.5 * math.sin(t * beat + phase)))

    def front(self, img, t):
        self.bubbles(img, t, shade(self.glow(), 0.45))

    def flake(self, img, flake, t, fade):
        x, y = round(flake.x), round(flake.y)
        if 0 <= x < self.ctx.width and 0 <= y < self.ctx.height:
            img.putpixel((x, y), blend(img.getpixel((x, y)), AMBER, fade * 0.9))
