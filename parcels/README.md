# Parcels, for the Bongo Matrix

Your parcels on their way, on the panel:

- **One parcel**: its nickname, how it's getting on (ARRIVES TODAY, OUT FOR DELIVERY, DELIVERED, and the rest below),
  the time slot or the day it's due, the courier's name, and a little van driving along a route bar (posted, at the
  depot, out for delivery, home) to the house.
- **Several parcels** take turns, 5 seconds each (longer if a nickname needs to scroll): out for delivery first, then
  arriving today, then the rest by when they're due, delivered ones last.
- **Delivered**: a box lands on the doorstep, with a tick, the time, and where it was left when the courier says
  (PORCH, NEIGHBOUR, SAFE PLACE, LOCKER, POST OFFICE...).
- **Pop-ups** when a parcel is out for delivery and when it's delivered (each can be switched off). Never in the
  sleep hours: a pop-up waits until they end, and is dropped if it's no longer news by then. The pop-up has a look
  of its own: a band drops in from the top in the news's colour, with OUT TODAY and the van driving in, or
  the tick, DELIVERED and the box; then the nickname, and under it the time slot and courier (12:15-13:15 DPD) or
  when, where and by whom (11:42 PORCH UPS). If that look ever fails, the Matrix shows its words instead ("Out
  today: New Boots (DPD), 12:15–13:15", "Delivered: New Boots: porch 11:42, UPS"; a long nickname is cut short with
  "…"). A long nickname and then the line under it are each held, slid through to their end and held, and the pop-up
  stays up long enough for both (10 to 20 seconds). On a 64-dot-high panel the screen's scene sits below the band
  (the van driving along the route to the house, or the box on the doorstep), and on a 128-dot-wide one the route
  and the house are to its right. The look is only a pop-up: it isn't offered as a screen for the playlist.
- **Nothing coming?** The screen is skipped: the playlist carries straight on.
- Delivered parcels leave the panel after 2 days (a setting).

