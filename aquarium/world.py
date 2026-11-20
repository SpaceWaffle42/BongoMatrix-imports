"""What lives in the tank and how it moves: fish, flakes of food, ripples.

No drawing here (that is ``tank.py``), and no clock of its own: ``World.step(t)`` is told the time and
moves everything on from the last time it was told. A long gap, or the clock going backwards, moves
nothing: the tank simply carries on from where it was.

Everything a person can do (feed, tap the glass, add or remove a fish) is optional. Left alone the fish
cruise for ever; nothing gets hungry and nothing needs looking after.
"""
import math
import random

MOST_FISH, FEWEST_FISH = 10, 1
FLAKES = 5              # in one feed
MOST_FLAKES = 12        # in the water at once: feeding again and again doesn't fill the tank
FLAKE_LIFE = 20.0       # s until an uneaten flake is gone
BITE = 1.6              # s of nibbling to finish a flake
EATERS = 4              # fish eating at once, two to a flake; the others wait their turn in the ring
RING = 3                # fish circling the food while others eat
FLEE, SCARED = 0.6, 1.8 # s a fish darts away after a tap, and how long it stays startled
STEP = 0.1              # s: the longest move made in one go


class Fish:
    __slots__ = ("kind", "x", "y", "vx", "vy", "direction", "speed", "lane", "bob", "beat", "phase", "gap",
                 "state", "flake", "side", "close", "flee_until", "scared_until", "away", "turned")

    def __init__(self, kind, rng, w, h, size, floor):
        self.kind = kind
        self.direction = rng.choice((1, -1))
        self.speed = rng.uniform(2.5, 8.0)                                   # LEDs a second when cruising
        self.lane = rng.uniform(1, max(2, h - size[1] - floor - 1))          # the depth it keeps to
        self.bob, self.beat, self.phase = rng.uniform(0.5, 2.0), rng.uniform(0.3, 0.9), rng.uniform(0, 6.28)
        self.gap = rng.uniform(6, 30)                                        # LEDs of empty water before it comes round again
        self.x, self.y = rng.uniform(-size[0], w), self.lane
        self.vx = self.vy = 0.0
        self.state = "swim"                                                  # or "arrive" (dropping in), "leave" (swimming off)
        self.flake, self.side, self.close = None, 1, False                   # the flake it is eating, from which side
        self.flee_until = self.scared_until = 0.0
        self.away = (0.0, 0.0)
        self.turned = 0.0                                                    # when it last turned round


class Flake:
    __slots__ = ("x", "y", "born", "phase", "settled", "bitten", "coral")

    def __init__(self, x, t, rng):
        self.x, self.y, self.born = x, 0.0, t
        self.phase, self.coral = rng.uniform(0, 6.28), rng.random() < 0.4
        self.settled, self.bitten = False, 0.0


