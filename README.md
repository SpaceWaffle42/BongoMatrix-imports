# Bongo Matrix imports

Optional modules for Bongo Matrix v3, kept outside the main `bongo_matrix` repository. They are not part of the
Matrix itself: each one is imported on a Matrix from its dashboard (**Settings › Modules › Import**), only when you
want it, and they double as examples for anyone writing their own. Nothing here runs on a Matrix until it has been
imported and you have ticked "I trust" for it.

Importing by link needs a Matrix with **import from other links** (Settings › Modules › Import accepts this
GitLab, not only GitHub and .zip files). Any Matrix can import a module from here as a .zip (see "Without a link"
below). Home Assistant and Sports also need a Matrix with the module abilities update (an older one says it needs
updating).

## What's in it

One folder per module, at the top of the repository. Each folder holds exactly what would go in that module's
.zip: `bongo-module.json`, the Python (`__init__.py` and the rest), any `art` (Animator projects), a README, a
CHANGELOG and a LICENSE. The version is in `bongo-module.json`.

```
bongo_imports/
├── README.md               (this file: not a module)
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
| `home_assistant/` | Home Assistant | The Matrix appears in Home Assistant through your MQTT broker: the panel as a light, the screen playing, Pause, Next and messages. Runs in the background and reaches one device on your home network (the broker) |
| `iss_tracker/` | ISS Tracker | Where the International Space Station is now |
| `pomodoro/` | Pomodoro | A focus timer: work and break rounds |
| `sports/` | Sports | Your football team: next match, live score, result and league table, with your own football-data.org key. May keep the panel while a match is live |
| `word_of_the_day/` | Word of the day | A new word and its meaning each day |

Each module's own README says how to set it up.

## Importing on a Matrix

1. Open the Matrix's dashboard: **Settings › Modules › Import**.
2. Paste this repository's link: `http://gitlab.home.lan/matrix_display/bongo_imports`
   (a branch or tag works too: `.../bongo_imports/-/tree/<branch-or-tag>`).
3. The Matrix warns you before it fetches anything, because this isn't GitHub:
   - it isn't GitHub: only import from a place you run or trust, because a module's code runs on the Matrix
     (inside its sandbox);
   - the address is on your home network;
   - the address isn't encrypted (http): someone on your network could change what's downloaded.
   Tick that you understand, then **Fetch**.
4. **Pick the modules.** Because this repository holds several modules, a list pops up with every module found:
   its name, version, author, what it does, what it asks for, and whether it's already on this Matrix (and if so,
   whether this is a newer version). **Nothing is ticked to start with.** Tick the ones you want and press
   **Review selected** (or **Cancel** to import nothing).
5. **Review each one.** Every ticked module gets the usual import review on its own: a test screen drawn by its
   code, the sites it may reach, every ability it asks for in plain words, and this source with its warnings.
   Tick "I trust …" for each module you want and install it. A module that fails its checks isn't installed, and
   never stops the others.
6. Set each module up where its README says (a key, a broker address and so on). Secrets you type there stay on
   the Matrix: never in its settings file, never sent back to a browser, never in a log or a backup.

A repository whose top folder is itself one module (with its own `bongo-module.json`) skips the list and goes
straight to the review, as before.

### This repository is private

So the Matrix needs a sign-in to fetch it. Make a **read-only** access token in GitLab: on this project,
**Settings › Access tokens**, role Reporter, scope `read_repository` (add `read_api` so the Matrix can see the
default branch and tags; without it, it tries `main`). Paste it into the **Access token** box on the import. The
token is used only to download from this GitLab and to check it for updates. It is kept like the Matrix's other
secrets (never in its settings file, the logs, a backup, a link or the hub) and is sent only to this same address.
Removing the last module that came from here forgets it.

### Without a link

Any Matrix can take one module from here as a .zip. The Matrix wants a zip with the module's files at the top (or
inside one folder). GitLab's "Download this directory" adds an extra folder, so build the zip from a clone
instead. In PowerShell, for the Aquarium:

```powershell
cd C:\Users\Billy
git clone http://gitlab.home.lan/matrix_display/bongo_imports.git
cd C:\Users\Billy\bongo_imports
git pull
Compress-Archive -Force -Path .\aquarium\* -DestinationPath C:\Users\Billy\Downloads\aquarium.zip
```

(Skip the `git clone` line if you already have `C:\Users\Billy\bongo_imports`.) Change `aquarium` to the folder
you want. Then import the zip from the Matrix's dashboard; importing a newer version over an older one updates it.
A module imported from a zip isn't checked for updates: do the same again for a newer version.

## Updates

Each module installed from here remembers this repository **and its own folder in it**, so it is checked for
updates from that folder only:

- once a day, on the Matrix's normal schedule, never because a page is open;
- against the newest **tag** if the repository has tags, otherwise the latest commit of the branch it came from;
- only a module whose own `version` in `bongo-module.json` went up shows an update (a tag for one module doesn't
  make the others look new);
- a newer version shows a badge on the module's row in Settings › Modules. **Nothing installs by itself**:
  press Update, see the review again, and agree;
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
     "version": "1.0.0",
     "author": "spacewaffle42",
     "description": "Your football team: next match, live score, result and league table.",
     "network": ["api.football-data.org"],
     "abilities": {"stay": true}
   }
   ```
   - `network`: the only sites it may reach; anything else is blocked.
   - `abilities`: only what it needs (`background`, `controls`, `home_address`, `settings`, `stay`); each is shown
     to the owner before they can tick "I trust". A module that asks for none runs exactly like any other screen.
   - `api`: the Matrix contract it needs, if it uses abilities (an older Matrix then says it needs updating instead
     of half-working).
3. **Bump `version`** in that module's `bongo-module.json` for every change you want Matrices to pick up, and say
   what changed in its CHANGELOG. Then push to the branch the Matrices follow (`main`), or tag the repository
   (for example `sports-1.1.0`).
4. **Never commit a secret**: no API keys, tokens, passwords or private links, in code, tests or examples. Each
   person types their own into the Matrix.
5. **Test before pushing**: try the module on a Matrix (import it as a .zip, or by link from a branch), and run
   its own tests if it has any (see its README).
6. **Pet art** from the main repository is never used here (its licence doesn't allow sharing it).

Large files (pictures, recordings) are fine in a module's folder, but keep a module well under the import size
limit; the Matrix refuses an archive that's too big.
