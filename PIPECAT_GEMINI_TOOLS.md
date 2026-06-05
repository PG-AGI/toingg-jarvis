# Pipecat Gemini tool bridge

Issue #11 requires Gemini function calls to reach the local launcher instead of
stopping at model-side tool declarations. `pipecat_gemini_tools.py` provides the
missing bridge:

1. Register `TOOL_DEFINITIONS` with the Gemini/Pipecat LLM service.
2. When the Pipecat proxy receives a function-call frame, call
   `handle_function_call_frame(frame)`.
3. Push the returned frame back into the Pipecat pipeline so Gemini receives the
   tool result and can verbally confirm the action.

The bridge keeps Pipecat optional. If Pipecat is installed, the returned object
is a `FunctionCallResultFrame`; otherwise tests use a compatible local dataclass.

## Launcher endpoint mapping

| Gemini tool | Launcher endpoint | Notes |
| --- | --- | --- |
| `open_browser` | `POST /open_window` | Adds `https://` when the model omits a scheme. |
| `close_tabs` | `POST /close_tabs` | Supports the launcher's `auto` flag. |
| `open_file` | `POST /file_action` | Uses the existing validated native file manager path. |
| `run_playwright` | `POST /playwright_action` | Runs one Playwright action through the launcher. |
| `playwright_actions` | `POST /playwright_actions` | Runs an ordered batch of Playwright actions. |

## Example proxy hook

```python
from pipecat_gemini_tools import TOOL_DEFINITIONS, handle_function_call_frame

# Register TOOL_DEFINITIONS with the Gemini LLM service setup.

async def on_frame(frame, transport):
    if frame.__class__.__name__ in ("FunctionCallFrame", "FunctionCallInProgressFrame"):
        result_frame = handle_function_call_frame(frame)
        await transport.push_frame(result_frame)
```

## Verification

```bash
python -m unittest test_pipecat_gemini_tools.py test_scheduled_actions.py
python -m py_compile pipecat_gemini_tools.py jarvis_launcher.py test_pipecat_gemini_tools.py
git diff --check
```
