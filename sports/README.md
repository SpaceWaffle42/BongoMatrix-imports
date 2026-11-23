# Sports for Bongo Matrix

Ten sports on the panel, and a countdown to the Olympics and Paralympics. Each Sports screen follows one thing:

- **a team**: Football, Cricket, Rugby union, American football, Basketball, Ice hockey or Baseball. The next
  match, the live score (where the source has one), the result, and the league table (where there is one);
- **the Formula 1 championship**: the next race with a countdown, the last race's podium, the drivers' standings,
  and a driver of your choice picked out;
- **a tennis or golf tour** (ATP or WTA, PGA Tour or DP World Tour): the current or next tournament, then its
  winner, with a player of your choice picked out when they appear.

The **Games** screen style counts down to the next Olympics or Paralympics, says DAY 5 OF 17 while they are on, and
shows the Games after that in turn. It needs no key.

Version 2.0.0, by spacewaffle42. MIT licence. This is a module you import. None of it is part of the Matrix itself.

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose `sports-2.0.0.zip` (or paste this repo's
link). The Matrix draws the screen on a test screen first, shows the three sites it can reach, and asks you to tick
that you trust the author. Then add a Sports screen to the playlist, one for each thing you follow: the playlist
takes them in turn.

Updating from 1.x: your screens carry over (a football screen keeps its team, views and source), and so does your
key, under **Key**. **Key** is only ever football-data.org's and **Premium key** only ever TheSportsDB's: nothing is
guessed and nothing falls back from one to the other. So if your 1.x screens used TheSportsDB there is one step.
Your 1.x TheSportsDB key is still under Key, which 2.0 only sends to football-data.org: paste it under Premium key,
then clear Key (or put your football-data.org key there). Until you do, those screens say NEEDS A KEY, THESPORTSDB
PREMIUM and fetch nothing.

## What you need for each sport

No key ships with this module, nothing is scraped, and no service here charges per request.

| Sport | Source | Key | Next | Live score | Result | Table |
|---|---|---|---|---|---|---|
| Football | football-data.org, or TheSportsDB | football-data.org's free key, or TheSportsDB Premium | Yes | TheSportsDB: about every 2 minutes. football-data.org's free plan: late ("delayed") | Yes | football-data.org only |
| Cricket | TheSportsDB | Premium | Yes | No | Yes, with the result in words ("won by 6 wickets") | No |
| Rugby union | TheSportsDB | Premium | Yes | No | Yes | No |
| Tennis | TheSportsDB | Premium | Current or next tournament | No | Its winner | No rankings |
| Formula 1 | Jolpica-F1 | None | Next race, with a countdown | No | The podium | Drivers' standings |
| Golf | TheSportsDB | Premium | Current or next tournament | No | Its winner | No rankings |
| American football | TheSportsDB | Premium | Yes | About every 2 minutes | Yes | No |
| Basketball | TheSportsDB | Premium | Yes | About every 2 minutes | Yes | No |
| Ice hockey | TheSportsDB | Premium | Yes | About every 2 minutes | Yes | No |
| Baseball | TheSportsDB | Premium | Yes | About every 2 minutes | Yes | No |
| Olympics and Paralympics | Bundled dates | None | Countdown, DAY n OF m | No medal table | | |

**TheSportsDB Premium** is a flat monthly fee (US$9 a month on its pricing page), never a charge per request.
Every sport but football and Formula 1 needs it. Its free key, "123", is one test key everyone shares, on its old
API only, where an answer is one fixture: too little for any of these screens, and not yours, so this module
doesn't offer it. Without Premium, those sports' screens say NEEDS A KEY, THESPORTSDB PREMIUM on the panel, and
their settings say so too.

### Setting up each sport

1. Add a Sports screen and pick the **Sport**.
2. **Football**: pick the **Source**. For football-data.org, register at football-data.org (free): your key, which
   it calls an API token, comes by email. Paste it under **Key**. For TheSportsDB, use the Premium key (step 3).
   Type your team under **Team**.
3. **Cricket, Rugby union, American football, Basketball, Ice hockey, Baseball**: subscribe to Premium on
   thesportsdb.com, copy the API key from your profile there, and paste it under **Premium key**. Type your team
   under **Team** (`Perth Scorchers`, `England`, `Knicks`), or its number on TheSportsDB.
4. **Tennis and golf**: the Premium key as in step 3, then pick the **Tour**. Optionally type a player under
   **Highlight** (`Draper`).
5. **Formula 1**: nothing to set up. Optionally type a driver under **Highlight** (`NOR` or `Norris`).
6. **The Games**: pick the **Games** screen style. Choose Olympics, Paralympics or both, and summer, winter or both.

Both keys are kept on the Matrix, entered once for every Sports screen, masked, and never shown again.

## What each source gives, and where it was read

Read on 23 November 2026 (football-data.org on 18 November).

