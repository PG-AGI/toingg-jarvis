# Pipecat & Gemini Live Multimodal Voice Pipeline (`#11`)

`pipecat_gemini_tools.py` and `pipecat_gemini_pipeline.py` integrate [Pipecat](https://github.com/pipecat-ai/pipecat) and the Google Gemini Multimodal Live API (`GeminiMultimodalLiveLLMService`) as an optional real-time voice, vision, and tool-calling backend alongside the default Toingg engine.

## 1. Backend Switching (`config.json`)

Toingg remains the default backend (`"BACKEND": "toingg"`). Setting `"BACKEND": "pipecat_gemini"` in `config.json` switches the session configuration to the local Pipecat/Gemini Live pipeline without breaking environments where Pipecat is not installed:

```json
{
  "BACKEND": "pipecat_gemini",
  "GEMINI_API_KEY": "your-gemini-api-key",
  "GEMINI_MODEL": "models/gemini-2.0-flash-live-001",
  "GEMINI_VOICE": "Puck",
  "PIPECAT_WS_URL": "ws://localhost:8767"
}
```

`resolve_effective_config(config)` in `pipecat_gemini_tools.py` preserves all Toingg settings by default and routes `WS_URL` to `PIPECAT_WS_URL` (`ws://localhost:8767`) only when `BACKEND=pipecat_gemini`.

## 2. Real-Time Audio, Multimodal Vision & Interruption Handling

`JarvisGeminiBridgeProcessor` in `pipecat_gemini_pipeline.py` bridges `jarvis_web.html` WebSocket events and Pipecat pipeline frames:

- **Inbound Browser Audio (`media`)**: Converts base64 Float32 mono audio chunks (`8000 Hz`) from `jarvis_web.html` into signed 16-bit PCM `InputAudioRawFrame` objects (`float32_b64_to_pcm16`) so microphone audio flows continuously into Gemini Live.
- **Inbound Multimodal Frames (`image`)**: Converts base64 image payloads into `InputImageRawFrame` objects for visual Q&A and screen/camera context.
- **Outbound Gemini Audio & Text**: Converts Gemini `OutputAudioRawFrame` / `TTSAudioRawFrame` PCM16 audio back into base64 Float32 `media` payloads (`pcm16_to_float32_b64`) and streams `aiTextStream` / `transcription` events to the UI.
- **Interruption Handling**: Translates barge-in `StartInterruptionFrame` / `UserStartedSpeakingFrame` events into `{"event": "clearAudio"}` so the browser immediately halts queued audio playback.

## 3. Launcher Tool-Calling Bridge (`localhost:8766`)

When Gemini invokes a tool, the pipeline catches `FunctionCallFrame` / `FunctionCallInProgressFrame`, executes the corresponding `localhost:8766` launcher endpoint, and pushes a `FunctionCallResultFrame` back into the pipeline so Gemini can verbally confirm the action:

| Gemini tool | Launcher endpoint | Notes |
| --- | --- | --- |
| `open_browser` | `POST /open_window` | Adds `https://` when the model omits a scheme. |
| `close_tabs` | `POST /close_tabs` | Supports the launcher's `auto` flag. |
| `open_file` | `POST /file_action` | Uses the validated native file manager path. |
| `run_playwright` | `POST /playwright_action` | Runs one Playwright action through the launcher. |
| `playwright_actions` | `POST /playwright_actions` | Runs an ordered batch of Playwright actions. |

## 4. Verification

```bash
python3 -m unittest test_pipecat_gemini_tools.py test_pipecat_gemini_pipeline.py
```
