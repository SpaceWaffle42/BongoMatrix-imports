"""Which part of a round it is. Kept apart from the drawing so every look shares it (and it's easy to test)."""
from dataclasses import dataclass


@dataclass
class Phase:
    working: bool      # True in the focus part, False in the break
    left: int          # seconds until this part ends
    length: int        # how long this part is, in seconds

    @property
    def part_left(self) -> float:
        """1.0 at the start of the part, down to 0.0 at its end."""
        return self.left / self.length

    @property
    def clock(self) -> str:
        return f"{self.left // 60:02d}:{self.left % 60:02d}"

    @property
    def ending(self) -> bool:
        """The last ten seconds: the looks flash, so you notice the change coming."""
        return self.left <= 10


def phase(now, work: int, rest: int) -> Phase:
    """The part of the round at ``now``, with rounds counted from midnight."""
    since_midnight = now.hour * 3600 + now.minute * 60 + now.second
    into = since_midnight % ((work + rest) * 60)
    if into < work * 60:
        return Phase(True, work * 60 - into, work * 60)
    return Phase(False, (work + rest) * 60 - into, rest * 60)
