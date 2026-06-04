"""Backend selection helpers for the JARVIS launcher.

The default path remains Toingg. The Pipecat/Gemini path is opt-in so users
without the optional dependencies or a Gemini key keep the current behavior.
"""

from __future__ import annotations

import json
import os
from typing import Any


BACKEND_TOINGG = "toingg"
BACKEND_PIPECAT_GEMINI = "pipecat_gemini"
DEFAULT_PIPECAT_GEMINI_WS_URL = "ws://localhost:8767/ws"


def load_runtime_config(config_path: str) -> dict[str, Any]:
    """Load the runtime config file without silently falling back to examples."""
    with open(config_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config.json must contain a JSON object")
    return data


def selected_backend(config: dict[str, Any]) -> str:
    """Return the normalized backend name from config."""
    backend = str(config.get("BACKEND") or BACKEND_TOINGG).strip().lower()
    if backend in {"", BACKEND_TOINGG}:
        return BACKEND_TOINGG
    if backend in {BACKEND_PIPECAT_GEMINI, "pipecat-gemini", "gemini"}:
        return BACKEND_PIPECAT_GEMINI
    raise ValueError(f"Unsupported BACKEND value: {backend}")


def requires_toingg_token(config: dict[str, Any]) -> bool:
    """Only the default Toingg backend requires the Toingg TOKEN prompt."""
    return selected_backend(config) == BACKEND_TOINGG


def pipecat_gemini_ws_url(config: dict[str, Any]) -> str:
    """Return the local browser-facing Pipecat/Gemini WebSocket URL."""
    return str(config.get("PIPECAT_GEMINI_WS_URL") or DEFAULT_PIPECAT_GEMINI_WS_URL).strip()


def build_web_config(config: dict[str, Any]) -> dict[str, Any]:
    """Build the config served to jarvis_web.html."""
    web_config = dict(config)
    if selected_backend(config) == BACKEND_PIPECAT_GEMINI:
        web_config["WS_URL"] = pipecat_gemini_ws_url(config)
    return web_config


def validate_pipecat_gemini_config(config: dict[str, Any]) -> list[str]:
    """Return missing Pipecat/Gemini settings, if any."""
    missing: list[str] = []
    if not str(config.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip():
        missing.append("GEMINI_API_KEY")
    if not str(config.get("GEMINI_MODEL") or "").strip():
        missing.append("GEMINI_MODEL")
    if not pipecat_gemini_ws_url(config):
        missing.append("PIPECAT_GEMINI_WS_URL")
    return missing
