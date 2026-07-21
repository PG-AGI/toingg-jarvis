"""
Pipecat/Gemini tool-call bridge for the local JARVIS launcher.

The bridge is intentionally dependency-light: it can be imported when Pipecat is
not installed, but it will return a real FunctionCallResultFrame when Pipecat is
available.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError


DEFAULT_LAUNCHER_URL = "http://localhost:8766"


TOOL_DEFINITIONS = [
    {
        "name": "open_browser",
        "description": "Open a URL in a managed browser window.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open"},
                "label": {"type": "string", "description": "Optional window label"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "close_tabs",
        "description": "Close JARVIS-managed browser tabs.",
        "parameters": {
            "type": "object",
            "properties": {
                "auto": {"type": "boolean", "description": "Only close auto-managed tabs"},
            },
        },
    },
    {
        "name": "open_file",
        "description": "Open a local file through the launcher file-action endpoint.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_playwright",
        "description": "Run one Playwright browser automation action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "selector": {"type": "string"},
                "value": {"type": "string"},
                "url": {"type": "string"},
                "timeout": {"type": "integer"},
                "token": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "playwright_actions",
        "description": "Run several Playwright browser automation actions in order.",
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "required": ["actions"],
        },
    },
]


@dataclass
class FunctionCall:
    name: str
    arguments: dict[str, Any]
    tool_call_id: str = ""


@dataclass
class LocalFunctionCallResultFrame:
    function_name: str
    tool_call_id: str
    arguments: dict[str, Any]
    result: dict[str, Any]


def _first_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _coerce_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("function call arguments must decode to a JSON object")
        return parsed
    try:
        return dict(raw)
    except Exception as exc:
        raise ValueError("function call arguments must be a mapping") from exc


def extract_function_call(frame: Any) -> FunctionCall:
    name = _first_attr(frame, "function_name", "name", "tool_name")
    if not name:
        raise ValueError("FunctionCallFrame is missing a function name")

    arguments = _coerce_arguments(
        _first_attr(frame, "arguments", "args", "function_args")
    )
    tool_call_id = _first_attr(frame, "tool_call_id", "id", "call_id") or ""
    return FunctionCall(str(name), arguments, str(tool_call_id))


def _normalize_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("open_browser requires a non-empty url")
    clean = url.strip()
    if "://" not in clean:
        clean = f"https://{clean}"
    return clean


def post_json(url: str, payload: dict[str, Any], timeout: float = 10) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"text": body}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "data": parsed}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"text": body}
        return {"ok": False, "status": exc.code, "data": parsed}
    except URLError as exc:
        return {"ok": False, "error": str(exc.reason)}


def call_launcher_tool(
    name: str,
    arguments: dict[str, Any],
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> dict[str, Any]:
    base = launcher_url.rstrip("/")

    if name == "open_browser":
        payload = {**arguments, "url": _normalize_url(str(arguments.get("url", "")))}
        return http_post(f"{base}/open_window", payload)

    if name == "close_tabs":
        return http_post(f"{base}/close_tabs", {"auto": bool(arguments.get("auto", False))})

    if name == "open_file":
        path = arguments.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("open_file requires path")
        return http_post(f"{base}/file_action", {"action": "open_file", "path": path})

    if name == "run_playwright":
        if not arguments.get("action"):
            raise ValueError("run_playwright requires action")
        return http_post(f"{base}/playwright_action", arguments)

    if name == "playwright_actions":
        actions = arguments.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("playwright_actions requires a non-empty actions list")
        return http_post(f"{base}/playwright_actions", {"actions": actions})

    raise ValueError(f"unsupported Gemini tool: {name}")


def build_function_result_frame(call: FunctionCall, result: dict[str, Any]) -> Any:
    try:
        from pipecat.frames.frames import FunctionCallResultFrame
    except Exception:
        return LocalFunctionCallResultFrame(
            function_name=call.name,
            tool_call_id=call.tool_call_id,
            arguments=call.arguments,
            result=result,
        )

    try:
        return FunctionCallResultFrame(
            function_name=call.name,
            tool_call_id=call.tool_call_id,
            arguments=call.arguments,
            result=result,
        )
    except TypeError:
        return FunctionCallResultFrame(
            call.name,
            call.tool_call_id,
            call.arguments,
            result,
        )


def handle_function_call_frame(
    frame: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> Any:
    call = extract_function_call(frame)
    result = call_launcher_tool(
        call.name,
        call.arguments,
        launcher_url=launcher_url,
        http_post=http_post,
    )
    return build_function_result_frame(call, result)


def build_tools_schema() -> Any:
    """Return Pipecat ToolsSchema when Pipecat is installed.

    The fallback keeps the module importable in the default Toingg path, where
    Pipecat is optional and may not be installed.
    """

    try:
        from pipecat.adapters.schemas.function_schema import FunctionSchema
        from pipecat.adapters.schemas.tools_schema import ToolsSchema
    except Exception:
        return TOOL_DEFINITIONS

    functions = [
        FunctionSchema(
            name=tool["name"],
            description=tool["description"],
            properties=tool.get("parameters", {}).get("properties", {}),
            required=tool.get("parameters", {}).get("required", []),
        )
        for tool in TOOL_DEFINITIONS
    ]
    return ToolsSchema(standard_tools=functions)


async def handle_function_call_params(
    params: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    function_name: str | None = None,
) -> dict[str, Any]:
    """Pipecat FunctionCallParams handler for the launcher-backed tools."""

    name = function_name or _first_attr(params, "function_name", "name")
    if not name:
        raise ValueError("FunctionCallParams is missing function_name")
    arguments = _coerce_arguments(_first_attr(params, "arguments", "args"))

    result = await asyncio.to_thread(
        call_launcher_tool,
        str(name),
        arguments,
        launcher_url,
        http_post,
    )

    callback = _first_attr(params, "result_callback")
    if callback:
        maybe_awaitable = callback(result)
        if hasattr(maybe_awaitable, "__await__"):
            await maybe_awaitable

    return result


def register_launcher_tools(
    llm_service: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    cancel_on_interruption: bool = True,
) -> list[str]:
    """Register all JARVIS launcher tools on a Pipecat LLM service."""

    if not hasattr(llm_service, "register_function"):
        raise TypeError("llm_service must provide register_function(name, handler, ...)")

    registered = []
    for tool in TOOL_DEFINITIONS:
        name = str(tool["name"])

        async def handler(params: Any, tool_name: str = name) -> dict[str, Any]:
            if not _first_attr(params, "function_name", "name"):
                try:
                    setattr(params, "function_name", tool_name)
                except Exception:
                    pass
            return await handle_function_call_params(
                params,
                launcher_url=launcher_url,
                http_post=http_post,
                function_name=tool_name,
            )

        llm_service.register_function(
            name,
            handler,
            cancel_on_interruption=cancel_on_interruption,
        )
        registered.append(name)
    return registered