- **football-data.org**, API v4: the key goes in the `X-Auth-Token` header. The free plan: 12 competitions,
  10 requests a minute, "Scores delayed", fixtures and league tables. Live scores start at its "Free w/ Livescores"
  plan (EUR 12 a month, flat). Used: `/v4/competitions/{code}/teams`, `/v4/teams/{id}`, `/v4/teams/{id}/matches`,
  `/v4/matches/{id}`, `/v4/competitions/{code}/standings`.
  <https://www.football-data.org/pricing>, <https://www.football-data.org/coverage>, <https://docs.football-data.org/general/v4/index.html>
- **TheSportsDB**, API v2, "only for premium subscribers": the key goes in the `X-API-KEY` header; 100 requests a
  minute; its pricing page lists two-minute live scores for football and four North American leagues (NFL, NBA,
  MLB, NHL), so live scores for football, American football, basketball, baseball and ice hockey only. Used: `/search/team/{name}`, `/lookup/team/{id}`,
  `/schedule/next/team/{id}`, `/schedule/previous/team/{id}`, `/livescore/{league id}`,
  `/schedule/next/league/{id}`, `/schedule/previous/league/{id}` (a tour's events), `/lookup/event_results/{id}`
  (a golf tournament's places). Tours by their league numbers there: ATP 4464, WTA 4517, PGA Tour 4425, DP World
  Tour 4426 (which TheSportsDB still calls the European Tour).
  <https://www.thesportsdb.com/documentation>, <https://www.thesportsdb.com/pricing>,
  <https://www.thesportsdb.com/sport/Tennis>, <https://www.thesportsdb.com/sport/Golf>
- **Jolpica-F1** (the successor to Ergast), free, no key: `/ergast/f1/current/races/`, `/current/last/results/`,
  `/current/driverstandings/`. Limits: 4 requests a second and 500 an hour, "subject to change", so the calendar is
  kept 12 hours and the rest asked for every 3 hours. It has no live timing.
  <https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md>, <https://github.com/jolpica/jolpica-f1/blob/main/docs/rate_limits.md>
- **The Games** (bundled, no source): LA 2028 Olympic Games 14 to 30 July 2028, Paralympic Games 15 to 27 August
  2028 (<https://olympics.com/en/news/la-2028-olympic-paralympic-games-dates-confirmed>); French Alps 2030 Olympic
  Winter Games 1 to 17 February 2030 and Paralympic Winter Games 1 to 10 March 2030, which olympics.com still calls
  proposed (<https://olympics.com/en/news/olympic-winter-games-french-alps-2030-top-facts-you-need-to-know-about-the-host>,
  <https://www.paralympic.org/french-alps-2030>). No free, documented source for live medal tables exists, so there
  is none here. Later Games come with later versions.

What these sources don't give, said plainly:

- **No league tables** but football's on football-data.org (and Formula 1's standings). TheSportsDB's table is only
  on its old API, with the key in the address: a key in an address is the usual way one leaks, so this module
  doesn't ask for it.
- **No live scores** for cricket, rugby union, tennis, golf or Formula 1. A match under way says STARTED, NO LIVE
  SCORES; a race says UNDER WAY, NO LIVE TIMING. Take over does nothing for them.
- **No world rankings** for tennis or golf: there is no free, documented source.
- **Cricket scores are runs only** (133-132): TheSportsDB's score fields have no wickets, so 133/4 can't be shown; the
  result line says who won and how ("PER WON BY 6 WKTS").
- **Tennis and golf are what TheSportsDB records**: tennis mostly as finals ("Fritz beat Tirante 2-1"), golf as
  tournaments whose winner is in its results once someone has filled them in. Until then the panel says NO RESULT
  YET, NOT ON THESPORTSDB YET.

**Not yet tried with a real key.** This version was written from the documentation above and tested against answers
in the documented shapes (Formula 1's with the real figures Jolpica gave on 23 November). TheSportsDB's v2 answers
are barely documented: the field names used are the ones its v1 answers give. Every field is read defensively, so a
surprise shows as a missing line, not a broken screen, but expect a 2.0.1 once a Premium key has been through it.

## Settings

| Setting | What it does | Default |
|---|---|---|
| **Key** | Your football-data.org key. Shared by every Sports screen. | (none) |
| **Premium key** | Your TheSportsDB Premium key. Shared by every Sports screen. | (none) |
| **Sport** | One of the ten. | Football |
| **Team** | For team sports: your team as the source spells it, or its number there. The preview shows the team it found. | (empty) |
| **Tour** | Tennis: ATP Tour or WTA Tour. Golf: PGA Tour or DP World Tour. | ATP Tour |
| **Highlight** | Formula 1: a driver to pick out. Tennis and golf: a player to pick out. | (empty) |
| **Show** | Next match or race, Live score, Result, Table or standings. | all four |
| **Take over** | Keep the panel during a live match, until two minutes after full time, for sports with live scores. Never in the sleep hours; Next still moves on. | off |
| **Source** | Football only: football-data.org or TheSportsDB. | football-data.org |
| **Games** (Games style) | Olympics and Paralympics, Olympics, or Paralympics. | both |
| **Season** (Games style) | Summer and winter, Summer, or Winter. | both |

Things worth knowing:

- **Take over starts on the screen's own turn.** An imported module only runs when its screen's turn comes round in
  the playlist, so the takeover begins the next time the Sports screen comes up after kick-off, then stays until full
  time. The Matrix allows any one module at most 4 hours of this in any 12.
- If a view needs something your key doesn't have, that view is left out and the others still show. The panel says
  KEY REFUSED or NOT IN PLAN in words; it never shows an error screen.
- If the Matrix can't reach a source, the last fixtures are still shown. A live score with no news for ten minutes
  stops saying LIVE and says how old it is.
- No club badges, league logos, Olympic rings, Paralympic symbols or Games emblems are drawn. A team is its three
  letters and its kit colours; each sport has its own small icon, and the Games have a torch, a sun and a snowflake.
- A driver or player you pick out is marked twice: in its own light blue, and with a ">" before the name (or, in the
  standings and on the podium, drawn dark on a light blue band), so it doesn't rely on colour alone.
- Every letter has a dark column after it, and words stay one LED in from each edge (a frame may hide the outermost
  LEDs); a line that doesn't fit is said more briefly, never cut. On a panel with room for one line, that line takes
  turns, every two seconds, between what the three lines would say. (On a panel narrower than 40 LEDs a word that
  needs every LED may use them all: an eight-letter word needs 31 of 32.)

## The art

Every picture is an Animator project in `art/`: an icon for each sport (`icon_<sport>.json`, 7 by 7), and the
Games' torch (three frames of flame), sun and snowflake. To change one: Animator > More > "Open a drawing file...",
choose the file from `art`, change it, download the project file back over the old one, and build the zip again.

## Being polite to the sources

One request at a time to each service, never closer together than it allows (7 seconds for football-data.org's 10
a minute, 2 seconds for the others). Fixtures every 3 hours, every 30 minutes in the 3 hours before kick-off, and
every 30 minutes in the hours after the start of a match or race with no live scores, until its result is in; a
match in play once a minute (football-data.org) or every 2 minutes (TheSportsDB); the table every 3 hours and once
after full time. After "too many requests" it waits as long as the service says; after any other failure the wait
doubles, from 30 seconds to 30 minutes. Nothing is fetched while no Sports screen is on the panel, and the Games
screen fetches nothing at all.

## Internet and files

It reaches `api.football-data.org`, `www.thesportsdb.com` and `api.jolpi.ca`, and nothing else. It keeps one file,
`cache.json`, in its working folder: team lists and the last fixtures and tables, so a restart has something to
show. Your keys are never written there, never printed, and only ever sent in a request's header, each to its own service (Jolpica is sent
none). Redirects are never followed (a redirect would carry the key's header elsewhere), and an answer that takes
more than 20 seconds in all is given up on.

## On an older Matrix

Its `bongo-module.json` asks for one ability, `"stay": true`, so that Take over can keep the panel while a match is
live; the import review says so before you tick that you trust the author. A Matrix that has module abilities but not
that one refuses the import and says it needs a newer Matrix: update it first.

It still imports on a Matrix from before module abilities. What a newer Matrix adds is asked for only where it exists:

- Without secret settings, the keys are ordinary text boxes on each Sports screen, shown as typed.
- Without `stay`, Take over does nothing: the screen has its usual seconds.
- Without notes under settings, the explanations are in the Help guide only.
- Without the Matrix's reader of Animator projects, the icons are left out and the words still show.

## For people writing their own module

This is the example to read if yours needs a key and a service with limits.

- `sources.py`, `f1.py`, `tours.py`: each service read into plain shapes, every field checked. No networking in them.
- `feed.py`: one background thread, a cache in the working folder, rate limits and back-off. `render` never waits.
- `board.py`, `racing.py`: which frame to show, and `self.stay` to ask for the panel while something is live.
- `games.py`: a second screen style with its own settings, drawn from bundled data.
- `draw.py`: every frame laid out from the canvas's own size, so a smaller safe area still reads.
- `art.py`: pictures that travel in the module's own folder as Animator projects.
- `__init__.py`: `secrets=("key", "premium_key")`, guarded so it still imports where a Matrix doesn't know the word.

## Tests

The tests need a Bongo Matrix checkout to run against:

```bash
PYTHONPATH=/path/to/bongo-matrix python3 -m pytest tests -q
python3 build.py            # writes sports-2.0.0.zip
```

Nothing in them touches the network: a pretend service answers from the files in `tests/fixtures`.
