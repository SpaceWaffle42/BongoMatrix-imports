"""Two looks: Ticker (one coin at a time, with a week's chart) and Board (a list)."""
from PIL import ImageColor

from bongo.module import Style

from .coins import COINS, CURRENCIES, money
from .feed import FEED

WHITE, GREY, DIM = (255, 255, 255), (150, 156, 166), (70, 74, 82)


class _Look(Style):
    fps = 4

    def setup(self):
        self.small = self.ctx.fonts("4x6")
        self.up = ImageColor.getrgb(self.settings["up_colour"])
        self.down = ImageColor.getrgb(self.settings["down_colour"])
        self.sign = CURRENCIES[self.settings["currency"]]

    def prices(self):
        """The coins picked that have a price, in the order picked; and whether the prices are recent."""
        FEED.ask(self.settings["coins"], self.settings["currency"], self.settings["refresh"])
        prices, fresh = FEED.prices_for(self.settings["currency"])
        return [(c, prices[c]) for c in self.settings["coins"] if c in prices], fresh

    def nothing(self, img, now):
        """No prices to show yet: say why, rather than draw a guess."""
        words = "PICK A COIN" if not self.settings["coins"] else "GETTING PRICES" if self.ctx.width >= 58 else "LOADING"
        middle = self.ctx.height // 2
        self.small.draw(img, max(0, (self.ctx.width - self.small.width(words)) // 2), middle + 1, words, GREY)
        if self.settings["coins"]:
            dots = "." * (1 + int(now.timestamp()) % 3)
            self.small.draw(img, max(0, (self.ctx.width - self.small.width(dots)) // 2), middle + 7, dots, GREY)
        return img

    def change(self, coin, fresh):
        """('+2.4%', its colour, +1 / -1 / 0): the day's change, never by colour alone (a sign and an arrow too)."""
        c = coin["change"]
        if c is None:
            return "", GREY, 0
        way = 1 if c > 0.05 else -1 if c < -0.05 else 0
        colour = GREY if not fresh or not way else self.up if way > 0 else self.down
        return (f"{c:+.1f}%" if way else "0.0%"), colour, way

    @staticmethod
    def arrow(img, x, y, way, colour):
        """A 5 x 3 arrowhead with its top-left at (x, y): up for a rise, down for a fall."""
        for row, (a, b) in enumerate(((2, 2), (1, 3), (0, 4))):
            for dx in range(a, b + 1):
                px, py = x + dx, y + (row if way > 0 else 2 - row)
                if 0 <= px < img.width and 0 <= py < img.height:
                    img.putpixel((px, py), colour)


class Ticker(_Look):
    """One coin at a time: its name and the day's change on top, the price in the middle, the week's chart below."""
    defaults = {"seconds_each": 6}
    limits = {"seconds_each": (3, 30)}

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        coins, fresh = self.prices()
        if not coins:
            return self.nothing(img, now)
        name, coin = coins[int(now.timestamp() // self.settings["seconds_each"]) % len(coins)]
        words, colour, way = self.change(coin, fresh)
        if not fresh:
            words, way = "OLD", 0                                  # kept from before, not live: said in words, not just grey
        head = self.ctx.fonts("5x7")
        head.draw(img, 1, 7, COINS[name][0], WHITE if fresh else GREY)
        right = w - self.small.width(words) - 1
        if right > 1 + head.width(COINS[name][0]) + 1:             # (a very narrow canvas keeps the coin's letters)
            self.small.draw(img, right, 6, words, colour)
            if way and right - 7 > 1 + head.width(COINS[name][0]):
                self.arrow(img, right - 7, 2, way, colour)
        chart = h >= 26 and len(coin["week"]) >= 2
        room = (h - 9 - (9 if chart else 0))                       # the band the price sits in
        # the exact price in the biggest font it fits in; only when it fits in none is it shortened (67.4K)
        for font_name in ("7x13B", "6x10", "5x7", "4x6"):
            font = self.ctx.fonts(font_name)
            price = money(coin["price"], self.sign, lambda text: font.width(text) <= w - 2, exact=True) if font.cap <= room else None
            if price:
                break
        else:
            font = self.small
            price = money(coin["price"], self.sign, lambda text: font.width(text) <= w - 2)
        font.draw(img, (w - font.width(price)) // 2, 9 + (room + font.cap) // 2, price, WHITE if fresh else GREY)
        if chart:
            self.week(img, coin["week"], colour if way else GREY, h - 8, 7)
        return img

    def week(self, img, values, colour, top, tall):
        """The last week as a line, ``tall`` LEDs high, right across the canvas."""
        w = img.width
        low, high = min(values), max(values)
        spread = (high - low) or 1
        last = None
        for x in range(w):
            v = values[min(len(values) - 1, x * len(values) // w)]
            y = top + tall - 1 - round((v - low) / spread * (tall - 1))
            for yy in range(min(y, last if last is not None else y), max(y, last if last is not None else y) + 1):
                img.putpixel((x, yy), colour)                         # join the steps so the line has no gaps
            last = y


class Board(_Look):
    """A list: each coin's letters, its price, and an arrow for the day. More than fit are paged."""
    defaults = {"seconds_each": 6}
    limits = {"seconds_each": (3, 30)}

    def render(self, now):
        img = self.ctx.canvas()
        w, h = self.ctx.width, self.ctx.height
        coins, fresh = self.prices()
        if not coins:
            return self.nothing(img, now)
        foot = 0 if fresh else 7                                   # old prices: a line at the bottom says so
        # a few coins get the bigger font and the currency sign, if every price fits in full; otherwise the small one
        bigger = self.ctx.fonts("5x7")
        big = len(coins) <= (h - foot - 1) // 8 and all(
            1 + bigger.width(COINS[name][0]) + 3 + bigger.width(money(coin["price"], self.sign)) <= w - 8 for name, coin in coins)
        font, step, sign = (bigger, 8, self.sign) if big else (self.small, 6, "")
        rows = max(1, (h - foot) // step)
        rows = -(-len(coins) // -(-len(coins) // rows))            # the pages even: 6 coins in 5 rows is 3 and 3, not 5 and 1
        pages = [coins[k:k + rows] for k in range(0, len(coins), rows)]
        page = pages[int(now.timestamp() // self.settings["seconds_each"]) % len(pages)]
        top = (h - foot - len(page) * step + step - font.cap + 1) // 2 + font.cap     # the block of rows, centred
        for k, (name, coin) in enumerate(page):
            baseline = top + k * step
            _, colour, way = self.change(coin, fresh)
            symbol = COINS[name][0]
            font.draw(img, 1, baseline, symbol, WHITE if fresh else GREY)
            if way:
                self.arrow(img, w - 6, baseline - font.cap + 1, way, colour)
            left = 1 + font.width(symbol) + 3
            price = money(coin["price"], sign, lambda text: left + font.width(text) <= w - 8)
            font.draw(img, max(left, w - 8 - font.width(price)), baseline, price, WHITE if fresh else GREY)
        if foot:
            words = "OLD PRICES" if w >= 42 else "OLD"
            self.small.draw(img, max(0, (w - self.small.width(words)) // 2), h - 1, words, GREY)
        return img
