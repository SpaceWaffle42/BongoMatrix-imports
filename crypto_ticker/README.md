# Crypto Ticker for Bongo Matrix

Prices for the coins you pick, with the day's change and the last week as a chart.

Version 1.0.0, by spacewaffle42. MIT licence.

**Information only. Nothing here is financial advice.** Prices can be a few minutes old.
Not affiliated with CoinGecko.

## Two looks

| Look | What it shows |
|---|---|
| **Ticker** | One coin at a time: its letters, the day's change, the price, and a week's chart |
| **Board** | A list of coins with their prices and an arrow for the day; more than fit are paged. Up to three coins are drawn larger, with the currency sign |

A rise is green with an up arrow and a plus sign; a fall is red with a down arrow and a minus sign,
so it never depends on colour alone.

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose this .zip.
The Matrix draws each look on a test screen first, and asks you to tick that you trust the author.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `coins` | Which coins, picked from a list of twelve | Bitcoin, Ethereum, Solana |
| `currency` | Pounds, US dollars or euros | pounds |
| `refresh` | Seconds between fetches (60 to 900) | 120 |
| `seconds_each` | How long each coin (or page) stays up (3 to 30) | 6 |
| `up_colour`, `down_colour` | The colours for a rise and a fall | green, red |

## What it reaches on the internet

One site, listed in `bongo-module.json`: **api.coingecko.com**. Price data is provided by CoinGecko's
free service, which needs no account. One request covers all the coins your screens show in one
currency, and each currency is asked for once every `refresh` seconds while one of this module's
screens is showing (previews in the dashboard count), and for a few minutes after. Whatever the
settings, requests are never less than 20 seconds apart. Only the request itself goes out: your
internet address, as with any website, this module's name, and which coins and currency you picked.

The free service limits how often it may be asked. If it says "too many requests", the module asks for
nothing for five minutes. If the internet is down, the screens say GETTING PRICES; if there are prices
from earlier, they are shown greyed out and marked OLD.

## Files it keeps

`prices.json` in the module's own working folder: the last prices, so there is something to show after
a restart. Nothing else.

## For people writing their own module

This is the example to read if your module fetches from the internet.
- `bongo-module.json`: the `network` list. The Matrix lets the module reach nothing else.
- `feed.py`: fetching on a background thread so `render` never waits, one request for everything the
  screens want, a least gap between requests, backing off when told to, checking every value that
  comes back, and stopping when no screen is asking.
- `__init__.py`: `choices` and `choice_names`, so the dashboard offers a pick-list instead of a text box.