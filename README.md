# Bongo Matrix imports

Optional modules for [Bongo Matrix](https://github.com/SpaceWaffle42/BongoMatrix) v3, kept outside the main
repository. They are not part of the Matrix itself: each one is imported on a Matrix from its dashboard
(**Settings › Modules › Import**), only when you want it, and they double as examples for anyone writing their
own. Nothing here runs on a Matrix until it has been imported and you have ticked "I trust" for it.

This repository: https://github.com/SpaceWaffle42/BongoMatrix-imports

Home Assistant and Sports need a Matrix with the module abilities update, and Drawing wall, Parcels, Phone
notifications and Steam need module API 3. An older Matrix says it needs updating instead of importing them.

## What's in it

One folder per module, at the top of the repository. Each folder holds exactly what would go in that module's
.zip: `bongo-module.json`, the Python (`__init__.py` and the rest), any `art` (Animator projects), a README, a
CHANGELOG and a LICENSE. The version is in `bongo-module.json`.

```
BongoMatrix-imports/
├── README.md               (this file: not a module)
├── LICENSE.md
├── aquarium/
│   ├── bongo-module.json
│   ├── __init__.py
│   ├── art/
│   └── ...
├── sports/
│   ├── bongo-module.json
│   ├── __init__.py
│   └── ...
└── ...
```

A folder counts as a module only if it holds **both** `bongo-module.json` and `__init__.py`. Anything else (this
README, a folder of notes or tools) is ignored by the Matrix. The Matrix looks at the top level and one folder
down, no deeper.

| Folder | Module | What it is |
|---|---|---|
| `aquarium/` | Aquarium | A tank of fish to leave alone or play with: feed, tap the glass, add or remove a fish |
| `crypto_ticker/` | Crypto ticker | Coin prices on the panel |
| `drawing_wall/` | Drawing wall | Draw on the panel from your phone, live: several phones at once, a history of the last few, and a pop-up when one is sent if you like. Runs in the background and has its own page for drawing |
| `home_assistant/` | Home Assistant | The Matrix appears in Home Assistant through your MQTT broker: the panel as a light, the screen playing, Pause, Next and messages. Runs in the background and reaches one device on your home network (the broker) |
| `iss_tracker/` | ISS Tracker | Where the International Space Station is now |
| `parcels/` | Parcels | Parcels on their way: arrives today, out for delivery, delivered. Needs a free Ship24 key (DHL and UPS keys optional). Pop-ups are never shown in the sleep hours |
| `phone_notifications/` | Phone notifications | A short pop-up over the playlist when your phone gets a notification, and the last few on a screen. Your phone sends them through ntfy.sh |
| `pomodoro/` | Pomodoro | A focus timer: work and break rounds |
| `sports/` | Sports | Ten sports (football, cricket, rugby union, tennis, Formula 1, golf, American football, basketball, ice hockey, baseball): next match, live score where there is one, result, and a countdown to the Olympics and Paralympics. Football and Formula 1 need no paid key; the others need your own TheSportsDB Premium key. May keep the panel while a match is live |
| `steam/` | Steam | Friends online and what they are playing, the game's picture, your recent games and newest achievement. Needs your own free Steam Web API key |
| `word_of_the_day/` | Word of the day | A new word and its meaning each day |

Each module's own README says how to set it up.

## Importing on a Matrix

1. Open the Matrix's dashboard: **Settings › Modules › Import**.
2. Paste this repository's link: `https://github.com/SpaceWaffle42/BongoMatrix-imports`
   (a release, tag or branch works too: `.../BongoMatrix-imports/tree/<branch-or-tag>`), then **Fetch**.
3. **Pick the modules.** Because this repository holds several modules, a list pops up with every module found:
   its name, version, author, what it does, what it asks for, and whether it's already on this Matrix (and if so,
   whether this is a newer version). **Nothing is ticked to start with.** Tick the ones you want and press
   **Review selected** (or **Cancel** to import nothing).
