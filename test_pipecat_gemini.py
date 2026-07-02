import asyncio
import base64
import importlib
import json
import struct
import sys
import types
import unittest


class DummyInputAudioRawFrame:
    def __init__(self, audio, sample_rate, num_channels):
        self.audio = audio
        self.sample_rate = sample_rate
        self.num_channels = num_channels


class DummyInputTextRawFrame:
    def __init__(self, text):
        self.text = text


class DummyInterruptionFrame:
    pass


class DummyGeminiLiveLLMService:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def event_handler(self, _event_name):
        def decorator(func):
            return func
        return decorator


def _install_pipecat_stubs():
    def module(name):
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    module("pipecat")
    module("pipecat.adapters")
    module("pipecat.adapters.schemas")

    function_schema = module("pipecat.adapters.schemas.function_schema")
    function_schema.FunctionSchema = lambda **kwargs: kwargs

    tools_schema = module("pipecat.adapters.schemas.tools_schema")
    tools_schema.ToolsSchema = lambda **kwargs: kwargs

    silero = module("pipecat.audio.vad.silero")
    silero.SileroVADAnalyzer = object
    module("pipecat.audio")
    module("pipecat.audio.vad")

    frames = module("pipecat.frames.frames")
    frames.InputAudioRawFrame = DummyInputAudioRawFrame
    frames.InputTextRawFrame = DummyInputTextRawFrame
    frames.InterruptionFrame = DummyInterruptionFrame
    module("pipecat.frames")

    pipeline_mod = module("pipecat.pipeline.pipeline")
    pipeline_mod.Pipeline = lambda components: components
    runner_mod = module("pipecat.pipeline.runner")
    runner_mod.PipelineRunner = object
    task_mod = module("pipecat.pipeline.task")
    task_mod.PipelineParams = lambda **kwargs: kwargs
    task_mod.PipelineTask = lambda pipeline, params=None: types.SimpleNamespace(
        pipeline=pipeline,
        params=params,
    )
    module("pipecat.pipeline")

    llm_mod = module("pipecat.services.google.gemini_live.llm")
    llm_mod.GeminiLiveLLMService = DummyGeminiLiveLLMService
    module("pipecat.services")
    module("pipecat.services.google")
    module("pipecat.services.google.gemini_live")


_install_pipecat_stubs()
pipecat_gemini = importlib.import_module("pipecat_gemini")


class FakeTask:
    def __init__(self):
        self.frames = []

    async def queue_frame(self, frame):
        self.frames.append(frame)


class FakeWebSocket:
    def __init__(self, messages):
        self._messages = iter(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._messages)
        except StopIteration:
            raise StopAsyncIteration


class PipecatGeminiBridgeTest(unittest.TestCase):
    def test_float32_base64_audio_is_converted_to_pcm16(self):
        payload = base64.b64encode(struct.pack("<4f", -1.0, 0.0, 0.5, 1.25)).decode()

        pcm = pipecat_gemini._float32_b64_to_pcm16(payload)

        self.assertEqual(
            pcm,
            b"\x01\x80\x00\x00\xff?\xff\x7f",
        )

    def test_websocket_audio_messages_are_forwarded_to_pipeline(self):
        task = FakeTask()
        pipeline = types.SimpleNamespace(task=task)
        bridge = pipecat_gemini.JarvisWebSocketBridge(pipeline)
        payload = base64.b64encode(struct.pack("<1f", 0.25)).decode()
        websocket = FakeWebSocket([
            json.dumps({"type": "audio", "data": payload}),
        ])

        asyncio.run(bridge.handle_ws(websocket))

        self.assertEqual(len(task.frames), 1)
        frame = task.frames[0]
        self.assertIsInstance(frame, DummyInputAudioRawFrame)
        self.assertEqual(frame.sample_rate, pipecat_gemini.BROWSER_AUDIO_SAMPLE_RATE)
        self.assertEqual(frame.num_channels, pipecat_gemini.BROWSER_AUDIO_CHANNELS)
        self.assertEqual(frame.audio, b"\xff\x1f")


if __name__ == "__main__":
    unittest.main()
