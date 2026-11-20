"""Pomodoro for Bongo Matrix: a focus timer the whole room shares.

It runs by the clock, not by a start button (a module has no buttons): the day is cut into rounds of
``work`` minutes then ``rest`` minutes, counted from midnight. With the usual 25 and 5, work starts on
the hour and the half hour, so everyone looking at the panel is on the same round.

A good first module to read: no internet, no files, everything drawn from ``now``.
"""
from bongo.module import Module

from .styles import Countdown, Minutes, Tomato

__version__ = "1.0.0"

MODULE = Module(
    id="pomodoro",
    name="Pomodoro",
    description="A focus timer for the whole room: work, then a break, round the clock.",
    styles={"countdown": Countdown, "tomato": Tomato, "minutes": Minutes},   # the first is the default look
    defaults={
        "work": 25,                  # minutes of focus
        "rest": 5,                   # minutes of break
        "work_colour": "#FF5A4F",
        "rest_colour": "#5FD068",
    },
    # every number that could misbehave gets a lowest and a highest: the dashboard's slider keeps to them
    limits={"work": (5, 90), "rest": (1, 30)},
    basic=("work", "rest"),          # shown up front; the colours sit under Advanced settings
)
