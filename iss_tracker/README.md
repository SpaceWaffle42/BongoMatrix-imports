# ISS Tracker for Bongo Matrix

Shows where the International Space Station is right now, on a 64x32 Bongo Matrix.

Version 1.0.0, by spacewaffle42. MIT licence.

Not affiliated with NASA or with wheretheiss.at.

## Three looks

| Look | What it shows |
|---|---|
| **Map** | The world, shaded by where it is day and night, with the station blinking on it and the path it has flown this orbit. Its position is written in a corner. |
| **Readout** | The numbers: latitude, longitude, how high it is, how fast it is going, and whether it is in sunlight. |
| **Distance** | How far the station is from your Matrix and in which direction, with a small radar. It says NEAR YOU when the station is within about 2,200 km, which is when it can be above your horizon. |

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose this .zip.
The Matrix draws each look on a test screen first, and asks you to tick that you trust the author.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `colour` | The station, and the headings | `#7FD4FF` |
| `miles` | Miles and mph instead of km and km/h | off |
| `refresh` | Seconds between positions (5 to 120) | 15 |
| `land` (Map) | The colour of the land | `#2E7D4F` |
| `trail` (Map) | Draw the path flown this orbit | on |
| `show_position` (Map) | Write the position in a corner | on |

## What it reaches on the internet

One site, listed in `bongo-module.json`: **api.wheretheiss.at**, a free service that needs no account.
It is asked for one small answer every `refresh` seconds while one of this module's screens is showing
(previews in the dashboard count), and for a few minutes after. Only the request itself goes out: your
internet address, as with any website, and this module's name. Never your location: the Distance look
works out the distance on the Matrix, from the place you set in its Settings.

If the internet or that service is down, the screens say FINDING ISS (before the first position) or
NO SIGNAL (after), and carry on when it is back.

## Files it keeps

`trail.json` in the module's own working folder: the path flown this orbit, so the trail is still
there after a restart. Nothing else.

## Good to know

- The map is coarse on purpose: one LED per 5.6 degrees. Small islands are not on it.
- Day and night on the map are worked out from the date and time, near enough for shading.
- Distance needs the Matrix's place set (Settings > Location). Without it, it asks you to set one.

## For people writing their own module

This is the example to read alongside Crypto Ticker if your module fetches from the internet, or uses
where the Matrix is.
- `feed.py`: a background fetch with a "no signal" state, and a small file kept between restarts.
- `world.py`: a map drawn from a table, and the sums for day and night, distance and direction.
- `styles.py`: `ctx.home`, the place set in the Matrix's Settings, used without sending it anywhere.
