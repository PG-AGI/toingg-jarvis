import unittest

from pipecat_gemini_tools import (
    LocalFunctionCallResultFrame,
    build_tools_schema,
    call_launcher_tool,
    extract_function_call,
    handle_function_call_params,
    handle_function_call_frame,
    register_launcher_tools,
)


class DummyFunctionCallFrame:
    function_name = "open_browser"
    tool_call_id = "call-123"
    arguments = {"url": "example.com", "label": "Example"}


class DummyFunctionCallParams:
    function_name = "close_tabs"
    arguments = {"auto": True}

    def __init__(self):
        self.results = []

    async def result_callback(self, result):
        self.results.append(result)


class DummyFunctionCallParamsWithoutName:
    arguments = {"url": "example.com"}

    def __init__(self):
        self.results = []

    async def result_callback(self, result):
        self.results.append(result)


class FakeLLMService:
    def __init__(self):
        self.functions = {}

    def register_function(self, name, handler, **kwargs):
        self.functions[name] = (handler, kwargs)


class PipecatGeminiToolBridgeTest(unittest.IsolatedAsyncioTestCase):
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

    def test_tools_schema_falls_back_without_pipecat_dependency(self):
        schema = build_tools_schema()

        self.assertIsInstance(schema, list)
        self.assertIn("open_browser", [tool["name"] for tool in schema])

    def test_registers_launcher_tools_with_pipecat_llm_service(self):
        llm = FakeLLMService()

        registered = register_launcher_tools(llm)

        self.assertIn("open_browser", registered)
        self.assertIn("playwright_actions", registered)
        self.assertEqual(len(registered), 5)
        self.assertTrue(callable(llm.functions["open_browser"][0]))
        self.assertTrue(llm.functions["open_browser"][1]["cancel_on_interruption"])

    async def test_registered_handler_uses_registered_tool_name(self):
        llm = FakeLLMService()
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200}

        register_launcher_tools(llm, http_post=fake_post)
        handler = llm.functions["open_browser"][0]
        params = DummyFunctionCallParamsWithoutName()

        await handler(params)

        self.assertEqual(calls[0][0], "http://localhost:8766/open_window")
        self.assertEqual(calls[0][1]["url"], "https://example.com")

    async def test_function_call_params_handler_calls_result_callback(self):
        params = DummyFunctionCallParams()
        calls = []

        def fake_post(url, payload):
            calls.append((url, payload))
            return {"ok": True, "status": 200}

        result = await handle_function_call_params(params, http_post=fake_post)

        self.assertTrue(result["ok"])
        self.assertEqual(params.results, [result])
        self.assertEqual(calls[0][0], "http://localhost:8766/close_tabs")
        self.assertEqual(calls[0][1]["auto"], True)


if __name__ == "__main__":
    unittest.main()
