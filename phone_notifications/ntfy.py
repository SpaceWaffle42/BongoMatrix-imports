"""Listening to ntfy (https://ntfy.sh), the free relay the phone posts to.

One connection stays open to ``<server>/<topic>/json``: ntfy sends one JSON line per notification, and a
"keepalive" line about every 45 seconds so a dead connection shows. It is read by a thread of its own, so the
background task's tick never waits on the network (a tick has 5 seconds, and a stream can be quiet for hours):
the thread puts what it hears in ``inbox`` and the tick takes it out. After a drop it connects again, asking
for anything it missed with ``since=<the last one's id>`` (ntfy.sh keeps them for 12 hours).
"""
from __future__ import annotations

import json
import queue
import re
import secrets
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

SERVER = "https://ntfy.sh"      # the one server, for now. Your own ntfy later: only this and "network" change
NAME = "ntfy.sh"                # how the panel and the card name it
QUIET = 100                     # s without a line (not even a keepalive) before the connection counts as dead
RESTS = (2, 5, 15, 30, 60, 120, 300)   # s between tries after a drop, longer each time it fails again
AGENT = "bongo-matrix-phone-notifications/1.0"

TOPIC = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")    # what ntfy allows in a topic's name
ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no 0/o, 1/l: easy to copy by eye


def make_topic() -> str:
    """A new topic name nobody could guess: 20 random letters and numbers, in groups of four."""
    letters = "".join(secrets.choice(ALPHABET) for _ in range(20))
    return "-".join(letters[i:i + 4] for i in range(0, 20, 4))


def address(topic: str) -> str:
    """The topic's page, as a phone opens it (what the setup code holds)."""
    return f"{SERVER}/{topic}"


def stream_url(topic: str, since: str | None) -> str:
    url = f"{SERVER}/{quote(topic, safe='')}/json"
    return url + (f"?since={quote(since, safe='')}" if since else "")


def why(error: BaseException) -> tuple[str, float]:
    """A failure in a few words for the card, and how long to wait before trying again (0: the usual rests)."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code in (401, 403):
            return f"{NAME} won't let it read this topic (check the access token)", 300
        if error.code == 429:
            return f"{NAME} says too many tries: waiting a few minutes", 600
        if error.code == 404:
            return f"{NAME} doesn't know that address", 300
        return f"{NAME} answered {error.code}", 0
    if isinstance(error, urllib.error.URLError):
        error = error.reason if isinstance(error.reason, BaseException) else error
        if isinstance(error, str):
            return error[:60], 0
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "no answer (the connection went quiet)", 0
    if isinstance(error, socket.gaierror):
        return "no internet (can't find it)", 0
    if isinstance(error, ConnectionRefusedError):
        return "it refused the connection", 0
    if isinstance(error, ValueError):
        return "it sent something that isn't ntfy's", 0
    text = str(error).strip() or type(error).__name__
    return text[:60], 0


class Listener(threading.Thread):
    """The one connection to a topic. ``inbox`` gets ("up",), ("message", event) and ("down", why); ``since``
    is the id of the last notification heard, for catching up."""

    def __init__(self, topic: str, token: str = "", since: str | None = None):
        super().__init__(daemon=True, name="ntfy")
        self.topic, self.token, self.since = topic, token, since
        self.inbox: queue.SimpleQueue = queue.SimpleQueue()
        self.stopping = threading.Event()
        self.response = None

    def stop(self) -> None:
        """Hang up (from another thread): the read in progress ends at once."""
        self.stopping.set()
        response = self.response
        try:
            response.fp.raw._sock.shutdown(socket.SHUT_RDWR)   # (closing alone may wait for the next line)
        except (AttributeError, OSError):
            pass

    def run(self) -> None:
        tries = 0
        while not self.stopping.is_set():
            heard = False
            try:
                heard = self._listen()
                rest = 1.0                                     # the far end closed it: straight back
            except Exception as error:                         # (anything: the thread must never die)
                if self.stopping.is_set():
                    return
                words, rest = why(error)
                self.inbox.put(("down", words))
                rest = rest or RESTS[min(tries, len(RESTS) - 1)]
            tries = 0 if heard else tries + 1
            self.stopping.wait(rest)

    def _listen(self) -> bool:
        """Read the stream until it ends. True if it was up (so the next failure starts the rests again)."""
        headers = {"User-Agent": AGENT, "Accept": "application/x-ndjson"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(stream_url(self.topic, self.since), headers=headers)
        with urllib.request.urlopen(request, timeout=QUIET) as response:
            self.response = response
            if self.stopping.is_set():
                return False
            self.inbox.put(("up",))
            for line in response:
                if self.stopping.is_set():
                    return True
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("not an event")
                if event.get("event") == "message" and isinstance(event.get("id"), str):
                    self.since = event["id"]
                    self.inbox.put(("message", event))
        return True


def drain(inbox: queue.SimpleQueue, most: int = 200) -> list:
    """What's waiting in an inbox, without waiting for more."""
    out = []
    while len(out) < most:
        try:
            out.append(inbox.get_nowait())
        except queue.Empty:
            break
    return out

