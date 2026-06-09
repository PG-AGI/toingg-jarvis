"""Minimal Pipecat/Gemini bridge stub for bounty #11.

This module provides a non-blocking, optional adapter that can be integrated
into the launcher to accept Pipecat/Gemini FunctionCall frames and forward them
as HTTP requests to the existing local launcher endpoints (e.g. localhost:8766).

The implementation here is intentionally minimal and non-invasive — it exposes
`handle_function_call(frame)` which returns a simulated result. Maintainers can
replace the stub with a full implementation that performs real JSON-RPC
translation.
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def handle_function_call(frame: Dict[str, Any]) -> Dict[str, Any]:
    """Handle a Pipecat/Gemini function call frame and return a result frame.

    This is a safe no-op placeholder that logs the incoming frame and returns
    a success result indicating the action was received. Replace with
    real launcher HTTP calls when integrating.
    """
    logger.info("Received function call frame: %s", json.dumps(frame))
    # Minimal validation
    name = frame.get("name") or frame.get("function") or "unknown"
    return {
        "name": name,
        "status": "ok",
        "result": {"message": f"stubbed handler received {name}"},
    }
