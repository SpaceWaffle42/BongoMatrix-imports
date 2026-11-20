# Word of the Day for Bongo Matrix

A new word every day, with what it means. 102 words to start with; add your own.

Version 1.0.0, by spacewaffle42. MIT licence.

## Two looks

| Look | What it shows |
|---|---|
| **Card** | The kind of word, the word as big as fits, and its meaning scrolling along the bottom |
| **Pages** | The word on top and its meaning in lines you can read still, a page at a time |

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose this .zip.
The Matrix draws each look on a test screen first, and asks you to tick that you trust the author.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `colour` | The colour of the word | `#FFD166` |
| `speed` | How fast the meaning scrolls on Card, in LEDs a second (6 to 60) | 20 |

## The words

They are in `words.json`, one entry each: `{"word": "zephyr", "kind": "noun", "meaning": "a soft, gentle breeze"}`.
The module works through the list in order, one a day, and round again. The meanings are short and in
plain words, written for this module. To use your own list, change that file before you import (keep
to plain letters: the panel's small fonts have no accents worth reading).

## Internet and files

None. It reaches nothing and keeps nothing.

## For people writing their own module

This is the example to read if your module ships its own data, or has text of any length to fit.
- `words.py`: reading a file beside the code, what to show if it is broken, and wrapping text into lines.
- `styles.py`: picking the biggest font that fits, scrolling what doesn't (from the clock, not by
  counting frames), and showing the lines a page at a time.