The other words it can show: ON ITS WAY, NOT SENT YET (the courier has the label but not the parcel), MISSED DELIVERY,
READY TO COLLECT, HELD UP (a problem the courier reports), NOT FOUND YET (the courier hasn't scanned it yet),
CHECKING, WAITING (past this month's free parcels, see below) and NEEDS A KEY.

No courier's logo or colours are used anywhere: the courier is named in plain words.

## Importing it

On the Matrix's dashboard: **Settings › Modules › Import**, paste this repo's GitHub link, read what it asks for and
tick "I trust". It asks to:

- work in the background while it's switched on (it checks your parcels);
- see whether the panel is asleep (so a pop-up never comes in the sleep hours) and show short messages (the pop-ups);
- keep the keys you type in as secrets.

It can only reach `api.ship24.com`, `api-eu.dhl.com` and `onlinetools.ups.com`, and needs a Matrix with module API 3
or later (pop-ups in a module's own look).

Then add **Parcels** to the playlist, and fill in its card in **Settings › Modules › Parcels**.

## Adding parcels

The card has four boxes, **Parcel 1** to **Parcel 4**. In each, put the tracking number, or paste the whole tracking
link from the courier's email or text, then a nickname:

```
JD0002240145 New boots
AB 1234 5678 9GB, Printer ink
https://www.ups.com/track?loc=en_GB&tracknum=1Z999AA10123456784 Birthday gift
```

Use a comma (or `=`) between them when the number has spaces in it. A link is read on the Matrix itself: only the
tracking number is ever sent anywhere. When a parcel has come, empty its box for the next one (it leaves the panel by
itself after "Keep delivered" days either way).

## The Ship24 key (needed, free)

Ship24 follows parcels from nearly every courier (Royal Mail, Parcelforce, Evri, DPD, Yodel, DHL, UPS, Amazon and some
2,500 more) and works out the courier from the number.

1. Sign up at [ship24.com](https://www.ship24.com) with an email address.
2. Choose the free **Tracking API** plan (the per-shipment one, "Tracking API & Webhook"). Not the free
   "All-in-one" plan, which has no API, nor the free "per call" plan.
3. In Ship24's dashboard, **Developers › API keys**: copy your key into **Ship24 key** on the card, and press Save.

What the free plan allows (as Ship24 describes it, November 2026):

- **10 new parcels a month.** A parcel uses one when the module first asks Ship24 to follow it. Checking it again
  after that, however often and for however long, uses nothing. (Ship24 says a few couriers count as 2 parcels.)
- **No overage, nothing to pay**: past the 10, Ship24 simply refuses new parcels until its month starts again. The
  module counts what it has used ("3 parcels · 4 of 10 used this month"); an 11th parcel shows WAITING with the day
  it starts (the 1st), and the card says so. If Ship24's own month starts on another day (it counts by its billing
  period), the module believes Ship24, and asks again once a day, which costs nothing when refused.
- Ship24 allows 10 requests a second; this module asks one question every 10 seconds at most.

## The optional DHL and UPS keys (free)

DHL and UPS have free tracking APIs of their own. With their keys set, their parcels are followed there instead, and
use none of Ship24's 10. A number that DHL or UPS doesn't know goes to Ship24 as usual (JD... numbers can be Yodel's
too), and if a key stops working its parcels go to Ship24 and the card says so.

**DHL** (Shipment Tracking - Unified API):

1. Sign up at [developer.dhl.com](https://developer.dhl.com).
2. **My Apps › Create app**, and add the API **Shipment Tracking - Unified**.
3. Once it's approved (usually quickly), open the app and copy its **API Key** (not the secret) into **DHL key**.

A free key allows 250 calls a day and one a second. The module keeps under 200 a day: with several DHL parcels each
is checked a little less often than "Check every" if that's needed.

**UPS** (Tracking API):

1. Sign up at [developer.ups.com](https://developer.ups.com) and log in.
2. **Create Application**, choose the **Tracking** API product (UPS may ask you to link a UPS account; opening one
   costs nothing).
3. Copy the app's **Client ID** and **Client Secret** into **UPS client ID** and **UPS client secret**.

The module gets a short-lived sign-in token from them (OAuth client credentials) and uses it until it runs out.

All four keys are kept by the Matrix as secrets: never shown again on the dashboard, never in the config or a backup,
and blanked out of the logs. They are given only to this module.

## The rest of the card

| Setting | Default | What it does |
| --- | --- | --- |
| Check every (minutes) | 15 | How often each parcel is checked, 10 to 240. A delivered parcel isn't checked again. |
| Keep delivered (days) | 2 | How long a delivered parcel stays on the panel. |
| Pop-up when out for delivery | on | |
| Pop-up when delivered | on | |

The line under the card says how things stand: `3 parcels · 4 of 10 used this month`, or what needs doing
(`Add your free Ship24 key`, `Parcel 2: no tracking number in that link`).

## What stays in the room

What's coming, from whom and where it was left are for the people who can see the panel. Every frame of the Parcels
screen and its pop-ups is kept off the web: the panel shows it as ever, but the hub's live picture (matrix.local),
the dashboard's Now page and the screen's preview show a dark stand-in with a small padlock while it plays. (A
pop-up's words, "Out today: New Boots (DPD), 12:15–13:15", are still said on the Now page by the Matrix itself, to
paired browsers only.)

## The pictures

The van, the house, the box, the doorstep and the tick are drawings made in the Matrix's Animator, in `art/`. Open
one in the Animator (File › Open a drawing file…) to change it; keep its size and layer names (the van's `Van` and
`Trail`, the house's `House` and hidden `Lit window`).

## Tests

The tests run against a checkout of the Matrix, with every courier's API stood in for:

```
BONGO_MATRIX=/path/to/matrix BONGO_OFFLINE=1 python -m pytest -q tests
```

They zip this repo and install it through the Matrix's own import, run its background task in a process of its own,
and draw every screen and the pop-up at several panel sizes. To draw the pop-up as LED-look GIFs for a look
(`popup-*.gif`, in the real sandbox):

```
PARCELS_REVIEW_OUT=/tmp/parcels-review BONGO_TEST_SANDBOX=on BONGO_MATRIX=/path/to/matrix python -m pytest -q tests/test_review.py
```

## Licence

MIT: see [LICENSE](LICENSE).
