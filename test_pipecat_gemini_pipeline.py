"""Unit tests for the real-time Pipecat and Gemini Live voice and multimodal pipeline."""

import base64
import struct
import unittest

from pipecat_gemini_pipeline import (
    GeminiLiveConfig,
    JarvisGeminiBridgeProcessor,
    LocalAudioInputFrame,
    LocalAudioOutputFrame,
    LocalImageInputFrame,
    LocalInterruptionFrame,
    build_gemini_live_pipeline,
    create_gemini_live_service,
    float32_b64_to_pcm16,
    pcm16_to_float32_b64,
)
from pipecat_gemini_tools import LocalFunctionCallResultFrame


class FakeGeminiLiveLLMService:
    """Offline test double for Pipecat's GeminiMultimodalLiveLLMService."""

    def __init__(self, **kwargs: object) -> None:
        self.api_key = kwargs.get("api_key", "")
        self.model = kwargs.get("model", "")
        self.voice_id = kwargs.get("voice_id", "")
        self.system_instruction = kwargs.get("system_instruction", "")
        self.tools = kwargs.get("tools")
        self.registered_functions: dict[str, tuple[object, dict]] = {}

    def register_function(self, name: str, handler: object, **kwargs: object) -> None:
        self.registered_functions[name] = (handler, kwargs)


class FakeTransport:
    """Offline test double for Pipecat WebSocket transport input/output stages."""

    def input(self) -> str:
        return "transport_input"

    def output(self) -> str:
        return "transport_output"


class DummyPlaywrightFunctionCallFrame:
    """Simulated Gemini FunctionCallFrame invoking run_playwright on localhost:8766."""

    function_name = "run_playwright"
    tool_call_id = "pw-call-42"
    arguments = {"action": "navigate", "url": "https://example.com"}


class DummyTextFrame:
    """Simulated Gemini text streaming frame."""

    def __init__(self, text: str) -> None:
        self.text = text


class PipecatGeminiPipelineTest(unittest.IsolatedAsyncioTestCase):
    """Validate audio conversion, multimodal frames, interruption, and tool-call round-trips."""

    def _make_config(self) -> GeminiLiveConfig:
        return GeminiLiveConfig.from_config(
            {
                "BACKEND": "pipecat_gemini",
                "GEMINI_API_KEY": "test-gemini-api-key",
                "GEMINI_MODEL": "models/gemini-2.0-flash-live-001",
                "GEMINI_VOICE": "Kore",
            }
        )

    def test_audio_float32_to_pcm16_round_trip_preserves_waveform(self) -> None:
        samples = [0.0, 0.5, -0.5, 0.95, -0.95]
        raw_f32 = struct.pack(f"<{len(samples)}f", *samples)
        b64_in = base64.b64encode(raw_f32).decode("ascii")

        pcm16 = float32_b64_to_pcm16(b64_in)
        self.assertEqual(len(pcm16), len(samples) * 2)

        b64_out = pcm16_to_float32_b64(pcm16)
        decoded_f32 = struct.unpack(f"<{len(samples)}f", base64.b64decode(b64_out))
        for original, restored in zip(samples, decoded_f32):
            self.assertAlmostEqual(original, restored, places=2)

    def test_browser_media_message_forwards_audio_frame_to_gemini(self) -> None:
        bridge = JarvisGeminiBridgeProcessor(self._make_config())
        raw_f32 = struct.pack("<4f", 0.25, -0.25, 0.5, -0.5)
        payload = base64.b64encode(raw_f32).decode("ascii")

        frame = bridge.handle_browser_message({"event": "media", "media": {"payload": payload}})

        self.assertIsInstance(frame, LocalAudioInputFrame)
        self.assertEqual(frame.sample_rate, 8000)
        self.assertEqual(len(frame.audio), 8)

    def test_browser_image_message_forwards_multimodal_frame(self) -> None:
        bridge = JarvisGeminiBridgeProcessor(self._make_config())
        image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
        b64_img = base64.b64encode(image_bytes).decode("ascii")

        frame = bridge.handle_browser_message(
            {
                "event": "image",
                "image": {"payload": b64_img, "size": [1280, 720], "format": "jpeg"},
            }
        )

        self.assertIsInstance(frame, LocalImageInputFrame)
        self.assertEqual(frame.image, image_bytes)
        self.assertEqual(frame.size, (1280, 720))
        self.assertEqual(frame.format, "JPEG")

    def test_interruption_frame_emits_clear_audio_browser_event(self) -> None:
        bridge = JarvisGeminiBridgeProcessor(self._make_config())
        interruption = bridge.handle_browser_message({"event": "interrupt"})
        self.assertIsInstance(interruption, LocalInterruptionFrame)

    async def test_pipeline_catches_function_call_frame_and_pushes_result_frame(self) -> None:
        calls: list[tuple[str, dict]] = []
        pushed_frames: list[object] = []

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"ok": True, "status": 200, "data": {"ok": True, "url": "https://example.com"}}

        async def push_frame(result_frame: object) -> None:
            pushed_frames.append(result_frame)

        bridge = JarvisGeminiBridgeProcessor(self._make_config(), http_post=fake_post)
        event = await bridge.process_pipeline_frame(
            DummyPlaywrightFunctionCallFrame(),
            push_frame=push_frame,
        )

        self.assertEqual(calls[0][0], "http://localhost:8766/playwright_action")
        self.assertEqual(calls[0][1]["action"], "navigate")
        self.assertEqual(len(pushed_frames), 1)
        self.assertIsInstance(pushed_frames[0], LocalFunctionCallResultFrame)
        self.assertEqual(event["event"], "toolResult")
        self.assertEqual(event["function_name"], "run_playwright")
        self.assertEqual(event["tool_call_id"], "pw-call-42")

    async def test_outbound_audio_and_text_frames_serialize_for_browser(self) -> None:
        bridge = JarvisGeminiBridgeProcessor(self._make_config())
        pcm = struct.pack("<2h", 16384, -16384)

        audio_ev = await bridge.process_pipeline_frame(LocalAudioOutputFrame(audio=pcm))
        text_ev = await bridge.process_pipeline_frame(DummyTextFrame("Opening browser window."))
        clear_ev = await bridge.process_pipeline_frame(LocalInterruptionFrame())

        self.assertEqual(audio_ev["event"], "media")
        self.assertTrue(audio_ev["media"]["payload"])
        self.assertEqual(text_ev, {"event": "aiTextStream", "text_chunk": "Opening browser window."})
        self.assertEqual(clear_ev, {"event": "clearAudio"})

    def test_create_service_and_build_pipeline_register_all_launcher_tools(self) -> None:
        config = self._make_config()
        service = create_gemini_live_service(config, service_cls=FakeGeminiLiveLLMService)
        bundle = build_gemini_live_pipeline(
            config,
            transport=FakeTransport(),
            llm_service=service,
        )

        self.assertEqual(service.api_key, "test-gemini-api-key")
        self.assertEqual(service.voice_id, "Kore")
        self.assertEqual(
            set(service.registered_functions.keys()),
            {"open_browser", "close_tabs", "open_file", "run_playwright", "playwright_actions"},
        )
        self.assertEqual(bundle.pipeline[0], "transport_input")
        self.assertEqual(bundle.pipeline[-1], "transport_output")


if __name__ == "__main__":
    unittest.main()
