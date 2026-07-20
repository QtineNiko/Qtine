import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from qtine.core.bus import EventBus
from qtine.core.plugin_manager import PluginManager
from qtine.plugins.base import (
    BasePlugin,
    on_command,
    on_event,
    on_keyword,
    on_regex,
)
from qtine.utils.models import Message
from sdk import Plugin, filter


class FakeConfig:
    def get(self, key, default=None):
        return default


class FakeBot:
    def __init__(self, manager):
        self.config = FakeConfig()
        self.event_bus = EventBus()
        self.plugin_manager = manager


class CommandPlugin(BasePlugin):
    name = "dispatch_command_test"


class SdkDispatchPlugin(Plugin):
    name = "dispatch_sdk_test"

    def __init__(self, bot=None):
        self.listener_texts = []
        self.event_values = []
        super().__init__(bot)

    @filter.on_message()
    def listen(self, ctx):
        self.listener_texts.append(ctx.text)

    @filter.on_event("dispatch.test")
    def event(self, data):
        self.event_values.append(data)


class DecoratedPlugin(BasePlugin):
    name = "dispatch_decorated_test"

    @on_command("decorated", aliases=["d"], permission="admin")
    def command(self, event, args):
        return args

    @on_regex(r"^decorated\s+(.+)$")
    def regex(self, event, match):
        return match.group(1)

    @on_keyword(["decorated-keyword"])
    def keyword(self, event):
        return "keyword"

    @on_event("decorated.test")
    def event(self, data):
        self.event_data = data


class LifecyclePlugin(BasePlugin):
    name = "dispatch_lifecycle_test"

    def __init__(self, bot=None):
        self.cleanup_count = 0
        super().__init__(bot)

    def cleanup(self):
        self.cleanup_count += 1
        super().cleanup()


class TypeErrorPlugin(Plugin):
    name = "dispatch_type_error_test"

    @filter.command("broken")
    def broken(self, ctx, args):
        raise TypeError("plugin body error")

    @filter.regex(r"^broken")
    def broken_regex(self, ctx, match):
        raise TypeError("regex body error")


class PluginDispatchTests(unittest.TestCase):
    def setUp(self):
        self.manager = PluginManager()
        self.manager._plugins.clear()
        self.manager._plugin_sources.clear()
        self.manager._mark_indexes_dirty()
        self.manager.bot = None
        self.bus = EventBus()
        self.bus.clear()
        self.bot = FakeBot(self.manager)
        self.manager.set_bot(self.bot)

    def tearDown(self):
        self.manager._plugins.clear()
        self.manager._plugin_sources.clear()
        self.manager._mark_indexes_dirty()
        self.bus.clear()

    def test_longest_complete_command_prefix_wins(self):
        plugin = CommandPlugin(self.bot)
        calls = []
        plugin.register_command(
            "qtine", lambda ctx, args: calls.append(("root", args))
        )
        plugin.register_command(
            "qtine reload", lambda ctx, args: calls.append(("reload", args))
        )
        self.manager.load_builtin(plugin)

        _, handler, args = self.manager.find_command_handler(
            "qtine reload demo"
        )
        self.assertIsNotNone(handler)
        self.assertEqual(args, ["demo"])
        handler(None, args)
        self.assertEqual(calls, [("reload", ["demo"])])

    def test_base_decorators_are_registered(self):
        plugin = DecoratedPlugin(self.bot)
        self.manager._register(plugin)

        found, handler, args = self.manager.find_command_handler("d one two")
        self.assertIs(found, plugin)
        self.assertEqual(args, ["one", "two"])
        self.assertEqual(handler(None, args), args)

        found, handler, match = self.manager.find_regex_handler("decorated value")
        self.assertIs(found, plugin)
        self.assertEqual(handler(None, match), "value")

        found, handler = self.manager.find_keyword_handler("has decorated-keyword")
        self.assertIs(found, plugin)
        self.assertEqual(handler(None), "keyword")

        self.bus.publish("decorated.test", 42)
        self.assertEqual(plugin.event_data, 42)
        self.assertIn("decorated.test", self.bus.events)
        self.assertTrue(self.manager.unload(plugin.name))
        self.assertNotIn("decorated.test", self.bus.events)

    def test_sdk_listener_dispatch_and_disable(self):
        plugin = SdkDispatchPlugin(self.bot)
        self.manager._register(plugin)
        message = Message(content="hello")

        self.manager.dispatch_message_listeners(message)
        self.assertEqual(plugin.listener_texts, ["hello"])

        self.manager.disable(plugin.name)
        self.manager.dispatch_message_listeners(Message(content="ignored"))
        self.assertEqual(plugin.listener_texts, ["hello"])

    def test_event_subscription_is_removed_on_unload(self):
        plugin = SdkDispatchPlugin(self.bot)
        self.manager._register(plugin)
        self.bus.publish("dispatch.test", 1)
        self.assertEqual(plugin.event_values, [1])
        self.assertIn("dispatch.test", self.bus.events)

        self.assertTrue(self.manager.unload(plugin.name))
        self.assertNotIn("dispatch.test", self.bus.events)
        self.bus.publish("dispatch.test", 2)
        self.assertEqual(plugin.event_values, [1])

    def test_concurrent_unload_cleans_plugin_once(self):
        plugin = LifecyclePlugin(self.bot)
        self.manager._register(plugin)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda _: self.manager.unload(plugin.name),
                    range(8),
                )
            )

        self.assertEqual(sum(results), 1)
        self.assertEqual(plugin.cleanup_count, 1)
        self.assertIsNone(self.manager.get(plugin.name))

    def test_plugin_type_error_is_not_signature_fallback(self):
        plugin = TypeErrorPlugin(self.bot)
        command_handler = plugin.get_all_command_handlers()[0][3]
        regex_handler = plugin.get_all_regex_handlers()[0][1]

        with self.assertRaisesRegex(TypeError, "plugin body error"):
            command_handler(None, [])
        with self.assertRaisesRegex(TypeError, "regex body error"):
            regex_handler(None, None)

    def test_concurrent_index_reads_are_stable(self):
        plugin = CommandPlugin(self.bot)
        plugin.register_command("ping", lambda ctx, args: None)
        self.manager.load_builtin(plugin)
        failures = []

        def find():
            try:
                for _ in range(200):
                    found, _, args = self.manager.find_command_handler(
                        "ping x"
                    )
                    if found is not plugin or args != ["x"]:
                        failures.append((found, args))
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=find) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
