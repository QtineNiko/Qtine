# -*- coding: utf-8 -*-
"""Example Qtine plugin - main entry point.
Demonstrates the standard zip plugin structure.
"""

from qtine.plugins.base import BasePlugin
from .command.ping import register_ping_commands
from .command.hello import register_hello_commands


class ExamplePlugin(BasePlugin):
    name = "example-plugin"
    package = "qtine-plugin-example"
    version = "1.0.0"
    description = "An example Qtine plugin"
    author = "Your Name"

    def __init__(self, bot=None):
        super().__init__(bot)
        register_ping_commands(self)
        register_hello_commands(self)

    def on_enable(self):
        self.logger.info("Example plugin enabled!")

    def on_disable(self):
        self.logger.info("Example plugin disabled!")
