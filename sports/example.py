"""A made-up match, for the screen's preview before it has been set up (and the test screen at import): the
six frames of the design, with two teams that don't exist. Never shown on the panel itself."""
from . import draw

SECONDS = 3.0
HOME = {"id": "1", "name": "Northtown FC", "code": "NTH", "colours": ["#C81E28", "#FFFFFF"]}
AWAY = {"id": "2", "name": "Southport", "code": "STH", "colours": ["#1E5AC8", "#FAD228"]}
TABLE = [{"pos": 3, "id": "3", "code": "CTY", "points": 30}, {"pos": 4, "id": "1", "code": "NTH", "points": 29},
         {"pos": 5, "id": "2", "code": "STH", "points": 27}, {"pos": 6, "id": "4", "code": "WST", "points": 26}]


def frames(ctx):
    return [
        lambda: draw.fixture(ctx, HOME, AWAY, ("SAT 21 NOV", "21 NOV"), "KO 15:00"),
        lambda: draw.scoreline(ctx, HOME, AWAY, [2, 1], "LIVE", draw.RED, ("GOAL 64' SMITH", "GOAL 64'"), draw.AMBER, minute="67'", dot=True),
        lambda: draw.scoreline(ctx, HOME, AWAY, [1, 1], "HALF TIME", draw.AMBER),
        lambda: draw.scoreline(ctx, HOME, AWAY, [3, 1], "FULL TIME", draw.GREEN, ("4TH IN TABLE", "4TH")),
        lambda: draw.table(ctx, TABLE, "1"),
        lambda: draw.fixture(ctx, HOME, AWAY, ("SAT 21 NOV", "21 NOV"), ("POSTPONED", "OFF"), draw.RED),
    ]