4. **Review each one.** Every ticked module gets the usual import review on its own: a test screen drawn by its
   code, the sites it may reach, and every ability it asks for in plain words. Tick "I trust …" for each module
   you want and install it. A module that fails its checks isn't installed, and never stops the others.
5. Set each module up where its README says (a key, a broker address and so on). Secrets you type there stay on
   the Matrix: never in its settings file, never sent back to a browser, never in a log or a backup.

A repository whose top folder is itself one module (with its own `bongo-module.json`) skips the list and goes
straight to the review.

### Without a link

Any Matrix can take one module from here as a .zip with the module's files at the top (or inside one folder).
Build it from a clone. In PowerShell, for the Aquarium (change `aquarium` to the folder you want):

```powershell
cd $HOME
git clone https://github.com/SpaceWaffle42/BongoMatrix-imports.git
cd $HOME\BongoMatrix-imports
git pull
Compress-Archive -Force -Path .\aquarium\* -DestinationPath $HOME\Downloads\aquarium.zip
```

(Skip the `git clone` line if you already have the folder.) Then import the zip from the Matrix's dashboard;
importing a newer version over an older one updates it. A module imported from a zip isn't checked for updates:
do the same again for a newer version.

## Updates

Each module installed from here remembers this repository **and its own folder in it**, so it is checked for
updates from that folder only:

- once a day, on the Matrix's normal schedule, never because a page is open;
- against the newest **release** if the repository has releases, otherwise the latest commit of the branch it
  came from;
- only a module whose own `version` in `bongo-module.json` went up shows an update (a release made for one
  module doesn't make the others look new);
- a newer version shows an **Update** button on the module's row in Settings › Modules. **Nothing installs by
  itself**: press Update, see the review again, and agree;
- if the new version asks for anything new (a new ability, a new site), you're asked again before it installs.

## Adding or changing a module here

1. **One folder per module**, named like its `id` (lower case, letters, digits and `_`). The folder holds what a
   single-module repository would: `bongo-module.json`, `__init__.py` with `MODULE`, its other files, a README,
   a CHANGELOG and a LICENSE. The full rules for writing a module are in the main repository's
   `docs/MODULES.md` ("The contract", "Sharing a module", and "Background modules, controls and the home
   network").
2. **`bongo-module.json`** says who it is and what it may do. For example:
   ```json
   {
     "id": "sports",
     "name": "Sports",
     "version": "2.0.0",
     "author": "spacewaffle42",
     "description": "Ten sports: next match, live score, result, and the Olympics and Paralympics.",
     "network": ["api.football-data.org", "www.thesportsdb.com", "api.jolpi.ca"],
     "abilities": {"stay": true}
   }
   ```
   - `network`: the only sites it may reach; anything else is blocked.
   - `abilities`: only what it needs (`background`, `controls`, `home_address`, `settings`, `stay`); each is shown
     to the owner before they can tick "I trust". A module that asks for none runs exactly like any other screen.
   - `api`: the Matrix contract it needs, if it uses abilities (an older Matrix then says it needs updating instead
     of half-working).
3. **Bump `version`** in that module's `bongo-module.json` for every change you want Matrices to pick up, and say
   what changed in its CHANGELOG. Then push to `main`. If the repository has any releases, Matrices follow the
   newest release only, so also make a release (for example `sports-2.1.0`); a push to `main` alone isn't picked
   up then.
4. **Never commit a secret**: no API keys, tokens, passwords or private links, in code, tests or examples. Each
   person types their own into the Matrix.
5. **Test before pushing**: try the module on a Matrix (import it as a .zip, or by link from a branch), and run
   its own tests if it has any (see its README).
6. **Licence**: everything here is under the MIT licence (`LICENSE.md`). A new module's folder gets its own copy
   as `LICENSE`, and nothing goes in that can't be shared under it (no art, fonts or code with another licence).

Large files (pictures, recordings) are fine in a module's folder, but keep a module well under the import size
limit; the Matrix refuses an archive that's too big.

## Licence

MIT: see [LICENSE.md](LICENSE.md). Copyright (c) 2026 spacewaffle42.
