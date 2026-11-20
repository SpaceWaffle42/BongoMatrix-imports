"""Prices, fetched in the background and shared by every screen of this module.

A screen calls ``FEED.ask(coins, currency, every)`` each frame; it returns at once. What has arrived is
read with ``FEED.prices_for(currency)``: ({coin: {"price", "change", "week": [...]}}, fresh).

Being polite to a free service is the point of this file:
- one request covers every coin any screen has asked for lately, in one currency;
- a currency is asked for again only when its ``every`` seconds are up (or a coin is new to it);
- whatever the screens ask, requests are never closer together than GAP seconds, and after the service
  says "too many requests" nothing is asked for REST seconds;
- the thread stops when no screen has asked for a while.
The last prices are kept in ``prices.json`` in the module's working folder, so after a restart there is
something to show (marked old until fresh ones arrive).
"""
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://api.coingecko.com/api/v3/coins/markets"
AGENT = "bongo-crypto-ticker/1.0 (a Bongo Matrix module)"
KEEP = "prices.json"
IDLE_AFTER = 300          # s since any screen asked: stop fetching (and forget what it asked for)
GAP = 20                  # s, the least between two requests, whatever the screens ask
REST = 300                # s without asking after "too many requests"
POINTS = 56               # of the week's chart that are kept (about one LED each on the panel)


def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:                          # a whole number too big to be a price
        return False


def _tidy(prices):
    """Only entries of the shape the screens draw: anything else (a damaged file, an odd answer) is dropped."""
    out = {}
    for coin, entry in prices.items() if isinstance(prices, dict) else ():
        if not isinstance(coin, str) or not isinstance(entry, dict) or not _number(entry.get("price")) or entry["price"] < 0:
            continue
        week = entry.get("week") if isinstance(entry.get("week"), list) else []
        out[coin] = {"price": float(entry["price"]),
                     "change": float(entry["change"]) if _number(entry.get("change")) else None,
                     "week": [float(p) for p in week if _number(p)][:POINTS]}
    return out


class Feed:
    def __init__(self):
        self._book = {}            # currency -> (prices, when fetched by the clock, fetched this run?)
        self._wants = {}           # currency -> {coin: when last asked for (monotonic)}
        self._every = 120
        self._fetched = {}         # currency -> when last fetched (monotonic)
        self._not_before = 0.0     # monotonic: no request before this
        self.problem = None
        self._thread = None
        self._lock = threading.Lock()
        self._load()

    # -- for the screens -----------------------------------------------------------------------
    def ask(self, coins, currency, every):
        if not coins:
            return                                 # nothing picked: nothing to fetch
        now = time.monotonic()
        with self._lock:
            self._every = max(60, min(900, int(every)))
            wanted = self._wants.setdefault(currency, {})
            for coin in coins:
                wanted[coin] = now
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="crypto-feed", daemon=True)
                self._thread.start()

    def prices_for(self, currency):
        """(prices, fresh): what is known in this currency, and whether it is recent and from this run."""
        prices, at, live = self._book.get(currency, ({}, 0.0, False))
        return prices, bool(prices) and live and 0 <= time.time() - at < self._every * 3 + 60

    # -- the thread ----------------------------------------------------------------------------
    def _due(self, now):
        """The currency to fetch next and its coins (None: nothing is due). Forgets what nobody asks for any more."""
        with self._lock:
            for currency in list(self._wants):
                self._wants[currency] = {c: t for c, t in self._wants[currency].items() if now - t < IDLE_AFTER}
                if not self._wants[currency]:
                    del self._wants[currency]
            wants = {currency: sorted(coins) for currency, coins in self._wants.items()}
        if not wants:
            return None, None, False
        waiting = []
        for currency, coins in wants.items():
            have = self._book.get(currency, ({}, 0.0, False))
            last = self._fetched.get(currency)
            new = last is None or any(c not in have[0] for c in coins) and now - last >= GAP * 3
            if new or now - last >= self._every:
                waiting.append((last or 0.0, currency, coins))
        if not waiting:
            return None, None, True
        _, currency, coins = min(waiting)          # the one fetched longest ago goes first
        return currency, coins, True

    def _run(self):
        while True:
            now = time.monotonic()
            currency, coins, busy = self._due(now)
            if not busy:
                return                             # no screen has asked for a while: stop (ask() starts it again)
            if currency is None or now < self._not_before:
                time.sleep(1)
                continue
            self._not_before = now + GAP
            self._fetched[currency] = now
            try:
                self._take(currency, self._fetch(coins, currency))
                self.problem = None
            except Exception as error:   # no network, too many requests, a bad answer: keep what we have
                if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                    self._not_before = time.monotonic() + REST      # asked too often: leave it alone a while
                if str(error) != self.problem:
                    print(f"crypto_ticker: couldn't get prices ({error})", flush=True)
                self.problem = str(error)

    def _fetch(self, coins, currency):
        query = urllib.parse.urlencode({"vs_currency": currency, "ids": ",".join(coins), "sparkline": "true",
                                        "price_change_percentage": "24h"})
        request = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as answer:
            rows = json.loads(answer.read(2_000_000))
        found = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            spark = row.get("sparkline_in_7d")
            week = [p for p in (spark.get("price") if isinstance(spark, dict) else None) or [] if _number(p)]
            if len(week) > POINTS:       # thin the whole week out evenly, first point to last
                week = [week[round(k * (len(week) - 1) / (POINTS - 1))] for k in range(POINTS)]
            found[row["id"]] = {"price": row.get("current_price"), "change": row.get("price_change_percentage_24h"), "week": week}
        found = _tidy(found)             # a coin with no price isn't shown, rather than shown wrong
        if not found:
            raise ValueError("an answer with no prices in it")
        return found

    def _take(self, currency, prices):
        self._book = {**self._book, currency: (prices, time.time(), True)}     # swapped whole: a screen never sees half
        try:
            with open(KEEP, "w") as f:
                json.dump({c: {"at": at, "prices": p} for c, (p, at, _) in self._book.items()}, f)
        except OSError:
            pass                         # nowhere to write: there's just nothing to show after a restart

    def _load(self):
        try:
            with open(KEEP, encoding="utf-8") as f:
                kept = json.load(f)
            for currency, entry in kept.items():
                prices, at = _tidy(entry.get("prices")), float(entry.get("at"))
                if prices and 0 <= time.time() - at < 86400:
                    self._book[currency] = (prices, at, False)      # not from this run: shown as old
        except (OSError, ValueError, TypeError, AttributeError, OverflowError):
            pass                         # no file, or a damaged one: start with nothing


FEED = Feed()
