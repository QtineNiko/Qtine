import os
import tempfile
import unittest

import yaml

from qtine.core.app import QtineApp
from qtine.core.config import Config


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.temp.name)
        with open("config.yml", "w", encoding="utf-8") as handle:
            yaml.safe_dump({
                "server": {"host": "0.0.0.0", "port": 4990, "debug": False},
                "adapters": {"onebot_v11": {"enabled": False}},
                "plugins": {"dir": "./plugins"},
                "storage": {"backend": "memory"},
                "security": {"production_mode": False},
                "logging": {"level": "ERROR", "file": ""},
            }, handle)
        Config._instance = None
        os.environ["QTINE_ADMIN_TOKEN"] = "a" * 64
        self.app = QtineApp("config.yml")
        self.client = self.app.flask_app.test_client()

    def tearDown(self):
        self.app.shutdown()
        Config._instance = None
        os.environ.pop("QTINE_ADMIN_TOKEN", None)
        os.chdir(self.previous)
        self.temp.cleanup()

    def test_health_is_public_but_management_api_is_not(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/api/status").status_code, 401)

    def test_bearer_token_authorizes_api(self):
        response = self.client.get(
            "/api/status",
            headers={"Authorization": "Bearer " + "a" * 64},
        )
        self.assertEqual(response.status_code, 200)

    def test_cross_origin_write_is_rejected(self):
        response = self.client.post(
            "/api/messages/clear",
            headers={
                "Authorization": "Bearer " + "a" * 64,
                "Origin": "https://attacker.example",
                "Host": "qtine.example",
            },
            json={},
        )
        self.assertEqual(response.status_code, 403)

    def test_only_official_github_source_is_available(self):
        headers = {"Authorization": "Bearer " + "a" * 64}
        response = self.client.get("/api/market/mirrors", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "current": "https://github.com",
            "mirrors": [
                {"name": "GitHub 官方", "url": "https://github.com"}
            ],
        })
        response = self.client.post(
            "/api/market/mirrors/set",
            headers=headers,
            json={"url": "https://example.com"},
        )
        self.assertEqual(response.status_code, 400)

    def test_security_headers_are_set(self):
        response = self.client.get("/health")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
