"""Pipecat and Gemini Live tool-call bridge and backend selector for JARVIS.

Maps Gemini function-call declarations and runtime FunctionCallFrame events to
the local JARVIS HTTP launcher on localhost:8766 while keeping Pipecat an
optional dependency so the default Toingg voice path remains unaffected.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError


DEFAULT_LAUNCHER_URL = "http://localhost:8766"
DEFAULT_BACKEND = "toingg"
PIPECAT_GEMINI_BACKEND = "pipecat_gemini"
DEFAULT_PIPECAT_WS_URL = "ws://localhost:8767"
DEFAULT_GEMINI_MODEL = "models/gemini-2.0-flash-live-001"
DEFAULT_GEMINI_VOICE = "Puck"


TOOL_DEFINITIONS: list[dict[str, Any]] = [
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
    """Normalized representation of a Gemini tool invocation frame."""

    name: str
    arguments: dict[str, Any]
    tool_call_id: str = ""


@dataclass
class LocalFunctionCallResultFrame:
    """Fallback result frame used when Pipecat is not installed in the active environment."""

    function_name: str
    tool_call_id: str
    arguments: dict[str, Any]
    result: dict[str, Any]


def resolve_backend_mode(config: dict[str, Any] | None) -> str:
    """Determine the active voice backend, defaulting to Toingg when omitted."""
    if not isinstance(config, dict):
        return DEFAULT_BACKEND
    raw_backend = str(config.get("BACKEND") or config.get("backend") or "").strip().lower()
    if raw_backend == PIPECAT_GEMINI_BACKEND:
        return PIPECAT_GEMINI_BACKEND
    return DEFAULT_BACKEND


def is_pipecat_gemini_backend(config: dict[str, Any] | None) -> bool:
    """Check whether config.json explicitly selects the Pipecat/Gemini Live backend."""
    return resolve_backend_mode(config) == PIPECAT_GEMINI_BACKEND


def resolve_effective_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize runtime configuration while preserving Toingg defaults when Pipecat is inactive."""
    base = dict(config) if isinstance(config, dict) else {}
    backend = resolve_backend_mode(base)
    base["BACKEND"] = backend
    if backend != PIPECAT_GEMINI_BACKEND:
        return base

    # Point the browser client to the local Pipecat WebSocket proxy unless a custom URL is set.
    pipecat_ws = str(base.get("PIPECAT_WS_URL") or DEFAULT_PIPECAT_WS_URL).strip()
    base["WS_URL"] = pipecat_ws
    base.setdefault("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    base.setdefault("GEMINI_VOICE", DEFAULT_GEMINI_VOICE)
    gemini_key = str(base.get("GEMINI_API_KEY") or base.get("GOOGLE_API_KEY") or "").strip()
    if gemini_key and not base.get("TOKEN"):
        base["TOKEN"] = gemini_key
    return base


def _first_attr(obj: Any, names: tuple[str, ...]) -> Any:
    """Retrieve the first non-None attribute or dictionary key matching the candidate names."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _decode_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON string argument payload and enforce object structure."""
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("function call arguments must decode to a JSON object")
    return parsed


def _coerce_arguments(raw: Any) -> dict[str, Any]:
    """Normalize tool arguments from dict, JSON string, or key-value iterable into a dictionary."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return _decode_json_object(raw)
    try:
        return dict(raw)
    except Exception as exc:
        raise ValueError("function call arguments must be a mapping") from exc


def extract_function_call(frame: Any) -> FunctionCall:
    """Extract tool name, arguments, and call ID from a Pipecat FunctionCallFrame."""
    name = _first_attr(frame, ("function_name", "name", "tool_name"))
    if not name:
        raise ValueError("FunctionCallFrame is missing a function name")

    raw_args = _first_attr(frame, ("arguments", "args", "function_args"))
    arguments = _coerce_arguments(raw_args)
    tool_call_id = _first_attr(frame, ("tool_call_id", "id", "call_id")) or ""
    return FunctionCall(str(name), arguments, str(tool_call_id))


def _normalize_url(url: str) -> str:
    """Ensure browser URLs emitted by Gemini include an explicit scheme for Chrome slot launch."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("open_browser requires a non-empty url")
    clean = url.strip()
    if "://" not in clean:
        return f"https://{clean}"
    return clean


def _parse_json_body(body: str) -> dict[str, Any]:
    """Decode HTTP response text as JSON or wrap plain text in a dictionary."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"text": body}


def post_json(url: str, payload: dict[str, Any], timeout: float = 10) -> dict[str, Any]:
    """Dispatch a JSON POST request to the local JARVIS launcher HTTP server."""
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
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "data": _parse_json_body(body)}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "data": _parse_json_body(body)}
    except URLError as exc:
        return {"ok": False, "error": str(exc.reason)}


def _build_open_browser_request(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map open_browser tool arguments to the launcher /open_window endpoint."""
    url = _normalize_url(str(arguments.get("url", "")))
    return "/open_window", {**arguments, "url": url}


def _build_close_tabs_request(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map close_tabs tool arguments to the launcher /close_tabs endpoint."""
    return "/close_tabs", {"auto": bool(arguments.get("auto", False))}


def _build_open_file_request(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map open_file tool arguments to the validated /file_action endpoint."""
    path = arguments.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("open_file requires path")
    return "/file_action", {"action": "open_file", "path": path}


def _build_run_playwright_request(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map single-step Playwright automation calls to /playwright_action."""
    if not arguments.get("action"):
        raise ValueError("run_playwright requires action")
    return "/playwright_action", arguments


def _build_playwright_actions_request(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map multi-step Playwright automation batches to /playwright_actions."""
    actions = arguments.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("playwright_actions requires a non-empty actions list")
    return "/playwright_actions", {"actions": actions}


_TOOL_REQUEST_BUILDERS: dict[str, Callable[[dict[str, Any]], tuple[str, dict[str, Any]]]] = {
    "open_browser": _build_open_browser_request,
    "close_tabs": _build_close_tabs_request,
    "open_file": _build_open_file_request,
    "run_playwright": _build_run_playwright_request,
    "playwright_actions": _build_playwright_actions_request,
}


def call_launcher_tool(
    name: str,
    arguments: dict[str, Any],
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> dict[str, Any]:
    """Execute a Gemini tool call against the corresponding localhost:8766 launcher endpoint."""
    builder = _TOOL_REQUEST_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"unsupported Gemini tool: {name}")
    endpoint, payload = builder(arguments)
    base = launcher_url.rstrip("/")
    return http_post(f"{base}{endpoint}", payload)


def build_function_result_frame(call: FunctionCall, result: dict[str, Any]) -> Any:
    """Construct a Pipecat FunctionCallResultFrame or local fallback frame for Gemini feedback."""
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
        return FunctionCallResultFrame(call.name, call.tool_call_id, call.arguments, result)


def handle_function_call_frame(
    frame: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> Any:
    """Process an incoming FunctionCallFrame against the launcher and return a result frame."""
    call = extract_function_call(frame)
    result = call_launcher_tool(
        call.name,
        call.arguments,
        launcher_url=launcher_url,
        http_post=http_post,
    )
    return build_function_result_frame(call, result)


def build_tools_schema() -> Any:
    """Build Pipecat ToolsSchema when Pipecat is installed, or return raw tool definitions."""
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


async def _invoke_result_callback(params: Any, result: dict[str, Any]) -> None:
    """Send tool execution output to Pipecat's FunctionCallParams result_callback if present."""
    callback = _first_attr(params, ("result_callback",))
    if not callback:
        return
    maybe_awaitable = callback(result)
    if hasattr(maybe_awaitable, "__await__"):
        await maybe_awaitable


async def handle_function_call_params(
    params: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    function_name: str | None = None,
) -> dict[str, Any]:
    """Handle async Pipecat FunctionCallParams invocations without blocking the audio loop."""
    name = function_name or _first_attr(params, ("function_name", "name"))
    if not name:
        raise ValueError("FunctionCallParams is missing function_name")
    arguments = _coerce_arguments(_first_attr(params, ("arguments", "args")))

    result = await asyncio.to_thread(
        call_launcher_tool,
        str(name),
        arguments,
        launcher_url,
        http_post,
    )
    await _invoke_result_callback(params, result)
    return result


def _create_tool_handler(
    tool_name: str,
    launcher_url: str,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> Callable[[Any], Any]:
    """Bind a specific launcher tool name to an async Pipecat function handler."""

    async def handler(params: Any) -> dict[str, Any]:
        if not _first_attr(params, ("function_name", "name")):
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

    return handler


def register_launcher_tools(
    llm_service: Any,
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    cancel_on_interruption: bool = True,
) -> list[str]:
    """Register all JARVIS launcher tools on a Pipecat Gemini LLM service instance."""
    if not hasattr(llm_service, "register_function"):
        raise TypeError("llm_service must provide register_function(name, handler, ...)")

    registered: list[str] = []
    for tool in TOOL_DEFINITIONS:
        name = str(tool["name"])
        handler = _create_tool_handler(name, launcher_url, http_post)
        llm_service.register_function(
            name,
            handler,
            cancel_on_interruption=cancel_on_interruption,
        )
        registered.append(name)
    return registered
