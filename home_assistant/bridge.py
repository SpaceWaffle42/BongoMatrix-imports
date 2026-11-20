"""What the Matrix and Home Assistant say to each other, through the MQTT broker.

Nothing here knows about the Matrix's code: ``Link`` is given a way to dial the broker, a folder to keep
this Matrix's id in, and at every tick the panel's controls (docs/MODULES.md of the Matrix, "Background
modules, controls and the home network"). That keeps it testable on its own (``tests/``).

Topics, where <id> is this Matrix's own id (eight letters and digits, made once, kept in ``matrix-id.txt``):

    bongo_matrix/<id>/availability      "online" / "offline"   kept by the broker; "offline" is also the last will
    bongo_matrix/<id>/light/state       {"state":"ON","brightness":70}   kept        on is awake, off is asleep
    bongo_matrix/<id>/light/set         {"state":"ON","brightness":40}   a command   brightness is 1 to 100
    bongo_matrix/<id>/screen/state      Clock                            kept        the screen now playing
    bongo_matrix/<id>/screen/attributes {"module":"clock","style":"big"} kept
    bongo_matrix/<id>/pause/state       ON / OFF                         kept        on is paused
    bongo_matrix/<id>/pause/set         ON / OFF                         a command
    bongo_matrix/<id>/next/press        PRESS                            a command
    bongo_matrix/<id>/notify/send       Washing done                     a command   or {"message":..,"title":..,"seconds":..}
    homeassistant/device/bongo_matrix_<id>/config                        the discovery message (not kept)
    homeassistant/status                "online": Home Assistant has (re)started, so everything is said again

Commands are never kept by the broker on purpose, and one that arrives marked as kept (somebody published it
with "retain") is ignored and wiped: otherwise an old "OFF" would put the panel to sleep at every reconnect.
"""
from __future__ import annotations

import json
import math
import random
import secrets
import time
from collections import deque
from pathlib import Path

try:
    from . import mqtt
except ImportError:                    # run from the folder itself (the tests)
    import mqtt

VERSION = "1.0.0"
DISCOVERY = "homeassistant"            # Home Assistant's discovery prefix (its default)
BIRTH = DISCOVERY + "/status"
DEFAULT_NAME = "Bongo Matrix"

GAP = 1.5                              # seconds between two uses of one control (the Matrix allows one a second)
AGAIN = 3.0                            # ...and before asking again for something that hasn't happened yet
PATIENCE = 10.0                        # how long a command from Home Assistant is worth carrying out
NOTE_GAP = 5.5                         # between two messages on the panel (the Matrix allows one every 5 seconds)
NOTE_KEEP = 3                          # messages that may wait their turn; more are dropped
NOTE_STALE = 30.0                      # a message that has waited this long is no longer news
NOTES_IN_TEN = 10                      # the Matrix shows at most 10 from one module in ten minutes
ONLINE_GAP = 2.0                       # "online" is said again at most this often when an "offline" is heard
REANNOUNCE = 900.0                     # say the discovery message again this often, in case a restart was missed
SHOWN = 60.0                           # how long a dropped message or a refusal stays in the status line


def matrix_id(folder) -> str:
    """This Matrix's id for topics and Home Assistant: made once, then always the same."""
    path = Path(folder) / "matrix-id.txt"
    try:
        found = path.read_text().strip().lower()
        if len(found) == 8 and all(c in "0123456789abcdef" for c in found):
            return found
    except OSError:
        pass
    made = secrets.token_hex(4)
    try:
        path.write_text(made + "\n")
    except OSError:
        pass                           # nowhere to keep it: it works, with a new id (and device) after a restart
    return made


def topics(mid: str) -> dict:
    base = f"bongo_matrix/{mid}"
    return {
        "availability": f"{base}/availability",
        "light_state": f"{base}/light/state", "light_set": f"{base}/light/set",
        "screen_state": f"{base}/screen/state", "screen_attributes": f"{base}/screen/attributes",
        "pause_state": f"{base}/pause/state", "pause_set": f"{base}/pause/set",
        "next_press": f"{base}/next/press",
        "notify_send": f"{base}/notify/send",
        "discovery": f"{DISCOVERY}/device/bongo_matrix_{mid}/config",
    }


