"""Sports for Bongo Matrix: ten sports, and a tracker for the Olympics and Paralympics.

A module you import (Settings > Modules > Import): none of it is part of the Matrix itself. Each Sports screen
follows one thing: a team (Football, Cricket, Rugby union, American football, Basketball, Ice hockey, Baseball),
the Formula 1 championship, or a tennis or golf tour. The Games screen counts down to the next Olympics and
Paralympics. Scores come from services you have your own key for (football-data.org, TheSportsDB Premium) or
that need none (Jolpica-F1): no key is shipped with this module and nothing is scraped. README.md says what each
service gives on which plan.

    sports.py    the ten sports and the tours
    sources.py   football-data.org and TheSportsDB (team sports), each read into the same plain shapes
    f1.py        Formula 1 from Jolpica-F1
    tours.py     tennis and golf tours from TheSportsDB
    feed.py      fetching in the background, politely, with a cache in the module's working folder
    board.py     the Sports screen: which frame to show now, and when to ask to keep the panel
    racing.py    its Formula 1 and tour views
    games.py     the Olympics and Paralympics tracker (bundled dates, no key)
    draw.py      the frames; art.py and art/ the pictures, made in the Animator
    example.py   a made-up match for the preview before a football screen is set up
"""
from bongo.module import Module

from .board import Board
from .games import Games
from .sources import SOURCES
from .sports import SPORTS, TOURS

__version__ = "2.0.0"

FREE_LEAGUES = "Premier League, Championship, Bundesliga, Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga, Brazil's Serie A"

HELP = {
    "title": "Set up Sports",
    "intro": "Each Sports screen follows one thing: a team, the Formula 1 championship, or a tennis or golf tour. "
             "Add one screen for each thing you follow; the playlist takes them in turn. The Games screen style counts down "
             "to the next Olympics and Paralympics and needs nothing set up.",
    "steps": [
        "Add a Sports screen to the playlist and open it. Pick the sport under Sport.",
        "Football: pick your source. football-data.org is free for the top leagues: " + FREE_LEAGUES + ". "
        "TheSportsDB covers nearly every league and needs its Premium key. Register at football-data.org (free): your key, "
        "which it calls an API token, comes by email. Paste it under Key.",
        "Cricket, Rugby union, Tennis, Golf, American football, Basketball, Ice hockey and Baseball need TheSportsDB Premium "
        "(a flat monthly fee, not a charge per request). Subscribe on thesportsdb.com, copy the API key from your profile there, "
        "and paste it under Premium key. Its free key is a shared test key with one fixture per answer: it isn't enough, so it isn't offered.",
        "Formula 1 needs no key: it comes from Jolpica-F1, which is free.",
        "Keys are kept on the Matrix, entered once for every Sports screen, and never shown again. Each is only ever sent to "
        "its own service: Key to football-data.org, Premium key to TheSportsDB.",
        "Upgrading from Sports 1.x with your screens on TheSportsDB? Your 1.x TheSportsDB key is still under Key, which 2.0 only sends to football-data.org: paste it under Premium key, then clear Key (or put your football-data.org key there). Until then those screens say NEEDS A KEY and fetch nothing.",
        "For a team sport, type your team under Team, as TheSportsDB or football-data.org spells it (`Arsenal`, `England`), "
        "or its number there. The preview shows the team it found: if that is the wrong one, type more of the name.",
        "For tennis or golf, pick the tour under Tour (ATP or WTA, PGA Tour or DP World Tour). For Formula 1, tennis or golf, "
        "type a driver or player under Highlight to have them picked out when they appear (`NOR`, `Norris`, `Sinner`).",
        "Tick what to show. With Take over on, the screen stays up for the whole of a live match.",
    ],
    "tips": [
        "Live scores: football (TheSportsDB, or football-data.org's paid Livescores plan), American football, basketball, "
        "ice hockey and baseball, about every two minutes. Cricket, rugby union, tennis, golf and Formula 1 have no live "
        "scores from these sources: fixtures and results only, and the screen says so.",
        "Tables: football with football-data.org, and Formula 1's drivers' standings. TheSportsDB's tables need its old "
        "address with the key in it, so this module doesn't use them.",
        "Tennis and golf: the current or next tournament and its winner, as TheSportsDB records them. No world rankings: "
        "there is no free, documented source for them.",
        "Formula 1: the next race with a countdown, the last podium and the drivers' standings. No live timing.",
        "The Games: LA 2028 and the French Alps 2030 winter Games. The 2030 dates are still called proposed, so they may move.",
        "Take over starts when the Sports screen's turn next comes round in the playlist, then stays until full time. It "
        "never runs in the sleep hours, and Next still moves on. It only works for sports with live scores.",
        "KEY REFUSED on the panel: copy the key again, whole. NOT IN PLAN: the team's league isn't covered by your key.",
        "No club badges, league logos, Olympic rings or Paralympic symbols are shown, by design.",
    ],
    "links": [
        {"label": "Register at football-data.org", "url": "https://www.football-data.org/client/register"},
        {"label": "What football-data.org's plans cover", "url": "https://www.football-data.org/coverage"},
        {"label": "TheSportsDB's plans", "url": "https://www.thesportsdb.com/pricing"},
        {"label": "Jolpica-F1", "url": "https://github.com/jolpica/jolpica-f1"},
    ],
    "required": True,
}

