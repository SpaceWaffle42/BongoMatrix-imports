# Aquarium for Bongo Matrix

A tank of fish. Leave it alone and they swim, and food drops in by itself now and then; or feed them, tap the glass, drop a fish in or let one
swim off. Something calm to have on between the useful screens.

Version 2.4.0, by spacewaffle42. MIT licence.

## Two looks

| Look | What it shows |
|---|---|
| **Reef** | Sunlit water, sand, swaying weed, bubbles, and four kinds of bright fish |
| **Deep** | Dark water where the only light is what lives there: jellyfish, an anglerfish, lantern fish |

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
| `bubbles` | Bubbles rising | on |
| `water` (Reef) | The colour of the water at the surface | `#0A3A66` |
| `glow` (Deep) | The colour of everything that glows | `#7FFFD4` |

## Internet and files

No internet. It keeps one small file, `tank.json`, in its own working folder: which fish are in each
tank (so the ones you added are still there after a restart) and when food last dropped in by itself.
Removing the module removes the file.

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
- `art.py`: the pictures are Animator projects in `art`, read with the Matrix's own `bongo.sprites`;
  nothing is exported from them. `sprites.py` flips and tints them.
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
