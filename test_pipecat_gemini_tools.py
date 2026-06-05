import unittest

from pipecat_gemini_tools import (
    LocalFunctionCallResultFrame,
    call_launcher_tool,
    extract_function_call,
    handle_function_call_frame,
)


class DummyFunctionCallFrame:
    function_name = "open_browser"
    tool_call_id = "call-123"
    arguments = {"url": "example.com", "label": "Example"}


class PipecatGeminiToolBridgeTest(unittest.TestCase):
    def test_extracts_function_call_frame_fields(self):
        call = extract_function_call(DummyFunctionCallFrame())

        self.assertEqual(call.name, "open_browser")
        self.assertEqual(call.tool_call_id, "call-123")
        self.assertEqual(call.arguments["url"], "example.com")

    def test_open_browser_maps_to_launcher_open_window_endpoint(self):
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200}

        result = call_launcher_tool(
            "open_browser",
            {"url": "example.com"},
            launcher_url="http://localhost:8766",
            http_post=fake_post,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0][0], "http://localhost:8766/open_window")
        self.assertEqual(calls[0][1]["url"], "https://example.com")

    def test_playwright_actions_map_to_batch_endpoint(self):
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200, "data": {"ok": True}}

        call_launcher_tool(
            "playwright_actions",
            {"actions": [{"action": "navigate", "url": "https://example.com"}]},
            http_post=fake_post,
        )

        self.assertEqual(calls[0][0], "http://localhost:8766/playwright_actions")
        self.assertEqual(calls[0][1]["actions"][0]["action"], "navigate")

    def test_frame_handler_returns_function_result_frame_compatible_object(self):
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200, "data": {"ok": True}}

        result = handle_function_call_frame(DummyFunctionCallFrame(), http_post=fake_post)

        self.assertIsInstance(result, LocalFunctionCallResultFrame)
        self.assertEqual(result.function_name, "open_browser")
        self.assertEqual(result.tool_call_id, "call-123")
        self.assertTrue(result.result["ok"])


if __name__ == "__main__":
    unittest.main()
