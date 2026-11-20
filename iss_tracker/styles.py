"""The three looks: Map, Readout and Distance. Each asks FEED for the latest position and draws one frame."""
import math
import time

from PIL import ImageColor, ImageDraw

from bongo.module import Style

from . import world
from .feed import FEED

WHITE, GREY, DIM = (255, 255, 255), (150, 156, 166), (70, 74, 82)
POINTS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
IN_RANGE_KM = 2200          # about how far away the station can still be above your horizon


def rgb(hex_colour, scale=1.0):
    return tuple(int(c * scale) for c in ImageColor.getrgb(hex_colour))


def place(lat, lon):
    """'52N 12W': whole degrees fit a small panel."""
    return f"{abs(round(lat))}{'N' if lat >= 0 else 'S'} {abs(round(lon))}{'E' if lon >= 0 else 'W'}"


def thousands(n):
    return f"{round(n):,}"


class _Base(Style):
    fps = 10

    def setup(self):
        self.small = self.ctx.fonts("4x6")
        self.accent = rgb(self.settings["colour"])
        self.miles = bool(self.settings["miles"])

    def fix(self):
        FEED.ask(self.settings["refresh"])
        return FEED.fix, FEED.fresh()

    def length(self, km):
        return (f"{thousands(km * 0.621371)} MI" if self.miles else f"{thousands(km)} KM")

    def centred(self, img, baseline, text, colour, outline=None):
        self.small.draw(img, max(0, (self.ctx.width - self.small.width(text)) // 2), baseline, text, colour, outline=outline)

    def waiting(self, img, now):
        """Before the first position arrives (or with no network): say so, don't draw a guess."""
        dots = "." * (1 + int(now.timestamp()) % 3)
        middle = self.ctx.height // 2
        self.centred(img, middle - 1, "FINDING ISS", self.accent, outline=(0, 0, 0))
        self.centred(img, middle + 6, dots, GREY, outline=(0, 0, 0))
        return img


class Map(_Base):
    """The world, day and night, with the station and the path it has flown this orbit."""
    defaults = {"land": "#2E7D4F", "trail": True, "show_position": True}
    basic = ("land", "trail", "show_position")

    def setup(self):
        super().setup()
        self._ground, self._ground_minute = None, None

    def xy(self, lon, lat):
        w, h = self.ctx.width, self.ctx.height
        return min(w - 1, int((lon + 180) / 360 * w)), min(h - 1, int((90 - lat) / 180 * h))

    def ground(self, now):
        """The land and sea, shaded by where it's day; redrawn once a minute."""
        minute = int(now.timestamp() // 60)
        if self._ground is None or minute != self._ground_minute:
            w, h = self.ctx.width, self.ctx.height
            sun = world.sun_over(world.as_utc(now))
            land_day, land_night = rgb(self.settings["land"]), rgb(self.settings["land"], 0.3)
            img = self.ctx.canvas()
            px = img.load()
            for y in range(h):
                lat = 90 - (y + 0.5) / h * 180
                for x in range(w):
                    lon = (x + 0.5) / w * 360 - 180
                    day = world.in_daylight(lon, lat, sun)
                    if world.is_land(lon, lat):
                        px[x, y] = land_day if day else land_night
                    else:
                        px[x, y] = (0, 9, 22) if day else (0, 2, 7)
            self._ground, self._ground_minute = img, minute
        return self._ground.copy()

    def render(self, now):
        img = self.ground(now)
        fix, fresh = self.fix()
        if fix is None:
            return self.waiting(img, now)
        px = img.load()
        if self.settings["trail"]:
            points = FEED.trail[:-1]
            for k, (_, lon, lat) in enumerate(points):
                x, y = self.xy(lon, lat)
                fade = 0.25 + 0.5 * (k + 1) / len(points)
                px[x, y] = tuple(int(c * fade) for c in self.accent)
        x, y = self.xy(fix["lon"], fix["lat"])
        beat = now.timestamp() % 1.5 / 1.5          # a slow pulse, from the clock so a frame can be redrawn
        arm = self.accent if fresh else GREY
        if beat < 0.6:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if 0 <= x + dx < self.ctx.width and 0 <= y + dy < self.ctx.height:
                    px[x + dx, y + dy] = arm
        px[x, y] = WHITE if fresh else GREY
        if self.settings["show_position"] and self.ctx.height >= 16:   # (a very short canvas keeps its map)
            text = place(fix["lat"], fix["lon"]) if fresh else "NO SIGNAL"
            # in the corner away from the station, so the label never sits on it
            left = x > self.ctx.width // 2
            tx = 1 if left else self.ctx.width - self.small.width(text) - 1
            self.small.draw(img, tx, self.ctx.height - 1, text, WHITE if fresh else GREY, outline=(0, 0, 0))
        return img


class Readout(_Base):
    """The numbers: where it is, how high, how fast, and whether it's in sunlight."""
    fps = 4

    def render(self, now):
        img = self.ctx.canvas()
        fix, fresh = self.fix()
        if fix is None:
            return self.waiting(img, now)
        value = WHITE if fresh else GREY
        speed = f"{thousands(fix['kmh'] * 0.621371)} MPH" if self.miles else f"{thousands(fix['kmh'])} KM/H"
        rows = [("ISS", "SUNLIT" if fix["sunlit"] else "IN SHADOW"),
                ("LAT", f"{abs(fix['lat']):.1f} {'N' if fix['lat'] >= 0 else 'S'}"),
                ("LON", f"{abs(fix['lon']):.1f} {'E' if fix['lon'] >= 0 else 'W'}"),
                ("UP", self.length(fix["km"])),
                ("AT", speed)]
        if not fresh:
            rows[0] = ("ISS", "NO SIGNAL")
        step = 6
        rows = rows[:max(1, self.ctx.height // step)]            # a short canvas shows the first lines
        top = (self.ctx.height - len(rows) * step) // 2 + step - 1
        for k, (label, text) in enumerate(rows):
            baseline = top + k * step
            self.small.draw(img, 1, baseline, label, self.accent)
            self.small.draw(img, max(17, self.ctx.width - self.small.width(text) - 1), baseline, text, value)
        return img


class Distance(_Base):
    """How far the station is from your Matrix, and which way: a small radar and two lines of words.
    Uses the place set in the Matrix's Settings (nothing is sent anywhere: the sum is done here)."""
    fps = 10

    def render(self, now):
        img = self.ctx.canvas()
        home = getattr(self.ctx, "home", None) or {}
        if not isinstance(home.get("latitude"), (int, float)) or not isinstance(home.get("longitude"), (int, float)):
            middle = self.ctx.height // 2
            self.centred(img, middle - 1, "SET YOUR PLACE", GREY)
            self.centred(img, middle + 6, "IN SETTINGS", GREY)
            return img
        fix, fresh = self.fix()
        if fix is None:
            return self.waiting(img, now)
        km, bearing = world.km_between(home["latitude"], home["longitude"], fix["lat"], fix["lon"])
        near = km <= IN_RANGE_KM and fresh
        lines = [("NEAR YOU" if near else "THE ISS", self.accent if near else GREY),
                 (self.length(km), WHITE if fresh else GREY),
                 (f"TO THE {POINTS[round(bearing / 45) % 8]}" if fresh else "NO SIGNAL", GREY)]
        words = max(self.small.width(text) for text, _ in lines)
        # the radar: you in the middle, north up, the edge 10,000 km away (left out where there's no room for it)
        r = min(self.ctx.height // 2 - 4, (self.ctx.width - words - 5) // 2)
        left = 0
        if r >= 5:
            cx, cy = r + 1, self.ctx.height // 2
            draw = ImageDraw.Draw(img)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=DIM)
            draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], outline=(60, 64, 72))
            sweep = now.timestamp() % 4 / 4 * 2 * math.pi
            draw.line([cx, cy, cx + round(r * math.sin(sweep)), cy - round(r * math.cos(sweep))], fill=(40, 90, 70))
            img.putpixel((cx, cy), GREY)
            reach = min(1.0, km / 10000) * (r - 1)
            bx, by = cx + round(reach * math.sin(math.radians(bearing))), cy - round(reach * math.cos(math.radians(bearing)))
            blink = now.timestamp() % 1 < 0.6
            img.putpixel((bx, by), (WHITE if blink or not near else self.accent) if fresh else GREY)
            left = cx + r + 3
        # the words, to the right of it (or in the middle, on their own)
        step = 7 if self.ctx.height >= 21 else 6
        lines = lines[:max(1, self.ctx.height // step)]
        top = (self.ctx.height - len(lines) * step) // 2 + 6
        for k, (text, colour) in enumerate(lines):
            x = left if left else max(0, (self.ctx.width - self.small.width(text)) // 2)
            self.small.draw(img, x, top + k * step, text, colour)
        return img
