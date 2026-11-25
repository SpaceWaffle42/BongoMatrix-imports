"""The wall itself: what is drawn on it now, who drew which line (so each phone's Undo takes back only its own), and
the last few drawings sent. Plain data: no panel and no page. task.py feeds it what the phones send, the screens
draw it, and it is kept in a file in the module's working folder (the only place it may write), so a restart
doesn't lose the drawing."""
from __future__ import annotations

import json
import os
import re

# The nine colours, fixed (the council: 4-0). 0 is nothing: the eraser, and every dot nobody has drawn.
PALETTE = [None, (242, 238, 230), (255, 74, 74), (255, 154, 46), (255, 216, 74), (90, 208, 74), (74, 200, 255),
           (90, 108, 255), (176, 122, 255), (255, 122, 200)]
# The colour each new person's name and pen take, in the order they first draw: the ones that read best as a name.
PEOPLE = (3, 9, 6, 5, 8, 4, 2, 7, 1)

SIZE = (64, 32)        # until a screen of the module has been drawn and so knows the panel's size
MOST_SIDE = 256        # a panel bigger than this each way isn't one (a wall that size would be no use anyway)
MOST_OPS = 400         # lines kept apart for Undo; older ones are folded into the wall underneath
MOST_DOTS = 4000       # dots in one line before it carries on as a new one (a scribble that never lifts off)
FILE = "wall.json"


def short_name(name: str) -> str:
    """What the panel calls someone: the first word of the name their browser was paired with, without an "'s"
    ("Billy's phone" is BILLY, "Mum" is MUM), in capitals, at most 8 letters."""
    word = (str(name or "").split() or ["SOMEONE"])[0]
    word = re.sub(r"['’]s$", "", word, flags=re.I) or word
    return word.upper()[:8]


def encode(grid: bytes | bytearray) -> str:
    """A picture as text for a page: each dot as its colour's digit, or, when that is shorter (most drawings are
    mostly empty), as runs: a letter for the colour (a is nothing, b to j the nine) and how many, if more than one."""
    raw = "".join("0123456789"[v] for v in grid)
    runs, k = [], 0
    while k < len(grid):
        e = k
        while e + 1 < len(grid) and grid[e + 1] == grid[k]:
            e += 1
        n = e - k + 1
        runs.append("abcdefghij"[grid[k]] + (str(n) if n > 1 else ""))
        k = e + 1
    packed = "".join(runs)
    return packed if len(packed) < len(raw) else raw


def decode(text: str, size: int) -> bytearray:
    """``encode`` turned back; anything that isn't a picture of ``size`` dots raises ValueError."""
    if not isinstance(text, str):
        raise ValueError("not a picture")
    if text[:1].isdigit() or not text:
        out = bytearray(int(c) for c in text) if text.isdigit() else None
    else:
        out = bytearray()
        for letter, count in re.findall(r"([a-j])(\d*)", text):
            out.extend(bytes([ord(letter) - 97]) * (int(count) if count else 1))
            if len(out) > size:
                break
        if "".join(a + b for a, b in re.findall(r"([a-j])(\d*)", text)) != text:
            out = None
    if out is None or len(out) != size:
        raise ValueError("not a picture of the wall's size")
    return out


def fit(grid: bytes, w: int, h: int, nw: int, nh: int) -> bytearray:
    """A picture of ``w`` x ``h`` put in the middle of one of ``nw`` x ``nh`` (cut at the edges if it's bigger)."""
    out = bytearray(nw * nh)
    dx, dy = (nw - w) // 2, (nh - h) // 2
    for y in range(h):
        ny = y + dy
        if 0 <= ny < nh:
            for x in range(w):
                nx = x + dx
                if 0 <= nx < nw and grid[y * w + x]:
                    out[ny * nw + nx] = grid[y * w + x]
    return out


