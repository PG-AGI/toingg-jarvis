"""Optional Pipecat + Gemini Live backend for J.A.R.V.I.S.

This module is intentionally optional: the default Toingg backend still works
without Pipecat installed. When `BACKEND=pipecat_gemini` is configured,
`jarvis_launcher.py` starts this local WebSocket proxy and `jarvis_web.html`
connects to it instead of the Toingg streaming endpoint.

Tool calls emitted by Gemini (`open_browser`, `close_tabs`, `open_file`,
`run_playwright`, and `playwright_actions`) are caught via both Pipecat's
`register_launcher_tools` handler and `LauncherToolFrameProcessor`, forwarded to
the local launcher HTTP endpoints on `localhost:8766`, and returned to Gemini as
a `FunctionCallResultFrame` so it can verbally confirm the completed action.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct
from typing import Any, Callable

from pipecat_gemini_tools import (
    DEFAULT_LAUNCHER_URL,
    build_tools_schema,
    handle_function_call_frame,
    post_json,
    register_launcher_tools,
)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8767
DEFAULT_WS_PATH = "/ws"
DEFAULT_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_VOICE = "Puck"
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are JARVIS, a concise, helpful desktop voice assistant. "
    "You have tools to open browser windows, close tabs, open local files, "
    "and run Playwright browser actions. When you execute a tool, briefly "
    "confirm the action aloud."
)

PLACEHOLDER_API_KEYS = {
    "",
    "your-gemini-api-key-here",
    "your-google-api-key-here",
    "your-api-key-here",
}


@dataclass(frozen=True)
class PipecatGeminiConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    ws_path: str = DEFAULT_WS_PATH
    api_key_env: str = "GOOGLE_API_KEY"
    api_key: str = ""
    model: str = DEFAULT_MODEL
    voice: str = DEFAULT_VOICE
    system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION
    input_sample_rate: int = 8000
    output_sample_rate: int = 24000
    launcher_url: str = DEFAULT_LAUNCHER_URL

    @property
    def ws_url(self) -> str:
        path = self.ws_path if self.ws_path.startswith("/") else f"/{self.ws_path}"
        return f"ws://{self.host}:{self.port}{path}"


def selected_backend(config: dict[str, Any] | None) -> str:
    raw = config or {}
    backend = str(raw.get("BACKEND") or raw.get("backend") or "toingg").strip().lower()
    if backend not in ("toingg", "pipecat_gemini"):
        return "toingg"
    return backend


def load_project_config(config_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = Path(config_path or Path(__file__).with_name("config.json"))
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_gemini_api_key(
    config: dict[str, Any] | None = None,
    api_key_env: str = "GOOGLE_API_KEY",
) -> str:
    cfg = config or {}
    candidates = [
        os.getenv(api_key_env),
        os.getenv("GOOGLE_API_KEY"),
        os.getenv("GEMINI_API_KEY"),
        cfg.get("GEMINI_API_KEY"),
        cfg.get("GOOGLE_API_KEY"),
    ]
    for candidate in candidates:
        cleaned = str(candidate or "").strip()
        if cleaned and cleaned.lower() not in PLACEHOLDER_API_KEYS:
            return cleaned
    return ""


def load_pipecat_config(config_path: str | os.PathLike[str] | None = None) -> PipecatGeminiConfig:
    cfg = load_project_config(config_path)
    api_key_env = str(cfg.get("PIPECAT_GEMINI_API_KEY_ENV") or "GOOGLE_API_KEY")
    return PipecatGeminiConfig(
        host=str(cfg.get("PIPECAT_HOST") or DEFAULT_HOST),
        port=int(cfg.get("PIPECAT_PORT") or DEFAULT_PORT),
        ws_path=str(cfg.get("PIPECAT_WS_PATH") or DEFAULT_WS_PATH),
        api_key_env=api_key_env,
        api_key=resolve_gemini_api_key(cfg, api_key_env=api_key_env),
        model=str(cfg.get("PIPECAT_GEMINI_MODEL") or cfg.get("GEMINI_MODEL") or DEFAULT_MODEL),
        voice=str(cfg.get("PIPECAT_GEMINI_VOICE") or DEFAULT_VOICE),
        system_instruction=str(
            cfg.get("PIPECAT_GEMINI_SYSTEM_INSTRUCTION") or DEFAULT_SYSTEM_INSTRUCTION
        ),
        input_sample_rate=int(cfg.get("PIPECAT_INPUT_SAMPLE_RATE") or 8000),
        output_sample_rate=int(cfg.get("PIPECAT_OUTPUT_SAMPLE_RATE") or 24000),
        launcher_url=str(cfg.get("LAUNCHER_URL") or DEFAULT_LAUNCHER_URL),
    )


def pipecat_enabled(config_path: str | os.PathLike[str] | None = None) -> bool:
    return selected_backend(load_project_config(config_path)) == "pipecat_gemini"


def effective_websocket_url(config: dict[str, Any] | None) -> str:
    """Return the browser WebSocket URL for the selected backend."""
    cfg = config or {}
    if selected_backend(cfg) == "pipecat_gemini":
        if cfg.get("PIPECAT_WS_URL"):
            return str(cfg["PIPECAT_WS_URL"])
        return PipecatGeminiConfig(
            host=str(cfg.get("PIPECAT_HOST") or DEFAULT_HOST),
            port=int(cfg.get("PIPECAT_PORT") or DEFAULT_PORT),
            ws_path=str(cfg.get("PIPECAT_WS_PATH") or DEFAULT_WS_PATH),
        ).ws_url
    return str(cfg.get("WS_URL") or "")


def float32_b64_to_pcm16(payload: str) -> bytes:
    """Convert the current web UI Float32Array base64 payload to PCM16 mono."""
    raw = base64.b64decode(payload)
    if len(raw) % 4:
        raise ValueError("Float32 audio payload length must be divisible by 4")
    samples = struct.iter_unpack("<f", raw)
    out = bytearray()
    for (sample,) in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        out.extend(struct.pack("<h", int(clipped * 32767)))
    return bytes(out)


def pcm16_to_float32_b64(audio: bytes) -> str:
    """Convert PCM16 mono bytes from Pipecat/Gemini into the web UI format."""
    if len(audio) % 2:
        raise ValueError("PCM16 audio length must be divisible by 2")
    out = bytearray()
    for (sample,) in struct.iter_unpack("<h", audio):
        out.extend(struct.pack("<f", max(-1.0, min(1.0, sample / 32768.0))))
    return base64.b64encode(bytes(out)).decode("ascii")


def is_function_call_frame(frame: Any) -> bool:
    """Return True if frame is a Pipecat FunctionCallFrame or equivalent tool-call frame."""
    if frame is None:
        return False
    cls_name = frame.__class__.__name__
    if cls_name in ("FunctionCallFrame", "FunctionCallInProgressFrame"):
        return True
    has_name = bool(
        getattr(frame, "function_name", None)
        or getattr(frame, "tool_name", None)
        or (isinstance(frame, dict) and (frame.get("function_name") or frame.get("tool_name")))
    )
    has_args = (
        hasattr(frame, "arguments")
        or hasattr(frame, "args")
        or hasattr(frame, "function_args")
        or (
            isinstance(frame, dict)
            and any(k in frame for k in ("arguments", "args", "function_args"))
        )
    )
    return has_name and has_args and cls_name != "LocalFunctionCallResultFrame" and cls_name != "FunctionCallResultFrame"


class LauncherToolFrameProcessor:
    """Pipeline frame processor that catches FunctionCallFrame from Pipecat,
    invokes the corresponding localhost:8766 launcher HTTP endpoint, and emits
    a FunctionCallResultFrame so Gemini can verbally confirm the action.
    """

    def __init__(
        self,
        launcher_url: str = DEFAULT_LAUNCHER_URL,
        http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
        push_frame_fn: Callable[[Any, Any], Any] | None = None,
    ) -> None:
        self.launcher_url = launcher_url
        self.http_post = http_post
        self._push_frame_fn = push_frame_fn
        self.emitted_frames: list[Any] = []

    async def push_frame(self, frame: Any, direction: Any = None) -> None:
        self.emitted_frames.append(frame)
        if self._push_frame_fn is not None:
            maybe_coro = self._push_frame_fn(frame, direction)
            if hasattr(maybe_coro, "__await__"):
                await maybe_coro

    async def process_frame(self, frame: Any, direction: Any = None) -> Any:
        if is_function_call_frame(frame):
            result_frame = await asyncio.to_thread(
                handle_function_call_frame,
                frame,
                self.launcher_url,
                self.http_post,
            )
            await self.push_frame(result_frame, direction)
            return result_frame

        await self.push_frame(frame, direction)
        return frame


def deserialize_jarvis_ws_message(
    data: str | bytes,
    config: PipecatGeminiConfig,
    audio_frame_cls: Any = None,
    text_frame_cls: Any = None,
    interruption_frame_cls: Any = None,
) -> Any:
    """Deserialize a browser WebSocket message into a Pipecat frame."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    msg = json.loads(data)
    if not isinstance(msg, dict):
        return None

    event = str(msg.get("event") or msg.get("type") or "").strip().lower()
    if event in ("media", "audio"):
        media_obj = msg.get("media") if isinstance(msg.get("media"), dict) else {}
        payload = media_obj.get("payload") or msg.get("payload") or msg.get("data")
        if not payload:
            return None
        sample_rate = int(
            media_obj.get("sampleRate")
            or msg.get("sampleRate")
            or msg.get("sample_rate")
            or config.input_sample_rate
        )
        pcm16 = float32_b64_to_pcm16(str(payload))
        if audio_frame_cls is None:
            from pipecat.frames.frames import InputAudioRawFrame  # type: ignore[import-not-found]

            audio_frame_cls = InputAudioRawFrame
        return audio_frame_cls(
            audio=pcm16,
            sample_rate=sample_rate,
            num_channels=1,
        )

    if event == "text":
        text = str(msg.get("text") or "")
        if not text:
            return None
        if text_frame_cls is None:
            from pipecat.frames.frames import InputTextRawFrame  # type: ignore[import-not-found]

            text_frame_cls = InputTextRawFrame
        return text_frame_cls(text=text)

    if event in ("stop", "interrupt", "clear", "clearaudio"):
        if interruption_frame_cls is None:
            from pipecat.frames.frames import InterruptionFrame  # type: ignore[import-not-found]

            interruption_frame_cls = InterruptionFrame
        return interruption_frame_cls()

    return None


