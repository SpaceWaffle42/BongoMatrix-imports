# Phone notifications

A module for the Bongo Matrix that puts notifications from your phone on the panel: a message from someone, a
parcel on its way, a missed call. A short pop-up cuts in over the playlist, then the playlist carries on, and
screens list the last few.

Your phone sends each notification to **ntfy.sh**, a free relay, under a private name (the *topic*). The Matrix
keeps one connection open to that topic and hears each one within a second or two. Nothing has to reach into the
Matrix, and there is no account to make and nothing to pay.

```
Your phone  ->  ntfy.sh (free relay)  ->  the Matrix
```

## What it shows

- **Pop-ups**: who it's from (by default), for a few seconds, over whatever is playing. At most one every
  2 minutes: any that come in between wait, then pop up together ("3 new"). Never in the sleep hours, and never in
  your own quiet hours if you set some. When those end, one pop-up says how many came meanwhile ("5 in quiet").
  The pop-up has a look of its own: a card slides down tinted in the kind's colour, with its icon, who it's from,
  the kind and how long ago, then "SEE YOUR PHONE" (or the text, with *Who and the text*), and a line along the
  bottom that shrinks as its time runs out. Several at once show the bell, "3 NEW" and each name in its kind's
  colour, set closer together when that lets them all be seen at once. On a 64-dot-high panel the card fills it: the
  icon twice the size, and the text wrapped over the lines below (with *Who and the text*), or several one to a line. If that look ever fails, the Matrix shows its words instead ("Mum: New message"). The look is only a
  pop-up: it isn't offered as a screen for the playlist, and it is never given more than the card says to show.
- **Recent** (a screen for the playlist): the last few, newest first, each with its kind's icon, who it's from and
  how long ago.
- **Latest one** (a screen): the newest one in full.
- **Setup code** (a screen): your topic as a QR code, for setting up a phone. Add it while you set up, then take
  it out again (see "Keeping it private").

When there's nothing to show, Recent and Latest one skip their turn (or say "Nothing new", if you'd rather: each
screen has the setting). When the Matrix can't reach ntfy.sh they say so, and so does the module's card in
Settings.

Each kind has its own icon and colour: messages, calls, deliveries, email, calendar alerts and other apps.

## Installing it

