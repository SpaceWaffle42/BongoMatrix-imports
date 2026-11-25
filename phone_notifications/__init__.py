"""Phone notifications: notifications from your phone on the panel. The phone sends each one to a topic on
ntfy.sh (a free relay); this module keeps one connection open to that topic in the background, keeps the last
few, and asks the Matrix for a short pop-up, in a look of its own, when one is allowed. Screens: Recent, Latest
one, Setup code."""
import bongo.module

if getattr(bongo.module, "API", 1) < 3:
    raise ImportError("This module needs a newer Matrix: update it in Settings > Software, then import it again.")

from bongo.module import Module  # noqa: E402

from .listen import Listen  # noqa: E402
from .popups import Note  # noqa: E402
from .screens import Latest, Recent, SetupCode  # noqa: E402

HELP = {
    "title": "Setting up your phone",
    "intro": "Your phone sends each notification to ntfy.sh, a free relay, under a private topic name. This module "
             "listens there. The topic name is in Settings › Modules › Phone notifications (made for you the first time).",
    "steps": [
        "Android: install MacroDroid (free) and make a macro: trigger Notification › Notification Received, with only the apps you want ticked.",
        "Add the action HTTP Request: POST to `https://ntfy.sh/`, body JSON with your topic, the notification's title and text, and the app name as a tag.",
        "iPhone: in Shortcuts › Automation make a Message (or Email) automation that runs immediately, with the action Get Contents of URL, POST to `https://ntfy.sh/`, the same JSON.",
        "Send yourself a test: it shows on the panel within a few seconds.",
    ],
    "tips": [
        "The full steps, word for word, are in the module's README.",
        "Treat the topic name like a password: anyone who has it can read what you send and post onto your panel.",
        "Never forward bank apps, login codes, health or dating apps.",
        "Add the Setup code screen to show the topic as a QR code on the panel, and take it out again when you're done.",
    ],
    "links": [{"label": "ntfy.sh", "url": "https://ntfy.sh/"},
              {"label": "MacroDroid", "url": "https://www.macrodroid.com/"}],
}

MODULE = Module(
    id="phone_notifications", name="Phone notifications",
    styles={"recent": Recent, "latest": Latest, "setup_code": SetupCode,
            "note": Note},          # (the pop-up's own look: only ever a pop-up)
    description="Notifications from your phone: a short pop-up over the playlist, and the last few on a screen.",
    help=HELP,
    actions={"clear": "Clear the list"},
    background=Listen,
    secrets=("topic", "token"),     # the topic name and access token: kept apart, never in a backup or a browser
)