def serialize_jarvis_ws_frame(frame: Any, default_sample_rate: int = 24000) -> str | None:
    """Serialize a Pipecat output frame into the JARVIS browser WebSocket JSON format."""
    if frame is None:
        return None
    cls_name = frame.__class__.__name__
    if cls_name == "OutputAudioRawFrame" or hasattr(frame, "audio"):
        audio = getattr(frame, "audio", None)
        if isinstance(audio, (bytes, bytearray)):
            sample_rate = int(getattr(frame, "sample_rate", None) or default_sample_rate)
            payload = pcm16_to_float32_b64(bytes(audio))
            return json.dumps(
                {"event": "media", "media": {"payload": payload, "sampleRate": sample_rate}}
            )

    if cls_name == "TranscriptionFrame":
        text = getattr(frame, "text", "")
        if text:
            return json.dumps({"event": "transcription", "role": "user", "content": text})

    if cls_name == "TextFrame":
        text = getattr(frame, "text", "")
        if text:
            return json.dumps({"event": "aiTextStream", "text_chunk": text})

    return None


def make_jarvis_json_serializer(config: PipecatGeminiConfig) -> Any:
    """Create a Pipecat FrameSerializer for the existing JARVIS web protocol."""
    from pipecat.serializers.base_serializer import (  # type: ignore[import-not-found]
        FrameSerializer,
        FrameSerializerType,
    )

    class JarvisJsonFrameSerializer(FrameSerializer):
        @property
        def type(self):
            return FrameSerializerType.TEXT

        async def deserialize(self, data: str | bytes):
            return deserialize_jarvis_ws_message(data, config)

        async def serialize(self, frame):
            return serialize_jarvis_ws_frame(frame, default_sample_rate=config.output_sample_rate)

    return JarvisJsonFrameSerializer()


