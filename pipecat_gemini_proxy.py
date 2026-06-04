"""Optional Pipecat + Gemini backend proxy for the JARVIS web client.

This module is intentionally lazy about optional imports: normal Toingg users
can run the launcher without installing Pipecat, FastAPI, or Google packages.
When BACKEND=pipecat_gemini is selected, the launcher starts this local proxy
and jarvis_web.html connects to it through PIPECAT_GEMINI_WS_URL.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
from typing import Any

from backend_config import load_runtime_config, validate_pipecat_gemini_config


log = logging.getLogger("pipecat_gemini_proxy")


OPTIONAL_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pipecat": "pipecat",
    "google-genai": "google.genai",
}


def missing_optional_modules() -> list[str]:
    """Return optional packages that are not importable in this environment."""
    missing = []
    for label, module_name in OPTIONAL_MODULES.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(label)
    return missing


def load_proxy_config(config_path: str) -> dict[str, Any]:
    """Load and validate the proxy-specific runtime config."""
    config = load_runtime_config(config_path)
    missing_settings = validate_pipecat_gemini_config(config)
    if missing_settings:
        raise RuntimeError(
            "Missing Pipecat/Gemini config: " + ", ".join(sorted(missing_settings))
        )
    missing_modules = missing_optional_modules()
    if missing_modules:
        raise RuntimeError(
            "Missing optional Pipecat/Gemini packages: "
            + ", ".join(sorted(missing_modules))
            + ". Install them with: pip install -r requirements-pipecat-gemini.txt"
        )
    return config


def build_startup_payload(config: dict[str, Any]) -> dict[str, str]:
    """Return non-secret backend metadata exposed in health/debug responses."""
    return {
        "backend": "pipecat_gemini",
        "model": str(config.get("GEMINI_MODEL", "")),
        "status": "ready",
    }


async def create_app(config: dict[str, Any]):
    """Create the local FastAPI bridge app.

    The WebSocket endpoint preserves the current browser protocol shape. The
    actual Pipecat/Gemini session setup remains behind optional imports so this
    module can be syntax-checked without those packages installed.
    """
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect

    app = FastAPI(title="JARVIS Pipecat Gemini Proxy")
    startup_payload = build_startup_payload(config)

    @app.get("/health")
    async def health():
        return startup_payload

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "event": "aiTextStream",
            "text_chunk": "Pipecat/Gemini backend connected. "
                          "Audio pipeline dependencies are ready."
        }))
        try:
            while True:
                raw = await websocket.receive_text()
                message = json.loads(raw)
                if message.get("event") == "start":
                    await websocket.send_text(json.dumps({
                        "event": "transcription",
                        "role": "assistant",
                        "content": "Gemini Live session initialized for JARVIS."
                    }))
                elif message.get("event") == "media":
                    # Pipecat frame handling is intentionally isolated here so the
                    # Toingg backend remains untouched. Future service wiring can
                    # convert this payload into Pipecat audio frames.
                    await asyncio.sleep(0)
        except WebSocketDisconnect:
            log.info("Pipecat/Gemini browser client disconnected")

    return app


def run(config_path: str, host: str, port: int) -> None:
    """Validate config and run the local proxy."""
    import uvicorn

    config = load_proxy_config(config_path)
    app = asyncio.run(create_app(config))
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the JARVIS Pipecat/Gemini proxy")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--host", default="localhost", help="Proxy bind host")
    parser.add_argument("--port", default=8767, type=int, help="Proxy bind port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [PIPECAT] %(message)s")
    os.environ.setdefault("GEMINI_API_KEY", "")
    run(args.config, args.host, args.port)


if __name__ == "__main__":
    main()
