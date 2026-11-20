"""A small map of the world, and where the sun is over it.

The land is 32 rows of 64 columns (each 5.625 degrees), written as the columns that are land in
each row, top (north) to bottom. Coarse on purpose: it is drawn at one LED per cell.
"""
import datetime as dt
import math

COLS, ROWS = 64, 32
LAND = [
    [],                                                       # 87N
    [(15, 19), (22, 27)],                                     # 82N  Ellesmere, north Greenland
    [(11, 18), (20, 28), (35, 35), (42, 51)],                 # 76N  Arctic islands, Greenland, Svalbard, Taymyr
    [(3, 18), (22, 27), (35, 63)],                            # 70N  Alaska, Canada, Greenland, Norway to Siberia
    [(2, 20), (23, 25), (28, 29), (34, 63)],                  # 65N  Iceland too
    [(3, 6), (9, 14), (18, 21), (31, 31), (33, 61)],          # 59N  Hudson Bay open, Scotland
    [(9, 21), (30, 31), (33, 58), (60, 60)],                  # 53N  British Isles, Kamchatka
    [(10, 21), (31, 56), (57, 57)],                           # 48N
    [(10, 19), (30, 32), (34, 36), (38, 55), (57, 57)],       # 42N  Spain, Italy and the Balkans, Asia, Hokkaido
    [(10, 18), (31, 33), (36, 39), (40, 53), (54, 54), (56, 57)],   # 37N  Korea, Japan
    [(11, 17), (30, 42), (43, 53)],                           # 31N
    [(13, 14), (17, 17), (29, 41), (43, 47), (48, 53)],       # 25N  Mexico, Florida, Sahara, Arabia, India
    [(13, 16), (18, 19), (29, 38), (39, 41), (45, 47), (49, 51), (53, 53)],   # 20N
    [(16, 17), (29, 39), (40, 40), (45, 46), (49, 51), (53, 54)],   # 14N
    [(17, 21), (30, 40), (46, 46), (50, 50), (54, 54)],       # 8N
    [(18, 23), (34, 39), (49, 50), (52, 53)],                 # 3N   Sumatra, Borneo
    [(18, 25), (34, 39), (50, 50), (52, 53), (55, 57)],       # 3S   New Guinea
    [(18, 25), (34, 38), (51, 52), (57, 58)],                 # 8S   Java
    [(19, 25), (34, 38), (40, 40), (54, 57)],                 # 14S  Madagascar, north Australia
    [(20, 24), (34, 38), (40, 40), (52, 58)],                 # 20S
    [(20, 23), (34, 37), (52, 59)],                           # 25S
    [(20, 22), (35, 37), (52, 59)],                           # 31S
    [(20, 21), (56, 58), (62, 63)],                           # 37S  New Zealand
    [(19, 20), (58, 58), (62, 62)],                           # 42S  Tasmania
    [(19, 20)],                                               # 48S  Patagonia
    [(19, 19)],                                               # 53S  Tierra del Fuego
    [],                                                       # 59S
    [(20, 21), (39, 58)],                                     # 65S  the Antarctic Peninsula and coast
    [(3, 21), (28, 61)],                                      # 70S
    [(0, 63)], [(0, 63)], [(0, 63)],                          # Antarctica
]
_GRID = [[any(a <= c <= b for a, b in row) for c in range(COLS)] for row in LAND]


def is_land(lon, lat):
    col = min(COLS - 1, max(0, int((lon + 180) / 360 * COLS)))
    row = min(ROWS - 1, max(0, int((90 - lat) / 180 * ROWS)))
    return _GRID[row][col]


def sun_over(utc):
    """(latitude, longitude) of the point the sun is straight above, near enough for shading a map."""
    day = utc.timetuple().tm_yday
    hours = utc.hour + utc.minute / 60 + utc.second / 3600
    return 23.44 * math.sin(2 * math.pi * (day - 81) / 365), ((12 - hours) * 15 + 180) % 360 - 180


def in_daylight(lon, lat, sun):
    a, b = math.radians(lat), math.radians(sun[0])
    return math.sin(a) * math.sin(b) + math.cos(a) * math.cos(b) * math.cos(math.radians(lon - sun[1])) > 0


def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance, and the compass bearing from the first place to the second."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    bearing = math.degrees(math.atan2(math.sin(dl) * math.cos(p2),
                                      math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)))
    return 12742 * math.asin(min(1, math.sqrt(a))), bearing % 360


def as_utc(now):
    return now.astimezone(dt.timezone.utc) if now.tzinfo else now
