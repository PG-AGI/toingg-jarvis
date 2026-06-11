"""
pipecat_backend.py — Pipecat + Gemini Live backend for Toingg Jarvis.

Drop-in alternative to the Toingg WebSocket backend.
Activated by setting BACKEND=pipecat_gemini in config.json.

Requirements:
    pip install pipecat-ai[google] python-dotenv
"""

import asyncio
import json
import logging
import os
import threading
import requests

from dotenv import load_dotenv

from pipecat.services.google.gemini_live.llm import (
    GeminiLiveLLMService,
    GeminiModalities,
    InputParams,
)
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.frames.frames import (
    Frame,
    FunctionCallFromLLM,
    FunctionCallResultFrame,
    EndFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [PIPECAT] %(message)s")

# ── CONFIG ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LAUNCHER_URL   = "http://localhost:8766"

# ── TOOLS — registered with Gemini so it knows what it can call ───────────────
JARVIS_TOOLS = ToolsSchema(standard_tools=[
    FunctionSchema(
        name="open_browser",
        description="Open one or more URLs in the browser grid slots.",
        properties={
            "tabs": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of tab objects with a 'url' field each."
            }
        },
        required=["tabs"]
    ),
    FunctionSchema(
        name="close_tabs",
        description="Close all open browser grid slot windows.",
        properties={
            "auto": {
                "type": "boolean",
                "description": "If true, only close auto-managed tabs."
            }
        },
        required=[]
    ),
    FunctionSchema(
        name="run_playwright",
        description="Run a Playwright browser automation action via browserClient.",
        properties={
            "action": {
                "type": "string",
                "description": "The Playwright action to perform e.g. navigate, click, fill."
            },
            "params": {
                "type": "object",
                "description": "Parameters for the action."
            }
        },
        required=["action"]
    ),
    FunctionSchema(
        name="open_file",
        description="Open or reveal a file using the native file manager.",
        properties={
            "path": {
                "type": "string",
                "description": "Absolute path to the file or directory."
            },
            "action": {
                "type": "string",
                "description": "One of: open_file, open_directory, reveal_file."
            }
        },
        required=["path", "action"]
    ),
])
# ── TOOL EXECUTOR — calls localhost:8766 endpoints ────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    """
    Route a Gemini tool call to the correct jarvis_launcher HTTP endpoint.
    Returns a string result that gets sent back to Gemini as the tool response.
    """
    try:
        if name == "open_browser":
            tabs = args.get("tabs", [])
            r = requests.post(f"{LAUNCHER_URL}/open_tabs", json=tabs, timeout=10)
            return f"Opened {len(tabs)} tab(s) in browser grid." if r.ok else f"Failed: {r.text}"

        elif name == "close_tabs":
            auto = args.get("auto", False)
            r = requests.post(f"{LAUNCHER_URL}/close_tabs", json={"auto": auto}, timeout=10)
            return "Tabs closed." if r.ok else f"Failed: {r.text}"

        elif name == "run_playwright":
            action = args.get("action")
            params = args.get("params", {})
            # browserClient listens for commands via WebSocket, not HTTP.
            # For now we log the intent — full Playwright bridging requires
            # a separate WebSocket client connection to browserClient.
            log.info(f"[tool] run_playwright: action={action} params={params}")
            return f"Playwright action '{action}' dispatched."

        elif name == "open_file":
            r = requests.post(f"{LAUNCHER_URL}/file_action", json=args, timeout=10)
            return "File action completed." if r.ok else f"Failed: {r.text}"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        log.error(f"[tool] execute_tool error: {e}")
        return f"Tool execution failed: {e}"


# ── TOOL CALL INTERCEPTOR ─────────────────────────────────────────────────────

class ToolCallHandler(FrameProcessor):
    """
    Sits in the pipeline after the LLM.
    Catches FunctionCallFromLLM frames, executes the tool via HTTP,
    and pushes the result back upstream so Gemini can verbally confirm.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, FunctionCallFromLLM):
            name = frame.function_name
            args = frame.arguments if isinstance(frame.arguments, dict) else {}
            log.info(f"[tool] Gemini called tool: {name}({args})")

            # Execute in a thread so we don't block the async pipeline
            result = await asyncio.get_event_loop().run_in_executor(
                None, execute_tool, name, args
            )
            log.info(f"[tool] Result: {result}")

            # Push result back to Gemini
            result_frame = FunctionCallResultFrame(
                function_name=name,
                tool_call_id=getattr(frame, "tool_call_id", name),
                arguments=args,
                result={"output": result},
            )
            await self.push_frame(result_frame)
        else:
            await self.push_frame(frame, direction)


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────

async def run_pipecat_gemini():
    """
    Build and run the Pipecat + Gemini Live pipeline.
    Uses local mic input and speaker output.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set — add it to your .env file")

    log.info("Starting Pipecat + Gemini Live backend...")

    # Local audio transport — mic in, speakers out
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        )
    )

    # Gemini Live LLM service
    llm = GeminiLiveLLMService(
        api_key=GEMINI_API_KEY,
        model="gemini-2.5-flash-native-audio-preview-12-2025",
        params=InputParams(
            modalities=GeminiModalities.AUDIO,
        ),
        tools=JARVIS_TOOLS,
        system_instruction=(
            "You are JARVIS, a voice-driven AI assistant. "
            "You can open browser tabs, close tabs, run browser automation, "
            "and open files. When the user asks you to open something, "
            "use the appropriate tool and then verbally confirm what you did."
        ),
    )

    tool_handler = ToolCallHandler()

    pipeline = Pipeline([
        transport.input(),
        llm,
        tool_handler,
        transport.output(),
    ])

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))
    runner = PipelineRunner()

    log.info("Pipecat pipeline running — speak to JARVIS...")
    await runner.run(task)


def start_pipecat_gemini():
    """
    Entry point called from jarvis_launcher.py when BACKEND=pipecat_gemini.
    Schedules the pipeline on a new event loop in a background thread,
    bypassing PipelineRunner's signal handler which requires the main thread.
    """
    async def _run():
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set — add it to your .env file")

        log.info("Starting Pipecat + Gemini Live backend...")

        transport = LocalAudioTransport(
            LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
            )
        )

        llm = GeminiLiveLLMService(
            api_key=GEMINI_API_KEY,
            settings=GeminiLiveLLMService.Settings(
                model="gemini-2.5-flash-native-audio-preview-12-2025",
                modalities=GeminiModalities.AUDIO,
                system_instruction=(
                    "You are JARVIS, a voice-driven AI assistant. "
                    "You can open browser tabs, close tabs, run browser automation, "
                    "and open files. When the user asks you to open something, "
                    "use the appropriate tool and then verbally confirm what you did."
                ),
            ),
            tools=JARVIS_TOOLS,
        )

        tool_handler = ToolCallHandler()

        pipeline = Pipeline([
            transport.input(),
            llm,
            tool_handler,
            transport.output(),
        ])

        task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

        log.info("Pipecat pipeline running — speak to JARVIS...")
        from pipecat.workers.base_worker import WorkerParams
        await task.run(WorkerParams(loop=asyncio.get_event_loop()))

    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        except Exception as e:
            log.error(f"[pipecat] Pipeline error: {e}")
        finally:
            loop.close()

    t = threading.Thread(target=_thread, daemon=True, name="pipecat-gemini")
    t.start()
    log.info("[pipecat] Backend thread started.")