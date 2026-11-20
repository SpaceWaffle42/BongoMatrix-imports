# Home Assistant for Bongo Matrix

The Matrix appears in Home Assistant by itself, as one device: a light for the panel, a sensor for the
screen that is playing, a pause switch, a Next button, and a way to show a short message on the panel
from an automation.

It talks to Home Assistant through the MQTT broker Home Assistant already uses (its Mosquitto broker, say),
with MQTT discovery. There is no Home Assistant token to make, no custom integration, and nothing to install
on the Home Assistant side.

Version 1.0.1, by spacewaffle42. MIT licence. It has no screens of its own: it works in the background.

## What you need

- A Bongo Matrix v3 new enough to import modules that work in the background (module API 2). On an older
  one the import stops with "This module needs a newer Matrix: update it in Settings > Software, then
  import it again."
- Home Assistant 2024.11 or newer, with its MQTT integration set up and discovery left on (it is by default).
- An MQTT broker on your home network that Home Assistant is connected to. Home Assistant's own
  "Mosquitto broker" is the usual one.

## Setting it up

1. **A user for the Matrix on the broker.** With Home Assistant's Mosquitto broker, any Home Assistant user
   can log in to the broker: in Home Assistant go to **Settings > People > Users**, add a user (say
   `matrix`) with a password made for this, and tick "Can only log in from the local network" if you like.
   Don't call it `homeassistant` or `addons` (the broker keeps those names for itself), and don't reuse a
   password from anywhere else: the Matrix hands it to this module's code. With another broker, add a user
   the way that broker does it.
2. **Import the module.** In the Matrix's dashboard: **Settings > Modules > Import**, then choose
   `home_assistant-1.0.1.zip`, or paste the bongo_imports repository's link and tick Home Assistant. The review lists what it asks for:
   to keep working in the background, to see what the panel is doing, to sleep and wake it, to change the
   brightness, to pause and skip, to show short messages, to connect to one device on your home network
   (ports 1883 and 8883), and to keep a password. Tick that you trust the author and install it.
3. **Fill in its card**, under Settings > Modules, "Home Assistant":
   - **Broker address**: the name or address of the computer the broker runs on (`homeassistant.local`, or
     something like `192.168.1.20`).
   - **Port**: 1883, or 8883 for the broker's encrypted port.
   - **Username** and **Password**: the user from step 1.
   - **Encrypted (TLS)**: on only with port 8883 (see "Encryption" below).
   - **Name in Home Assistant**: what the device is called there. Give each Matrix its own.
4. The line under the fields says **Connected to the broker**, and in Home Assistant the Matrix is under
   **Settings > Devices & services > MQTT**, as a device with the name you gave it.

## What appears in Home Assistant

| Entity | What it is | Kind |
|---|---|---|
| *Bongo Matrix* | The panel. On is awake, off is asleep; the brightness is the Matrix's own 1 to 100% | light |
| Screen | The screen now playing ("Clock"), "Asleep" while it sleeps. Attributes: `module` and `style` | sensor |
| Pause | On is paused (the panel stays on the screen it is on), off is playing | switch |
| Next | Moves on to the next screen | button |
| Message | Shows a few words on the panel, from `notify.send_message` | notify |

All five belong to one device and go "unavailable" together when the Matrix is off, unplugged, or the
module is switched off (within about 45 seconds if the power is simply cut).

Things worth knowing:

- **Brightness set from Home Assistant counts as set by hand**: it stays until you switch back to Auto; with
  Follow daylight on (Settings > Device) it also ends by itself at the next sunrise, sunset or sleep change.
  That is the Matrix's rule for any brightness set by hand.
- **Off from Home Assistant sleeps the panel** until you turn it back on (from Home Assistant, or Wake now
  on the dashboard) or until the Matrix's sleep hours next start or end; with no sleep hours set, for a week.
- A brightness sent while the panel is asleep and staying asleep is not set (it would not outlast the
  waking). "Turn on at 40%" wakes it first and then sets 40%.
- **Pause is a switch, not a button**, because the Matrix knows whether it is paused: Home Assistant shows
  it, and a pause from the dashboard shows up there too.
- **Messages** are cut to what the panel takes: 120 characters, shown for 10 seconds. The Matrix shows at
  most one every 5 seconds and 10 in ten minutes from this module. Up to three wait their turn; beyond
  that they are dropped and the card says "Dropped 4 messages: too many at once" for a minute. The same
  words twice in a row while one is still waiting are shown once.