1. On the dashboard: **Settings › Modules › Import**, and give it this module's link (or its .zip).
2. Read what it asks for, tick "I trust ..." and install. It asks to:
   - work in the background (to keep the connection to ntfy.sh open),
   - see whether the panel is asleep (so pop-ups wait for the morning),
   - show short messages on the panel (the pop-ups, in their own look: "Note, its pop-ups only"),
   - keep two secrets you type in (the topic name and an optional access token).
   It can reach ntfy.sh and nothing else. It needs a Matrix with module API 3 (pop-ups in a module's own look).
3. Open **Settings › Modules › Phone notifications**. The line under Save says **"Topic made: add the Setup code
   screen and scan it with your phone"**: a topic of 20 random letters and numbers has been made for you. It is
   never shown on the dashboard. Add the **Setup code** screen to the playlist: it shows the topic's full address
   (`https://ntfy.sh/...`) as a QR code on the panel. Scan it with the phone, then take the screen out again. (Or
   type a topic of your own into **Topic name**, and put that in the phone instead.)
4. Add **Recent** or **Latest one** to the playlist if you want them.

## Setting up the phone

### Android (MacroDroid, free)

Android lets an app read notifications if you allow it. MacroDroid is free (the free version keeps up to 5
automations, with adverts; this needs one) and lets you pick exactly which apps are sent.

1. **Install MacroDroid** from the Play Store. Open it and skip the tour.
2. **Make a macro that starts on a notification**: Add Macro › Triggers › Notification › **Notification Received**.
3. Tap **Select application(s)** and tick only the apps you want on the panel: your messages app, a courier's app,
   your phone app for missed calls. Leave out your bank, anything that sends login codes, health and dating apps.
   Tick **Ignore ongoing notifications** and **Prevent multiple triggers**. Allow notification access when it asks.
4. **Keep login codes on the phone** (recommended): in the same trigger, set the text filter to **Excludes** and type
   `code`, so "your code is 123456" never leaves the phone.
5. **Add the action that sends it**: Actions › search **HTTP Request**. Method **POST**, address
   `https://ntfy.sh/`. Body type **JSON**, and paste this, with your topic in place of the example:

   ```json
   {"topic": "k7q2-xp9w-4rzt-m8vd-3hfa",
    "title": "[notification title]",
    "message": "[notification text]",
    "tags": ["[app name]"]}
   ```

   Put the notification's title, text and app name in with MacroDroid's **...** (magic text) button: pick the
   notification title, the notification text and the application name. To keep the text private, type
   `"message": "New"` instead: then only who it's from and the app leave the phone.
6. **Save it and let it run**: tap the tick and call it "To the Matrix". If your phone asks about the battery,
   choose **Don't optimise** for MacroDroid, or it may be stopped in the background.
7. **Check it**: send yourself a message. It shows on the panel within a few seconds.

Already have Tasker? Its "Notification" event and "HTTP Request" action do the same.

### iPhone (Shortcuts)

An iPhone never lets one app read another app's notifications, so this can't pass on WhatsApp, a courier's app or
missed calls. What it can do, with the built-in **Shortcuts** app: run when a text or iMessage arrives (from people
you pick, or containing a word you pick), or when an email arrives in the Mail app. Calendar alerts don't need the
phone: the Matrix's own Calendar module already shows your calendars.

1. **Start a new automation**: Shortcuts › Automation › **+** › **Message**.
2. **Pick which messages**: under **Sender**, choose the people (say, family). Or use **Message Contains** with a
   word like `delivery` for courier texts. Make one automation for each.
3. **Let it run on its own**: choose **Run Immediately**. If you see **Notify When Run**, you can turn it off.
4. **Add the action that sends it**: New Blank Automation › Add Action › **Get Contents of URL**. Address
   `https://ntfy.sh/`. Tap **›** to open it: Method **POST**, Request Body **JSON**, and add four fields:

   | Key | Type | Value |
   | --- | --- | --- |
   | `topic` | Text | your topic, e.g. `k7q2-xp9w-4rzt-m8vd-3hfa` |
   | `title` | Text | Shortcut Input › **Sender** |
   | `message` | Text | Shortcut Input › **Content** |
   | `tags` | Array | one Text item: `message` |

   For "Shortcut Input › Sender", tap the field, pick **Shortcut Input**, tap it again and choose **Sender** (and
   **Content** for the message). To keep the text private, type `New` as the message instead of the Content.
5. **Do the same for email** (if you like): Automation › **+** › **Email**, pick senders or a subject word, and
   send **Sender** and **Subject** (not the whole email), with the tag `email`.
6. **Check it**: ask someone you picked to text you. It shows on the panel within a few seconds.

Other iPhone automations can send to the panel the same way, with whatever text you type: **Sound Recognition**
(a doorbell heard by the phone), **Charger** or **Battery Level**.

### The kinds, and the tags that say which is which

The module sorts each notification by its tags. A kind word as a tag says it outright; otherwise the app's name
decides (WhatsApp, Signal and Messages are messages, Gmail and Outlook are email, a courier's app is a delivery,
the phone app is a call), and anything it doesn't know is "other apps".

| Kind | Tag | Settings line |
| --- | --- | --- |
| Messages: texts and chat apps | `message` | Messages |
| Calls: missed calls (Android) | `call` | Calls |
| Deliveries: a courier's app or texts | `delivery` | Deliveries |
| Email | `email` | Email |
| Calendar alerts | `calendar` | Calendar and other apps |
| Anything else | the app's name | Calendar and other apps |

## Settings (Settings › Modules › Phone notifications)

- **Topic name**: leave it empty and one is made for you. Or type your own: letters, numbers, `-` and `_`, up to 64.
  Make it long and random, never a word or a name.
- **Access token (optional)**: only if you reserved your topic on an ntfy.sh account; a token from there (`tk_...`).
- **On the panel, show**: *Only who it's from* (the default), *Who and the text*, or *Only the kind of app*
  ("New message"; for a shop or a shared room).
- **Pop-ups at most every**: 2 (the default), 5, 15 or 30 minutes.
- **Quiet hours**: no pop-ups then, like `21:30-07:00` (empty: none). They still go in the list. There are never
  pop-ups in the sleep hours (Settings › Sleep), whatever this says.
- **Keep the last**: how many the screens list (8 by default). Each is forgotten a day after it came.
- **Messages, Calls, Deliveries, Email, Calendar and other apps**: for each kind, *Show and pop up*,
  *Show, no pop-up* or *Don't show*. By default messages, calls and deliveries pop up; email, calendar alerts and
  other apps are only listed.
- **Sum up after quiet hours**: one pop-up when quiet or sleep hours end, saying how many came (on by default).

The **Clear the list** button (on the Now page while Recent or Latest one is on the panel) empties the list.

## Keeping it private

On the free public server, what you send passes through ntfy.sh. It's sent over HTTPS and ntfy says it doesn't
log message text, but it does keep each message for up to 12 hours (so the Matrix can catch up after a restart),
and anyone who knows (or guesses) the topic name can read it. So:

- **Treat the topic name like a password.** The one made for you is 20 random letters and numbers. It's a secret
  setting: kept out of the config, out of backups, and never sent back to a browser.
- **Choose the apps on the phone, not just on the Matrix.** An app switched off on the Matrix has already been sent
  through ntfy.sh.
- **Leave the text out on the phone** when who it's from is enough. "Only who it's from" hides the text from the
  room, but it has still passed through ntfy.sh.
- **Never forward** bank and payment apps, login and security codes, health, dating, or work email you aren't
  allowed to share.
- **The Setup code screen shows your topic to anyone who can see the panel**, for as long as it's in the playlist.
  Add it while you set up a phone, then take it out. It is never in a picture on the web: while the code is on the
  panel, the hub's live picture (matrix.local), the dashboard's Now page and a preview all show a dark stand-in with a
  small padlock instead.
- **Who sent you what stays in the room too.** Recent, Latest one and the pop-ups are never in a picture on the web
  either, whatever "On the panel, show" says: the hub's live picture and the Now page show the padlocked stand-in
  while they play ("Nothing new" is shown as it is). One thing the Matrix itself shows: the Now page says what a
  pop-up's words are ("A pop-up from Phone notifications: Mum: New message"), to paired browsers only, so keep
  "Only who it's from" if that matters.
- **Spam on the panel**: only someone with the topic name can post. If it ever happens, type a new topic into
  Topic name (long and random) and change it on the phone too. Pop-ups are rate-limited
  anyway.
- The list of notifications is kept only in the module's own folder on the Matrix, never in a backup.

### Which apps to let through (a suggestion for a home)

- Messages from people (texts, chat apps): show, pop up.
- Deliveries (a courier's app or texts): show, pop up. "Out for delivery" is exactly what the panel is for.
- Missed calls (Android only): show, pop up.
- Email: only from a few people, show, no pop-up.
- Calendar alerts: the Matrix's Calendar module already shows your calendars.
- Everything else (games, shopping, news, social media): don't send. They're noise on a 64×32 panel.

## ntfy.sh's free limits

- 250 messages a day sent from one place (your phone's connection). Past that it stops passing them on until the
  next day. Nothing is charged.
- Each message up to 4,096 bytes; it keeps messages for up to 12 hours.

If the module says **"Can't reach ntfy.sh"**, the Matrix has no internet or ntfy.sh is down: it tries again by
itself, and asks for anything it missed when it's back.

Your own ntfy server (so nothing leaves the house) isn't offered yet.

## Troubleshooting

- **Nothing arrives**: check the topic on the phone is exactly the one in Settings (no spaces). Open
  `https://ntfy.sh/your-topic` in a browser and send again: if it shows there, the phone is fine.
- **Some messages don't arrive (Android)**: a message with a double quote (`"`) in it can break the JSON. Sending
  `"message": "New"` (who only) avoids it.
- **No pop-ups**: they never come in the sleep hours or quiet hours, at most one every 2 minutes, and only for
  kinds set to *Show and pop up*.

## For developers

The module's folder is this repo (`bongo-module.json` beside `__init__.py`, the way Settings › Modules › Import
expects it). The icons are Animator drawings in `art/`: open them in the Matrix's Animator (File › Open a drawing
file) to change them.

Tests run against a checkout of the Matrix's code:

```bash
BONGO_MATRIX=/path/to/bongo_matrix BONGO_OFFLINE=1 python -m pytest -q -p no:cacheprovider tests
```

They import this repo through the Matrix's real import flow (zip, test screen, review, install) and talk to a
stand-in for ntfy.sh; nothing reaches the real one. To draw the pop-up as LED-look GIFs for a look (`popup-*.gif`,
in the real sandbox):

```bash
NOTIFICATIONS_REVIEW_OUT=/tmp/review BONGO_TEST_SANDBOX=on BONGO_MATRIX=/path/to/bongo_matrix python -m pytest -q tests/test_review.py
```

## Licence

MIT: see LICENSE.
