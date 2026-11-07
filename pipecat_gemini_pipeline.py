"""Real-time Pipecat and Gemini Multimodal Live voice and tool pipeline for JARVIS.

Bridges browser WebSocket media/image events from jarvis_web.html into Pipecat
audio, vision, interruption, and FunctionCallResultFrame streams backed by the
local HTTP launcher on localhost:8766.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import struct
from typing import Any, Callable

from pipecat_gemini_tools import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GEMINI_VOICE,
    DEFAULT_LAUNCHER_URL,
    DEFAULT_PIPECAT_WS_URL,
    build_tools_schema,
    handle_function_call_frame,
    post_json,
    register_launcher_tools,
)


DEFAULT_SYSTEM_INSTRUCTION = (
    "You are J.A.R.V.I.S., a real-time multimodal voice assistant. "
    "Use registered browser, tab, file, and Playwright tools whenever the user "
    "requests local actions, and verbally confirm the outcome once the tool finishes."
)

_FUNCTION_CALL_FRAME_NAMES = frozenset({"FunctionCallFrame", "FunctionCallInProgressFrame"})
_INTERRUPTION_FRAME_NAMES = frozenset(
    {"StartInterruptionFrame", "UserStartedSpeakingFrame", "LocalInterruptionFrame"}
)
_AUDIO_OUTPUT_FRAME_NAMES = frozenset(
    {"OutputAudioRawFrame", "TTSAudioRawFrame", "AudioRawFrame", "LocalAudioOutputFrame"}
)
_INTERRUPTION_EVENTS = frozenset({"interrupt", "clear", "clearAudio"})


def _cfg_str(cfg: dict[str, Any], key: str, default: str) -> str:
    """Resolve a configuration string from the config dict, environment, or fallback default."""
    raw = cfg.get(key) or os.environ.get(key) or default
    return str(raw)


def _resolve_gemini_api_key(cfg: dict[str, Any]) -> str:
    """Locate the Gemini API credential from config keys or environment variables."""
    candidates = (
        cfg.get("GEMINI_API_KEY"),
        cfg.get("GOOGLE_API_KEY"),
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GOOGLE_API_KEY"),
        cfg.get("TOKEN"),
    )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@dataclass
class GeminiLiveConfig:
    """Configuration parameters for the Pipecat Gemini Multimodal Live voice pipeline."""

    api_key: str
    model: str = DEFAULT_GEMINI_MODEL
    voice_id: str = DEFAULT_GEMINI_VOICE
    system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION
    launcher_url: str = DEFAULT_LAUNCHER_URL
    ws_url: str = DEFAULT_PIPECAT_WS_URL
    input_sample_rate: int = 8000
    output_sample_rate: int = 22050
    enable_multimodal: bool = True

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> GeminiLiveConfig:
        """Build a validated GeminiLiveConfig from config.json values and environment variables."""
        cfg = config if isinstance(config, dict) else {}
        api_key = _resolve_gemini_api_key(cfg)
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is required for pipecat_gemini backend")
        return cls(
            api_key=api_key,
            model=_cfg_str(cfg, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            voice_id=_cfg_str(cfg, "GEMINI_VOICE", DEFAULT_GEMINI_VOICE),
            system_instruction=_cfg_str(cfg, "SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION),
            launcher_url=_cfg_str(cfg, "LAUNCHER_URL", DEFAULT_LAUNCHER_URL),
            ws_url=_cfg_str(cfg, "PIPECAT_WS_URL", DEFAULT_PIPECAT_WS_URL),
            input_sample_rate=int(cfg.get("INPUT_SAMPLE_RATE", 8000)),
            output_sample_rate=int(cfg.get("OUTPUT_SAMPLE_RATE", 22050)),
            enable_multimodal=bool(cfg.get("ENABLE_MULTIMODAL", True)),
        )


@dataclass
class LocalAudioInputFrame:
    """Fallback inbound PCM16 audio frame used when Pipecat is not installed."""

    audio: bytes
    sample_rate: int = 8000
    num_channels: int = 1


@dataclass
class LocalAudioOutputFrame:
    """Fallback outbound PCM16 audio frame used for deterministic offline testing."""

    audio: bytes
    sample_rate: int = 22050
    num_channels: int = 1


@dataclass
class LocalImageInputFrame:
    """Fallback multimodal image frame carrying raw image bytes and dimensions."""

    image: bytes
    size: tuple[int, int] = (640, 480)
    format: str = "JPEG"


@dataclass
class LocalInterruptionFrame:
    """Fallback barge-in interruption frame signalling immediate playback flush."""

    reason: str = "user_speaking"


@dataclass
class JarvisPipelineBundle:
    """Container holding the assembled Gemini Live service, bridge processor, and pipeline."""

    config: GeminiLiveConfig
    llm_service: Any
    bridge: JarvisGeminiBridgeProcessor
    pipeline: Any


def float32_b64_to_pcm16(payload_b64: str) -> bytes:
    """Convert base64 Float32 mono audio from jarvis_web.html into signed 16-bit PCM bytes."""
    if not payload_b64:
        return b""
    raw_bytes = base64.b64decode(payload_b64)
    sample_count = len(raw_bytes) // 4
    if sample_count == 0:
        return b""
    floats = struct.unpack(f"<{sample_count}f", raw_bytes[: sample_count * 4])
    clamped = [max(-32768, min(32767, int(max(-1.0, min(1.0, sample)) * 32767.0))) for sample in floats]
    return struct.pack(f"<{sample_count}h", *clamped)


def pcm16_to_float32_b64(pcm_bytes: bytes) -> str:
    """Convert signed 16-bit PCM audio from Gemini Live into base64 Float32 chunks for browser playback."""
    if not pcm_bytes:
        return ""
    sample_count = len(pcm_bytes) // 2
    if sample_count == 0:
        return ""
    shorts = struct.unpack(f"<{sample_count}h", pcm_bytes[: sample_count * 2])
    floats = [sample / 32768.0 for sample in shorts]
    float_bytes = struct.pack(f"<{sample_count}f", *floats)
    return base64.b64encode(float_bytes).decode("ascii")


def build_audio_input_frame(pcm_bytes: bytes, sample_rate: int = 8000) -> Any:
    """Create a Pipecat InputAudioRawFrame when available, or a LocalAudioInputFrame fallback."""
    try:
        from pipecat.frames.frames import InputAudioRawFrame
    except Exception:
        return LocalAudioInputFrame(audio=pcm_bytes, sample_rate=sample_rate, num_channels=1)
    return InputAudioRawFrame(audio=pcm_bytes, sample_rate=sample_rate, num_channels=1)


def build_image_input_frame(
    image_bytes: bytes,
    dimensions: tuple[int, int] = (640, 480),
    image_format: str = "JPEG",
) -> Any:
    """Create a Pipecat InputImageRawFrame when available, or a LocalImageInputFrame fallback."""
    try:
        from pipecat.frames.frames import InputImageRawFrame
    except Exception:
        return LocalImageInputFrame(image=image_bytes, size=dimensions, format=image_format)
    return InputImageRawFrame(image=image_bytes, size=dimensions, format=image_format)


def _parse_browser_event(raw_message: str | dict[str, Any]) -> dict[str, Any]:
    """Decode incoming WebSocket JSON text or dictionary payload from jarvis_web.html."""
    if isinstance(raw_message, dict):
        return raw_message
    if isinstance(raw_message, str):
        parsed = json.loads(raw_message)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Browser WebSocket message must be a JSON object")


def _extract_image_dimensions(image_meta: dict[str, Any]) -> tuple[int, int]:
    """Extract width and height tuple from a browser multimodal image payload."""
    size = image_meta.get("size")
    if isinstance(size, (list, tuple)) and len(size) == 2:
        return int(size[0]), int(size[1])
    return int(image_meta.get("width", 640)), int(image_meta.get("height", 480))


def _decode_media_event(msg: dict[str, Any], sample_rate: int) -> Any:
    """Decode a browser media event payload into an inbound PCM16 audio frame."""
    media = msg.get("media")
    payload = str(media.get("payload", "")) if isinstance(media, dict) else ""
    pcm_bytes = float32_b64_to_pcm16(payload)
    if not pcm_bytes:
        return None
    return build_audio_input_frame(pcm_bytes, sample_rate=sample_rate)


def _decode_image_event(msg: dict[str, Any]) -> Any:
    """Decode a browser multimodal image event into an inbound image frame."""
    image_meta = msg.get("image")
    if not isinstance(image_meta, dict):
        return None
    raw_b64 = str(image_meta.get("payload", ""))
    if not raw_b64:
        return None
    dims = _extract_image_dimensions(image_meta)
    fmt = str(image_meta.get("format", "JPEG")).upper()
    return build_image_input_frame(base64.b64decode(raw_b64), dimensions=dims, image_format=fmt)


def _is_function_call_frame(frame: Any) -> bool:
    """Identify whether a pipeline frame represents a pending Gemini tool invocation."""
    if frame.__class__.__name__ in _FUNCTION_CALL_FRAME_NAMES:
        return True
    has_name = bool(getattr(frame, "function_name", None) or getattr(frame, "tool_name", None))
    has_result = hasattr(frame, "result") and getattr(frame, "result") is not None
    return has_name and not has_result


def _serialize_output_frame(frame: Any) -> dict[str, Any] | None:
    """Translate outbound Pipecat audio, text, or interruption frames into jarvis_web.html JSON events."""
    cls_name = frame.__class__.__name__
    if cls_name in _INTERRUPTION_FRAME_NAMES:
        return {"event": "clearAudio"}

    audio_bytes = getattr(frame, "audio", None)
    if cls_name in _AUDIO_OUTPUT_FRAME_NAMES and isinstance(audio_bytes, (bytes, bytearray)):
        payload = pcm16_to_float32_b64(bytes(audio_bytes))
        return {"event": "media", "media": {"payload": payload}} if payload else None

    text_val = getattr(frame, "text", None)
    if isinstance(text_val, str) and text_val:
        if cls_name == "TranscriptionFrame":
            role = str(getattr(frame, "user_id", "") or "user")
            return {"event": "transcription", "role": role, "content": text_val}
        return {"event": "aiTextStream", "text_chunk": text_val}
    return None


class JarvisGeminiBridgeProcessor:
    """Bidirectional frame bridge connecting jarvis_web.html, Pipecat, and the local launcher."""

    def __init__(
        self,
        config: GeminiLiveConfig,
        http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    ) -> None:
        self.config = config
        self.http_post = http_post

    def handle_browser_message(self, raw_message: str | dict[str, Any]) -> Any:
        """Convert browser WebSocket media, image, or control messages into Pipecat frames."""
        msg = _parse_browser_event(raw_message)
        event = str(msg.get("event", "")).strip()
        if event == "media":
            return _decode_media_event(msg, self.config.input_sample_rate)
        if event == "image" and self.config.enable_multimodal:
            return _decode_image_event(msg)
        if event in _INTERRUPTION_EVENTS:
            return LocalInterruptionFrame(reason=event)
        return None

    async def process_pipeline_frame(
        self,
        frame: Any,
        push_frame: Callable[[Any], Any] | None = None,
    ) -> dict[str, Any] | None:
        """Intercept FunctionCallFrames for localhost:8766 execution or serialize output for browser WS."""
        if not _is_function_call_frame(frame):
            return _serialize_output_frame(frame)

        result_frame = handle_function_call_frame(
            frame,
            launcher_url=self.config.launcher_url,
            http_post=self.http_post,
        )
        if push_frame is not None:
            maybe_coro = push_frame(result_frame)
            if hasattr(maybe_coro, "__await__"):
                await maybe_coro
        return {
            "event": "toolResult",
            "function_name": getattr(result_frame, "function_name", ""),
            "tool_call_id": getattr(result_frame, "tool_call_id", ""),
            "result": getattr(result_frame, "result", {}),
        }


def _resolve_gemini_service_class(service_cls: Any = None) -> Any:
    """Import Pipecat's GeminiMultimodalLiveLLMService or return the caller-supplied test double."""
    if service_cls is not None:
        return service_cls
    try:
        from pipecat.services.gemini_multimodal_live.gemini import GeminiMultimodalLiveLLMService

        return GeminiMultimodalLiveLLMService
    except Exception:
        from pipecat.services.google.gemini_live.llm import GeminiMultimodalLiveLLMService

        return GeminiMultimodalLiveLLMService


