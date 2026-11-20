# Bongo Matrix imports

Optional modules for Bongo Matrix v3. They are not part of the Matrix itself: each one is imported on a Matrix
from its dashboard (**Settings > Modules > Import**), and they double as examples for anyone writing their own.

Each module is its own folder, holding exactly what goes in its .zip: `bongo-module.json` at the top, the
Python, any `art` (Animator projects), a README, CHANGELOG and LICENSE. The version is in `bongo-module.json`.

| Folder | Module | What it is |
|---|---|---|
| `aquarium/` | Aquarium | A tank of fish to leave alone or play with: feed, tap the glass, add or remove a fish |
| `home_assistant/` | Home Assistant | Your Home Assistant's states and alerts on the panel |
| `sports/` | Sports | Live scores and fixtures |

## Making the .zip to import

The Matrix wants a zip with the module's files at the top (or inside one folder). GitLab's "Download this
directory" adds an extra folder, so build the zip from a clone instead. In PowerShell, for the Aquarium:

```powershell
cd C:\Users\Billy
git clone http://gitlab.home.lan/matrix_display/bongo_imports.git
cd C:\Users\Billy\bongo_imports
git pull
Compress-Archive -Force -Path .\aquarium\* -DestinationPath C:\Users\Billy\Downloads\aquarium.zip
```

(Skip the `git clone` line if you already have `C:\Users\Billy\bongo_imports`.) Change `aquarium` to the folder
you want. Then import the zip from the Matrix's dashboard; importing a newer version over an older one updates it.
