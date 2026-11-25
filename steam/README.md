# Steam, for the Bongo Matrix

A module for the Bongo Matrix LED panel that shows what's happening on Steam.
It is an imported module: you add it to your Matrix in **Settings › Modules › Import**, and it runs in a process
of its own that can reach Steam and nothing else.

## What it shows

Four screens, each one you can put in your playlist:

| Screen | What's on it |
| --- | --- |
| **Friends online** | Who's on and what they're playing, those in a game first, then online (and away, if you switch that on). Four to a page on a 64 × 32 panel; the pages take turns, and a long name or game slides along so it can be read. |
| **Now playing** | You or a friend in a game: the game's own picture from Steam across the top (its capsule art, cut down to the panel), who, the game, and how long they've been in it (from when the Matrix saw them start). Several people in games take turns. |
| **Recent games** | Your games of the last two weeks, most played first, with the hours and a bar for each. |
| **Newest achievement** | Your newest achievement: its icon from Steam, its name, the game, and how many players have it ("RARE" when it's 10% or fewer). |

When there's nothing to show (nobody on, nobody playing) a screen skips its turn at once: the playlist carries
straight on.
When something stops it (no key yet, a private profile) the screen says what, in a few words, and the module's
status line in Settings says it in full.

It can also **pop up** when a friend starts a game. That is off until you switch it on, and never shows in the sleep
hours. The pop-up has a look of its own: a band in Steam's blue drops in from the top with their status dot, their
name and STARTED, and the game sliding along under it, then goes back up (on a 64-dot-high panel the game's picture
from Steam sits above the band, and on a 128-dot-wide one to its right). If that look ever fails, the Matrix shows
its words instead: "Jess started Iron Tide" (a long name or game cut short with "…", so the Matrix's banner reads
them through well inside 20 seconds). A pop-up is up for 8 seconds, or, for a long name and game, as long as they
take to slide through, never more than 20 seconds. The pop-up's look is only a pop-up: it isn't offered as a screen
for the playlist.

It needs a Matrix with module API 3 (pop-ups in a module's own look); an older one says to update first.

## Adding it to your Matrix

1. On the dashboard, go to **Settings › Modules › Import**, and give it this repository's link (or a .zip of it).
2. The Matrix draws each screen on a test screen and shows you what the module asks for:
   - **Sites:** `api.steampowered.com` (Steam's Web API), `store.steampowered.com` (only to find where a game's
     picture is) and `shared.akamai.steamstatic.com`, `shared.fastly.steamstatic.com`,
     `shared.cloudflare.steamstatic.com` (Steam's picture servers: the same pictures on each). Nothing else.
   - **Keep working in the background:** it asks Steam what's new while none of its screens is on.
   - **See what the panel is doing:** only so a pop-up never comes in the sleep hours.
   - **Show short messages on the panel:** the pop-up, in its own look ("Started, its pop-ups only").
   - **Keep a secret you type in:** your Steam Web API key.
3. Tick "I trust" and install it. Then fill in its card in **Settings › Modules › Steam** (below) and add its
   screens to your playlist.

## Getting a Steam Web API key (free)

1. Sign in at **https://steamcommunity.com/dev/apikey** with your Steam account. The account mustn't be a *limited*
   one: Steam only gives keys to accounts that have spent at least US$5 in the Steam store (games, DLC or a gift
   card all count).
2. For **Domain Name** type anything that names your Matrix, for example `matrix.local`. Tick that you agree to the
   Steam Web API Terms of Use and press **Register**. Steam may ask you to confirm in the Steam Mobile app.
3. Steam shows your key: 32 letters and digits. Copy it into **Steam Web API key** on the module's card and press
   Save.

The key is kept on the Matrix with its other secrets: never in the config or a backup, never sent back to a browser
(the card only says one is saved), and blanked out of anything the module prints. It is only ever sent to Steam.
The free key allows 100,000 calls a day; this module uses about 2,000.

## Your profile: a link or your SteamID64

**Your Steam profile** takes any of these:

- your profile's link: in Steam, click your name at the top › **Profile**, then copy the address
  (in the Steam app: right-click the page › **Copy Page URL**). It looks like
  `https://steamcommunity.com/id/yourname/` or `https://steamcommunity.com/profiles/7656119.../`;
- just the name in a custom link (`yourname`);
- your **SteamID64**, the 17-digit number starting `7656119`: it's the number in a `/profiles/` link, and Steam shows
  it in **Account details** (under your account name: "Steam ID").

## Privacy settings it needs

Steam only tells the module what your profile shows to everyone. In Steam: your name › **Profile** › **Edit Profile**
› **Privacy Settings**, and set:

| Setting | Needed for |
| --- | --- |
| **My profile: Public** | anything at all |
| **Friends List: Public** | Friends online, Now playing (friends) and the pop-up |
| **Game details: Public** | Recent games, Newest achievement and you on Now playing |
| "Always keep my total playtime private": **off** | the hours on Recent games |

Each friend's own settings decide what you see of them: a friend whose game details aren't public shows as online,
not in a game. If something is private, the module's status line says which part it can't see, and the screens
that need it say so.

## Its settings card

| Setting | |
| --- | --- |
| Steam Web API key | your key (a secret) |
| Your Steam profile | a profile link, the name in a custom link, or your SteamID64 |
| Only these friends | names, with commas between: only those friends are shown and pop up. Empty: all your friends |
| Show friends who are away | off: away friends aren't shown (unless they're in a game) |
| Pop-up: a friend starts a game | off. On: a few seconds' message when a friend you'd see starts a game |

The **status line** under it says how it's going: "Signed in as Sam · 3 friends online · checked 20 s ago", or plainly
what's wrong:

| It says | What to do |
| --- | --- |
| Add your Steam Web API key above | get one (above) and save it |
| Type your Steam profile link or SteamID64 above / That isn't a Steam profile link or SteamID64 | see "Your profile" |
| Steam has no profile called ... | check the custom name in your profile link |
| Steam didn't accept the API key: check it's typed right | copy it again from steamcommunity.com/dev/apikey |
| Your Steam profile is private / Your friends list is private / Your profile's game details are private | see "Privacy settings" |
| Steam asked us to slow down: trying again in 5 min | nothing: it rests, longer each time it's asked |
| Can't reach Steam just now: trying again in 1 min | check the Matrix's internet; the screens keep showing what they had |

## How often it asks Steam

One call at a time, each with a 3-second limit: who's online and playing every minute, your friend list every half
hour, your recent games every 10 minutes, your newest achievement every 15 minutes (one recent game at a time),
its rarity once a day, and each game's picture and icon once (kept in the module's own folder on the Matrix, about
15 kB each, the newest 400). What it found is kept too, so after a restart the screens start from the last news.

## Its pictures

The game pictures and achievement icons are Steam's own, fetched from Steam's picture servers. Everything else (the
status dots, the trophy shown for an achievement with no icon, the controller shown for a game with no picture,
the key and the padlock) is drawn in the Matrix's Animator: the files in `art/` are Animator drawings, and you can
open and change them there (**File › Open a drawing file…**). The status dot is one drawing with a layer for each of
In game, Online and Away; the screens write each person's name and game in their dot's colour.

This module doesn't use Steam's logo, and isn't made or endorsed by Valve. Steam is a trademark of Valve Corporation.

## For developers

The module's folder is the top of this repository (`bongo-module.json` beside `__init__.py`). The tests run against a
Matrix's own code, with Steam played by a stand-in (`tests/fake_steam.py`): nothing reaches the real Steam.

```bash
PYTHONPATH=/path/to/bongo-matrix python -m pytest -q tests
```

`tests/test_import.py` imports this repository as a .zip through the Matrix's real import, its gate and its
sandbox, against the stand-in served over HTTPS. To draw every screen, and the pop-up at 64 × 32, 128 × 32 and
64 × 64 (`popup-*.gif`), as LED-look GIFs for a look (`BONGO_TEST_SANDBOX=on` to draw them in the real sandbox):

```bash
STEAM_REVIEW_OUT=/tmp/steam-review PYTHONPATH=/path/to/bongo-matrix python -m pytest -q tests/test_review.py
```

The tests and tools aren't part of what's installed (`.gitattributes` leaves them out of the archive).

## Licence

MIT: see [LICENSE](LICENSE).
