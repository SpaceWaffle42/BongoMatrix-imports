"""Today's word, from words.json."""
import json
from pathlib import Path

FILE = Path(__file__).parent / "words.json"
SPARE = {"word": "word", "kind": "noun", "meaning": "words.json is missing or can't be read"}


def load():
    try:
        words = json.loads(FILE.read_text(encoding="utf-8"))
        good = [w for w in words if isinstance(w, dict) and all(isinstance(w.get(k), str) and w[k] for k in ("word", "kind", "meaning"))]
        return good or [SPARE]
    except (OSError, ValueError, TypeError):
        return [SPARE]             # a broken list shouldn't break the panel: say what's wrong instead


WORDS = load()


def today(now):
    """One word per day, working through the list in order and round again."""
    return WORDS[now.date().toordinal() % len(WORDS)]


def wrap(text, fits):
    """Split ``text`` into lines; ``fits(line)`` says whether a line is short enough."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and not fits(trial):
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines
