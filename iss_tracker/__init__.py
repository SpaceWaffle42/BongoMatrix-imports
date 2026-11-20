"""ISS Tracker for Bongo Matrix: where the International Space Station is right now.

Three looks: a world map with the station and its trail, a plain read-out of its position, height
and speed, and how far it is from where your Matrix is. Positions come from api.wheretheiss.at
(free, no account), asked for every few seconds on a background thread so a slow answer never
holds up the panel.
"""
from bongo.module import Module

from .styles import Distance, Map, Readout

__version__ = "1.0.0"

MODULE = Module(
    id="iss_tracker",
    name="ISS Tracker",
    description="Where the International Space Station is right now.",
    styles={"map": Map, "readout": Readout, "distance": Distance},
    defaults={
        "colour": "#7FD4FF",   # the station, and the headings
        "miles": False,        # miles and mph instead of km and km/h
        "refresh": 15,         # seconds between positions
    },
    limits={"refresh": (5, 120)},
    basic=("colour", "miles"),
)