def make_pipecat_tool_processor(
    launcher_url: str = DEFAULT_LAUNCHER_URL,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> Any:
    """Build a Pipecat FrameProcessor subclass that intercepts FunctionCallFrame
    and pushes FunctionCallResultFrame back into the pipeline.
    """
    try:
        from pipecat.processors.frame_processor import FrameProcessor  # type: ignore[import-not-found]
    except Exception:
        return LauncherToolFrameProcessor(launcher_url=launcher_url, http_post=http_post)

    class PipecatLauncherToolProcessor(FrameProcessor):
        def __init__(self) -> None:
            super().__init__()
            self._delegate = LauncherToolFrameProcessor(
                launcher_url=launcher_url,
                http_post=http_post,
                push_frame_fn=self.push_frame,
            )

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            await self._delegate.process_frame(frame, direction)

    return PipecatLauncherToolProcessor()


async def run_bot(websocket: Any, config: PipecatGeminiConfig) -> None:
    """Run one Pipecat Gemini Live pipeline for a connected browser client."""
    from loguru import logger  # type: ignore[import-not-found]
    from pipecat.audio.vad.silero import SileroVADAnalyzer  # type: ignore[import-not-found]
    from pipecat.frames.frames import LLMRunFrame  # type: ignore[import-not-found]
    from pipecat.pipeline.pipeline import Pipeline  # type: ignore[import-not-found]
    from pipecat.pipeline.runner import PipelineRunner  # type: ignore[import-not-found]
    from pipecat.pipeline.task import PipelineParams, PipelineTask  # type: ignore[import-not-found]
    from pipecat.processors.aggregators.llm_context import LLMContext  # type: ignore[import-not-found]
    from pipecat.processors.aggregators.llm_response_universal import (  # type: ignore[import-not-found]
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.services.google.gemini_live.llm import (  # type: ignore[import-not-found]
        GeminiLiveLLMService,
    )
    from pipecat.transports.websocket.fastapi import (  # type: ignore[import-not-found]
        FastAPIWebsocketParams,
        FastAPIWebsocketTransport,
    )

    api_key = config.api_key or resolve_gemini_api_key(api_key_env=config.api_key_env)
    if not api_key:
        await websocket.send_json(
            {
                "event": "transcription",
                "role": "ai",
                "content": (
                    f"Missing {config.api_key_env} or GEMINI_API_KEY; "
                    "Pipecat Gemini backend is not configured."
                ),
            }
        )
        await websocket.close()
        return

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=make_jarvis_json_serializer(config),
        ),
    )

    tools_schema = build_tools_schema()
    llm = GeminiLiveLLMService(
        api_key=api_key,
        tools=tools_schema,
        settings=GeminiLiveLLMService.Settings(
            model=config.model,
            voice=config.voice,
            system_instruction=config.system_instruction,
        ),
    )
    register_launcher_tools(llm, launcher_url=config.launcher_url)
    tool_processor = make_pipecat_tool_processor(launcher_url=config.launcher_url)

    context = LLMContext(
        [
            {
                "role": "user",
                "content": "Start by greeting the user briefly as JARVIS.",
            }
        ],
        tools=tools_schema,
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            user_aggregator,
            llm,
            tool_processor,
            transport.output(),
            assistant_aggregator,
        ]
    )
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("JARVIS Pipecat client ready")
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("JARVIS web client connected to Pipecat Gemini")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("JARVIS web client disconnected from Pipecat Gemini")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)


def create_app(config: PipecatGeminiConfig | None = None) -> Any:
    from fastapi import FastAPI, WebSocket  # type: ignore[import-not-found]

    config = config or load_pipecat_config()
    app = FastAPI(title="JARVIS Pipecat Gemini Backend")

    @app.get("/health")
    async def health():
        return {
            "ok": True,
            "backend": "pipecat_gemini",
            "model": config.model,
            "voice": config.voice,
            "ws": config.ws_url,
            "launcher_url": config.launcher_url,
        }

    @app.websocket(config.ws_path)
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await run_bot(websocket, config)

    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the optional JARVIS Pipecat Gemini backend")
    parser.add_argument("--config", default=None, help="Path to config.json")
    args = parser.parse_args(argv)
    config = load_pipecat_config(args.config)

    try:
        import uvicorn  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Missing optional dependencies. Install with: "
            "pip install -r requirements-pipecat-gemini.txt"
        ) from exc

    uvicorn.run(create_app(config), host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