SETTINGS = dict(
    id="sports",
    name="Sports",
    description="Ten sports: your team, Formula 1, or a tennis or golf tour, plus an Olympics and Paralympics countdown. "
                "Some need your own key from football-data.org or TheSportsDB.",
    styles={"scoreboard": Board, "games": Games},
    defaults={"key": "", "premium_key": ""},
    choice_names={
        "sport": {"labels": {k: v["name"] for k, v in SPORTS.items()}},
        "tour": {"labels": {k: v["name"] for k, v in TOURS.items()}},
        "show": {"labels": {"next": "Next match or race", "live": "Live score", "result": "Result", "table": "Table or standings"}},
        "source": {"labels": {"football_data": "football-data.org", "thesportsdb": "TheSportsDB"}},
        "games": {"labels": {"both": "Olympics and Paralympics", "olympics": "Olympics", "paralympics": "Paralympics"}},
        "season": {"labels": {"both": "Summer and winter", "summer": "Summer", "winter": "Winter"}},
    },
    help=HELP,
)

# What a newer Matrix adds, asked for only where it has it, so this still imports on an older one:
# without ``notes`` the lines under the settings are missing (Help has them); without ``secrets`` the keys are
# ordinary text settings of each screen, shown as typed; ``take_over`` needs a Matrix that knows ``Style.stay``
# (an older one ignores it and the screen simply has its usual seconds).
if "notes" in Module.__dataclass_fields__:
    SETTINGS["notes"] = {
        "sport": "One sport a screen. Formula 1 needs no key. Football needs a free football-data.org key or TheSportsDB Premium. "
                 "Every other sport needs TheSportsDB Premium (a flat monthly fee), and says so until it has it.",
        "team": "Team sports: your team's name as the source spells it, or its number there. The preview shows the team it found.",
        "tour": "Tennis: ATP Tour or WTA Tour. Golf: PGA Tour or DP World Tour. The current or next tournament, then its winner. "
                "A tour of the other sport is taken as the sport's first.",
        "highlight": "Optional. Formula 1: a driver to pick out in the podium and standings (NOR, Norris). "
                     "Tennis and golf: a player to pick out when they appear. Picked out in light blue, with a > or a band.",
        "show": "Live score: football, American football, basketball, ice hockey and baseball only. Table: football with "
                "football-data.org, and Formula 1's standings. Cricket, rugby union, tennis and golf: fixtures and results only.",
        "take_over": "Take over the panel during a live match (not in the sleep hours), for sports with live scores. An imported "
                     "module only runs on its turn: it starts when this screen next comes round in the playlist, then stays until full time.",
        "source": "Football only. football-data.org: free, top leagues only (see Help for which), scores delayed on the free plan. "
                  "TheSportsDB: nearly every league, but it needs its Premium key (a flat monthly fee, not per request).",
        "key": "Your football-data.org key (it calls it an API token), and only that: it is only ever sent to football-data.org. "
               "Entered once for every Sports screen.",
        "premium_key": "Your TheSportsDB Premium key, for every sport but Formula 1 (and football on football-data.org). "
                       "Upgrading from Sports 1.x on TheSportsDB? Your 1.x TheSportsDB key is still under Key, which 2.0 only sends to football-data.org: paste it under Premium key, then clear Key (or put your football-data.org key there).",
        "games": "Which Games to count down to. No key needed: the dates come with this module. No live medal table: "
                 "there is no free, documented source for one.",
        "season": "Summer (LA 2028), winter (French Alps 2030: dates to be confirmed, still called proposed), or both.",
    }
if "secrets" in Module.__dataclass_fields__:
    SETTINGS["secrets"] = ("key", "premium_key")

MODULE = Module(**SETTINGS)
