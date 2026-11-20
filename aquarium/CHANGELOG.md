# Changelog

## 2.5.0
- **Both looks are much more detailed**, to match the Animator's Aquarium preset (they were a flat gradient
  with a few dots before). The Reef: bright water with sunbeams that sway and a shimmering surface, sand with
  dunes, pebbles and shells, a shaded rock, pale coral, a deep purple sea fan, an anemone, and three kinds of
  weed that sway, some behind the fish and a clump in front. (The coral is pale and the fan dark so that the
  orange clownfish never sits on its own colour.) The Deep: very dark water with a faint shaft of light from far
  above, marine snow drifting down, a seabed of dark silt and rock with a chimney glowing at its mouth,
  anemones and tube worms whose tips glow one after another, and a sea pen in front with lights running up it.
  Everything that glows is in the `glow` colour, and the seabed glows quieter than the fish.
- **The fish are redrawn**: shaded (lit from above, darker underneath), with fins and an eye; the angler's
  lure lights the water round it, the jellyfish glows. Same fish, same names; the angler is a row taller.
  The tang is now a yellow tang: the blue one was lost against blue water.
- **Bubbles are a drawing too**: columns of bubbles rising and wobbling, bigger as they near the surface
  (`reef_bubbles`, `deep_bubbles`). Still switched on and off by `bubbles`.
- All of it is drawn in the Matrix's own Animator, so any piece can be opened and changed there: the new
  scenery is in `art/scenery`. A layer called Glow that adds light, drawn in magenta, is light in the `glow`
  colour (see the README).
- The scenery fits every size of panel: the water fills the height and the seabed runs along the bottom.
  The rocks and weed come from an arrangement for 64 wide, or one with more pieces for 128 wide (from 96 up).
  On a panel under 24 tall the anemone and fan are left out, the weed is shorter, and the fish keep to the
  clear water above.
- `water`'s default is now `#2A8AC8`, the preset's bright blue (it was `#0A3A66`, which looked almost black
  on the panel). A saved `#0A3A66` is taken to be the old default and drawn as `#2A8AC8` too; to keep the
  dark water on purpose, choose a colour a hair away from it (`#0A3A67`). Any other colour you chose still
  applies: the whole water, sunbeams and all, is turned to it.
- The fish keep a little higher off the bottom, above the deeper seabed.
- Faster to draw than 2.4.0: each frame of the scenery is put together once, then just shown. Putting it
  together takes a moment the first time the Aquarium shows (about a tenth of a second on a desktop
  computer, perhaps a second on a Pi Zero 2 W), and again for a new size or colour.

## 2.4.0
- From the Reef to the Deep (one straight after the other on the panel), the view sinks down to it
  over four seconds instead of just switching; from the Deep to the Reef it rises.

## 2.3.0
- Food drops in by itself 8 times a day, at random times at least 45 minutes apart (different every
  day). Nothing to set.
- Changing the number of fish: new ones drop in at the top, or fish swim off the side, one at a time,
  until there are that many. (Before, each number was a separate tank.) The fish you had are kept.

## 2.2.0
- **Feed now** in place of feeding times: the fish are fed when you want to, from the dashboard, and
  never by the clock. Any feeding times you had set are tidied away by the Matrix on its next start.

## 2.1.0
- Feeding times are picked with time pickers (**+ Add feeding time**), in place of the `feed_at`
  text box, so there is nothing to type and nothing to get wrong. If you had typed times into Feed at,
  add them again under Feeding times. It is with the main settings now, not under Advanced.

## 2.0.0
- Buttons in the dashboard while the Aquarium is on the panel: Feed, Tap the glass, Add a fish,
  Remove a fish. All optional: nothing gets hungry and nothing needs looking after.
- The fish now turn and swim to places instead of following fixed paths, and are where you left them
  when the Aquarium comes round again.
- `feed_at`: times to drop food in by itself. Off unless you set it.
- The fish you add or remove are remembered (a small file in the module's working folder).
- A startled puffer puffs up (`art/scared`).
- The fish are now Animator projects (the `art` folder), so they can be opened and changed in the
  Matrix's Animator.
- `fish` is now how many the tank starts with.

## 1.0.0
- First release.
