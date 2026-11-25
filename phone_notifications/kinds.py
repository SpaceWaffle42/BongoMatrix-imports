"""What a notification is: which kind of app it came from (its icon and colour), and how the owner asked for that
kind to be handled. Nothing here touches the network or the panel."""
from __future__ import annotations

import re
import unicodedata

# kind: (the words for it on the panel, its colour, the setting that says how it's handled)
KINDS = {
    "message": ("Message", (90, 200, 222), "messages"),
    "call": ("Call", (74, 222, 128), "calls"),
    "delivery": ("Delivery", (208, 138, 74), "deliveries"),
    "email": ("Email", (255, 181, 71), "email"),
    "calendar": ("Calendar", (232, 228, 220), "other_apps"),
    "other": ("Notification", (255, 212, 107), "other_apps"),
}
ART = {"message": "message", "call": "call", "delivery": "delivery", "email": "mail", "calendar": "calendar", "other": "other"}

# What a pop-up or a screen says of one, when the text isn't shown
NEW = {"message": "New message", "call": "Missed call", "delivery": "Delivery update", "email": "New email",
       "calendar": "Reminder", "other": "New notification"}

# How each kind is handled: the choices of its setting in the module's card
POP, SHOW, IGNORE = "Show and pop up", "Show, no pop-up", "Don't show"
HANDLING = [POP, SHOW, IGNORE]

# A tag that names a kind outright (the iPhone steps send these), and the words that mark one in an app's name.
# Short words count only as whole words ("ups" is a courier, "groups" isn't).
WORDS = {"message": "message", "messages": "message", "text": "message", "sms": "message", "chat": "message",
         "call": "call", "calls": "call", "missed_call": "call", "phone": "call",
         "delivery": "delivery", "deliveries": "delivery", "parcel": "delivery", "courier": "delivery", "package": "delivery",
         "email": "email", "mail": "email", "e-mail": "email",
         "calendar": "calendar", "reminder": "calendar",
         "other": "other"}
APP_WORDS = [   # in this order: "Royal Mail" is a courier before it is mail
    ("delivery", ("royal mail", "parcel", "courier", "delivery", "deliveroo", "evri", "hermes", "yodel", "inpost",
                  "fedex", "postnl", "amazon shopping", "dpd", "dhl", "ups", "gls")),
    ("call", ("phone", "dialer", "dialler", "missed call", "call")),
    ("message", ("whatsapp", "signal", "telegram", "messenger", "messages", "message", "imessage", "viber", "wechat",
                 "discord", "slack", "teams", "sms", "chat", "line")),
    ("email", ("gmail", "outlook", "proton", "thunderbird", "mail", "spark", "yahoo")),
    ("calendar", ("calendar", "reminders")),
]
SHORT = 4   # an app word this long or shorter must be a whole word


def kind_of(tags, app: str = "") -> str:
    """The kind of a notification from its ntfy tags (the app's name, or a kind word) and its app's name."""
    for tag in tags or ():
        word = str(tag).strip().lower().replace(" ", "_")
        if word in WORDS:
            return WORDS[word]
    names = [str(t).lower() for t in (tags or ())] + ([app.lower()] if app else [])
    for name in names:
        words = set(re.findall(r"[a-z0-9]+", name))
        for kind, keys in APP_WORDS:
            if any((key in words) if len(key) <= SHORT else (key in name) for key in keys):
                return kind
    return "other"


def handling(kind: str, settings: dict) -> str:
    """POP, SHOW or IGNORE for a kind, as its setting says (a value this version doesn't know: SHOW)."""
    value = (settings or {}).get(KINDS.get(kind, KINDS["other"])[2])
    return value if value in HANDLING else SHOW


# -- text -----------------------------------------------------------------------------------------------------
FOLD = {"ß": "ss", "æ": "ae", "Æ": "AE", "ø": "o", "Ø": "O", "œ": "oe", "Œ": "OE", "ð": "d", "Ð": "D", "þ": "th", "Þ": "TH",
        "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", "€": "EUR"}


def plain(text, most: int = 200) -> str:
    """Text the panel's small fonts can draw: accents taken off, emoji and anything else unprintable dropped,
    on one line, at most ``most`` characters."""
    out = []
    for ch in unicodedata.normalize("NFKD", "".join(FOLD.get(c, c) for c in str(text or ""))):
        if unicodedata.combining(ch):
            continue
        if ch == "£" or (" " <= ch <= "~"):
            out.append(ch)
        elif ch.isspace():
            out.append(" ")
    return " ".join("".join(out).split())[:most]


NOTHING = {"", "new", "triggered"}   # what the phone sends to keep the text private, and ntfy's word for no text


def text_of(message) -> str:
    """A notification's text, or "" when the phone kept it back."""
    text = plain(message)
    return "" if text.lower() in NOTHING else text
