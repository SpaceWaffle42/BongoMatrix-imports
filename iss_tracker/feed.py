"""The station's position, fetched in the background and shared by every screen of this module.

``FEED.ask(every)`` is all a screen calls: it starts the fetching thread if need be and returns at once.
``FEED.fix`` is the latest position (or None before the first answer), ``FEED.trail`` the path so far.
The thread rests when no screen has asked for a while, so a module that isn't on the panel asks for nothing.
"""
import json
import math
import threading
import time
import urllib.request

URL = "https://api.wheretheiss.at/v1/satellites/25544"
AGENT = "bongo-iss-tracker/1.0 (a Bongo Matrix module)"
TRAIL_FILE = "trail.json"      # in the module's working folder: the trail survives a restart
TRAIL_SECONDS = 92 * 60        # one orbit
IDLE_AFTER = 120               # s with no screen asking: stop fetching


class Feed:
    def __init__(self):
        self.fix = None            # {"lat", "lon", "km", "kmh", "sunlit", "at"}
        self.trail = []            # [(at, lon, lat)], oldest first
        self.problem = None        # why the last fetch failed, for the log
        self._every = 15
        self._asked = 0.0
        self._thread = None
        self._lock = threading.Lock()
        self._saved = 0.0
        self._load()

    # -- for the screens -----------------------------------------------------------------------
    def ask(self, every=15):
        self._every = max(5, min(120, int(every)))
        self._asked = time.monotonic()
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="iss-feed", daemon=True)
                self._thread.start()

    def fresh(self, now=None):
        """Is the latest position recent enough to trust?"""
        return self.fix is not None and (now or time.time()) - self.fix["at"] < self._every * 3 + 30

    # -- the thread ----------------------------------------------------------------------------
    def _run(self):
        while time.monotonic() - self._asked < IDLE_AFTER:
            try:
                self._take(self._fetch())
                self.problem = None
            except Exception as error:   # no network, a bad answer: keep the last position and try again
                if str(error) != self.problem:
                    print(f"iss_tracker: couldn't get the position ({error})", flush=True)
                self.problem = str(error)
            time.sleep(self._every)

    def _fetch(self):
        request = urllib.request.Request(URL, headers={"User-Agent": AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=8) as answer:
            data = json.loads(answer.read(20000))
        lat, lon = float(data["latitude"]), float(data["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("a position that isn't on Earth")
        km, kmh = float(data.get("altitude", 0)), float(data.get("velocity", 0))
        if not (math.isfinite(km) and math.isfinite(kmh)):
            raise ValueError("a height or speed that isn't a number")
        return {"lat": lat, "lon": lon, "km": km, "kmh": kmh,
                "sunlit": data.get("visibility") != "eclipsed", "at": time.time()}

    def _take(self, fix):
        self.fix = fix
        trail = [p for p in self.trail if 0 <= fix["at"] - p[0] < TRAIL_SECONDS]   # (0 <=: the clock may have been put back)
        trail.append((fix["at"], fix["lon"], fix["lat"]))
        self.trail = trail
        if fix["at"] - self._saved > 60:
            self._saved = fix["at"]
            try:
                with open(TRAIL_FILE, "w") as f:
                    json.dump([[round(a), round(lon, 2), round(lat, 2)] for a, lon, lat in trail], f)
            except OSError:
                pass   # nowhere to write: the trail just starts again after a restart

    def _load(self):
        try:
            with open(TRAIL_FILE) as f:
                saved = json.load(f)
            now = time.time()
            self.trail = [(float(a), float(lon), float(lat)) for a, lon, lat in saved
                          if 0 <= now - float(a) < TRAIL_SECONDS and -180 <= lon <= 180 and -90 <= lat <= 90]
        except (OSError, ValueError, TypeError):
            self.trail = []


FEED = Feed()
