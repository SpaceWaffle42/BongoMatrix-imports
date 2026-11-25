"""Parcels: your parcels on their way, on the panel. "Arrives today", "Out for delivery", "Delivered", with the
courier's name and a van driving along a route bar to the house; a pop-up when one is out for delivery and when it
has come, in a look of its own. Tracking from Ship24's free plan (10 new parcels a month), or DHL's and UPS's own
free keys for theirs.

An imported module (docs/MODULES.md in the Matrix, "Sharing a module"): a background task follows the parcels and
the one screen draws what it found."""
import bongo.module

if getattr(bongo.module, "API", 1) < 3:
    raise ImportError("This module needs a newer Matrix: update it in Settings > Software, then import it again.")

from bongo.module import Module  # noqa: E402

from .popups import Parcel  # noqa: E402
from .screen import Parcels  # noqa: E402
from .tracker import Tracker  # noqa: E402

SECRETS = ("ship24_key", "dhl_key", "ups_client_id", "ups_secret")

MODULE = Module(
    id="parcels", name="Parcels",
    styles={"parcels": Parcels, "parcel": Parcel},     # ("parcel": the pop-up's own look, only ever a pop-up)
    background=Tracker,
    description="Parcels on their way: arrives today, out for delivery, delivered.",
    **({"secrets": SECRETS} if "secrets" in Module.__dataclass_fields__ else {}),
)
