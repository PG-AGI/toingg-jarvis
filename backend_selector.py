import json
import os
from pathlib import Path

from .pipecat_gemini_tools import register_launcher_tools

# Load the project's configuration (config.json or config.example.json)
CONFIG_PATH = Path(__file__).parent / "config.json"
if not CONFIG_PATH.exists():
    CONFIG_PATH = Path(__file__).parent / "config.example.json"

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise RuntimeError(f"Failed to load configuration from {CONFIG_PATH}: {exc}")

_config = _load_config()

def get_backend_name() -> str:
    """Return the backend identifier selected in the config.

    Expected values:
        - "toingg" (default, existing implementation)
        - "pipecat_gemini" (optional Pipecat + Gemini integration)
    """
    return str(_config.get("BACKEND", "toingg")).lower()

def maybe_register_pipecat_tools(llm_service: any) -> None:
    """If the Pipecat/Gemini backend is selected, register the launcher‑backed tools.

    The function is safe to call even when Pipecat is not installed – the
    ``register_launcher_tools`` helper gracefully falls back to a no‑op when the
    required Pipecat classes are missing.
    """
    if get_backend_name() == "pipecat_gemini":
        # ``register_launcher_tools`` returns the list of tool names that were
        # successfully registered; we ignore the return value here because the
        # caller only needs the side‑effect of registration.
        register_launcher_tools(llm_service)
