import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pipecat_gemini_proxy import (
    DEFAULT_WS_PATH,
    PipecatGeminiConfig,
    effective_websocket_url,
    float32_b64_to_pcm16,
    load_pipecat_config,
    pcm16_to_float32_b64,
    pipecat_enabled,
    selected_backend,
)


class PipecatGeminiProxyTests(unittest.TestCase):
    def test_default_backend_is_toingg(self):
        self.assertEqual(selected_backend({}), "toingg")
        self.assertEqual(effective_websocket_url({"WS_URL": "wss://example"}), "wss://example")

    def test_pipecat_url_defaults(self):
        cfg = {"BACKEND": "pipecat_gemini"}
        self.assertEqual(effective_websocket_url(cfg), f"ws://localhost:8767{DEFAULT_WS_PATH}")

    def test_load_pipecat_config_from_config_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps({"BACKEND": "pipecat_gemini", "PIPECAT_PORT": 9001}))
            self.assertTrue(pipecat_enabled(path))
            self.assertEqual(load_pipecat_config(path).port, 9001)

    def test_float32_to_pcm16_clips(self):
        raw = struct.pack("<fff", -2.0, 0.0, 2.0)
        payload = base64.b64encode(raw).decode("ascii")
        pcm = float32_b64_to_pcm16(payload)
        self.assertEqual(struct.unpack("<hhh", pcm), (-32767, 0, 32767))

    def test_pcm16_to_float32_round_trip_shape(self):
        payload = pcm16_to_float32_b64(struct.pack("<hh", -32768, 32767))
        raw = base64.b64decode(payload)
        self.assertEqual(len(raw), 8)
        left, right = struct.unpack("<ff", raw)
        self.assertLessEqual(left, -0.99)
        self.assertGreaterEqual(right, 0.99)

    def test_config_ws_url_property(self):
        self.assertEqual(PipecatGeminiConfig(host="127.0.0.1", port=9999).ws_url, "ws://127.0.0.1:9999/ws")


if __name__ == "__main__":
    unittest.main()