- Everything Home Assistant asks is carried out within a second or two, one change of each kind at a time
  (the Matrix allows one a second): drag a dimmer and the Matrix gets where you stopped, not every step.

### Examples

```yaml
# "Washing done" on the panel
action: notify.send_message
target:
  entity_id: notify.bongo_matrix_message
data:
  message: "Washing done"
```

```yaml
# Dim the panel when a film starts, wake it at 40% in the morning
action: light.turn_on
target:
  entity_id: light.bongo_matrix
data:
  brightness_pct: 40
```

Home Assistant's notify entity sends only the message. For a title, or to choose how long it stays up (3
to 30 seconds), publish to the Matrix's topic yourself (the id is in the device's page, and in the topics
below):

```yaml
action: mqtt.publish
data:
  topic: bongo_matrix/1a2b3c4d/notify/send
  payload: '{"message": "Someone is at the door", "title": "Doorbell", "seconds": 20}'
```

Leave "retain" off for anything you publish to the Matrix. A command the broker has kept is ignored and
wiped, so that an old "off" can't put the panel to sleep every time the Matrix reconnects.

## Encryption

- **Encrypted (TLS) off** (port 1883): nothing is encrypted. The username and password cross your home
  network as they are, as with most things that talk to a broker at home.
- **Encrypted (TLS) on** (port 8883): the connection is encrypted, so the password can't be read on the
  way. **The broker's certificate is not checked** against any authority or name, because a broker at home
  usually has a certificate of its own making that no authority knows. Something on your network that
  pretended to be the broker would not be noticed. The card says so: "Connected to the broker (encrypted,
  certificate not checked)".
- **Certificate fingerprint** (optional): paste the SHA-256 fingerprint of the broker's certificate and the
  module connects only to a broker that shows exactly that certificate, and hangs up before sending the
  password to any other. The card then says "(encrypted, certificate matches)". This is the only check there
  is. When the broker's certificate is renewed the fingerprint changes and must be pasted again.

  Where to get it: once connected without one, the Matrix's **Logs** page has a line "the broker's
  certificate isn't checked. Its SHA-256 fingerprint, ...". Or on a computer:
  `openssl s_client -connect homeassistant.local:8883 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256`
  (colons and capitals are fine). Compare it with the certificate you gave the broker if you want to be sure
  it is the right one.
- A broker set to ask every client for a certificate of its own (`require_certificate`) is not supported.

## If it doesn't work

The line in the card says why, in a few words.

| The card says | What to do |
|---|---|
| Type the broker's address above | Nothing is set yet |
| Not connected: no answer from that address | Wrong address, or that computer is off. The card also shows what the Matrix itself found ("couldn't reach ...") |
| Not connected: nothing is listening at that address and port | The address is right but no broker is on that port: is the Mosquitto broker running? |
| Not connected: the broker refused the username or password | Check them (Password: Replace). It tries again by itself, less and less often (after 30 seconds, then up to every 10 minutes), and at once when you save the card |
| Not connected: the broker wants a username and password | Home Assistant's broker has no anonymous logins: make a user (step 1) |
| Not connected: no MQTT answer: an encrypted port needs Encrypted (TLS) on | You chose 8883 with the switch off, or that isn't a broker |
| Not connected: no encrypted answer: is that the broker's encrypted (TLS) port? | You switched TLS on for 1883, or the broker has no certificate set up |
| Not connected: the broker's certificate doesn't match the fingerprint | The certificate was renewed (paste the new fingerprint), or that isn't your broker |
| Not connected: the broker hung up / stopped answering | The broker restarted or the network dropped: it reconnects by itself within a minute |
| Connected, but the broker won't let this user receive commands | The broker has access rules (an ACL) that stop this user subscribing: see below |
| Connected. The Matrix refused a change: ... | Home Assistant asked for more than the Matrix allows a module (for example 30 sleeps in ten minutes) |
| An address is refused when you save | The Matrix only lets a module reach a private home-network address, and never the Matrix itself |

Connected, but nothing in Home Assistant?

- Is Home Assistant's MQTT integration connected to the *same* broker, with discovery on and the discovery
  prefix left as `homeassistant`? (A changed prefix is not supported.)
- Is Home Assistant 2024.11 or newer? Older ones don't know this kind of discovery message.
- With access rules on the broker, the Matrix's user needs: read and write on `bongo_matrix/#`, write on
  `homeassistant/device/#`, read on `homeassistant/status`.

