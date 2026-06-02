"""Optional Pipecat + Gemini Live backend for J.A.R.V.I.S.

This module is intentionally optional: the default Toingg backend still works
without Pipecat installed. When `BACKEND=pipecat_gemini` is configured,
`jarvis_launcher.py` starts this local WebSocket proxy and `jarvis_web.html`
connects to it instead of the Toingg streaming endpoint.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8767
DEFAULT_WS_PATH = "/ws"
DEFAULT_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_VOICE = "Puck"
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are JARVIS, a concise, friendly desktop voice assistant. "
    "Answer briefly because your response is spoken aloud."
)


@dataclass(frozen=True)
class PipecatGeminiConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    ws_path: str = DEFAULT_WS_PATH
    api_key_env: str = "GOOGLE_API_KEY"
    model: str = DEFAULT_MODEL
    voice: str = DEFAULT_VOICE
    system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION
    input_sample_rate: int = 8000
    output_sample_rate: int = 24000

    @property
    def ws_url(self) -> str:
        path = self.ws_path if self.ws_path.startswith("/") else f"/{self.ws_path}"
        return f"ws://{self.host}:{self.port}{path}"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def selected_backend(config: dict[str, Any]) -> str:
    return str(config.get("BACKEND") or config.get("backend") or "toingg").strip().lower()


def load_project_config(config_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = Path(config_path or Path(__file__).with_name("config.json"))
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_pipecat_config(config_path: str | os.PathLike[str] | None = None) -> PipecatGeminiConfig:
    cfg = load_project_config(config_path)
    return PipecatGeminiConfig(
        host=str(cfg.get("PIPECAT_HOST") or DEFAULT_HOST),
        port=int(cfg.get("PIPECAT_PORT") or DEFAULT_PORT),
        ws_path=str(cfg.get("PIPECAT_WS_PATH") or DEFAULT_WS_PATH),
        api_key_env=str(cfg.get("PIPECAT_GEMINI_API_KEY_ENV") or "GOOGLE_API_KEY"),
        model=str(cfg.get("PIPECAT_GEMINI_MODEL") or DEFAULT_MODEL),
        voice=str(cfg.get("PIPECAT_GEMINI_VOICE") or DEFAULT_VOICE),
        system_instruction=str(
            cfg.get("PIPECAT_GEMINI_SYSTEM_INSTRUCTION") or DEFAULT_SYSTEM_INSTRUCTION
        ),
        input_sample_rate=int(cfg.get("PIPECAT_INPUT_SAMPLE_RATE") or 8000),
        output_sample_rate=int(cfg.get("PIPECAT_OUTPUT_SAMPLE_RATE") or 24000),
    )


def pipecat_enabled(config_path: str | os.PathLike[str] | None = None) -> bool:
    return selected_backend(load_project_config(config_path)) == "pipecat_gemini"


def effective_websocket_url(config: dict[str, Any]) -> str:
    """Return the browser WebSocket URL for the selected backend."""
    if selected_backend(config) == "pipecat_gemini":
        if config.get("PIPECAT_WS_URL"):
            return str(config["PIPECAT_WS_URL"])
        return PipecatGeminiConfig(
            host=str(config.get("PIPECAT_HOST") or DEFAULT_HOST),
            port=int(config.get("PIPECAT_PORT") or DEFAULT_PORT),
            ws_path=str(config.get("PIPECAT_WS_PATH") or DEFAULT_WS_PATH),
        ).ws_url
    return str(config.get("WS_URL") or "")


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


def make_jarvis_json_serializer(config: PipecatGeminiConfig):
    """Create a Pipecat FrameSerializer for the existing JARVIS web protocol."""
    from pipecat.frames.frames import (  # type: ignore[import-not-found]
        InputAudioRawFrame,
        OutputAudioRawFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.serializers.base_serializer import (  # type: ignore[import-not-found]
        FrameSerializer,
        FrameSerializerType,
    )

    class JarvisJsonFrameSerializer(FrameSerializer):
        @property
        def type(self):
            return FrameSerializerType.TEXT

        async def deserialize(self, data: str | bytes):
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            msg = json.loads(data)
            event = msg.get("event")
            if event == "media":
                payload = (msg.get("media") or {}).get("payload")
                if not payload:
                    return None
                pcm16 = float32_b64_to_pcm16(payload)
                return InputAudioRawFrame(
                    audio=pcm16,
                    sample_rate=config.input_sample_rate,
                    num_channels=1,
                )
            return None

        async def serialize(self, frame):
            if isinstance(frame, OutputAudioRawFrame):
                payload = pcm16_to_float32_b64(frame.audio)
                return json.dumps({"event": "media", "media": {"payload": payload, "sampleRate": frame.sample_rate}})
            if isinstance(frame, TranscriptionFrame):
                return json.dumps(
                    {"event": "transcription", "role": "user", "content": frame.text}
                )
            if isinstance(frame, TextFrame):
                return json.dumps({"event": "aiTextStream", "text_chunk": frame.text})
            return None

    return JarvisJsonFrameSerializer()


async def run_bot(websocket, config: PipecatGeminiConfig) -> None:
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

    api_key = os.getenv(config.api_key_env)
    if not api_key:
        await websocket.send_json(
            {
                "event": "transcription",
                "role": "ai",
                "content": f"Missing {config.api_key_env}; Pipecat Gemini backend is not configured.",
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
    llm = GeminiLiveLLMService(
        api_key=api_key,
        settings=GeminiLiveLLMService.Settings(
            model=config.model,
            voice=config.voice,
            system_instruction=config.system_instruction,
        ),
    )
    context = LLMContext(
        [
            {
                "role": "user",
                "content": "Start by greeting the user briefly as JARVIS.",
            }
        ]
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline(
        [transport.input(), user_aggregator, llm, transport.output(), assistant_aggregator]
    )
    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
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


def create_app(config: PipecatGeminiConfig | None = None):
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
