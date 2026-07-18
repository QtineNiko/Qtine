import io
import os
import tempfile
import unittest
import zipfile

from qtine.utils.archive import safe_extract_zip, validate_package_name


class ArchiveSecurityTests(unittest.TestCase):
    def test_rejects_parent_path(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("../escape.txt", "bad")
        data.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(data) as archive:
                with self.assertRaises(ValueError):
                    safe_extract_zip(archive, directory)
            self.assertFalse(
                os.path.exists(os.path.join(os.path.dirname(directory), "escape.txt"))
            )

    def test_rejects_symlink(self):
        data = io.BytesIO()
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(info, "target")
        data.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(data) as archive:
                with self.assertRaises(ValueError):
                    safe_extract_zip(archive, directory)

    def test_validates_package_names(self):
        self.assertEqual(validate_package_name("weather-plugin_1.0"), "weather-plugin_1.0")
        for value in ("../plugin", "plugin/name", "", ".", ".."):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_package_name(value)


if __name__ == "__main__":
    unittest.main()
