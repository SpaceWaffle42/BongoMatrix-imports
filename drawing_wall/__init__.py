"""Drawing wall: draw on the panel from your phone, live. Anyone with a paired phone or computer opens the module's
page on the dashboard and draws with a finger; several can draw at once, every dot shows on the panel (and on the
other phones) as it's drawn, and Send keeps a drawing in the wall's history (and pops it up, if the owner wants).

An imported module (docs/MODULES.md in the Matrix, "Pop-ups in a look of your own, and a page on the dashboard"):
the background task hears the page and keeps the wall; the screens draw it."""
import bongo.module

if getattr(bongo.module, "API", 1) < 3:
    raise ImportError("This module needs a newer Matrix: update it in Settings > Software, then import it again.")

from bongo.module import Module  # noqa: E402

from .screens import HistoryScreen, LiveLook, SentLook, WallScreen  # noqa: E402
from .task import Task  # noqa: E402

MODULE = Module(
    id="drawing_wall", name="Drawing wall",
    styles={"wall": WallScreen, "history": HistoryScreen, "live": LiveLook, "sent": SentLook},
    background=Task,
    description="Draw on the panel from your phone, live: several phones at once, a history of the last few, "
                "and a pop-up when one is sent if you like.",
)