Removing it: remove the module in Settings > Modules, then delete the device in Home Assistant (Settings >
Devices & services > MQTT > the device > Delete). Nothing is left on the broker that brings it back, apart
from a few small kept messages under `bongo_matrix/<id>/` (the last states, and "offline").

If you remove the module and import it again, it makes a new id, so Home Assistant sees a new device: delete
the old one there.

## What it can and cannot do

It can: see whether the panel is asleep or paused, its brightness and the name of the screen playing; sleep
and wake it; set the brightness; pause, resume and skip; show short messages; talk to the one broker you
named, on port 1883 or 8883.

It cannot: change the playlist or any setting, see the picture on the panel or any module's settings, reach
anything else on your home network or anything on the internet, or run when it is switched off in Settings >
Modules. The Matrix enforces all of that, not this module, and limits how often each control can be used.

Not in this version: choosing a screen from Home Assistant, going back to the Matrix's own brightness from
Home Assistant (it does so by itself at the next sleep or wake), a discovery prefix other than
`homeassistant`, MQTT 5, client certificates.

## Privacy

- It sends to your broker, and only there: whether the panel is asleep, its brightness, whether it is
  paused, and the name, module and style of the screen playing ("Clock", `clock`, `big`). Never a screen's
  contents or settings (no calendar entries, no message text, no picture).
- Anything that can read your broker can read those, and anything that can publish to your broker can do
  what Home Assistant can do here: sleep the panel, change its brightness, show a message on it.
- The password is kept by the Matrix (never in a backup, never sent back to a browser) and given to this
  module, which sends it to the broker and nowhere else. It is never written to a log, a status line or a
  topic. Use a password made for this.
- It keeps one small file in its own folder: `matrix-id.txt`, eight random letters and digits that name
  this Matrix on the broker. Nothing about you is in it.
- No internet. The module lists no sites, so the Matrix lets it reach none.

## Topics, for the curious

`<id>` is this Matrix's id (in `matrix-id.txt`, and in the device's identifiers in Home Assistant).

| Topic | Payload | |
|---|---|---|
| `homeassistant/device/bongo_matrix_<id>/config` | the discovery message (JSON) | sent on connecting, when Home Assistant starts (`homeassistant/status` says `online`), and every 15 minutes; not kept by the broker |
| `bongo_matrix/<id>/availability` | `online` / `offline` | kept; `offline` is also the last will |
| `bongo_matrix/<id>/light/state` | `{"state":"ON","brightness":70}` | kept |
| `bongo_matrix/<id>/light/set` | `{"state":"ON","brightness":40}`, `{"state":"OFF"}` | command; brightness 1 to 100 |
| `bongo_matrix/<id>/screen/state` | `Clock` | kept |
| `bongo_matrix/<id>/screen/attributes` | `{"module":"clock","style":"big"}` | kept |
| `bongo_matrix/<id>/pause/state` | `ON` / `OFF` | kept |
| `bongo_matrix/<id>/pause/set` | `ON` / `OFF` | command |
| `bongo_matrix/<id>/next/press` | `PRESS` | command |
| `bongo_matrix/<id>/notify/send` | the message, or `{"message":..., "title":..., "seconds":...}` | command |

It speaks MQTT 3.1.1 with a clean session and a 30-second keep-alive, subscribes at QoS 0 (a command sent
while the Matrix was away is not delivered late), and publishes states at QoS 0 and the discovery message
and "online" at QoS 1.

## For people changing it

- `mqtt.py`: the MQTT client. Python's own library only, and it never waits: a background task on the
  Matrix must return within seconds, so connecting, the TLS handshake, a silent broker and a flood are all
  handled a step at a time.
- `bridge.py`: the topics, the discovery message, and how commands become uses of the panel's controls.
- `__init__.py`: the few lines that join them to the Matrix.

Tests (they need `pytest`; the first two need nothing of the Matrix):

```bash
python3 -m pytest tests                      # the MQTT client and the bridge, against tests/fake_broker.py

# on a real Matrix: its own import, sandbox and gate, with a broker on a stand-in home network.
# Needs Linux and root (it makes two network namespaces); skipped otherwise.
sudo BONGO_MATRIX=/path/to/a/matrix/checkout python3 -m pytest tests/test_on_a_matrix.py
sudo python3 tests/e2e.py /path/to/a/matrix/checkout --older /path/to/an/older/checkout     # the same, line by line
```

Build the zip with `python3 build.py`.
