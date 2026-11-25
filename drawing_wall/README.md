# Drawing wall, for the Bongo Matrix

A family message board on the panel. Anyone in the house with a paired phone or computer opens the wall's page on
the dashboard and draws with a finger: "Gone to the shops", a heart, a quick doodle.

- **Live.** Every dot shows up on the panel as it's drawn, and on every other phone that has the page open.
  Several phones can draw at once; each one's pen shows on the panel, with their name for the first moments.
- **It cuts in.** When someone starts drawing, the wall comes straight onto the panel (as a pop-up in its own look)
  and stays while dots keep coming, until 8 seconds after the last one. Never in the sleep hours, and not while
  the panel is paused. Or, if you'd rather,
  the drawing waits for the wall's turn in the playlist (a setting).
- **Nine colours**, fixed, and a rubber; a thin or a thick pen; **Undo** takes back your own last line only (other
  phones' lines stay); **words** typed in go on in the Matrix's own letters, as big as fits, in the middle (moved
  along a little if they'd touch what's drawn there).
- Held sideways (or on a computer), the tools sit beside the wall and the wall is as big as the height allows.
- **Clear asks first**, on the page: "Clear the wall for everyone?", Keep it or Clear it.
- **Send** keeps the drawing in the wall's **history** (the last 5, or 1 to 12). Tap one in the history to put it
  back up. A **pop-up** when a drawing is sent is there if you want it: it's off unless you switch it on.
- The picture is always the panel's own size, dot for dot: 64 × 32, 128 × 32 or 64 × 64 (the phone's canvas
  takes the panel's shape).

It needs no internet and no account: everything stays on the Matrix.

## On the panel

| Look | What it shows |
| --- | --- |
| **The wall** (a screen for the playlist) | The drawing as it stands. When it comes on, everyone who drew on it and when show first, for a moment (if "Show who drew it" is on). While someone draws on it, every dot as it comes, with their pen; it keeps the panel while they draw (Stay on while live) and hands over 8 s after the last dot. An empty wall skips its turn, or says DRAW ON ME and where (MATRIX.LOCAL) (a setting). |
| **History** (a screen for the playlist) | The drawings sent, newest first: who sent it and when, then the drawing slides in and shows for 3 s. Dots at the bottom right say which one it is. It skips its turn while nothing has been sent. |
| **Live** (only ever a pop-up) | The wall cutting in when someone starts drawing: up to 30 s at a time, another following on if they're still going, and it ends itself after a quiet spell, or when the drawing is sent. |
| **Sent** (only ever a pop-up) | A drawing just sent: a frame runs round the edge in the sender's colour, who sent it (for 2 s, as big as the panel allows), then the drawing grows from the middle. |

The Matrix allows a module 10 pop-ups in ten minutes (cutting in and sent drawings together). Past that, a drawing
shows when the wall's turn in the playlist comes, and stays on while someone draws.

## Importing it

On the Matrix's dashboard: **Settings › Modules › Import**, paste this repo's link, read what it asks for and tick
"I trust". It needs a Matrix with module API 3. It asks to:

- work in the background while it's switched on (it keeps the wall, and hears the phones);
- keep the panel while something is live (someone drawing on the wall's screen);
- see whether the panel is asleep or paused (so it never cuts in or pops up in the sleep hours or over a pause), and show short messages (the
  cut-in and the sent pop-up, in its own looks);
- show a page on your dashboard (Drawing wall), for paired phones and computers only, in a box: it can only send
  small messages to this module.
- see this Matrix's web address (like kitchen.local), so an empty wall can say where to draw. Without it (or
  on a Matrix that doesn't tell modules its name) the wall says MATRIX.LOCAL.

It can't reach any site or your home network. It needs a Matrix with module API 3 that tells modules the size of the
panel and its own address; on one before that, the wall learns the size from its own screens and says MATRIX.LOCAL. Then add **Drawing wall** (and its **History**, if you like) to the
playlist, and open the page from **Open Drawing wall** on its row in **Settings › Modules** (or go to
`http://<your Matrix>/m/drawing_wall`).

## Its card (Settings › Modules › Drawing wall)

| Setting | Default | What it does |
| --- | --- | --- |
| When someone starts drawing | Show it straight away | Or **Wait for its turn**: the drawing shows when the wall's turn comes in the playlist. |
| Pop-up when a drawing is sent | Off | Or on, for 5, 10, 15, 20 or 30 seconds. |
| Drawings kept in the history | 5 | 1 to 12. The oldest goes when a new one is sent. |
| Clear the wall by itself | Never | Or **Every night at midnight**, or **A day after the last drawing**. A drawing that was never sent is kept in the history first. |
| When the wall is empty | Skip its screen | Or **Show "Draw on me"**. |
| Show who drew it | on | The name each browser was paired with ("Sam's phone" shows as SAM), on the panel for a moment. |

Who may draw isn't a setting: it's every paired browser, as for the rest of the dashboard. The line under the card
says how things stand: `2 people drawing now · last sent 10:42 from Sam's phone · 4 in the history`.

## How the page talks to the module

The page is one file, `page.html` (CSS and JS inside it, nothing from anywhere else), shown by the dashboard in its
sealed frame. It only ever talks to this module, through the dashboard, within the Matrix's limits:

- **Page to module** (JSON, at most 2 KB each, 20 a second from one browser): the page sends the dots of the line
  being drawn in batches 10 times a second, each with the line's number, colour and thickness, at most 200 dots a
  message; then Undo, Clear, words, Send and "put this one back up".
- **Module to pages** (JSON, at most 8 KB each, 10 a second): the module keeps to 8 a second. It sends the other
  phones' dots in batches as they come (every 0.15 s while someone draws, and at once when a line ends), the whole
  wall after an Undo, a Clear or a picture put back, and the history when it changes. A phone that opens the page
  gets the wall as it stands and the history straight away.

Pictures travel as short text: each dot a digit (0 is nothing, 1 to 9 the colours), or runs of one colour when
that's shorter (most of a drawing is empty: a 64 × 32 picture of a few words is a few hundred characters).

The module keeps the wall and the history in `wall.json` in its own working folder, so a restart loses nothing.

The Matrix tells the module the size of the panel's module area (the safe area), and the wall takes it: if the
panel (or its safe area) changes, the drawing moves to the middle of a wall of the new size, and the open pages hear
of it. On a Matrix that doesn't say, the wall learns the size from its own screens the first time one is drawn.

The empty wall says where to draw: the name the Matrix is reached by, in capitals (KITCHEN.LOCAL). A name too long
for the panel scrolls in its own space, from its first letter; on a 64 × 64 panel it goes on two lines first
(MATRIX-0001 over .LOCAL).

## The pictures

The little pencil on an empty wall, the blinking point of a pen drawing on the panel and the DRAW ON ME squiggle in
the wall's nine colours are drawings made in the Matrix's Animator, in `art/`. Open one in the Animator
(File › Open a drawing file…) to change it; keep its size and layer name. `tools/animator/` has the script that drew
them through the Animator's own page, and a check of each.

## Tests

The tests run against a checkout of the Matrix (module API 3):

```bash
BONGO_MATRIX=/path/to/bongo-matrix BONGO_OFFLINE=1 python -m pytest -q tests
```

They cover the wall itself (lines, each phone's Undo, clearing, the history, sizes, pictures as text, the file),
the background task (what the pages hear, cutting in, the pop-up, clearing by itself, the limits), every look at
each panel size, and the repo imported through the Matrix's own import, run in its own process, with two paired
phones drawing on its page over the dashboard's live connection. `tests/test_page.py` drives the page in headless
Chrome with two browsers (skipped without Chrome and Playwright). With the sandbox's jail on:
`BONGO_TEST_SANDBOX=on`.

Review pictures (LED-look GIFs of every look at each size, recorded while two browsers draw, and screenshots of the
page), only when asked:

```bash
DRAWING_WALL_REVIEW_OUT=/tmp/wall-review BONGO_MATRIX=/path/to/bongo-matrix python -m pytest -q tests/test_review.py
```

## Licence

MIT.