def discovery(mid: str, name: str) -> dict:
    """The one message that makes the Matrix appear in Home Assistant as a device with five entities
    (device-based MQTT discovery: https://www.home-assistant.io/integrations/mqtt/#device-discovery-payload)."""
    t, uid = topics(mid), f"bongo_matrix_{mid}"
    return {
        "device": {"identifiers": [uid], "name": name or DEFAULT_NAME, "manufacturer": "Bongo Matrix",
                   "model": "LED panel", "sw_version": f"Home Assistant module {VERSION}"},
        "origin": {"name": "Bongo Matrix Home Assistant module", "sw_version": VERSION},
        "availability_topic": t["availability"],
        "payload_available": "online",
        "payload_not_available": "offline",
        "components": {
            "panel": {"platform": "light", "unique_id": f"{uid}_panel", "name": None, "schema": "json",
                      "command_topic": t["light_set"], "state_topic": t["light_state"],
                      "brightness": True, "brightness_scale": 100, "supported_color_modes": ["brightness"],
                      "flash": False, "transition": False, "icon": "mdi:led-strip-variant"},
            "screen": {"platform": "sensor", "unique_id": f"{uid}_screen", "name": "Screen",
                       "state_topic": t["screen_state"], "json_attributes_topic": t["screen_attributes"],
                       "icon": "mdi:television-guide"},
            "pause": {"platform": "switch", "unique_id": f"{uid}_pause", "name": "Pause",
                      "command_topic": t["pause_set"], "state_topic": t["pause_state"],
                      "payload_on": "ON", "payload_off": "OFF", "icon": "mdi:pause"},
            "next": {"platform": "button", "unique_id": f"{uid}_next", "name": "Next",
                     "command_topic": t["next_press"], "payload_press": "PRESS", "icon": "mdi:skip-next"},
            "message": {"platform": "notify", "unique_id": f"{uid}_message", "name": "Message",
                        "command_topic": t["notify_send"], "icon": "mdi:message-text-outline"},
        },
    }


# ------------------------------------------------------------------------------ reading what was asked

def _words(payload: bytes, most: int = 512):
    if len(payload) > most:
        return None
    try:
        return payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None


def light_command(payload: bytes):
    """{"awake": bool, "brightness": 1..100} (either may be missing), or None for anything else."""
    words = _words(payload)
    if not words:
        return None
    if words.upper() in ("ON", "OFF"):
        return {"awake": words.upper() == "ON"}
    try:
        asked = json.loads(words)
    except ValueError:
        return None
    if not isinstance(asked, dict):
        return None
    out = {}
    if "state" in asked:
        state = asked["state"]
        if not isinstance(state, str) or state.upper() not in ("ON", "OFF"):
            return None
        out["awake"] = state.upper() == "ON"
    if "brightness" in asked and out.get("awake") is not False:
        level = asked["brightness"]
        if isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(level):
            return None
        if not 0 < level <= 100:
            return None
        out["brightness"] = max(1, min(100, round(level)))
    return out or None


def switch_command(payload: bytes):
    """True for ON, False for OFF, None for anything else."""
    words = (_words(payload) or "").upper()
    return {"ON": True, "OFF": False}.get(words)


def press_command(payload: bytes) -> bool:
    return (_words(payload) or "").upper() == "PRESS"


def _tidy(value: str, most: int) -> str:
    return " ".join("".join(c if c.isprintable() else " " for c in value).split())[:most]


def notify_command(payload: bytes):
    """(text, title, seconds) or None. The payload is the message itself (what Home Assistant's notify
    entity sends), or {"message": "...", "title": "...", "seconds": 3 to 30} for anyone publishing by hand."""
    words = payload[:4000].decode("utf-8", "replace").strip()
    title, seconds = "", 10
    if words.startswith("{"):
        try:
            asked = json.loads(words)
        except ValueError:
            asked = None
        if isinstance(asked, dict) and isinstance(asked.get("message"), str):
            words = asked["message"]
            if isinstance(asked.get("title"), str):
                title = asked["title"]
            wanted = asked.get("seconds")
            if isinstance(wanted, (int, float)) and not isinstance(wanted, bool) and math.isfinite(wanted):
                seconds = int(max(3, min(30, round(wanted))))
    words, title = _tidy(words, 120), _tidy(title, 40)
    return (words, title, seconds) if words else None


# ------------------------------------------------------------------------------------------- the link