class World:
    def __init__(self, w, h, floor, sizes, kinds, rng=None, ignores=(), jets=(), sink=3.0):
        """``sizes``: {kind: (width, height)} of every picture. ``kinds``: the kind of each fish to start with.
        ``ignores``: kinds that take no notice of food. ``jets``: kinds that shoot upwards when startled.
        ``sink``: how fast food falls, in LEDs a second."""
        self.w, self.h, self.floor, self.sizes = w, h, floor, sizes
        self.rng = rng or random.Random()
        self.ignores, self.jets, self.sink = set(ignores), set(jets), sink
        self.fish = [Fish(k, self.rng, w, h, sizes[k], floor) for k in kinds if k in sizes]
        self.flakes, self.ripples = [], []            # ripples: (x, when)
        self.at = None                                # the time everything is at
        self.asked = []                               # buttons pressed, for the next frame to do (tank.py, act)

    # -- what a person can do -------------------------------------------------------------------
    def kinds(self):
        """The fish that live here (not one that is swimming off for good)."""
        return [f.kind for f in self.fish if f.state != "leave"]

    def feed(self, t):
        room = MOST_FLAKES - len(self.flakes)
        middle = self.rng.uniform(self.w * 0.25, self.w * 0.75)
        for k in range(min(FLAKES, room)):
            x = min(self.w - 2.0, max(1.0, middle + (k - FLAKES // 2) * 6 + self.rng.uniform(-1.5, 1.5)))
            flake = Flake(x, t, self.rng)
            flake.y = -self.rng.uniform(0, 9)          # not all at once
            self.flakes.append(flake)
        self.ripples.append((middle, t))

    def tap(self, t):
        cx, cy = self.w / 2, (self.h - self.floor) / 2
        for f in self.fish:
            width, height = self.sizes[f.kind]
            if f.state != "swim" or not self._in_view(f):        # one waiting out of sight stays there
                continue
            dx, dy = f.x + width / 2 - cx, f.y + height / 2 - cy
            far = math.hypot(dx, dy) or 1.0
            dash = max(14.0, f.speed * 3)
            f.away = (0.0, -12.0) if f.kind in self.jets else ((dx / far or f.direction) * dash, dy / far * dash * 0.5)
            f.flee_until, f.scared_until = t + FLEE, t + SCARED
            f.flake = None

    def _in_view(self, f):
        return -2 <= f.x <= self.w - self.sizes[f.kind][0] + 2

    def add(self, t):
        """Drop one more fish in at the top: the kind there are fewest of. False when the tank is full."""
        living = self.kinds()
        if len(living) >= MOST_FISH or not self.sizes:
            return False
        kind = min(sorted(self.sizes), key=living.count)
        f = Fish(kind, self.rng, self.w, self.h, self.sizes[kind], self.floor)
        f.x = self.rng.uniform(self.w * 0.2, max(self.w * 0.2, self.w * 0.8 - self.sizes[kind][0]))
        f.y, f.state = -float(self.sizes[kind][1]), "arrive"
        self.fish.append(f)
        self.ripples.append((f.x + self.sizes[kind][0] / 2, t))
        return True

    def remove(self):
        """The newest fish swims off the nearest side and doesn't come back. False when only one is left."""
        living = [f for f in self.fish if f.state != "leave"]
        if len(living) <= FEWEST_FISH:
            return False
        f = next((k for k in reversed(living) if self._in_view(k) and k.state == "swim"),       # one you can see go
                 next((k for k in reversed(living) if k.state != "arrive"), living[-1]))
        f.state, f.flake = "leave", None
        f.direction = -1 if f.x + self.sizes[f.kind][0] / 2 < self.w / 2 else 1
        return True

    # -- time passing ---------------------------------------------------------------------------
    def step(self, t):
        if self.at is not None and -1 <= t - self.at <= 0:    # the same moment again (or a hair earlier): nothing to do
            return
        if self.at is None or not 0 <= t - self.at <= 3:      # the first frame, a long gap, or the clock moved:
            self.at = t                                       # carry on from here, moving nothing
            self.flakes = [f for f in self.flakes if -1 <= t - f.born < FLAKE_LIFE]
            self.ripples = [r for r in self.ripples if -1 <= t - r[1] < 1.5]
            return
        while t - self.at > 1e-6:
            dt = min(STEP, t - self.at)
            self.at += dt
            self._move(self.at, dt)

    def _move(self, t, dt):
        bottom = self.h - self.floor - 1
        for flake in self.flakes:
            if not flake.settled:
                flake.y += self.sink * dt
                flake.x += math.sin(t * 2.2 + flake.phase) * 1.5 * dt       # it flutters as it falls
                if flake.y >= bottom:
                    flake.y, flake.settled = bottom, True
        self.flakes = [f for f in self.flakes if t - f.born < FLAKE_LIFE and f.bitten < BITE]
        self.ripples = [r for r in self.ripples if t - r[1] < 1.5]
        ring = self._roles()
        for f in list(self.fish):
            self._swim(f, t, dt, ring.get(id(f)))

    def _roles(self):
        """Who does what about the food. Two fish eat each flake, one from each side; a few more circle
        the food; the rest keep cruising. (Everyone heading for one spot is a blob, not a swarm.)
        Returns the place in the ring of each circling fish: {id(fish): (place, of how many)}."""
        food = [f for f in self.flakes if f.y >= 5 or f.settled]      # left to flutter down a little first
        free = []
        for f in self.fish:
            if f.flake is not None and f.flake not in food:
                f.flake = None
            keen = f.state == "swim" and f.kind not in self.ignores and self._in_view(f)
            if keen and f.flake is None:
                free.append(f)
        busy = sum(f.flake is not None for f in self.fish)
        for flake in sorted(food, key=lambda k: -k.y):                 # the lowest flake first
            eating = [f for f in self.fish if f.flake is flake]
            while len(eating) < 2 and free and busy < EATERS:
                busy += 1
                f = min(free, key=lambda f: abs(f.x - flake.x) + abs(f.y - flake.y))
                free.remove(f)
                f.flake = flake
                f.side = -eating[0].side if eating else (-1 if f.x < flake.x else 1)   # -1: on its left
                eating.append(f)
        circling = free[:RING] if food else []
        return {id(f): (k, len(circling)) for k, f in enumerate(circling)}

    def _swim(self, f, t, dt, place):
        width, height = self.sizes[f.kind]
        deepest = max(0.0, self.h - self.floor - height)
        f.close = False
        if f.state == "leave":                                   # off the side, and gone
            want = (f.direction * max(12.0, f.speed * 3), 0.0)
        elif f.state == "arrive":                                # sinking in from the top
            want = (0.0, 9.0)
            if f.y >= min(f.lane, deepest):
                f.state = "swim"
        elif t < f.flee_until:
            want = f.away
        elif f.flake is not None:                                # to its side of the flake, then nibble
            tx = f.flake.x - width - 0.5 if f.side < 0 else f.flake.x + 1.5
            ty = min(deepest, max(0.0, f.flake.y - height / 2))
            dx, dy = tx - f.x, ty - f.y
            far = math.hypot(dx, dy)
            pace = min(12.0, far * 4)
            want = (dx / far * pace, dy / far * pace) if far > 0.05 else (0.0, 0.0)
            if far < 2.5:
                f.close = True
                if abs(f.vx) < 2.5 and t - f.turned >= 0.6:      # facing the food, once it has slowed down
                    f.direction, f.turned = (1 if f.side < 0 else -1), t
                f.flake.bitten += dt
        elif place is not None:                                  # circling the food
            food = [k for k in self.flakes if k.y >= 0] or self.flakes
            cx = min(self.w - 10.0, max(10.0, sum(k.x for k in food) / len(food)))
            cy = min(deepest - 4, max(4.0, sum(k.y for k in food) / len(food)))
            angle = t * 0.9 + place[0] * 2 * math.pi / place[1]
            tx = cx + min(9.0, self.w / 5) * math.cos(angle) - width / 2
            ty = cy + min(5.0, self.h / 6) * math.sin(angle) - height / 2
            dx, dy = tx - f.x, ty - f.y
            far = math.hypot(dx, dy)
            pace = min(9.0, far * 3)
            want = (dx / far * pace, dy / far * pace) if far > 0.05 else (0.0, 0.0)
        else:                                                    # cruising along its lane, bobbing a little
            want = (f.direction * f.speed, (f.lane + f.bob * math.sin(t * f.beat + f.phase) - f.y) * 1.5)
        if f.flake is not None or place is not None:             # round the food, fish keep out of each other's way
            for other in self.fish:
                if other is not f and (other.flake is not None or other.state == "swim"):
                    ow, oh = self.sizes[other.kind]
                    dx = (f.x + width / 2) - (other.x + ow / 2)
                    dy = (f.y + height / 2) - (other.y + oh / 2)
                    if abs(dx) < (width + ow) / 2 and abs(dy) < (height + oh) / 2 + 1:
                        want = (want[0] + (3.0 if dx >= 0 else -3.0), want[1] + (5.0 if dy >= 0 else -5.0))
        ease = min(1.0, 5 * dt)                                  # it turns; it doesn't snap round
        f.vx += (want[0] - f.vx) * ease
        f.vy += (want[1] - f.vy) * ease
        f.x += f.vx * dt
        f.y += f.vy * dt
        if f.state != "arrive":
            f.y = min(deepest, max(0.0, f.y))
        if not f.close and abs(f.vx) > 2.5 and (f.vx > 0) != (f.direction > 0) and t - f.turned >= 0.6:
            f.direction, f.turned = (1 if f.vx > 0 else -1), t    # (not at every little change of mind)
        cruising = f.state == "swim" and f.flake is None and place is None and t >= f.flee_until
        if f.state == "leave":
            if f.x > self.w + 1 or f.x < -width - 1:
                self.fish.remove(f)
        elif cruising:                                           # off one side, a wait, and in at the other
            if f.direction > 0 and f.x > self.w + f.gap:
                f.x = -float(width)
            elif f.direction < 0 and f.x < -width - f.gap:
                f.x = float(self.w)
        else:                                                    # busy with food or startled: stays in the tank
            f.x = min(self.w - width + 2.0, max(-2.0, f.x))
