"""Aquarium for Bongo Matrix: a tank of fish you can leave alone, or play with.

Two looks: Reef (bright fish, seaweed, bubbles) and Deep (dark water, things that glow).
When one look follows the other on the panel, the view sinks from the Reef down to the Deep (or rises
back up) instead of just switching.
Left alone the fish just swim, and food drops in by itself 8 times a day at random times (at least
45 minutes apart). From the dashboard you can feed them now (they gather round the food), tap the
glass (they dart away), and drop a fish in or let one swim off. None of it is needed: nothing gets
hungry and nothing has to be looked after.

Where to look:
- ``art.py``: the pictures, which are Animator projects in the ``art`` folder; ``sprites.py`` readies the fish;
  ``scenery.py`` puts the water, seabed, rocks and weed together for each size.
- ``world.py``: how the fish move (no drawing).
- ``tank.py``: drawing the two looks, and the dashboard's buttons (``act``).
- ``keep.py``: remembering which fish there are, and when food last dropped in, in a small file.
No internet.
"""
from bongo.module import Module

from .tank import Deep, Reef


__version__ = "2.5.0"

BUTTONS = {"feed": "Feed now", "tap": "Tap the glass", "add": "Add a fish", "remove": "Remove a fish"}

MODULE = Module(
    id="aquarium",
    name="Aquarium",
    description="A tank of fish to leave alone or play with: feed them, tap the glass, add or remove a fish.",
    styles={"reef": Reef, "deep": Deep},
    defaults={"fish": 5, "bubbles": True},   # (no feeding setting: food drops in by itself at random, tank.py)
    limits={"fish": (1, 10)},          # a count always gets a limit: 500 fish would stall the panel
    basic=("fish", "bubbles"),
    # buttons came with a later Matrix: on an older one the module still loads, without them
    **({"actions": BUTTONS} if "actions" in Module.__dataclass_fields__ else {}),
)
