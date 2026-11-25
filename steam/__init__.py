"""Steam: what's happening on Steam, on the panel. Four screens: friends online (who's on and what they're playing),
now playing (the game's own capsule art from Steam across the top), recent games (the last two weeks, with hours) and
your newest achievement (its icon, the game, and how rare it is). A background task asks Steam's free Web API a little
at a time and shares what it finds with the screens; it can also pop up a short message, in a look of its own, when
a friend starts a game (off unless switched on). Set it up in Settings › Modules › Steam: a free Steam Web API key
and your profile link."""
import bongo.module

if getattr(bongo.module, "API", 1) < 3:
    raise ImportError("This module needs a newer Matrix: update it in Settings > Software, then import it again.")

from bongo.module import Module  # noqa: E402

from .popups import Started  # noqa: E402
from .screens import Achievement, Friends, NowPlaying, Recent  # noqa: E402
from .task import Watch  # noqa: E402

MODULE = Module(
    id="steam", name="Steam",
    styles={"friends": Friends, "now_playing": NowPlaying, "recent": Recent, "achievement": Achievement,
            "started": Started},          # (the pop-up's own look: only ever a pop-up)
    background=Watch,
    secrets=("api_key",),           # the key in its settings card: kept with the Matrix's secrets, never in a backup
    description="Friends online and what they're playing, the game's picture, your recent games and newest achievement.",
)
