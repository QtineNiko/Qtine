# -*- coding: utf-8 -*-
"""Ping command module."""


def register_ping_commands(plugin):
    plugin.register_command("/ping", _handle_ping, aliases=["/p"])


def _handle_ping(event, args):
    return "pong!"
