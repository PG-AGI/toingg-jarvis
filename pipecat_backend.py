"""
pipecat_backend.py — Optional Pipecat + Gemini backend for J.A.R.V.I.S.

Runs a real-time voice pipeline using the Pipecat framework with Google's
Gemini Multimodal Live API as the LLM (handles STT, reasoning, and TTS).
This is an alternative to the default Toingg WebSocket backend; the two
backends are independent and selected via config.json ("BACKEND": "pipecat").

Usage:
    python pipecat_backend.py [--api-key <GEMINI_API_KEY>] [--model <model>]

Requirements:
    pip install "pipecat-ai[google,silero,local]" python-dotenv
"""

import argparse
import asyncio
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PIPECAT] %(message)s")
log = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_DIR, "config.json")

DEFAULT_MODEL = "models/gemini-2.0-flash-exp"
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are J.A.R.V.I.S, a concise, helpful voice assistant. "
    "Reply in short spoken sentences."
)


def _load_config():
    """Read config.json if present; return {} otherwise. Same convention as the Toingg path."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        log.warning("config.json is not valid JSON (%s); ignoring", e)
        return {}


async def run(api_key: str, model: str, system_instruction: str):
    """Build and run the Pipecat pipeline. Imports are local so this module
    can be imported (e.g. for --help) without the Pipecat extras installed."""
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineParams, PipelineTask
        from pipecat.services.gemini_multimodal_live.gemini import (
            GeminiMultimodalLiveLLMService,
        )
        from pipecat.transports.local.audio import (
            LocalAudioTransport,
            LocalAudioTransportParams,
        )
    except ImportError as e:
        log.error(
            "Pipecat is not installed. Install with:\n"
            '    pip install "pipecat-ai[google,silero,local]"\n'
            "Original error: %s",
            e,
        )
        sys.exit(1)

    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )

    llm = GeminiMultimodalLiveLLMService(
        api_key=api_key,
        model=model,
        system_instruction=system_instruction,
    )

    pipeline = Pipeline([transport.input(), llm, transport.output()])
    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    log.info("Starting Pipecat + Gemini pipeline (model=%s)", model)
    await PipelineRunner().run(task)


def main():
    cfg = _load_config()

    parser = argparse.ArgumentParser(description="Pipecat + Gemini backend for J.A.R.V.I.S")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GEMINI_API_KEY") or cfg.get("GEMINI_API_KEY"),
        help="Google Gemini API key (or set GEMINI_API_KEY env var / config.json)",
    )
    parser.add_argument(
        "--model",
        default=cfg.get("GEMINI_MODEL", DEFAULT_MODEL),
        help=f"Gemini model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--system",
        default=cfg.get("SYSTEM_INSTRUCTION", DEFAULT_SYSTEM_INSTRUCTION),
        help="System instruction for the assistant",
    )
    args = parser.parse_args()

    if not args.api_key:
        log.error(
            "Missing Gemini API key. Pass --api-key, set GEMINI_API_KEY, "
            'or add "GEMINI_API_KEY" to config.json. Get one at https://ai.google.dev'
        )
        sys.exit(2)

    try:
        asyncio.run(run(args.api_key, args.model, args.system))
    except KeyboardInterrupt:
        log.info("Stopped by user")


if __name__ == "__main__":
    main()
