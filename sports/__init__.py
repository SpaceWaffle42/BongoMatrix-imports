"""Sports for Bongo Matrix: your football team's next match, live score, result and league table.

A module you import (Settings > Modules > Import): none of it is part of the Matrix itself. Football only, for
now. The scores come from a service you have your own key for, football-data.org or TheSportsDB: no key is
shipped with this module and nothing is scraped. README.md says what each service gives on which plan.

    sources.py   the two services, each read into the same plain shapes
    feed.py      fetching in the background, politely, with a cache in the module's working folder
    board.py     the screen: which frame to show now, and when to ask to keep the panel
    draw.py      the frames
    example.py   a made-up match for the preview before the screen is set up
"""
from bongo.module import Module

from .board import Board
from .sources import SOURCES

__version__ = "1.0.0"

FREE_LEAGUES = "Premier League, Championship, Bundesliga, Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga, Brazil's Serie A"

HELP = {
    "title": "Set up Sports",
    "intro": "Sports shows one football team: its next match, the live score, the result and the league table. "
             "The scores come from a service you have your own key for. Nothing is shown until a key and a team are set.",
    "steps": [
        "Pick your source. football-data.org is free for the top leagues: " + FREE_LEAGUES + ". "
        "TheSportsDB covers nearly every league, and needs its Premium key (a flat monthly fee, not a charge per request).",
        "For football-data.org: register at football-data.org (free). Your key, which it calls an API token, comes by email and is on your account page.",
        "For TheSportsDB: subscribe to Premium on thesportsdb.com, then copy the API key from your profile there.",
        "Add a Sports screen to the playlist and open it. Paste the key under Key and press Save. It is kept on the Matrix for every Sports screen and never shown again.",
        "Type your team's name under Team, as the source spells it (`Arsenal`, `Bayern`), or its number on the source. "
        "The preview shows the team it found: if that is the wrong one, type more of the name.",
        "Tick what to show. With Take over on, the screen stays up for the whole of a live match.",
    ],
    "tips": [
        "Live scores: football-data.org's free plan gives scores late (it calls them delayed). Live ones need its paid Livescores plan. TheSportsDB's update about every two minutes.",
        "The table comes from football-data.org only. With TheSportsDB the other views still show.",
        "Take over starts when the Sports screen's turn next comes round in the playlist, then stays until full time. It never runs in the sleep hours, and Next still moves on.",
        "KEY REFUSED on the panel: copy the key again, whole. NOT IN YOUR PLAN: the team's league isn't covered by your key.",
        "No club badges are shown, by design: a team is its three letters and its kit colours.",
    ],
    "links": [
        {"label": "Register at football-data.org", "url": "https://www.football-data.org/client/register"},
        {"label": "What football-data.org's plans cover", "url": "https://www.football-data.org/coverage"},
        {"label": "TheSportsDB's plans", "url": "https://www.thesportsdb.com/pricing"},
    ],
    "required": True,
}

SETTINGS = dict(
    id="sports",
    name="Sports",
    description="Your football team: next match, live score, result and table. Needs your own key from football-data.org or TheSportsDB.",
    styles={"scoreboard": Board},
    defaults={
        "team": "",
        "show": ["next", "live", "result", "table"],
        "take_over": False,
        "source": "football_data",
        "key": "",
    },
    choices={"show": ["next", "live", "result", "table"], "source": list(SOURCES)},
    choice_names={"show": {"labels": {"next": "Next match", "live": "Live score", "result": "Result", "table": "Table"}},
                  "source": {"labels": {"football_data": "football-data.org", "thesportsdb": "TheSportsDB"}}},
    help=HELP,
)

# What a newer Matrix adds, asked for only where it has it, so this still imports on an older one:
# without ``notes`` the lines under the settings are missing (Help has them); without ``secrets`` the key is an
# ordinary text setting of each screen, shown as typed; ``take_over`` needs a Matrix that knows ``Style.stay``
# (an older one ignores it and the screen simply has its usual seconds).
if "notes" in Module.__dataclass_fields__:
    SETTINGS["notes"] = {
        "team": "Your team's name as the source spells it, or its number there. The preview shows the team it found.",
        "show": "Live score: football-data.org's free plan gives scores late (it calls them delayed), live ones need its "
                "Livescores plan. Table: football-data.org only.",
        "take_over": "Take over the panel during a live match (not in the sleep hours). An imported module only runs on its turn: "
                     "it starts when this screen next comes round in the playlist, then stays until full time. Next still moves on.",
        "source": "A key of your own, entered once. football-data.org: free, top leagues only (see Help for which). "
                  "TheSportsDB: nearly every league, but it needs its Premium key (a flat monthly fee, not per request): "
                  "its free key is a test key everyone shares and gives too little. Football first: other sports need their own layouts.",
        "key": "The key for the source above. football-data.org calls it an API token.",
    }
if "secrets" in Module.__dataclass_fields__:
    SETTINGS["secrets"] = ("key",)

MODULE = Module(**SETTINGS)
