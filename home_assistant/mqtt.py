"""MQTT 3.1.1: as much of it as this module needs, and written so that it never waits.

An imported module may use only Python's own library, and its background task must return quickly every
time (a tick that takes 5 seconds is taken for a hang), so this is a client made of small steps:

    client = Client(dial, "bongo-matrix-1a2b3c4d", username="matrix", password="...", will=(topic, b"offline"))
    for event in client.step():        # once a tick: does what can be done now and returns
        ...                            # ("up",) ("down", why) ("message", topic, payload, retained) ("subscribed", codes)

``dial()`` returns a connected socket (the Matrix's ``home_connect``), and is the only call here that may
wait, for as long as its own timeout. Everything after it is non-blocking: the TLS handshake, the hello, a
broker that accepts and then says nothing, half a packet, a flood. What is spoken: CONNECT with a user name,
password and last will, a clean session, SUBSCRIBE, PUBLISH in and out at QoS 0 and 1 (retained or not),
PINGREQ to keep the connection alive, DISCONNECT. QoS 2 is not: nothing here subscribes at it.
"""
from __future__ import annotations

import hashlib
import random
import select
import socket
import ssl
import time

CONNECT, CONNACK, PUBLISH, PUBACK, PUBREC, PUBREL, PUBCOMP = 1, 2, 3, 4, 5, 6, 7
SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ, PINGRESP, DISCONNECT = 8, 9, 10, 11, 12, 13, 14
LONGEST = 268_435_455                 # the most a packet's "remaining length" can say (four bytes of seven bits)

REFUSALS = {                          # CONNACK return codes, in plain words
    1: "the broker doesn't speak this kind of MQTT (3.1.1)",
    2: "the broker refused this Matrix's client name",
    3: "the broker isn't ready yet",
    4: "the broker refused the username or password",
    5: "the broker refused the username or password",
}


class ProtocolError(Exception):
    """What arrived isn't MQTT 3.1.1 as a broker speaks it."""


# ---------------------------------------------------------------------------------------------- the codec

def encode_length(n: int) -> bytes:
    """The "remaining length" of a packet: seven bits a byte, lowest first, the top bit meaning "more"."""
    if not 0 <= n <= LONGEST:
        raise ValueError("a packet can't be that long")
    out = bytearray()
    while True:
        n, low = n >> 7, n & 0x7F
        out.append(low | (0x80 if n else 0))
        if not n:
            return bytes(out)


def decode_length(data, start: int = 0):
    """(the length, how many bytes said it), or None when the bytes so far stop in the middle of it."""
    value = 0
    for k in range(4):
        if start + k >= len(data):
            return None
        byte = data[start + k]
        value |= (byte & 0x7F) << (7 * k)
        if not byte & 0x80:
            return value, k + 1
    raise ProtocolError("a packet's length ran past four bytes")


