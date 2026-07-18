import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

try:
    from qtine.integrations.napcat import EmbeddedNapCat
except ModuleNotFoundError:
    EmbeddedNapCat = None


@unittest.skipUnless(EmbeddedNapCat, "embedded NapCat is not included")
class EmbeddedNapCatTests(unittest.TestCase):
    def test_disabled_component_is_not_started(self):
        manager = EmbeddedNapCat({"enabled": False}, os.getcwd())
        self.assertFalse(manager.start())

    @patch("qtine.integrations.napcat.os.path.isfile", return_value=True)
    @patch("qtine.integrations.napcat.subprocess.Popen")
    def test_starts_bundled_runtime_from_its_working_directory(self, popen, _):
        process = MagicMock()
        process.pid = 123
        process.poll.return_value = None
        popen.return_value = process
        manager = EmbeddedNapCat({
            "enabled": True,
            "root": "vendor/napcat",
            "executable": "node.exe",
            "arguments": ["index.js"],
            "show_console": True,
        }, os.getcwd())

        self.assertTrue(manager.start())
        command = popen.call_args.args[0]
        kwargs = popen.call_args.kwargs
        self.assertTrue(command[0].endswith(os.path.join("vendor", "napcat", "node.exe")))
        self.assertEqual(command[1:], ["index.js"])
        self.assertTrue(kwargs["cwd"].endswith(os.path.join("vendor", "napcat")))

    @patch("qtine.integrations.napcat.os.path.isfile", return_value=True)
    @patch("qtine.integrations.napcat.subprocess.Popen")
    def test_stops_only_the_process_it_started(self, popen, _):
        process = MagicMock()
        process.pid = 123
        process.poll.return_value = None
        popen.return_value = process
        manager = EmbeddedNapCat({"enabled": True}, os.getcwd())
        manager.start()
        manager.stop()
        process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
