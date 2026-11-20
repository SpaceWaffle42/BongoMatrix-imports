# Sports for Bongo Matrix

Your football team on the panel: the next match, the live score, the result, and the league table around
your team. Football only for now: other sports need their own layouts.

Version 1.0.0, by spacewaffle42. MIT licence.

This is a module you import. None of it is part of the Matrix itself.

## What it shows

| View | What it shows |
|---|---|
| **Next match** | The day, the two teams, and kick-off in the Matrix's own time zone. Says so if it is postponed. |
| **Live score** | Score, minute and (where the source gives it) the last goal. Half time, extra time and penalties too. |
| **Result** | The final score, and where that leaves your team in the table. |
| **Table** | The rows of the league table around your team. |

The ticked views take turns on the one screen. While a match is in play there is only the live view.
A team is its three letters and two stripes of its kit colours: no club or league badge is ever drawn.

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose `sports-1.0.0.zip` (or paste this
repo's GitHub link). The Matrix draws the screen on a test screen first, shows the two sites it can reach, and
asks you to tick that you trust the author. Then add a Sports screen to the playlist.

Before it is set up, the preview shows a made-up match (Northtown v Southport) so you can see the design.
On the panel a screen that isn't set up says what it needs: ADD YOUR KEY, TYPE YOUR TEAM.

## Your own key

The scores come from a service you have your own key for. No key ships with this module, nothing is scraped,
and no service here charges per request.

| Source | What you need | Leagues | Next match, Result | Table | Live score |
|---|---|---|---|---|---|
| **football-data.org** | Its free key (register, it comes by email) | Premier League, Championship, Bundesliga, Serie A, La Liga, Ligue 1, Eredivisie, Primeira Liga, Brazil's Serie A (and the Champions League, World Cup and Euros for a team in those leagues) | Yes | Yes | Yes, but late: the free plan's scores are "delayed". Live ones need its paid "Free w/ Livescores" plan |
| **TheSportsDB** | Its **Premium** key (a flat monthly fee, not per request) | Nearly every league | Yes | No (see below) | Yes, about every 2 minutes |

What was read, and where (18 November 2026):

- football-data.org's free plan: 12 competitions, 10 requests a minute, "Scores delayed", "Schedules delayed",
  fixtures and league tables included. Live scores start at the "Free w/ Livescores" plan (EUR 12 a month, flat).
  <https://www.football-data.org/pricing>, <https://www.football-data.org/coverage>
- Its API, v4: the key goes in the `X-Auth-Token` header. Used here: `/v4/competitions/{code}/teams`,
  `/v4/teams/{id}`, `/v4/teams/{id}/matches`, `/v4/matches/{id}`, `/v4/competitions/{code}/standings`.
  <https://docs.football-data.org/general/v4/team.html>, <https://docs.football-data.org/general/v4/match.html>,
  <https://docs.football-data.org/general/v4/competition.html>, <https://docs.football-data.org/general/v4/lookup_tables.html>,
  <https://docs.football-data.org/general/v4/policies.html>, <https://docs.football-data.org/general/v4/errors.html>
- TheSportsDB's free key is not a key of your own: it is one test key everyone shares, on the old v1 API, where
  an answer is limited to one fixture ("free key only shows home event"), five table rows ("limited to featured
  soccer leagues only") and a team search "limited to just Arsenal". That is too little for this screen, and it is
  not yours, so this module doesn't use it. Its v2 API "is only for premium subscribers", takes the key in the
  `X-API-KEY` header, and has live scores ("2 min livescore"). Premium is 9 a month, flat (USD on its pricing page); 100 requests a minute.
  Used here: `/api/v2/json/search/team/{name}`, `/lookup/team/{id}`, `/schedule/next/team/{id}`,
  `/schedule/previous/team/{id}`, `/livescore/{league id}`.
  <https://www.thesportsdb.com/documentation>, <https://www.thesportsdb.com/pricing>, <https://thesportsdb.com/docs_api_examples>
- TheSportsDB's league table is only on v1, where the key is part of the address. A key in an address is the
  usual way one leaks, so this module doesn't ask for it: with TheSportsDB the Table view, and the "4th in table"
  line under a result, are simply not shown.

**Not yet tried against the real services.** This version was written from the documentation above and tested
against hand-written answers in the documented shapes, with no real key. TheSportsDB's v2 answers in particular
are barely documented (the field names used are the ones its v1 answers give). Every field is read defensively,
so a surprise shows as a missing line, not a broken screen, but expect a 1.0.1 once real keys have been through it.
If it matters to you today, football-data.org is the better documented of the two.

## Settings

| Setting | What it does | Default |
|---|---|---|
| **Team** | Your team's name as the source spells it (`Arsenal`, `Bayern`), or its number there. The preview shows the team it found, so a wrong match shows at once: type more of the name. | (empty) |
| **Show** | Next match, Live score, Result, Table: tick what you want. | all four |
| **Take over** | Keep the panel during a live match, until two minutes after full time. Never in the sleep hours; Next still moves on. | off |
| **Source** | football-data.org or TheSportsDB. | football-data.org |
| **Key** | Your key for that source. Saved on the Matrix for every Sports screen, masked, and never shown again. | (none) |

Things worth knowing:

- **Take over starts on the screen's own turn.** An imported module only runs when its screen's turn comes
  round in the playlist. So the takeover begins the next time the Sports screen comes up after kick-off, then
  stays until full time. Give the playlist a Sports screen often enough if you don't want to miss the start.
  The Matrix allows any one module at most 4 hours of this in any 12.
- **One key for all Sports screens.** Two screens (two teams) use the same source's key. Two screens on
  different sources aren't supported in this version.
- If a view needs something your key doesn't have, that view is left out and the others still show. The panel
  says KEY REFUSED or NOT IN PLAN in words; it never shows an error screen.
- If the Matrix can't reach the source, the last fixtures are still shown. A live score with no news for ten
  minutes stops saying LIVE and says how old it is; fixtures a day old say so.

## Being polite to the source

One request at a time, never closer together than the source allows (7 seconds for football-data.org's 10 a
minute). Fixtures every 3 hours, every 30 minutes in the 3 hours before kick-off; a match in play once a minute
(football-data.org) or every 2 minutes (TheSportsDB); the table every 3 hours and once after full time. After
"too many requests" it waits as long as the service says; after any other failure the wait doubles, from 30
seconds to 30 minutes. Nothing is fetched while the Sports screen isn't on the panel.

## Internet and files

It reaches `api.football-data.org` and `www.thesportsdb.com`, and nothing else. It keeps one file,
`cache.json`, in its working folder: team lists and the last fixtures and table, so a restart has something to
show. Your key is never written there, never printed, and only ever sent in a request's header.

## On an older Matrix

Its `bongo-module.json` asks for one ability, `"stay": true`, so that Take over can keep the panel while a match
is live; the import review says so before you tick that you trust the author. A Matrix that has module abilities
but not that one refuses the import and says it needs a newer Matrix: update it first.

It still imports on a Matrix from before module abilities. What a newer Matrix adds is asked for only where it exists:

- Without secret settings, Key is an ordinary text box on each Sports screen, shown as typed.
- Without `stay`, Take over does nothing: the screen has its usual seconds.
- Without notes under settings, the explanations are in the Help guide only.

## For people writing their own module

This is the example to read if yours needs a key and a service with limits.

- `sources.py`: each service read into the same plain shapes, every field checked. No networking in it.
- `feed.py`: one background thread, a cache in the working folder, rate limits and back-off. `render` never waits.
- `board.py`: which frame to show, and `self.stay` to ask for the panel while something is live.
- `draw.py`: every frame laid out from the canvas's own size, so a smaller safe area still reads.
- `__init__.py`: `secrets=("key",)`, guarded so it still imports where a Matrix doesn't know the word.

## Tests

The tests need a Bongo Matrix checkout to run against:

```bash
PYTHONPATH=/path/to/bongo-matrix python3 -m pytest tests -q
python3 build.py            # writes sports-1.0.0.zip
```

Nothing in them touches the network: a pretend service answers from the hand-written files in `tests/fixtures`.
