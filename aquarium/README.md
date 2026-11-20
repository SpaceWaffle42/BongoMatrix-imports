# Aquarium for Bongo Matrix

A tank of fish. Leave it alone and they swim, and food drops in by itself now and then; or feed them, tap the glass, drop a fish in or let one
swim off. Something calm to have on between the useful screens.

Version 2.5.0, by spacewaffle42. MIT licence.

## Two looks

| Look | What it shows |
|---|---|
| **Reef** | Bright water with sunbeams swaying down from a shimmering surface; sand with pebbles and shells, a shaded rock, pale coral, a sea fan, an anemone, and weed of three kinds swaying behind and in front of the fish; bubbles; four kinds of bright fish (clownfish, yellow tang, puffer, minnow) |
| **Deep** | Very dark water with a faint light from far above and marine snow drifting down; dark rock and silt with a chimney glowing at its mouth, anemones and tube worms whose tips glow in turn, a sea pen in front with lights running up it; bubbles; jellyfish, an anglerfish whose lure lights the water, lantern fish. Everything that glows is in the `glow` colour |

The scenery is drawn for the 64 x 32 panel and fits any other size: the water fills the height, and the
seabed runs along the bottom. The rocks and weed are spread to the width, from an arrangement for 64 wide
or, from 96 wide up, one with more pieces for 128 wide. On a panel under 24 tall the scenery keeps low
(no anemone or sea fan, shorter weed) and the fish swim in the clear water above it. Nothing is stretched
but the soft water.

## From one look to the other

When a Deep screen comes straight after a Reef one, the view sinks for four seconds: the reef rises out of
sight, the water darkens, specks stream upwards, and the Deep comes up from below. From the Deep to
the Reef it rises the same way. (Only when one comes straight after the other on the panel, at the
same size; a preview just shows the look.)

## Feeding by itself

Food drops in by itself **8 times a day**, at random times that are at least **45 minutes apart**. The
times are different every day. There is nothing to set. If one comes round while another screen is on,
the food drops in when the Aquarium is next on, but never sooner than 45 minutes after the last.

## Playing with it

While the Aquarium is on the panel, the dashboard's Now page shows four buttons under the picture:

| Button | What happens |
|---|---|
| **Feed now** | Flakes of food drop in and flutter down. Up to four fish eat at a time, two to a flake, a few more circle, and the rest carry on until there is room. In the Deep it is glowing "snow": the lantern fish come for it, the jellyfish take no notice, and the angler stays where it is |
| **Tap the glass** | The fish in view dart away from the middle, then carry on. The puffer puffs up; jellyfish shoot upwards |
| **Add a fish** | One more drops in at the top (up to 10) |
| **Remove a fish** | The newest one in view swims off the side and doesn't come back (down to 1) |

**None of this is needed.** Nothing gets hungry, nothing sulks and nothing dies. A tank nobody touches
for a year looks the same as it did on the first day.

The buttons need a Matrix that has module buttons. On an older Matrix the module still works as a
tank to watch.

## Installing

In the Matrix's dashboard: **Settings > Modules > Import**, then choose this .zip.
The Matrix draws each look on a test screen first, and asks you to tick that you trust the author.
If you have version 1 installed, importing this one updates it.

## Settings

| Setting | What it does | Default |
|---|---|---|
| `fish` | How many fish (1 to 10). Change it and, next time the Aquarium is on, new fish drop in at the top, or fish swim off the side, one at a time, until there are that many. Every Aquarium screen of the same look shares one tank, so give them the same number | 5 |
| `bubbles` | Columns of bubbles rising (a drawing, `reef_bubbles` / `deep_bubbles`) | on |
| `water` (Reef) | The colour of the water at the surface: the whole water, sunbeams and all, is turned to it. (`#0A3A66`, the default before 2.5.0, is drawn as `#2A8AC8`) | `#2A8AC8` |
| `glow` (Deep) | The colour of everything that glows | `#7FFFD4` |

## Internet and files

No internet. It keeps one small file, `tank.json`, in its own working folder: which fish are in each
tank (so the ones you added are still there after a restart) and when food last dropped in by itself.
Removing the module removes the file.

## The pictures

Everything you see is an **Animator project**: the same files the Matrix's Animator opens and saves.
The fish are in `art`, the scenery in `art/scenery`:

| File | What it is |
|---|---|
| `reef_water` | The Reef's water: a gradient, a layer of sunbeams and a layer of surface shimmer, both adding light (48 frames). Drawn in the default blue; the `water` setting turns it |
| `reef_sand` | The sand, 64 wide; it repeats along the bottom |
| `reef_rock`, `reef_coral`, `reef_fan`, `reef_anemone` | Behind the fish |
| `reef_kelp`, `reef_weed`, `reef_grass` | Weed that sways, tall to short (a short panel uses a shorter one) |
| `reef_front` | Weed in front of the fish, darker so the fish stay the brightest |
| `deep_water` | The Deep's water: a gradient, the faint light from above, and marine snow on a Glow layer (64 frames) |
| `deep_floor`, `deep_rocks`, `deep_vent`, `deep_anemone`, `deep_worms` | The seabed, behind the fish |
| `deep_pen` | The sea pen, in front of the fish |
| `reef_bubbles`, `deep_bubbles` | A column of bubbles rising, 32 tall, looping top to bottom; a few go across the tank. The Deep's are magenta: the `glow` colour |
| `reef_bubbles_tall`, `deep_bubbles_tall` | The same, 64 tall, for a panel over 40 tall, so a bubble rises the whole way up |

The scenery all loops in step: the Reef's in 6 seconds (48 frames of 125 ms), the Deep's in 8 (64 frames).
Keep a changed piece to the same frames and timing and it stays in step with the rest.

**Glow.** Pure magenta (`#FF00FF`) is the Deep's `glow` colour, and darker magenta (`#800080`: red and blue
the same, no green) is that colour, darker. A layer named **Glow** whose mode is "Adds light", drawn in
magenta, is light in the `glow` colour, added onto the water round it, so it brightens what is behind
rather than covering it. Other layers that add light (the sunbeams, the vent's plume) are added as light too.

The drawings were made with the Animator's own tools, by a script that drives the Animator page (it is
not part of this .zip). Opening any of them in the Animator shows its layers.

## Adding your own fish

The fish are **Animator projects** in the `art` folder: the same files the Matrix's Animator opens and
saves. To change one, open it there (Animator > More > "Open a drawing file…"), edit it, and download
the project file back into `art`.

To add one, draw it in the Animator facing right, with **two frames** (the tail in two positions), on a
canvas the size of the fish: the ones here are 5 to 9 LEDs wide. Save the project file into `art` with a
name starting `reef_` to join the Reef or `deep_` for the Deep. Pure magenta (`#FF00FF`) is swapped for
the Deep look's `glow` colour.

A fish can have a second picture for when it is startled: a project of the same name in `art/scared`
(the puffer has one). It can be a different size.

Put the file in the folder before you zip and import the module (an installed module's folder can't be
changed). The tank starts with the kinds dealt out in file-name order, and **Add a fish** drops in
whichever kind there are fewest of.

## For people writing their own module

This is the example to read if your module needs pictures, things that move by themselves, or buttons.
- `art.py`: the pictures are Animator projects in `art`; nothing is exported from them. It takes a drawing
  apart into what is drawn, the light it adds and its Glow, reading the project's text itself (the
  Matrix's `bongo.sprites` gives the layers already put together), and falls back to `bongo.sprites` if a
  file won't read that way. `sprites.py` flips and tints the fish.
- `scenery.py`: scenery that loops, fitted to the panel's size and put together once per frame of the loop,
  so drawing a frame on the panel is a copy and a paste. Shown by time with `bongo.sprites`.
- `world.py`: the fish, with no drawing in it. `step(t)` is told the time and moves everything on from
  the last time it was told, in small steps, so a slow frame never makes a fish jump.
- `tank.py`: drawing, and `act(name)`, which the Matrix calls when a button is pressed. It only notes
  what was asked; the next frame does it. The tank is kept at module level, because the Matrix
  builds a new screen object every time the module's turn comes round.
- `keep.py`: a small file in the working folder, written only when something changes and replaced
  whole, so a power cut can't leave half of one.
- `__init__.py`: `actions=` is passed only if the Matrix knows about buttons, so the module still
  imports on an older one.
- A dashboard preview can ask for any moment, real or made up, so each preview (`ctx.preview`) gets a
  tank of its own and only the screen on the panel moves the real one.
