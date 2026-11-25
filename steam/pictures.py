"""Steam's own pictures, cut down to the panel: a game's capsule art (the wide picture Steam shows it with in lists),
a game's small icon and an achievement's icon. Each is fetched once from Steam's CDN by the background task and kept
as it came in the module's working folder (``pictures/``); the screens cut it to the size they need, with good
resampling, a little sharpening and a few less colours, so it reads on the LEDs rather than as JPEG noise."""
from __future__ import annotations

import hashlib
import io
import os
import time
import urllib.parse
from functools import lru_cache

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

FOLDER = "pictures"
CDN = ("shared.akamai.steamstatic.com", "shared.fastly.steamstatic.com", "shared.cloudflare.steamstatic.com")
MOST_FILES = 400                 # about 6 MB of capsules: well inside the 100 MB a module may keep
RETRY = 24 * 3600                # s before a picture Steam didn't have is asked for again


def capsule_urls(appid) -> list[str]:
    """Where a game's capsule art usually is, the small one first (231x87 is plenty for 64 dots across)."""
    base = f"https://{CDN[0]}/store_item_assets/steam/apps/{int(appid)}"
    return [f"{base}/capsule_231x87.jpg", f"{base}/header.jpg"]


def icon_url(appid, file_hash: str) -> str | None:
    """A game's (or an achievement's) icon from the hash Steam's API gives for it."""
    if not file_hash or not all(c in "0123456789abcdef" for c in file_hash.lower()):
        return None
    return f"https://{CDN[0]}/community_assets/images/apps/{int(appid)}/{file_hash.lower()}.jpg"


def on_cdn(url: str, appid=None) -> str | None:
    """A picture address Steam gave us, moved to a CDN host this module may reach (the same file is on each of
    them; older answers name hosts it doesn't list). None if it isn't a Steam picture at all."""
    try:
        parts = urllib.parse.urlsplit(str(url))
    except ValueError:
        return None
    path = parts.path
    if not path.lower().endswith((".jpg", ".jpeg", ".png")) or ".." in path:
        return None
    old = "/steamcommunity/public/images/apps/"            # (the old place for icons: now community_assets)
    if path.startswith(old):
        path = "/community_assets/images/apps/" + path[len(old):]
    host = parts.hostname if parts.hostname in CDN else CDN[0]
    return f"https://{host}{path}"


def name_for(key: str) -> str:
    return os.path.join(FOLDER, hashlib.sha1(key.encode()).hexdigest()[:20] + ".img")


def have(key: str) -> bool:
    return os.path.isfile(name_for(key))


def keep(key: str, data: bytes) -> bool:
    """Keep a fetched picture under ``key`` ("capsule:620"). False if it isn't a picture Pillow can read."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception:              # (Pillow raises many kinds for a broken file)
        return False
    os.makedirs(FOLDER, exist_ok=True)
    with open(name_for(key) + ".new", "wb") as f:
        f.write(data)
    os.replace(name_for(key) + ".new", name_for(key))
    tidy()
    return True


def tidy() -> None:
    """Only the newest ``MOST_FILES`` are kept: games nobody plays any more fall out."""
    try:
        files = [os.path.join(FOLDER, n) for n in os.listdir(FOLDER) if n.endswith(".img")]
    except OSError:
        return
    if len(files) > MOST_FILES:
        files.sort(key=lambda p: os.stat(p).st_mtime)
        for path in files[:len(files) - MOST_FILES]:
            try:
                os.remove(path)
            except OSError:
                pass


def picture(key: str, w: int, h: int) -> Image.Image | None:
    """The picture kept under ``key``, cut to ``w`` x ``h`` (covering it, the middle kept), or None if there isn't one."""
    path = name_for(key)
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return None
    return _cut(path, stamp, w, h)


@lru_cache(maxsize=48)
def _cut(path: str, stamp: int, w: int, h: int) -> Image.Image | None:
    try:
        with Image.open(path) as img:
            img.draft("RGB", (w * 2, h * 2))          # (a JPEG decodes smaller straight away: much less work)
            return cut(img.convert("RGB"), w, h)
    except Exception:              # a damaged file: as if there were none (it is fetched again another day)
        return None


def cut(img: Image.Image, w: int, h: int, colours: int = 64) -> Image.Image:
    """``img`` scaled to cover ``w`` x ``h`` and its middle kept: Lanczos, sharpened a little (scaling down blurs
    the edges that make it readable), a touch more colourful (LEDs wash out pale colours), then held to a few
    colours without dithering, which only shows on a panel as speckle."""
    scale = max(w / img.width, h / img.height)
    size = (max(w, round(img.width * scale)), max(h, round(img.height * scale)))
    big = img.resize(size, Image.LANCZOS, reducing_gap=3.0)
    left, top = (size[0] - w) // 2, (size[1] - h) // 2
    out = big.crop((left, top, left + w, top + h))
    out = out.filter(ImageFilter.UnsharpMask(radius=0.8, percent=60, threshold=2))
    out = ImageEnhance.Color(out).enhance(1.15)
    return out.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")


def accent(img: Image.Image | None, fallback=(255, 181, 71)) -> tuple:
    """A picture's liveliest colour, brightened: a game's bar on the recent games screen."""
    if img is None:
        return fallback
    a = np.asarray(img.convert("RGB").resize((6, 6)), dtype=float).reshape(-1, 3)
    best = a[(a.max(1) - a.min(1) + a.max(1) * 0.3).argmax()]
    return tuple(int(v) for v in best / max(best.max(), 1) * 255)


def missing_again(missing: dict, key: str, now: float | None = None) -> bool:
    """Whether a picture Steam didn't have (``missing``: key -> when) may be asked for again."""
    now = time.time() if now is None else now
    return now - missing.get(key, 0) > RETRY
