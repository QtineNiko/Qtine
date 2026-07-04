# -*- coding: utf-8 -*-
"""Hello command module."""


def register_hello_commands(plugin):
    plugin.register_command("/hello", _handle_hello, aliases=["/hi"])


def _handle_hello(event, args):
    name = event.message.sender.nickname if event.message.sender else "world"
    return f"Hello, {name}!"
