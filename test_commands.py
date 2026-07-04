"""Simplified test of command matching."""
import sys
sys.path.insert(0, '.')

from qtine.plugins.builtin.help import HelpPlugin
from qtine.plugins.builtin.echo import EchoPlugin
from qtine.plugins.builtin.admin import AdminPlugin
from qtine.plugins.builtin.ban import BanPlugin
from qtine.plugins.builtin.welcome import WelcomePlugin
from qtine.plugins.builtin.repeat import RepeatPlugin

print("=== Testing command matching ===")

class MockBot:
    def format_status(self, public=False):
        return "Qtine status: running"
    def plugin_manager(self):
        pass

bot = MockBot()

plugins = [
    HelpPlugin(bot),
    EchoPlugin(bot),
    AdminPlugin(bot),
    BanPlugin(bot),
    WelcomePlugin(bot),
    RepeatPlugin(bot),
]

print(f"\nAll registered commands ({len(plugins)} plugins):")
for p in plugins:
    for cmd, aliases, perm, h in p.get_all_command_handlers():
        aliases_str = ", ".join(aliases) if aliases else ""
        print(f"  [{p.name}] {cmd} | aliases: {aliases_str} | perm: {perm}")

print("\n=== Command matching test ===")

def find_command_handler(content, plugins_list):
    for plugin in plugins_list:
        for cmd, aliases, perm, handler in plugin.get_all_command_handlers():
            parts = content.strip().split()
            if not parts:
                continue
            first = parts[0]
            if first == cmd or first in aliases:
                return plugin, handler, parts[1:]
    return None, None, []

test_cases = [
    "/echo hello",
    "echo hello",
    "#help",
    "#帮助",
    "help",
    "/help",
    "#qtine",
    "qtine",
    "/ban 123",
    "/unban 123",
    "/blacklist",
    "/welcome",
]

for tc in test_cases:
    plugin, handler, args = find_command_handler(tc, plugins)
    if plugin:
        print(f"✓ '{tc}' -> [{plugin.name}] {handler.__name__}, args={args}")
    else:
        print(f"✗ '{tc}' -> NOT FOUND")

print("\n=== Done ===")
