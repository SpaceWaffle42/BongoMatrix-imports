"""Home Assistant for Bongo Matrix: the Matrix appears in Home Assistant by itself, through the MQTT broker
Home Assistant already uses.

No screens: it works in the background. ``mqtt.py`` is the MQTT client (Python's own library only, and it
never waits), ``bridge.py`` is what is said over it. README.md says what appears in Home Assistant and how
to set it up.
"""
import bongo.module

if getattr(bongo.module, "API", 1) < 2:
    raise ImportError("This module needs a newer Matrix: update it in Settings > Software, then import it again.")

from bongo.module import Background, Module, home_connect  # noqa: E402

from .bridge import VERSION, Link  # noqa: E402

__version__ = VERSION


class Bridge(Background):
    every = 1                                  # a command from Home Assistant is carried out within about a second

    def start(self):
        # The only call that may wait is the dial, for 2 seconds at most; nothing after it ever does.
        self.link = Link(dial=lambda: home_connect(timeout=2), folder=".", report=self.report)

    def settings_changed(self):
        self.link.configure(self.settings)

    def stop(self):
        # Called by a Matrix whose Background has a stop hook (switched off, removed, shutting down): "offline"
        # and a clean DISCONNECT at once. An older Matrix never calls it; then the broker's last will says
        # "offline" when the process ends, a few moments later.
        self.link.close()

    def tick(self, now):
        self.link.configure(self.settings)     # (does nothing unless they changed)
        self.link.tick(self.panel)


MODULE = Module(
    id="home_assistant",
    name="Home Assistant",
    description="The Matrix appears in Home Assistant by itself (MQTT discovery), through the MQTT broker "
                "Home Assistant already uses (its Mosquitto broker, say).",
    styles={},
    background=Bridge,
    secrets=("password",),
)
