"""Asking where a parcel is: Ship24 (any courier, its free plan), or DHL's and UPS's own free tracking APIs when their
keys are set. Each answer is turned into the same few words (``Result``) so the rest of the module needn't care
who answered. One call each, with a short timeout: the background task has 5 seconds a tick.

Ship24  https://docs.ship24.com  (per-shipment plan: a new tracker uses one of the month's parcels; asking for its
        results again costs nothing)
DHL     Shipment Tracking - Unified API, https://developer.dhl.com  (250 calls a day on a free key, 1 a second)
UPS     Tracking API with an OAuth client-credentials token, https://developer.ups.com
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

SHIP24 = "https://api.ship24.com/public/v1"
DHL = "https://api-eu.dhl.com/track/shipments"
UPS_TOKEN = "https://onlinetools.ups.com/security/v1/oauth/token"
UPS_TRACK = "https://onlinetools.ups.com/api/track/v1/details/"
HOSTS = ("api.ship24.com", "api-eu.dhl.com", "onlinetools.ups.com")   # all it reaches (bongo-module.json "network")
WAIT = 3.5            # s for one answer: two can't overrun a tick, and only one is asked for in a tick
AGENT = "bongo-parcels/1.0"


class Refused(Exception):
    """A courier or Ship24 said no. ``why``: "key" (the key or ID is wrong), "quota" (this month's free parcels are
    used), "plan" (the Ship24 account has no free API plan switched on), "not_found" (it doesn't know the number),
    "busy" (asked too often: ``wait`` seconds), "token" (UPS's sign-in token has run out: get another), "down" (no
    answer, or a fault at their end)."""

    def __init__(self, why: str, words: str = "", wait: float | None = None):
        super().__init__(words or why)
        self.why, self.wait = why, wait


# -- the answer, the same whoever gave it ----------------------------------------------------------------------
STATES = ("pending", "info", "transit", "out", "failed", "pickup", "problem", "delivered")


def result(state="pending", courier=None, eta=None, slot=None, delivered_at=None, where=None) -> dict:
    """``state`` one of STATES; ``eta`` "YYYY-MM-DD"; ``slot`` [from "HH:MM" or None, to "HH:MM" or None];
    ``delivered_at`` "YYYY-MM-DDTHH:MM" in the Matrix's time; ``where`` a few words (PORCH) or None."""
    return {"state": state, "courier": courier, "eta": eta, "slot": slot, "delivered_at": delivered_at, "where": where}


# -- asking ------------------------------------------------------------------------------------------------------
def ask(url, headers=None, body=None, form=None, timeout=WAIT, opener=None):
    """(status, the JSON answer or None). A fault on the way is Refused("down")."""
    data = None
    headers = {"Accept": "application/json", "User-Agent": AGENT, **(headers or {})}
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    elif form is not None:
        data, headers["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            return r.status, _json(r.read(1 << 20))
    except urllib.error.HTTPError as error:
        try:
            answer = _json(error.read(1 << 16))
        except OSError:
            answer = None
        if error.code == 429:
            raise Refused("busy", "asked too often", _retry_after(error.headers)) from None
        if error.code >= 500:
            raise Refused("down", f"answered {error.code}") from None
        return error.code, answer
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise Refused("down", f"no answer ({getattr(error, 'reason', error)})") from None


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8")) if raw else None
    except ValueError:
        return None


def _retry_after(headers) -> float | None:
    try:
        return max(1.0, min(3600.0, float((headers or {}).get("Retry-After"))))
    except (TypeError, ValueError):
        return None


# -- Ship24 ------------------------------------------------------------------------------------------------------
def ship24_start(key: str, number: str, tz, opener=None) -> tuple[str, dict]:
    """Starts following a parcel (uses one of the month's free parcels) and gives (its tracker's id, where it is)."""
    status, answer = ask(f"{SHIP24}/trackers/track", {"Authorization": f"Bearer {key}"}, body={"trackingNumber": number},
                         opener=opener)
    _ship24_refused(status, answer)
    trackings = ((answer or {}).get("data") or {}).get("trackings") or []
    if not trackings or not (trackings[0].get("tracker") or {}).get("trackerId"):
        raise Refused("down", "Ship24 gave no tracker")
    return trackings[0]["tracker"]["trackerId"], ship24_result(trackings[0], tz)


def ship24_check(key: str, tracker: str, tz, opener=None) -> dict:
    """Where a parcel Ship24 already follows has got to (costs nothing)."""
    status, answer = ask(f"{SHIP24}/trackers/{urllib.parse.quote(tracker, safe='')}/results",
                         {"Authorization": f"Bearer {key}"}, opener=opener)
    _ship24_refused(status, answer)
    trackings = ((answer or {}).get("data") or {}).get("trackings") or []
    if not trackings:
        raise Refused("not_found", "Ship24 has no tracker of that number")
    return ship24_result(trackings[0], tz)


def _ship24_refused(status: int, answer) -> None:
    if status in (200, 201):
        return
    codes = [str(e.get("code")) for e in ((answer or {}).get("errors") or []) if isinstance(e, dict)]
    if "quota_limit_reached" in codes:
        raise Refused("quota", "this month's free parcels are used")
    if "no_active_subscription" in codes:
        raise Refused("plan", "no free API plan on the Ship24 account")
    if status in (401, 403):
        raise Refused("key", "Ship24 didn't accept the key")
    if "tracker_not_found" in codes or status == 404:
        raise Refused("not_found", "Ship24 doesn't know that tracker")
    raise Refused("down", f"Ship24 answered {status}{': ' + codes[0] if codes else ''}")


MILESTONES = {"info_received": "info", "in_transit": "transit", "out_for_delivery": "out", "failed_attempt": "failed",
              "available_for_pickup": "pickup", "exception": "problem", "delivered": "delivered", "pending": "pending"}


def ship24_result(tracking: dict, tz) -> dict:
    shipment = tracking.get("shipment") or {}
    events = sorted((e for e in tracking.get("events") or [] if isinstance(e, dict)),
                    key=lambda e: str(e.get("occurrenceDatetime") or ""), reverse=True)
    state = MILESTONES.get(shipment.get("statusMilestone"), "transit" if events else "pending")
    code = next((e.get("courierCode") for e in events if e.get("courierCode")), None)
    delivery = shipment.get("delivery") or {}
    eta, slot = None, None
    window = delivery.get("courierEstimatedDeliveryDate")
    if isinstance(window, dict) and (window.get("from") or window.get("to")):
        eta, slot = _window(window.get("from"), window.get("to"), tz)
    if eta is None and delivery.get("estimatedDeliveryDate"):
        eta = (_when(delivery["estimatedDeliveryDate"], tz) or (None,))[0]
    done = None
    if state == "delivered":
        stamps = (tracking.get("statistics") or {}).get("timestamps") or {}
        took = stamps.get("deliveredDatetime") or next((e.get("occurrenceDatetime") for e in events
                                                         if e.get("statusMilestone") == "delivered"), None)
        done = _stamp(took, tz)
    said = next((e.get("status") for e in events if e.get("statusMilestone") == shipment.get("statusMilestone")), None)
    return result(state, courier_name(code), eta, slot, done, where(said) if state in ("delivered", "pickup") else None)


NAMES = {"royal-mail": "Royal Mail", "parcelforce": "Parcelforce", "evri": "Evri", "hermes-uk": "Evri", "myhermes-uk": "Evri",
         "dpd-uk": "DPD", "dpd": "DPD", "dpd-local": "DPD Local", "yodel": "Yodel", "dhl": "DHL", "dhl-parcel-uk": "DHL",
         "dhl-express": "DHL", "dhl-ecommerce": "DHL", "ups": "UPS", "fedex": "FedEx", "fedex-uk": "FedEx", "tnt": "TNT",
         "gls": "GLS", "usps": "USPS", "amazon": "Amazon", "amazon-logistics": "Amazon", "an-post": "An Post",
         "inpost-uk": "InPost", "inpost": "InPost", "dx": "DX", "dx-freight": "DX", "apc-overnight": "APC",
         "arrowxl": "ArrowXL", "tuffnells": "Tuffnells", "china-post": "China Post", "cainiao": "Cainiao",
         "yanwen": "Yanwen", "4px": "4PX", "postnl": "PostNL", "deutsche-post": "Deutsche Post", "la-poste": "La Poste"}


def courier_name(code) -> str | None:
    """A courier's name in words (no logo, no colours) from Ship24's code for it: "royal-mail" -> "Royal Mail"."""
    if not code:
        return None
    code = str(code).lower()
    if code in NAMES:
        return NAMES[code]
    words = [w for w in re.split(r"[-_ ]+", code) if w and w not in ("uk", "gb", "com", "api")]
    return " ".join(w.upper() if not set(w) & set("aeiou") else w.capitalize() for w in words)[:20] or None   # (GLS, but New)


# -- DHL -----------------------------------------------------------------------------------------------------------
def dhl(key: str, number: str, tz, opener=None) -> dict:
    status, answer = ask(f"{DHL}?{urllib.parse.urlencode({'trackingNumber': number, 'language': 'en'})}",
                         {"DHL-API-Key": key}, opener=opener)
    if status in (401, 403):
        raise Refused("key", "DHL didn't accept the key")
    if status == 404:
        raise Refused("not_found", "DHL doesn't know that number")
    if status != 200:
        raise Refused("down", f"DHL answered {status}")
    shipments = (answer or {}).get("shipments") or []
    if not shipments:
        raise Refused("not_found", "DHL doesn't know that number")
    s = shipments[0]
    status_ = s.get("status") or {}
    words = " ".join(str(status_.get(k) or "") for k in ("status", "description", "remark")).lower()
    state = {"pre-transit": "info", "transit": "transit", "delivered": "delivered", "failure": "problem"}.get(
        status_.get("statusCode"), "transit")
    if state == "transit" and re.search(r"out for delivery|with (the )?(delivery )?courier|on (its|the) way to you today|loaded onto", words):
        state = "out"
    elif state == "problem" and re.search(r"attempt|not at home|no one", words):
        state = "failed"
    elif state == "transit" and re.search(r"ready for (pick|collect)|available for (pick|collect)|awaiting collection", words):
        state = "pickup"
    eta, slot = None, None
    frame = s.get("estimatedDeliveryTimeFrame") or {}
    if frame.get("estimatedFrom") or frame.get("estimatedThrough"):
        eta, slot = _window(frame.get("estimatedFrom"), frame.get("estimatedThrough"), tz)
    if eta is None and s.get("estimatedTimeOfDelivery"):
        eta = (_when(s["estimatedTimeOfDelivery"], tz) or (None,))[0]
    done = _stamp(status_.get("timestamp"), tz) if state == "delivered" else None
    return result(state, "DHL", eta, slot, done, where(words) if state in ("delivered", "pickup") else None)


# -- UPS -----------------------------------------------------------------------------------------------------------
def ups_token(client_id: str, secret: str, opener=None) -> tuple[str, float]:
    """(a token, seconds it lasts) for UPS's APIs, from the app's client ID and secret."""
    pair = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    status, answer = ask(UPS_TOKEN, {"Authorization": f"Basic {pair}"}, form={"grant_type": "client_credentials"},
                         opener=opener)
    if status in (400, 401, 403):
        raise Refused("key", "UPS didn't accept the client ID and secret")
    if status != 200 or not (answer or {}).get("access_token"):
        raise Refused("down", f"UPS answered {status}")
    try:
        lasts = float(answer.get("expires_in") or 3600)
    except (TypeError, ValueError):
        lasts = 3600.0
    return answer["access_token"], lasts


def ups(token: str, number: str, tz, opener=None) -> dict:
    status, answer = ask(f"{UPS_TRACK}{urllib.parse.quote(number, safe='')}?locale=en_GB&returnSignature=false",
                         {"Authorization": f"Bearer {token}", "transId": uuid.uuid4().hex[:32], "transactionSrc": "bongo-parcels"},
                         opener=opener)
    if status == 401:
        raise Refused("token", "UPS's token has run out")
    if status == 403:
        raise Refused("key", "UPS refused the app (is the Tracking API added to it?)")
    if status == 404:
        raise Refused("not_found", "UPS doesn't know that number")
    if status != 200:
        raise Refused("down", f"UPS answered {status}")
    shipments = ((answer or {}).get("trackResponse") or {}).get("shipment") or []
    packages = (shipments[0].get("package") or []) if shipments else []
    if not packages:
        raise Refused("not_found", "UPS doesn't know that number")
    p = packages[0]
    current = p.get("currentStatus") or {}
    words = " ".join(str(current.get(k) or "") for k in ("description", "simplifiedTextDescription")).lower()
    kind = str(current.get("type") or "").upper()
    state = {"D": "delivered", "X": "problem", "M": "info", "P": "transit", "I": "transit"}.get(kind, "transit")
    if state != "delivered" and "out for delivery" in words:
        state = "out"
    elif state != "delivered" and re.search(r"attempt", words):
        state = "failed"
    elif state != "delivered" and re.search(r"access point|ready for (pick|collect)|available for (pick|collect)", words):
        state = "pickup"
    dates = {d.get("type"): str(d.get("date") or "") for d in p.get("deliveryDate") or [] if isinstance(d, dict)}
    eta = _ymd(dates.get("RDD") or dates.get("SDD"))
    time_ = p.get("deliveryTime") or {}
    slot = None
    if time_.get("type") in ("EDW", "CDW", "IDW"):
        slot = [_hm(time_.get("startTime")), _hm(time_.get("endTime"))]
    elif time_.get("type") in ("CMT", "EOD") and time_.get("endTime"):
        slot = [None, _hm(time_.get("endTime"))]
    done = None
    if state == "delivered":
        day = _ymd(dates.get("DEL")) or eta
        at = _hm(time_.get("endTime")) if time_.get("type") == "DEL" else None
        done = f"{day}T{at or '00:00'}" if day else None
    left = ((p.get("deliveryInformation") or {}).get("location") or "") if state == "delivered" else ""
    return result(state, "UPS", eta, slot if slot and any(slot) else None, done,
                  where(left) or (str(left).upper()[:16] if left else None) if state in ("delivered", "pickup") else None)


# -- times and places, in words for the panel -----------------------------------------------------------------------
def _when(text, tz) -> tuple[str, str | None] | None:
    """("YYYY-MM-DD", "HH:MM" or None for a date alone) in the Matrix's time, from an ISO date or time. A time of
    exactly midnight is a date written as a time: kept as the date it says, never moved by the time zone."""
    if not text:
        return None
    text = str(text).strip()
    try:
        if len(text) <= 10:
            return dt.date.fromisoformat(text[:10]).isoformat(), None
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if (when.hour, when.minute, when.second) == (0, 0, 0):
        return when.date().isoformat(), None
    if when.tzinfo is not None and tz is not None:
        when = when.astimezone(tz)
    return when.date().isoformat(), when.strftime("%H:%M")


def _stamp(text, tz) -> str | None:
    found = _when(text, tz)
    return None if found is None else f"{found[0]}T{found[1] or '00:00'}"


def _window(start, end, tz) -> tuple[str | None, list | None]:
    a, b = _when(start, tz), _when(end, tz)
    day = (b or a)[0] if (a or b) else None
    if a and b and a[0] != b[0]:                       # a window over days: only the last day means anything
        return b[0], None
    slot = [a[1] if a else None, b[1] if b else None]
    return day, slot if any(slot) else None


def _ymd(text) -> str | None:
    text = str(text or "")
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if re.fullmatch(r"\d{8}", text) else None


def _hm(text) -> str | None:
    text = str(text or "")
    return f"{text[:2]}:{text[2:4]}" if re.fullmatch(r"\d{4}(\d{2})?", text) else None


PLACES = ((r"porch", "PORCH"), (r"neighbou?r", "NEIGHBOUR"), (r"safe ?place", "SAFE PLACE"), (r"locker", "LOCKER"),
          (r"parcel ?shop", "PARCEL SHOP"), (r"post office", "POST OFFICE"), (r"(pick-?up|collection|access) point", "PICKUP POINT"),
          (r"letter ?box|mail ?box|through the door", "LETTERBOX"), (r"front door", "FRONT DOOR"), (r"back door", "BACK DOOR"),
          (r"side door", "SIDE DOOR"), (r"reception", "RECEPTION"), (r"mail ?room|post ?room", "MAIL ROOM"),
          (r"garage", "GARAGE"), (r"shed", "SHED"), (r"garden", "GARDEN"), (r"doorstep|front step", "DOORSTEP"),
          (r"in person|handed|to (the )?(recipient|resident|customer|addressee)|signed", "HANDED OVER"))


def where(text) -> str | None:
    """Where a parcel was left, in a word or two the panel can show (PORCH, NEIGHBOUR), from a courier's words.
    Never a name: who signed for it stays out."""
    text = str(text or "").lower()
    return next((said for pattern, said in PLACES if re.search(pattern, text)), None)
