import asyncio
import base64
import json
import struct
import unittest

from pipecat_gemini import JarvisWebSocketBridge, LauncherToolClient, handle_tool_call


class FakeFrame:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class FakeTask:
    def __init__(self):
        self.frames = []

    async def queue_frame(self, frame):
        self.frames.append(frame)


class PipecatGeminiTests(unittest.TestCase):
    def test_tool_calls_route_to_launcher_endpoints(self):
        calls = []

        def poster(url, payload):
            calls.append((url, payload))
            return {"ok": True}

        client = LauncherToolClient("http://launcher", poster=poster)

        result = asyncio.run(
            handle_tool_call(
                "run_playwright",
                {"action": "click", "params": {"selector": "#go"}},
                "call-1",
                client=client,
            )
        )

        self.assertEqual(result["tool_call_id"], "call-1")
        self.assertEqual(
            calls[0],
            (
                "http://launcher/playwright_action",
                {"action": "click", "params": {"selector": "#go"}},
            ),
        )

    def test_open_file_uses_native_file_endpoint_action(self):
        calls = []
        client = LauncherToolClient(
            "http://launcher",
            poster=lambda url, payload: calls.append((url, payload)) or {"ok": True},
        )

        asyncio.run(handle_tool_call("open_file", {"path": "/tmp/report.txt"}, client=client))

        self.assertEqual(
            calls[0],
            (
                "http://launcher/file_action",
                {"action": "open_file", "path": "/tmp/report.txt"},
            ),
        )

    def test_media_messages_are_forwarded_as_audio_frames(self):
        samples = struct.pack("<ff", 0.5, -0.5)
        payload = base64.b64encode(samples).decode("ascii")
        task = FakeTask()
        bridge = JarvisWebSocketBridge(task, audio_frame_class=FakeFrame)

        frame = asyncio.run(
            bridge.handle_message(json.dumps({"event": "media", "media": {"payload": payload}}))
        )

        self.assertIs(frame, task.frames[0])
        self.assertEqual(frame.kwargs["sample_rate"], 16000)
        self.assertEqual(frame.kwargs["num_channels"], 1)
        self.assertEqual(len(frame.kwargs["audio"]), 4)


if __name__ == "__main__":
    unittest.main()