class Link:
    """Keeps the connection, tells Home Assistant what the panel is doing, and does what it asks."""

    def __init__(self, dial, folder=".", report=None, clock=time.monotonic, say=print, chance=random.random):
        self.dial, self.report, self.clock, self.say, self.chance = dial, report or (lambda text, ok=True: None), clock, say, chance
        self.id = matrix_id(folder)
        self.topics = topics(self.id)
        self.commands = {self.topics[k]: k for k in ("light_set", "pause_set", "next_press", "notify_send")}
        self.key = None                # the settings the connection was made with
        self.name = DEFAULT_NAME
        self.client = None
        self.fault = "Type the broker's address above"     # why there is no client at all
        self.said = None               # the last status reported, and the last line printed
        self.printed = None
        self.notes_sent = ()           # when each message was shown (these outlast a reconnection: so do the Matrix's limits)
        self.dropped, self.dropped_at = 0, -1e9
        self.refused, self.refused_at = "", -1e9
        self._fresh()

    def _fresh(self):
        """Forget everything that belonged to one connection."""
        self.told = {}                 # topic -> the payload last published
        self.announce_at = None
        self.echo_at = None
        self.wants = {}                # "awake" / "brightness" / "paused" -> {"value", "since", "tries"}
        self.nexts = 0
        self.notes = deque()           # (text, title, seconds, arrived)
        self.asked = {}                # control -> when it was last used
        self.wiped = set()
        self.deaf = False
        self.online_at = None          # when to say "online" again (see _availability)
        self.said_online = -1e9

    # -- settings

    def configure(self, settings: dict) -> None:
        """Call with the module's settings at the start and whenever they may have changed."""
        settings = settings or {}
        address = str(settings.get("address") or "").strip()
        try:
            port = int(settings.get("port") or 1883)
        except (TypeError, ValueError):
            port = 1883
        username, password = str(settings.get("username") or ""), str(settings.get("password") or "")
        secure, typed = bool(settings.get("secure")), str(settings.get("fingerprint") or "")
        name = _tidy(str(settings.get("name") or ""), 40) or DEFAULT_NAME
        key = (address, port, username, password, secure, typed)
        if key != self.key:
            self.key = key
            self._hang_up()
            self.fault, tls = "", None
            if not address:
                self.fault = "Type the broker's address above"
            elif password and not username:
                self.fault = "Type the username too: a password needs one"
            elif secure:
                try:
                    tls = {"fingerprint": mqtt.fingerprint(typed), "name": address}
                except ValueError:
                    self.fault = "The certificate fingerprint should be 64 letters and digits (SHA-256)"
            elif typed.strip():
                self.fault = "A certificate fingerprint needs Encrypted (TLS) switched on"
            if not self.fault:
                self.client = mqtt.Client(
                    self.dial, f"bongo-matrix-{self.id}", username=username, password=password, tls=tls,
                    will=(self.topics["availability"], b"offline", 1, True),
                    subscribe=[(topic, 0) for topic in (*self.commands, BIRTH, self.topics["availability"])], clock=self.clock, chance=self.chance)
        if name != self.name:
            self.name = name
            if self.client is not None and self.client.up:
                self.announce_at = self.clock()

    def close(self) -> None:
        """Say "offline" and hang up tidily (switched off, removed, the Matrix stopping). Never waits."""
        self._hang_up()
        self.key = None

    def _hang_up(self):
        if self.client is not None:
            self.client.close(farewell=[(self.topics["availability"], b"offline", True)])
        self.client = None
        self._fresh()

    # -- one tick

    def tick(self, panel) -> None:
        now = self.clock()
        if self.client is not None:
            for event in self.client.step():
                self._event(event, now)
            if self.client.up:
                if self.announce_at is not None and now >= self.announce_at:
                    self._announce(now)
                if self.online_at is not None and now >= self.online_at:
                    self.online_at, self.said_online = None, now
                    self.client.publish(self.topics["availability"], b"online", qos=1, retain=True)
                self._act(panel, now)
                self._tell(getattr(panel, "status", None), now)
        self._refusals(panel, now)
        self._status(now)

    def _event(self, event, now):
        if event[0] == "up":
            self._fresh()
            self.announce_at = now
            if self.client.tls is not None and self.client.seen_certificate and not self.client.checked:
                self._print("the broker's certificate isn't checked. Its SHA-256 fingerprint, to paste into "
                            "Certificate fingerprint if it is the right one: " + self.client.seen_certificate)
        elif event[0] == "down":
            self._fresh()
        elif event[0] == "subscribed":
            self.deaf = any(code & 0x80 for code in event[1])
            self._online_soon(now)                    # once more, now that the broker has sorted out any old session
        elif event[0] == "message":
            self._message(event[1], event[2], event[3], now)

    def _online_soon(self, now):
        self.online_at = max(now, self.said_online + ONLINE_GAP) if self.online_at is None else self.online_at

    def _message(self, topic, payload, retained, now):
        if topic == self.topics["availability"]:
            # Our own availability, heard back. "offline" while we are connected is an old connection's last will
            # landing after our "online" (the broker noticed the old one late, or handed this client id over):
            # left alone, Home Assistant would show the Matrix unavailable until the next reconnection.
            if payload.strip() != b"online":
                self._online_soon(now)
            return
        if topic == BIRTH:
            if payload.strip() == b"online":          # Home Assistant has started: say it all again, after a
                soon = now + 1 + 4 * self.chance()    # moment (its documentation asks for a random delay)
                self.announce_at = soon if self.announce_at is None else min(self.announce_at, soon)
            return
        kind = self.commands.get(topic)
        if kind is None or not payload:
            return                                    # not ours, or the echo of a wipe
        if retained:                                  # an old command the broker kept: never carried out
            if topic not in self.wiped:
                if not self.wiped:
                    self._print("ignored an old command the broker had kept (published with retain), and cleared it")
                self.wiped.add(topic)
                self.client.publish(topic, b"", retain=True)
            return
        if kind == "light_set":
            asked = light_command(payload)
            if asked is None:
                return
            if "awake" in asked:
                self._want("awake", asked["awake"], now)
                if not asked["awake"]:
                    self.wants.pop("brightness", None)
            if "brightness" in asked:
                self._want("brightness", asked["brightness"], now)
        elif kind == "pause_set":
            asked = switch_command(payload)
            if asked is not None:
                self._want("paused", asked, now)
        elif kind == "next_press":
            if press_command(payload):
                self.nexts = min(3, self.nexts + 1)
                self.echo_at = now + GAP
        elif kind == "notify_send":
            note = notify_command(payload)
            if note is None:
                return
            if any(note[:2] == waiting[:2] for waiting in self.notes):
                return                                # the same words are already waiting their turn
            if len(self.notes) >= NOTE_KEEP or len(self.sent_notes(now)) + len(self.notes) >= NOTES_IN_TEN:
                self._dropped(now)
            else:
                self.notes.append((*note, now))

    def _want(self, what, value, now):
        self.wants[what] = {"value": value, "since": now, "tries": 0}
        self.echo_at = now + GAP                      # say the state again soon, so Home Assistant shows what is true

    # -- doing what was asked, one use of each control at a time

    def sent_notes(self, now):
        self.notes_sent = tuple(t for t in self.notes_sent if now - t < 600)
        return self.notes_sent

    def _dropped(self, now, count=1):
        if now - self.dropped_at > SHOWN:
            self.dropped = 0
        self.dropped, self.dropped_at = self.dropped + count, now

    def _may(self, control, now, tries=0) -> bool:
        """May this control be used now? Never two within GAP; a thing asked for and not yet so is asked for
        again after AGAIN, three times at most."""
        return tries < 3 and now - self.asked.get(control, -1e9) >= (AGAIN if tries else GAP)

    def _act(self, panel, now):
        status = getattr(panel, "status", None) or {}
        for what in list(self.wants):
            if now - self.wants[what]["since"] > PATIENCE:
                del self.wants[what]                  # it didn't happen (the Matrix said no): let it go
                self.echo_at = now

        want = self.wants.get("awake")
        if want is not None:
            if "asleep" in status and status["asleep"] != want["value"]:
                del self.wants["awake"]
            elif self._may("sleep", now, want["tries"]):
                (panel.wake if want["value"] else panel.sleep)()
                self.asked["sleep"], want["tries"] = now, want["tries"] + 1

        want = self.wants.get("brightness")
        if want is not None:
            if status.get("brightness") == want["value"] and status.get("brightness_by_hand"):
                del self.wants["brightness"]
            elif status.get("asleep"):
                if "awake" not in self.wants:         # asleep and staying so: a brightness wouldn't outlast the
                    del self.wants["brightness"]      # waking (the Matrix's rule), so it isn't set
            elif self._may("brightness", now, want["tries"]):
                panel.brightness(want["value"])
                self.asked["brightness"], want["tries"] = now, want["tries"] + 1

        want = self.wants.get("paused")
        if want is not None:
            if "paused" in status and status["paused"] == want["value"]:
                del self.wants["paused"]
            elif self._may("playback", now, want["tries"]):
                (panel.pause if want["value"] else panel.resume)()
                self.asked["playback"], want["tries"] = now, want["tries"] + 1
        elif self.nexts and self._may("playback", now):
            panel.next()
            self.asked["playback"], self.nexts = now, self.nexts - 1

        while self.notes and now - self.notes[0][3] > NOTE_STALE:
            self.notes.popleft()
            self._dropped(now)
        if self.notes and now - self.asked.get("message", -1e9) >= NOTE_GAP:
            words, title, seconds, _ = self.notes.popleft()
            panel.message(words, title=title, seconds=seconds)
            self.asked["message"] = now
            self.notes_sent = (*self.sent_notes(now), now)

    # -- telling Home Assistant

    def _announce(self, now):
        qos1 = self.client.publish
        qos1(self.topics["availability"], b"online", qos=1, retain=True)
        self.said_online = now
        qos1(self.topics["discovery"], json.dumps(discovery(self.id, self.name), separators=(",", ":")), qos=1)
        self.told = {}                                # states are said again after every announcement
        self.announce_at = now + REANNOUNCE

    def _tell(self, status, now):
        if not isinstance(status, dict):
            return
        if self.echo_at is not None and now >= self.echo_at:
            self.echo_at, self.told = None, {}
        light = {"state": "OFF" if status.get("asleep") else "ON"}
        level = status.get("brightness")
        if isinstance(level, (int, float)) and not isinstance(level, bool) and 1 <= level <= 100:
            light["brightness"] = int(round(level))
        screen = status.get("screen") or ("Asleep" if status.get("asleep") else "Nothing playing")
        out = {
            self.topics["light_state"]: json.dumps(light, separators=(",", ":")),
            self.topics["screen_state"]: _tidy(str(screen), 255) or "Nothing playing",
            self.topics["screen_attributes"]: json.dumps({"module": status.get("module"), "style": status.get("style")}, separators=(",", ":")),
            self.topics["pause_state"]: "ON" if status.get("paused") else "OFF",
        }
        for topic, payload in out.items():
            if self.told.get(topic) != payload and self.client.publish(topic, payload, retain=True):
                self.told[topic] = payload

    # -- the status line

    def _refusals(self, panel, now):
        for said in getattr(panel, "refused", None) or ():
            if isinstance(said, dict) and said.get("why"):
                self.refused, self.refused_at = _tidy(str(said["why"]), 80), now

    def _status(self, now):
        client = self.client
        if client is None:
            text, ok = self.fault, False
        elif not client.up:
            text, ok = (f"Not connected: {client.problem}" if client.problem else "Connecting to the broker"), False
        elif self.deaf:
            text, ok = "Connected, but the broker won't let this user receive commands", False
        elif now - self.refused_at < SHOWN:
            text, ok = f"Connected. The Matrix refused a change: {self.refused}", False
        elif now - self.dropped_at < SHOWN:
            text, ok = f"Connected. Dropped {self.dropped} message{'s' if self.dropped != 1 else ''}: too many at once", False
        elif client.tls is None:
            text, ok = "Connected to the broker", True
        elif client.checked:
            text, ok = "Connected to the broker (encrypted, certificate matches)", True
        else:
            text, ok = "Connected to the broker (encrypted, certificate not checked)", True
        text = self._safe(text)[:80]
        if (text, ok) != self.said:
            self.said = (text, ok)
            self.report(text, ok=ok)
            self._print(text[:1].lower() + text[1:])

    def _safe(self, text: str) -> str:
        """Never the password, whatever an error dragged in."""
        password = self.key[3] if self.key else ""
        return text.replace(password, "***") if len(password) >= 4 else text

    def _print(self, line: str):
        line = self._safe(line)
        if line != self.printed:                      # the Matrix keeps a module's output short: no repeats
            self.printed = line
            try:
                self.say(line)                        # (the Matrix puts the module's name in front in its Logs)
            except Exception:  # noqa: BLE001 - a full pipe must never stop the bridge
                pass
