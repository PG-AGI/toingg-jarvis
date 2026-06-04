import json
import os
import tempfile
import unittest

from backend_config import (
    BACKEND_PIPECAT_GEMINI,
    BACKEND_TOINGG,
    build_web_config,
    load_runtime_config,
    requires_toingg_token,
    selected_backend,
    validate_pipecat_gemini_config,
)
from pipecat_gemini_proxy import build_startup_payload


class BackendConfigTests(unittest.TestCase):
    def test_toingg_is_default_backend(self):
        config = {"WS_URL": "wss://example.invalid/ws", "TOKEN": "token"}

        self.assertEqual(selected_backend(config), BACKEND_TOINGG)
        self.assertTrue(requires_toingg_token(config))
        self.assertEqual(build_web_config(config)["WS_URL"], "wss://example.invalid/ws")

    def test_pipecat_backend_overrides_browser_ws_url(self):
        config = {
            "BACKEND": "pipecat_gemini",
            "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
            "PIPECAT_GEMINI_WS_URL": "ws://localhost:8767/ws",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-live-test",
        }

        self.assertEqual(selected_backend(config), BACKEND_PIPECAT_GEMINI)
        self.assertFalse(requires_toingg_token(config))
        self.assertEqual(build_web_config(config)["WS_URL"], "ws://localhost:8767/ws")
        self.assertEqual(validate_pipecat_gemini_config(config), [])

    def test_pipecat_validation_reports_missing_settings(self):
        missing = validate_pipecat_gemini_config({"BACKEND": "pipecat_gemini"})

        self.assertIn("GEMINI_API_KEY", missing)
        self.assertIn("GEMINI_MODEL", missing)

    def test_load_runtime_config_requires_json_object(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            json.dump(["not", "an", "object"], handle)
            path = handle.name
        try:
            with self.assertRaises(ValueError):
                load_runtime_config(path)
        finally:
            os.unlink(path)

    def test_proxy_health_payload_does_not_expose_secret(self):
        payload = build_startup_payload({
            "GEMINI_API_KEY": "secret",
            "GEMINI_MODEL": "gemini-live-test",
        })

        self.assertEqual(payload["backend"], "pipecat_gemini")
        self.assertEqual(payload["model"], "gemini-live-test")
        self.assertNotIn("secret", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