def text(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 0xFFFF:
        raise ValueError("too long for MQTT")
    return len(raw).to_bytes(2, "big") + raw


def packet(kind: int, flags: int, body: bytes = b"") -> bytes:
    return bytes([kind << 4 | flags]) + encode_length(len(body)) + body


def connect_packet(client_id: str, keepalive: int, username: str = "", password: str = "", will=None) -> bytes:
    """CONNECT, clean session. ``will`` is (topic, payload, qos, retain) or None."""
    flags, payload = 0x02, text(client_id)
    if will:
        topic, message, qos, retain = will
        flags |= 0x04 | (qos & 3) << 3 | (0x20 if retain else 0)
        payload += text(topic) + len(message).to_bytes(2, "big") + message
    if username:
        flags |= 0x80
        payload += text(username)
    if password:
        if not username:
            raise ValueError("MQTT 3.1.1 takes a password only with a user name")
        raw = password.encode("utf-8")
        flags |= 0x40
        payload += len(raw).to_bytes(2, "big") + raw
    return packet(CONNECT, 0, b"\x00\x04MQTT\x04" + bytes([flags]) + keepalive.to_bytes(2, "big") + payload)


def publish_packet(topic: str, payload: bytes, qos: int = 0, retain: bool = False, packet_id: int = 0, dup: bool = False) -> bytes:
    if qos not in (0, 1):
        raise ValueError("only QoS 0 and 1 are spoken here")
    if not topic or "#" in topic or "+" in topic or "\0" in topic:
        raise ValueError("not a topic to publish to")
    body = text(topic) + (packet_id.to_bytes(2, "big") if qos else b"") + payload
    return packet(PUBLISH, (0x08 if dup else 0) | qos << 1 | (1 if retain else 0), body)


def subscribe_packet(packet_id: int, topics) -> bytes:
    """``topics``: [(filter, qos), ...]."""
    return packet(SUBSCRIBE, 0x02, packet_id.to_bytes(2, "big") + b"".join(text(t) + bytes([q]) for t, q in topics))


def read_publish(flags: int, body: bytes):
    """(topic, payload, qos, retained, packet id, dup) of a PUBLISH. The topic is None if it isn't UTF-8."""
    qos = flags >> 1 & 3
    if qos == 3 or len(body) < 2:
        raise ProtocolError("a PUBLISH that makes no sense")
    end = 2 + int.from_bytes(body[:2], "big")
    if end + (2 if qos else 0) > len(body):
        raise ProtocolError("a PUBLISH shorter than it says")
    try:
        topic = body[2:end].decode("utf-8")
    except UnicodeDecodeError:
        topic = None
    packet_id = int.from_bytes(body[end:end + 2], "big") if qos else 0
    return topic, bytes(body[end + (2 if qos else 0):]), qos, bool(flags & 1), packet_id, bool(flags & 8)


class Reader:
    """Cuts the stream into packets, whatever pieces it arrives in.

    A packet longer than ``limit`` is not kept: its bytes are thrown away as they come and ``oversize``
    counts it. One longer than ``refuse`` raises ProtocolError: better to hang up than to read it out."""

    def __init__(self, limit: int = 16_384, refuse: int = 1_048_576):
        self.limit, self.refuse = limit, refuse
        self.buffer = bytearray()
        self.skip = 0                 # bytes of an oversize packet still to throw away
        self.oversize = 0

    def feed(self, data: bytes) -> list:
        """Give it what arrived; get [(kind, flags, body), ...] for every packet now complete."""
        self.buffer += data
        out = []
        while True:
            if self.skip:
                gone = min(self.skip, len(self.buffer))
                del self.buffer[:gone]
                self.skip -= gone
                if self.skip:
                    return out
            if len(self.buffer) < 2:
                return out
            kind, flags = self.buffer[0] >> 4, self.buffer[0] & 0x0F
            if kind in (0, 15):
                raise ProtocolError("not an MQTT packet")
            length = decode_length(self.buffer, 1)
            if length is None:
                return out
            size, used = length
            if size > self.refuse:
                raise ProtocolError("a packet far too big")
            if size > self.limit:
                self.skip, self.oversize = 1 + used + size, self.oversize + 1
                continue
            if len(self.buffer) < 1 + used + size:
                return out
            out.append((kind, flags, bytes(self.buffer[1 + used:1 + used + size])))
            del self.buffer[:1 + used + size]


# ---------------------------------------------------------------------------------------------- the client

class Down(Exception):
    """The connection is over (or never began). ``kind`` picks how long to rest before the next try:
    "net" (the broker can't be reached or hung up), "auth" (it said no: asking again soon won't help),
    "refused" (the Matrix won't dial that address at all)."""

    def __init__(self, why: str, kind: str = "net"):
        super().__init__(why)
        self.kind = kind


RESTS = {                             # seconds before the next try, by how many have failed in a row
    "net": (3, 6, 12, 25, 50, 60),
    "auth": (30, 60, 120, 300, 600),
    "refused": (60,),
}
WANTS = (BlockingIOError, InterruptedError, ssl.SSLWantReadError, ssl.SSLWantWriteError)


def fingerprint(value: str) -> str:
    """A certificate fingerprint as typed (AB:CD:..., spaces, either case) to 64 lower-case hex digits, or ""
    for none. Raises ValueError if it isn't a SHA-256 one."""
    plain = "".join(c for c in str(value or "").lower().rpartition("=")[2] if c not in ": -\t")   # ("sha256 Fingerprint=AB:CD...")
    if not plain:
        return ""
    if len(plain) != 64 or any(c not in "0123456789abcdef" for c in plain):
        raise ValueError("not a SHA-256 fingerprint")
    return plain


class Client:
    """One broker, one set of credentials. Make a new one when either changes.

    ``tls``: None for a plain connection, or a dict {"fingerprint": 64 hex digits or "", "name": the
    address as typed}. The connection is then encrypted. The broker's certificate is NOT checked against
    any authority or name (a broker at home has one of its own making); with a fingerprint, the certificate
    must be exactly that one or the connection is dropped before anything is sent over it.
    """

    KEEPALIVE = 30                    # seconds; the broker posts the last will 1.5 times this after silence
    HELLO = 8.0                       # how long the TLS handshake and the broker's answer may take, each
    PONG = 10.0                       # how long a ping may go unanswered
    WAIT = 0.8                        # the most one step waits on the network after dialling (while saying hello)
    SPEND = 2.8                       # ...and the most a whole step may take, dialling included
    OUTBOX = 262_144                  # bytes that may wait to be sent before the broker is taken for stuck

    def __init__(self, dial, client_id: str, *, username: str = "", password: str = "", will=None, tls=None,
                 subscribe=(), clock=time.monotonic, chance=random.random):
        self.dial, self.client_id, self.username, self.password = dial, client_id, username, password
        self.will, self.tls, self.topics = will, tls, list(subscribe)
        self.clock, self.chance = clock, chance
        self.state = "idle"           # idle -> (tls ->) hello -> up
        self.sock = None
        self.problem = ""             # why it isn't connected, in plain words ("" before the first try)
        self.fails = 0
        self.retry_at = 0.0
        self.seen_certificate = ""    # the SHA-256 of the certificate the broker showed, as hex
        self.checked = False          # True: that certificate was matched against a fingerprint
        self.ignored = 0              # packets thrown away for being too big, or with a topic that isn't text
        self._reset()

    # -- what the owner of the client calls

    @property
    def up(self) -> bool:
        return self.state == "up"

    def step(self) -> list:
        """Do what can be done now. Returns the events since the last step, oldest first."""
        events, began = [], self.clock()
        try:
            if self.state == "idle":
                if began < self.retry_at:
                    return events
                self._dial()
            waiting = min(self.clock() + self.WAIT, began + self.SPEND)
            if self.state == "tls":
                self._handshake(waiting)
            if self.state in ("hello", "up"):
                self._pump(events, waiting)
            self._timers()
        except Down as down:
            self._down(str(down), down.kind, events)
        except (ProtocolError, OSError) as error:     # (a broken TLS connection is an OSError too)
            if self.state == "hello":
                self._down(self._no_hello(), "net", events)
            else:
                self._down("the broker sent something that isn't MQTT" if isinstance(error, ProtocolError) else "the broker hung up", "net", events)
        return events

    def _no_hello(self) -> str:
        """Hello was said and no broker answered it (silence, a closed door, or something that isn't MQTT)."""
        return "no MQTT answer from that address" if self.tls else "no MQTT answer: an encrypted port needs Encrypted (TLS) on"

    def publish(self, topic: str, payload, qos: int = 0, retain: bool = False) -> bool:
        """Queue a message. False (and nothing queued) when not connected."""
        if self.state != "up":
            return False
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        packet_id = self._next_id() if qos else 0
        if qos:
            self.unacked[packet_id] = self.clock()
        self._queue(publish_packet(topic, payload, qos, retain, packet_id))
        return True

    def close(self, farewell=()) -> None:
        """Hang up tidily if the connection allows it: ``farewell`` is [(topic, payload, retain), ...] to
        say first (a clean DISCONNECT makes the broker forget the last will, so "offline" must be said).
        Never waits: what the socket won't take at once is not sent, and the last will covers it."""
        if self.state == "up" and self.sock is not None:
            try:
                for topic, payload, retain in farewell:
                    self.publish(topic, payload, 0, retain)
                self._queue(packet(DISCONNECT, 0))
                self._flush()
            except (OSError, Down, ProtocolError, ValueError):
                pass
        self._hang_up()
        self.state = "idle"

    def retry_now(self) -> None:
        self.fails, self.retry_at = 0, 0.0

    # -- the steps

    def _reset(self):
        self.reader = Reader()
        self.outbox = bytearray()
        self.chunk = b""              # what is being sent now (TLS wants the very same bytes again after a "not yet")
        self.unacked = {}             # our QoS 1 packet ids -> when sent
        self.packet_id = 0
        self.deadline = 0.0           # for the handshake, then for the broker's answer to hello
        self.last_sent = self.up_since = 0.0
        self.ping_sent = None
        self.subscribed = None        # the broker's answer to SUBSCRIBE: a list of granted QoS, 0x80 for "no"

    def _next_id(self) -> int:
        for _ in range(0xFFFF):
            self.packet_id = self.packet_id % 0xFFFF + 1
            if self.packet_id not in self.unacked:
                return self.packet_id
        raise Down("the broker stopped answering")

    def _dial(self):
        self._reset()
        self.seen_certificate, self.checked = "", False
        if self.password and not self.username:
            raise Down("a password needs a username too", "refused")
        try:
            sock = self.dial()
        except PermissionError as error:      # the Matrix won't dial it, and says why in plain words
            raise Down(str(error) or "the Matrix won't connect to that address", "refused") from None
        except (socket.timeout, TimeoutError):
            raise Down("no answer from that address") from None
        except ConnectionRefusedError:
            raise Down("nothing is listening at that address and port") from None
        except OSError as error:
            raise Down(plain(error) or "that address can't be reached") from None
        self.sock = sock
        sock.setblocking(False)
        self.deadline = self.clock() + self.HELLO
        if self.tls is None:
            return self._hello()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False        # said plainly in the README and by the switch: encrypted, and
        context.verify_mode = ssl.CERT_NONE   # checked only against the fingerprint, when one is given
        try:
            self.sock = context.wrap_socket(sock, do_handshake_on_connect=False, server_hostname=self.tls.get("name") or None)
        except (ssl.SSLError, ValueError, OSError):
            raise Down("the encrypted connection couldn't be started") from None
        self.state = "tls"

    def _handshake(self, waiting: float):
        while True:
            try:
                self.sock.do_handshake()
                break
            except ssl.SSLWantReadError:
                ready = self._wait(waiting, read=True)
            except ssl.SSLWantWriteError:
                ready = self._wait(waiting, read=False)
            except (ssl.SSLError, OSError):
                raise Down("no encrypted answer: is that the broker's encrypted (TLS) port?") from None
            if not ready:
                if self.clock() > self.deadline:
                    raise Down("no encrypted answer: is that the broker's encrypted (TLS) port?")
                return
        shown = self.sock.getpeercert(binary_form=True)
        self.seen_certificate = hashlib.sha256(shown).hexdigest() if shown else ""
        wanted = self.tls.get("fingerprint") or ""
        if wanted:
            if self.seen_certificate != wanted:
                raise Down("the broker's certificate doesn't match the fingerprint", "auth")
            self.checked = True
        self.deadline = self.clock() + self.HELLO
        self._hello()

    def _hello(self):
        self.state = "hello"
        self._queue(connect_packet(self.client_id, self.KEEPALIVE, self.username, self.password, self.will))

    def _wait(self, until: float, read: bool) -> bool:
        """Wait for the socket, never past ``until``. True if it is ready."""
        left = until - self.clock()
        if left <= 0:
            return False
        try:
            r, w, _ = select.select([self.sock] if read else [], [] if read else [self.sock], [], min(left, self.WAIT))
        except (OSError, ValueError):
            raise Down("the broker hung up") from None
        return bool(r or w)

    def _pump(self, events: list, waiting: float):
        self._flush()
        reads = 0
        while reads < 16 and len(events) < 2000:
            try:
                data = self.sock.recv(16_384)
            except WANTS:
                if self.state == "hello" and self._wait(waiting, read=True):
                    continue                  # only while saying hello: a broker answers within moments
                break
            reads += 1
            if not data:
                raise Down(self._no_hello() if self.state == "hello" else "the broker hung up")
            if self.state == "hello" and not self.reader.buffer and data[0] != CONNACK << 4:
                raise ProtocolError("not a broker's answer to hello")
            for kind, flags, body in self.reader.feed(data):
                self._packet(kind, flags, body, events)
        self.ignored += self.reader.oversize
        self.reader.oversize = 0
        self._flush()

    def _packet(self, kind: int, flags: int, body: bytes, events: list):
        if self.state == "hello":
            if kind != CONNACK or len(body) != 2:
                raise ProtocolError("no CONNACK")
            if body[1]:
                why = REFUSALS.get(body[1], "the broker refused the connection")
                if body[1] in (4, 5) and not self.username:
                    why = "the broker wants a username and password"
                raise Down(why, "auth" if body[1] in (4, 5) else "net")
            self.state, self.up_since, self.problem = "up", self.clock(), ""
            if self.topics:
                self._queue(subscribe_packet(self._next_id(), self.topics))
            events.append(("up",))
        elif kind == PUBLISH:
            topic, payload, qos, retained, packet_id, _ = read_publish(flags, body)
            if qos == 2:
                raise ProtocolError("QoS 2 was never asked for")
            if qos == 1:
                self._queue(packet(PUBACK, 0, packet_id.to_bytes(2, "big")))
            if topic is None:
                self.ignored += 1
            else:
                events.append(("message", topic, payload, retained))
        elif kind == PUBACK and len(body) == 2:
            self.unacked.pop(int.from_bytes(body, "big"), None)
        elif kind == SUBACK and len(body) >= 3:
            self.subscribed = list(body[2:])
            events.append(("subscribed", self.subscribed))
        elif kind == PINGRESP:
            self.ping_sent = None
        elif kind == CONNACK:
            raise ProtocolError("a second CONNACK")
        # anything else a broker has no business sending is let go by

    def _timers(self):
        now = self.clock()
        if self.state in ("tls", "hello") and now > self.deadline:
            if self.state == "tls":
                raise Down("no encrypted answer: is that the broker's encrypted (TLS) port?")
            raise Down(self._no_hello())
        if self.state != "up":
            return
        if self.ping_sent is not None and now - self.ping_sent > self.PONG:
            raise Down("the broker stopped answering")
        if self.unacked and now - min(self.unacked.values()) > self.KEEPALIVE:
            raise Down("the broker stopped answering")
        if self.ping_sent is None and now - self.last_sent >= self.KEEPALIVE / 2:
            self._queue(packet(PINGREQ, 0))
            self.ping_sent = now
            self._flush()

    def _queue(self, data: bytes):
        if len(self.outbox) + len(data) > self.OUTBOX:
            raise Down("the broker stopped listening")
        self.outbox += data
        self.last_sent = self.clock()

    def _flush(self):
        for _ in range(64):
            if not self.chunk:
                if not self.outbox:
                    return
                self.chunk = bytes(self.outbox[:16_384])
                del self.outbox[:16_384]
            try:
                sent = self.sock.send(self.chunk)
            except WANTS:
                return
            self.chunk = self.chunk[sent:]

    def _hang_up(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def _down(self, why: str, kind: str, events: list):
        was_up = self.state == "up"
        if was_up and self.clock() - self.up_since >= 60:
            self.fails = 0                    # it had been working: start the rests from the shortest again
        self._hang_up()
        self.state, self.problem = "idle", why
        rests = RESTS[kind]
        rest = rests[min(self.fails, len(rests) - 1)]
        self.fails += 1
        self.retry_at = self.clock() + rest * (0.85 + 0.3 * self.chance())   # not every Matrix at the same moment
        events.append(("down", why))


def plain(error: BaseException) -> str:
    """An error as a few plain words: its own message without the "[Errno 111]" in front."""
    words = (getattr(error, "strerror", None) or str(error) or "").strip()
    if words.startswith("[Errno") and "]" in words:
        words = words.split("]", 1)[1].strip()
    return words[:1].lower() + words[1:] if words else ""
