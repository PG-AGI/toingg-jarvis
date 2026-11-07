"""Unit tests for the JARVIS Pipecat/Gemini tool bridge and backend selector."""

import unittest

from pipecat_gemini_tools import (
    DEFAULT_BACKEND,
    DEFAULT_PIPECAT_WS_URL,
    LocalFunctionCallResultFrame,
    PIPECAT_GEMINI_BACKEND,
    build_tools_schema,
    call_launcher_tool,
    extract_function_call,
    handle_function_call_frame,
    handle_function_call_params,
    is_pipecat_gemini_backend,
    register_launcher_tools,
    resolve_backend_mode,
    resolve_effective_config,
)


class DummyFunctionCallFrame:
    """Simulated Pipecat FunctionCallFrame for browser window open action."""

    function_name = "open_browser"
    tool_call_id = "call-123"
    arguments = {"url": "example.com", "label": "Example"}


class DummyFunctionCallParams:
    """Simulated Pipecat FunctionCallParams with an async result callback."""

    function_name = "close_tabs"
    arguments = {"auto": True}

    def __init__(self) -> None:
        self.results: list[dict] = []

    async def result_callback(self, result: dict) -> None:
        self.results.append(result)


class DummyFunctionCallParamsWithoutName:
    """Simulated FunctionCallParams omitting an explicit function_name attribute."""

    arguments = {"url": "example.com"}

    def __init__(self) -> None:
        self.results: list[dict] = []

    async def result_callback(self, result: dict) -> None:
        self.results.append(result)


class FakeLLMService:
    """Test double mimicking Pipecat LLMService.register_function."""

    def __init__(self) -> None:
        self.functions: dict = {}

    def register_function(self, name: str, handler: object, **kwargs: object) -> None:
        self.functions[name] = (handler, kwargs)


class PipecatGeminiToolBridgeTest(unittest.IsolatedAsyncioTestCase):
    """Verify tool mapping, frame handling, and backend configuration switching."""

    def _invoke_tool(self, tool_name: str, arguments: dict) -> tuple[dict, list[tuple[str, dict]]]:
        calls: list[tuple[str, dict]] = []

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"ok": True, "status": 200, "data": {"ok": True}}

        result = call_launcher_tool(
            tool_name,
            arguments,
            launcher_url="http://localhost:8766",
            http_post=fake_post,
        )
        return result, calls

    def test_extracts_function_call_frame_fields(self) -> None:
        call = extract_function_call(DummyFunctionCallFrame())

        self.assertEqual(call.name, "open_browser")
        self.assertEqual(call.tool_call_id, "call-123")
        self.assertEqual(call.arguments["url"], "example.com")

    def test_open_browser_maps_to_launcher_open_window_endpoint(self) -> None:
        result, calls = self._invoke_tool("open_browser", {"url": "example.com"})

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0][0], "http://localhost:8766/open_window")
        self.assertEqual(calls[0][1]["url"], "https://example.com")

    def test_playwright_and_file_tools_map_to_launcher_endpoints(self) -> None:
        _, pw_single = self._invoke_tool("run_playwright", {"action": "click", "selector": "#btn"})
        self.assertEqual(pw_single[0][0], "http://localhost:8766/playwright_action")
        self.assertEqual(pw_single[0][1]["action"], "click")

        _, pw_batch = self._invoke_tool(
            "playwright_actions",
            {"actions": [{"action": "navigate", "url": "https://example.com"}]},
        )
        self.assertEqual(pw_batch[0][0], "http://localhost:8766/playwright_actions")
        self.assertEqual(pw_batch[0][1]["actions"][0]["action"], "navigate")

        _, file_call = self._invoke_tool("open_file", {"path": "/tmp/notes.txt"})
        self.assertEqual(file_call[0][0], "http://localhost:8766/file_action")
        self.assertEqual(file_call[0][1], {"action": "open_file", "path": "/tmp/notes.txt"})

    def test_frame_handler_returns_function_result_frame_compatible_object(self) -> None:
        result = handle_function_call_frame(
            DummyFunctionCallFrame(),
            http_post=lambda _u, _p: {"ok": True, "status": 200, "data": {"ok": True}},
        )

        self.assertIsInstance(result, LocalFunctionCallResultFrame)
        self.assertEqual(result.function_name, "open_browser")
        self.assertEqual(result.tool_call_id, "call-123")
        self.assertTrue(result.result["ok"])

    def test_tools_schema_falls_back_without_pipecat_dependency(self) -> None:
        schema = build_tools_schema()

        self.assertIsInstance(schema, list)
        self.assertIn("open_browser", [tool["name"] for tool in schema])

    def test_registers_launcher_tools_with_pipecat_llm_service(self) -> None:
        llm = FakeLLMService()

        registered = register_launcher_tools(llm)

        self.assertIn("open_browser", registered)
        self.assertIn("playwright_actions", registered)
        self.assertEqual(len(registered), 5)
        self.assertTrue(callable(llm.functions["open_browser"][0]))
        self.assertTrue(llm.functions["open_browser"][1]["cancel_on_interruption"])

    async def test_registered_handler_uses_registered_tool_name(self) -> None:
        llm = FakeLLMService()
        calls: list[tuple[str, dict]] = []

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"ok": True, "status": 200}

        register_launcher_tools(llm, http_post=fake_post)
        handler = llm.functions["open_browser"][0]
        params = DummyFunctionCallParamsWithoutName()

        await handler(params)

        self.assertEqual(calls[0][0], "http://localhost:8766/open_window")
        self.assertEqual(calls[0][1]["url"], "https://example.com")

    async def test_function_call_params_handler_calls_result_callback(self) -> None:
        params = DummyFunctionCallParams()
        calls: list[tuple[str, dict]] = []

        def fake_post(url: str, payload: dict) -> dict:
            calls.append((url, payload))
            return {"ok": True, "status": 200}

        result = await handle_function_call_params(params, http_post=fake_post)

        self.assertTrue(result["ok"])
        self.assertEqual(params.results, [result])
        self.assertEqual(calls[0][0], "http://localhost:8766/close_tabs")
        self.assertEqual(calls[0][1]["auto"], True)

    def test_backend_switching_preserves_toingg_default_and_activates_pipecat_gemini(self) -> None:
        default_cfg = resolve_effective_config({"WS_URL": "wss://prepodapi.toingg.com/ws", "TOKEN": "tok"})
        self.assertEqual(default_cfg["BACKEND"], DEFAULT_BACKEND)
        self.assertFalse(is_pipecat_gemini_backend(default_cfg))
        self.assertEqual(default_cfg["WS_URL"], "wss://prepodapi.toingg.com/ws")

        gemini_cfg = resolve_effective_config({"BACKEND": "pipecat_gemini", "GEMINI_API_KEY": "gem-key-123"})
        self.assertEqual(resolve_backend_mode(gemini_cfg), PIPECAT_GEMINI_BACKEND)
        self.assertTrue(is_pipecat_gemini_backend(gemini_cfg))
        self.assertEqual(gemini_cfg["WS_URL"], DEFAULT_PIPECAT_WS_URL)
        self.assertEqual(gemini_cfg["TOKEN"], "gem-key-123")


if __name__ == "__main__":
    unittest.main()
