## Backend selection

The project now supports two voice/LLM backends:

1. **Toingg** – the original implementation (default).
2. **Pipecat + Gemini** – an optional, real‑time pipeline.

The backend is chosen via the ``BACKEND`` field in ``config.json`` (or
``config.example.json``). Example:

```json
{
  "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
  "TOKEN": "your-token-here",
  "CAMP_ID": "your-campaign-id-here",
  "BACKEND": "pipecat_gemini"
}
```

When ``pipecat_gemini`` is selected, the Pipecat‑Gemini bridge defined in
``pipecat_gemini_tools.py`` is activated. It automatically registers the
required tools (open_browser, close_tabs, open_file, run_playwright,
playwright_actions) with the LLM service and forwards tool calls to the local
launcher running on ``http://localhost:8766``.

If Pipecat is not installed or the backend is set to ``toingg``, the existing
behaviour remains unchanged.
