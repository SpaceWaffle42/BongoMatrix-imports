"""The ten sports, and what "following" means in each.

    team          a team: next match, live score where the source has one, last result, the table where there is one
    championship  Formula 1: the next race, the last podium, the drivers' standings (Jolpica-F1, no key)
    tour          tennis and golf: a tour's current or next tournament, then its winner (TheSportsDB Premium)

Words: soccer is always "Football" here, and American football is always "American football" (the league can be
named NFL, the sport never). ``tsdb`` is the sport's name in TheSportsDB's answers (its ``strSport``), which is
never shown. ``live``: TheSportsDB Premium's live scores cover this sport (its pricing page lists "2 min livescore
(Soccer, NFL, NBA, MLB, NHL)", https://www.thesportsdb.com/pricing, read 23 Nov 2026).
"""

SPORTS = {
    "football": {"name": "Football", "words": ("FOOTBALL",), "kind": "team", "tsdb": "Soccer", "live": True},
    "cricket": {"name": "Cricket", "words": ("CRICKET",), "kind": "team", "tsdb": "Cricket", "live": False},
    "rugby_union": {"name": "Rugby union", "words": ("RUGBY UNION", "RUGBY"), "kind": "team", "tsdb": "Rugby", "live": False},
    "tennis": {"name": "Tennis", "words": ("TENNIS",), "kind": "tour", "tsdb": "Tennis", "tours": ("atp", "wta")},
    "formula_1": {"name": "Formula 1", "words": ("FORMULA 1", "F1"), "kind": "championship"},
    "golf": {"name": "Golf", "words": ("GOLF",), "kind": "tour", "tsdb": "Golf", "tours": ("pga", "dpwt")},
    "american_football": {"name": "American football", "words": ("AMERICAN FOOTBALL", "AMERICAN FTBL", "US FTBL"), "kind": "team", "tsdb": "American Football", "live": True},
    "basketball": {"name": "Basketball", "words": ("BASKETBALL",), "kind": "team", "tsdb": "Basketball", "live": True},
    "ice_hockey": {"name": "Ice hockey", "words": ("ICE HOCKEY", "HOCKEY"), "kind": "team", "tsdb": "Ice Hockey", "live": True},
    "baseball": {"name": "Baseball", "words": ("BASEBALL",), "kind": "team", "tsdb": "Baseball", "live": True},
}

# The tours, by their league numbers on TheSportsDB (its sport pages, read 23 Nov 2026:
# https://www.thesportsdb.com/sport/Tennis, https://www.thesportsdb.com/sport/Golf). TheSportsDB still files the
# DP World Tour under its old name, "European Tour" (league 4426).
TOURS = {
    "atp": {"name": "ATP Tour", "words": ("ATP TOUR", "ATP"), "league": "4464", "sport": "tennis"},
    "wta": {"name": "WTA Tour", "words": ("WTA TOUR", "WTA"), "league": "4517", "sport": "tennis"},
    "pga": {"name": "PGA Tour", "words": ("PGA TOUR", "PGA"), "league": "4425", "sport": "golf"},
    "dpwt": {"name": "DP World Tour", "words": ("DP WORLD TOUR", "DP WORLD"), "league": "4426", "sport": "golf"},
}


def tour_for(sport, tour):
    """The tour a screen follows: the one chosen if it is one of this sport's, else the sport's first."""
    tours = SPORTS.get(sport, {}).get("tours") or ()
    return tour if tour in tours else (tours[0] if tours else None)
