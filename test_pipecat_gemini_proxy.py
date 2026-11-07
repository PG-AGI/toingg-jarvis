import base64
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from pipecat_gemini_proxy import (
    DEFAULT_WS_PATH,
    LauncherToolFrameProcessor,
    PipecatGeminiConfig,
    deserialize_jarvis_ws_message,
    effective_websocket_url,
    float32_b64_to_pcm16,
    is_function_call_frame,
    load_pipecat_config,
    pcm16_to_float32_b64,
    pipecat_enabled,
    resolve_gemini_api_key,
    selected_backend,
    serialize_jarvis_ws_frame,
)
from pipecat_gemini_tools import LocalFunctionCallResultFrame


class DummyInputAudioRawFrame:
    def __init__(self, audio: bytes, sample_rate: int, num_channels: int):
        self.audio = audio
        self.sample_rate = sample_rate
        self.num_channels = num_channels


class DummyInputTextRawFrame:
    def __init__(self, text: str):
        self.text = text


class DummyInterruptionFrame:
    pass


class OutputAudioRawFrame:
    def __init__(self, audio: bytes, sample_rate: int = 24000):
        self.audio = audio
        self.sample_rate = sample_rate


class TranscriptionFrame:
    def __init__(self, text: str):
        self.text = text


class TextFrame:
    def __init__(self, text: str):
        self.text = text


class FunctionCallFrame:
    def __init__(self, function_name: str, arguments: dict, tool_call_id: str = "call-1"):
        self.function_name = function_name
        self.arguments = arguments
        self.tool_call_id = tool_call_id


class PipecatGeminiProxyTests(unittest.IsolatedAsyncioTestCase):
    def test_default_backend_is_toingg(self):
        self.assertEqual(selected_backend({}), "toingg")
        self.assertEqual(selected_backend({"BACKEND": "unknown"}), "toingg")
        self.assertEqual(
            effective_websocket_url({"WS_URL": "wss://example.com/ws"}),
            "wss://example.com/ws",
        )

    def test_pipecat_url_defaults_and_overrides(self):
        cfg = {"BACKEND": "pipecat_gemini"}
        self.assertEqual(effective_websocket_url(cfg), f"ws://localhost:8767{DEFAULT_WS_PATH}")
        custom_cfg = {"BACKEND": "pipecat_gemini", "PIPECAT_WS_URL": "ws://127.0.0.1:9000/live"}
        self.assertEqual(effective_websocket_url(custom_cfg), "ws://127.0.0.1:9000/live")

    def test_load_pipecat_config_from_config_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "BACKEND": "pipecat_gemini",
                        "PIPECAT_PORT": 9001,
                        "GEMINI_API_KEY": "test-gemini-key-123",
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(pipecat_enabled(path))
            cfg = load_pipecat_config(path)
            self.assertEqual(cfg.port, 9001)
            self.assertEqual(cfg.api_key, "test-gemini-key-123")

    def test_resolve_gemini_api_key_ignores_placeholder(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                resolve_gemini_api_key({"GEMINI_API_KEY": "your-gemini-api-key-here"}),
                "",
            )
            self.assertEqual(
                resolve_gemini_api_key({"GEMINI_API_KEY": "real-key-abc"}),
                "real-key-abc",
            )

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

    def test_deserialize_media_text_and_interruption_messages(self):
        cfg = PipecatGeminiConfig(input_sample_rate=8000)
        raw_f32 = struct.pack("<ff", 0.5, -0.5)
        b64 = base64.b64encode(raw_f32).decode("ascii")

        audio_frame = deserialize_jarvis_ws_message(
            json.dumps({"event": "media", "media": {"payload": b64}}),
            cfg,
            audio_frame_cls=DummyInputAudioRawFrame,
        )
        self.assertIsInstance(audio_frame, DummyInputAudioRawFrame)
        self.assertEqual(audio_frame.sample_rate, 8000)
        self.assertEqual(audio_frame.num_channels, 1)
        self.assertEqual(len(audio_frame.audio), 4)

        text_frame = deserialize_jarvis_ws_message(
            json.dumps({"event": "text", "text": "open github.com"}),
            cfg,
            text_frame_cls=DummyInputTextRawFrame,
        )
        self.assertIsInstance(text_frame, DummyInputTextRawFrame)
        self.assertEqual(text_frame.text, "open github.com")

        stop_frame = deserialize_jarvis_ws_message(
            json.dumps({"event": "stop"}),
            cfg,
            interruption_frame_cls=DummyInterruptionFrame,
        )
        self.assertIsInstance(stop_frame, DummyInterruptionFrame)

    def test_serialize_output_audio_transcription_and_text_frames(self):
        pcm = struct.pack("<hh", 0, 16384)
        out_audio = serialize_jarvis_ws_frame(OutputAudioRawFrame(pcm, sample_rate=24000))
        parsed_audio = json.loads(out_audio)
        self.assertEqual(parsed_audio["event"], "media")
        self.assertEqual(parsed_audio["media"]["sampleRate"], 24000)
        self.assertTrue(parsed_audio["media"]["payload"])

        out_tx = serialize_jarvis_ws_frame(TranscriptionFrame("open example.com"))
        self.assertEqual(
            json.loads(out_tx),
            {"event": "transcription", "role": "user", "content": "open example.com"},
        )

        out_text = serialize_jarvis_ws_frame(TextFrame("Opening example.com now."))
        self.assertEqual(
            json.loads(out_text),
            {"event": "aiTextStream", "text_chunk": "Opening example.com now."},
        )

    async def test_launcher_tool_frame_processor_routes_all_required_tools(self):
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200, "data": {"executed": True}}

        processor = LauncherToolFrameProcessor(
            launcher_url="http://localhost:8766",
            http_post=fake_post,
        )

        tool_frames = [
            FunctionCallFrame("open_browser", {"url": "example.com"}, "call-1"),
            FunctionCallFrame("close_tabs", {"auto": True}, "call-2"),
            FunctionCallFrame("open_file", {"path": "/tmp/demo.txt"}, "call-3"),
            FunctionCallFrame(
                "run_playwright",
                {"action": "navigate", "url": "https://example.com"},
                "call-4",
            ),
            FunctionCallFrame(
                "playwright_actions",
                {"actions": [{"action": "click", "selector": "#submit"}]},
                "call-5",
            ),
        ]

        for frame in tool_frames:
            self.assertTrue(is_function_call_frame(frame))
            res_frame = await processor.process_frame(frame)
            self.assertIsInstance(res_frame, LocalFunctionCallResultFrame)
            self.assertTrue(res_frame.result["ok"])

        self.assertEqual(len(processor.emitted_frames), 5)
        self.assertEqual(
            [c[0] for c in calls],
            [
                "http://localhost:8766/open_window",
                "http://localhost:8766/close_tabs",
                "http://localhost:8766/file_action",
                "http://localhost:8766/playwright_action",
                "http://localhost:8766/playwright_actions",
            ],
        )
        self.assertEqual(calls[0][1]["url"], "https://example.com")
        self.assertEqual(calls[1][1], {"auto": True})
        self.assertEqual(calls[2][1], {"action": "open_file", "path": "/tmp/demo.txt"})
        self.assertEqual(calls[3][1]["action"], "navigate")
        self.assertEqual(calls[4][1]["actions"][0]["action"], "click")


if __name__ == "__main__":
    unittest.main()