class Wall:
    """The drawing on the wall now: ``base`` (what is no longer kept apart for Undo) with ``ops`` on top, each a
    line ({"k": "line", "by", "id", "c", "w", "p": [x, y, x, y...]}), a clear ({"k": "clear", "by"}) or a picture
    put back from the history ({"k": "set", "by", "g"}). ``grid`` is the result, kept up to date as dots come."""

    def __init__(self, w: int = SIZE[0], h: int = SIZE[1]):
        self.w, self.h = w, h
        self.base = bytearray(w * h)
        self.base_drawers: list[list[str]] = []   # who drew what is in ``base``: [[device, name], ...]
        self.grid = bytearray(w * h)
        self.ops: list[dict] = []
        self.open: dict[tuple, dict] = {}      # (device, line id) -> its op, while it may still get dots
        self.history: list[dict] = []          # newest first: {"id", "who", "by", "at", "w", "h", "g"}
        self.colours: dict[str, int] = {}      # device -> its colour (a PALETTE index), in the order they drew
        self.last: dict | None = None          # who drew last, and when: {"who", "by", "at"}
        self.next_id = 1
        self.changed = 0                       # counts every change, so whoever keeps a copy knows it's out of date

    # -- drawing ----------------------------------------------------------------------------------------------------
    def colour_of(self, device: str) -> int:
        if device not in self.colours:
            self.colours[device] = PEOPLE[len(self.colours) % len(PEOPLE)]
        return self.colours[device]

    def _dot(self, grid: bytearray, x: int, y: int, c: int, width: int) -> None:
        for b in range(width):
            for a in range(width):
                if 0 <= x + a < self.w and 0 <= y + b < self.h:
                    grid[(y + b) * self.w + x + a] = c

    def _apply(self, grid: bytearray, op: dict) -> None:
        if op["k"] == "clear":
            grid[:] = bytes(len(grid))
        elif op["k"] == "set":
            grid[:] = op["g"]
        else:
            p, c, width = op["p"], op["c"], op["w"]
            for k in range(0, len(p), 2):
                self._dot(grid, p[k], p[k + 1], c, width)

    @staticmethod
    def _drew(drawers: list, op: dict) -> list:
        """Who has drawn on the wall, after ``op``: a clear starts afresh, a picture put back brings its own."""
        if op["k"] == "clear":
            return []
        if op["k"] == "set":
            return [list(d) for d in op["drawers"]]
        if op["c"] and op["p"] and not any(d[0] == op["by"] for d in drawers):
            return drawers + [[op["by"], op["who"]]]
        return drawers

    def drawers(self) -> list[list[str]]:
        """Everyone who drew on the wall as it stands, first to draw first: [[device, name], ...]."""
        out = [list(d) for d in self.base_drawers]
        for op in self.ops:
            out = self._drew(out, op)
        return out

    def _add(self, op: dict) -> dict:
        self.ops.append(op)
        while len(self.ops) > MOST_OPS:                      # the oldest can't be undone any more: into the base
            old = self.ops.pop(0)
            self._apply(self.base, old)
            self.base_drawers = self._drew(self.base_drawers, old)
            self.open = {k: v for k, v in self.open.items() if v is not old}
        self.changed += 1
        return op

    def dots(self, device: str, who: str, line: int, c: int, width: int, points: list[int], at: float) -> list[int]:
        """Dots of one line from one phone (``points`` x, y, x, y...; off the wall is left out). Returns the
        ones kept, for the other phones and the panel."""
        kept = [v for k in range(0, len(points) - 1, 2) for v in points[k:k + 2]
                if 0 <= points[k] < self.w and 0 <= points[k + 1] < self.h]
        if not kept:
            return []
        op = self.open.get((device, line))             # (an op leaves ``open`` whenever it leaves ``ops``)
        if op is None or op["c"] != c or op["w"] != width or len(op["p"]) >= 2 * MOST_DOTS:
            op = self._add({"k": "line", "by": device, "who": who, "id": line, "c": c, "w": width, "p": []})
            self.open[(device, line)] = op
        op["p"].extend(kept)
        for k in range(0, len(kept), 2):
            self._dot(self.grid, kept[k], kept[k + 1], c, width)
        self.changed += 1
        self.colour_of(device)
        if c:
            self.last = {"who": who, "by": device, "at": at}
        return kept

    def stamp(self, device: str, who: str, c: int, points: list[int], at: float) -> list[int]:
        """Dots that go on all at once (words written in the Matrix's own letters): one line of their own, so Undo
        takes them back together."""
        line = -self.next_id
        self.next_id += 1
        kept = self.dots(device, who, line, c, 1, points, at)
        self.open.pop((device, line), None)
        return kept

    def _redo(self) -> None:
        self.grid = bytearray(self.base)
        for op in self.ops:
            self._apply(self.grid, op)
        self.changed += 1

    def undo(self, device: str) -> bool:
        """Takes back the last thing this phone did (a line, its words, a clear or a picture put back). Other
        phones' lines stay."""
        for k in range(len(self.ops) - 1, -1, -1):
            if self.ops[k]["by"] == device:
                gone = self.ops.pop(k)
                self.open = {key: v for key, v in self.open.items() if v is not gone}
                self._redo()
                return True
        return False

    def clear(self, device: str) -> bool:
        if not any(self.grid):
            return False
        self._add({"k": "clear", "by": device})
        self.open.clear()
        self.grid = bytearray(len(self.grid))
        return True

    def empty(self) -> bool:
        return not any(self.grid)

    # -- the history --------------------------------------------------------------------------------------------
    def send(self, device: str, who: str, at: float, keep: int) -> dict | None:
        """Keeps the wall as it stands in the history, newest first, at most ``keep``. None if it's empty."""
        if self.empty():
            return None
        item = {"id": self.next_id, "who": who, "by": device, "at": at, "w": self.w, "h": self.h, "g": bytes(self.grid),
                "drawers": self.drawers()}
        self.next_id += 1
        self.history.insert(0, item)
        self.trim(keep)
        self.changed += 1
        return item

    def trim(self, keep: int) -> bool:
        if len(self.history) > keep:
            del self.history[keep:]
            self.changed += 1
            return True
        return False

    def put_back(self, device: str, item_id: int) -> bool:
        """A drawing from the history back up on the wall (in the middle, if the panel has changed size since)."""
        item = next((i for i in self.history if i["id"] == item_id), None)
        if item is None:
            return False
        self._add({"k": "set", "by": device, "g": fit(item["g"], item["w"], item["h"], self.w, self.h),
                   "drawers": item.get("drawers") or [[item["by"], item["who"]]]})
        self.open.clear()
        self._redo()
        return True

    def keep_unsent(self, at: float, keep: int) -> None:
        """Before the wall clears itself: a drawing that was never sent goes in the history first."""
        if not self.empty() and not (self.history and self.history[0]["g"] == bytes(self.grid)
                                     and (self.history[0]["w"], self.history[0]["h"]) == (self.w, self.h)):
            last = self.last or {"who": "", "by": ""}
            self.send(last["by"], last["who"], at, keep)

    # -- the panel's size ---------------------------------------------------------------------------------------
    def resize(self, w: int, h: int) -> bool:
        """The panel is another size than the wall: the drawing moves to the middle of a wall of the new size, and
        what was kept apart for Undo is folded in (a new panel is rare)."""
        if (w, h) == (self.w, self.h) or not (1 <= w <= MOST_SIDE and 1 <= h <= MOST_SIDE):
            return False
        self.grid = fit(self.grid, self.w, self.h, w, h)
        self.base = bytearray(self.grid)
        self.base_drawers = self.drawers()
        self.w, self.h = w, h
        self.ops.clear()
        self.open.clear()
        self.changed += 1
        return True

    # -- kept in a file -----------------------------------------------------------------------------------------
    def to_json(self) -> dict:
        return {"w": self.w, "h": self.h, "g": encode(self.grid), "drawers": self.drawers(), "colours": self.colours, "last": self.last,
                "next_id": self.next_id,
                "history": [{**i, "g": encode(i["g"])} for i in self.history]}

    @classmethod
    def from_json(cls, data: dict) -> "Wall":
        wall = cls(int(data["w"]), int(data["h"]))
        wall.grid = decode(data["g"], wall.w * wall.h)
        wall.base = bytearray(wall.grid)
        wall.base_drawers = [[str(d), str(n)] for d, n in data.get("drawers") or []]
        wall.colours = {str(k): int(v) for k, v in dict(data.get("colours") or {}).items() if int(v) in PEOPLE}
        last = data.get("last")
        wall.last = {"who": str(last["who"]), "by": str(last["by"]), "at": float(last["at"])} if isinstance(last, dict) else None
        wall.next_id = int(data.get("next_id", 1))
        for i in data.get("history") or []:
            wall.history.append({"id": int(i["id"]), "who": str(i["who"]), "by": str(i["by"]), "at": float(i["at"]),
                                 "w": int(i["w"]), "h": int(i["h"]), "g": bytes(decode(i["g"], int(i["w"]) * int(i["h"]))),
                                 "drawers": [[str(d), str(n)] for d, n in i.get("drawers") or []]})
        return wall


def load(path: str = FILE) -> Wall:
    """The kept wall, or an empty one if there's none or it can't be read."""
    try:
        with open(path, encoding="utf-8") as f:
            return Wall.from_json(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return Wall()


def save(wall: Wall, path: str = FILE) -> None:
    """Written whole, then swapped in, so a stop half-way never leaves half a file."""
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as f:
        json.dump(wall.to_json(), f, separators=(",", ":"))
    os.replace(part, path)
