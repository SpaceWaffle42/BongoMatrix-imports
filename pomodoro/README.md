# Pomodoro for Bongo Matrix

A focus timer the whole room shares: 25 minutes of work, 5 of break, round the clock.

Version 1.0.0, by spacewaffle42. MIT licence.

## How it keeps time

A module has no buttons, so there is nothing to start. The day is cut into rounds, counted from
midnight: with the usual 25 and 5, **work starts on the hour and on the half hour**. Everyone looking
at the panel is on the same round. In the last ten seconds of a part the colours swap twice a second, so you
notice the change coming.

To run it only while you work, give it times of day in its Timing card (When it plays).

## Three looks

| Look | What it shows |
|---|---|
| **Countdown** | FOCUS or BREAK, big minutes and seconds, and a bar that runs down |
| **Tomato** | A tomato that empties as you work and ripens again over the break |
| **Minutes** | One block per minute of this part; they go out one by one, and the last one lit blinks. On a small canvas a block stands for several minutes |

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose this .zip.
The Matrix draws each look on a test screen first, and asks you to tick that you trust the author.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `work` | Minutes of focus (5 to 90) | 25 |
| `rest` | Minutes of break (1 to 30) | 5 |
| `work_colour` | Colour while working | `#FF5A4F` |
| `rest_colour` | Colour on a break | `#5FD068` |

Rounds are counted afresh from midnight. If `work` + `rest` divides evenly into a day (30, 45, 60 or
90 minutes do: 25 + 5, 30 + 15, 50 + 10, 45 + 15, 75 + 15), every round is whole. Otherwise the last
round of the day is cut short at midnight.

## Internet and files

None. It reaches nothing and keeps nothing.

## For people writing their own module

This is the simplest of the examples: no internet, no files, everything drawn from `now`.
- `__init__.py`: the `MODULE`, its settings, and `limits` for the two numbers.
- `timer.py`: which part of the round it is. Kept apart from the drawing so all three looks share it.
- `styles.py`: one class per look, each drawing relative to `ctx.width` and `ctx.height`.
