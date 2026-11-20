"""Crypto Ticker for Bongo Matrix: prices for the coins you pick.

Two looks: Ticker (one coin at a time, with the last week as a chart) and Board (several coins in a
list). Prices come from CoinGecko's free service, which needs no account.

The module to read if yours fetches from the internet:
- ``bongo-module.json`` lists the one site it uses; the Matrix lets it reach nothing else.
- ``feed.py`` fetches on a background thread, so ``render`` never waits for the internet.
- The settings use ``choices``, so the dashboard offers a pick-list and nobody has to type a coin's name.

Information only. Nothing here is financial advice.
"""
from bongo.module import Module

from .coins import COINS, CURRENCIES
from .styles import Board, Ticker

__version__ = "1.0.0"

MODULE = Module(
    id="crypto_ticker",
    name="Crypto Ticker",
    description="Prices for the coins you pick, with the day's change. Information only, not advice.",
    styles={"ticker": Ticker, "board": Board},
    defaults={
        "coins": ["bitcoin", "ethereum", "solana"],
        "currency": "gbp",
        "refresh": 120,              # seconds between fetches: the free service asks you not to hurry
        "up_colour": "#5FD068",
        "down_colour": "#FF6B6B",
    },
    # a setting with choices gets a pick-list; a list setting with choices lets you tick several
    choices={"coins": list(COINS), "currency": list(CURRENCIES)},
    choice_names={"coins": {"labels": {coin: f"{name} ({symbol})" for coin, (symbol, name) in COINS.items()}},
                  "currency": {"labels": {"gbp": "Pounds (£)", "usd": "US dollars ($)", "eur": "Euros (€)"}}},
    limits={"refresh": (60, 900)},
    basic=("coins", "currency"),
)