def create_gemini_live_service(
    config: GeminiLiveConfig,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
    service_cls: Any = None,
) -> Any:
    """Instantiate GeminiMultimodalLiveLLMService and register all 5 JARVIS launcher tools."""
    cls = _resolve_gemini_service_class(service_cls)
    tools = build_tools_schema()
    llm_service = cls(
        api_key=config.api_key,
        model=config.model,
        voice_id=config.voice_id,
        system_instruction=config.system_instruction,
        tools=tools,
    )
    register_launcher_tools(
        llm_service,
        launcher_url=config.launcher_url,
        http_post=http_post,
    )
    return llm_service


def build_gemini_live_pipeline(
    config: GeminiLiveConfig,
    transport: Any = None,
    llm_service: Any = None,
    http_post: Callable[[str, dict[str, Any]], dict[str, Any]] = post_json,
) -> JarvisPipelineBundle:
    """Assemble the complete Pipecat Gemini Live audio/multimodal pipeline and tool bridge."""
    service = llm_service or create_gemini_live_service(config, http_post=http_post)
    bridge = JarvisGeminiBridgeProcessor(config, http_post=http_post)
    stages: list[Any] = []
    if transport is not None and hasattr(transport, "input"):
        stages.append(transport.input())
    stages.extend([bridge, service])
    if transport is not None and hasattr(transport, "output"):
        stages.append(transport.output())

    try:
        from pipecat.pipeline.pipeline import Pipeline

        pipeline_obj: Any = Pipeline(stages)
    except Exception:
        pipeline_obj = stages

    return JarvisPipelineBundle(
        config=config,
        llm_service=service,
        bridge=bridge,
        pipeline=pipeline_obj,
    )
