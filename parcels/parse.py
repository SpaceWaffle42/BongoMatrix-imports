"""Reading what was typed into a Parcel box: a tracking number (or the courier's whole tracking link) and a nickname.

    JD0002240145 New boots
    AB 1234 5678 9GB, Printer ink            (a comma or "=" when the number itself has spaces)
    https://www.ups.com/track?loc=en_GB&tracknum=1Z999AA10123456784 Birthday gift

Only the number ever leaves the Matrix: a link is read here and nothing else of it is sent anywhere."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit

# query keys couriers put the number under, most telling first
KEYS = ("tracknum", "tracknumbers", "trackingnumber", "tracking_number", "tracking-id", "trackingid", "tracking",
        "parcel", "parcelnumber", "consignment", "consignmentnumber", "awb", "shipmentid", "id", "tn", "number",
        "ref", "reference", "q", "query", "barcode", "item")
TOKEN = re.compile(r"[A-Z0-9]{8,35}")


@dataclass(frozen=True)
class Typed:
    number: str            # "" when none could be found
    nickname: str          # "" when none was typed
    hint: str | None       # "dhl" or "ups" when a pasted link was the courier's own; else None
    problem: str | None    # what's wrong, in a few words, for the status line


def read(text: str) -> Typed | None:
    """What one Parcel box says, or None when it's empty."""
    text = " ".join((text or "").split())
    if not text:
        return None
    first, _, rest = text.partition(" ")
    if _is_link(first):
        number, hint = from_link(first)
        nickname = _nickname(rest)
        if not number:
            return Typed("", nickname, hint, "no tracking number in that link")
        return Typed(number, nickname, hint, None)
    for mark in (",", "="):                            # "AB 1234 5678 9GB, Printer ink"
        if mark in text:
            left, _, right = text.partition(mark)
            return _typed(left, _nickname(right))
    words = text.split(" ")                            # "JD0002240145 New boots"; "AB 1234 5678 9GB New boots": a number
    k = 1                                              # typed in short groups has digits in every group after the first
    while len(words[0]) < 8 and k < len(words) and len(words[k]) <= 5 and any(c.isdigit() for c in words[k]):
        k += 1
    return _typed(" ".join(words[:k]), _nickname(" ".join(words[k:])))


def _typed(number: str, nickname: str) -> Typed:
    number = clean(number)
    if not number:
        return Typed("", nickname, None, "no tracking number")
    if not 5 <= len(number) <= 50:
        return Typed("", nickname, None, "that doesn't look like a tracking number")
    return Typed(number, nickname, None, None)


def clean(number: str) -> str:
    """A number as couriers want it: capitals, no spaces or dashes."""
    return re.sub(r"[^A-Z0-9]", "", (number or "").upper())


def _nickname(text: str) -> str:
    return text.strip(" ,=-:;·–").strip()[:60]


def _is_link(word: str) -> bool:
    return bool(re.match(r"(?i)^(https?://|www\.)", word))


def from_link(link: str) -> tuple[str, str | None]:
    """(the tracking number in a courier's tracking link, "dhl"/"ups" if it was theirs). "" if there's none."""
    parts = urlsplit(link if "://" in link else "https://" + link)
    host = (parts.hostname or "").lower()
    hint = "dhl" if re.search(r"(^|\.)dhl\.", host) else "ups" if re.search(r"(^|\.)ups\.com$", host) else None
    query = {k.lower(): v for k, v in parse_qsl(parts.query, keep_blank_values=False)}
    for key in KEYS:                                   # a value under a key that says what it is
        if key in query and (found := _best(query[key])):
            return found, hint
    for value in query.values():                       # any other value that looks like one
        if found := _best(value):
            return found, hint
    for piece in reversed((parts.path + "/" + parts.fragment).split("/")):   # then the path, last part first
        if found := _best(piece):
            return found, hint
    return "", hint


def _best(text: str) -> str:
    """The likeliest tracking number in a piece of a link: letters and digits, 8 to 35 long, with digits in it."""
    found = [t for t in TOKEN.findall(text.upper()) if sum(c.isdigit() for c in t) >= 4]
    return max(found, key=len) if found else ""


# -- which courier's own key could follow it ----------------------------------------------------------------------
UPS = re.compile(r"^1Z[0-9A-Z]{16}$")
DHL = (re.compile(r"^J?JD\d{16,20}$"), re.compile(r"^\d{10}$"), re.compile(r"^GM\d{16,22}$"),
       re.compile(r"^(3S|JVGL)[A-Z0-9]{8,30}$"), re.compile(r"^00340\d{15}$"), re.compile(r"^[A-Z]{2}\d{9}DE$"))


def looks_like(number: str, hint: str | None) -> str | None:
    """"ups" or "dhl" when the number (or the link it came from) is probably that courier's; else None. Only a
    guess: a number the courier doesn't know goes to Ship24 instead (JD numbers are Yodel's too)."""
    if hint:
        return hint
    if UPS.match(number):
        return "ups"
    if any(p.match(number) for p in DHL):
        return "dhl"
    return None
