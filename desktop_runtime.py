"""Dependency-free configuration and process control for the desktop app."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


DEFAULTS = {
    "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
    "TOKEN": "",
    "CAMP_ID": "",
    "BROWSER_HEADLESS": False,
    "VOICE_ENABLED": True,
}


class ConfigStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return dict(DEFAULTS)
        with self.path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object.")
        return {**DEFAULTS, **data}

    def save(self, changes):
        data = {**self.load(), **changes}
        for name in ("TOKEN", "CAMP_ID", "WS_URL"):
            if not isinstance(data[name], str):
                raise ValueError(name + " must be text.")
        endpoint = urlsplit(data["WS_URL"])
        if endpoint.scheme not in ("ws", "wss") or not endpoint.hostname:
            raise ValueError("The streaming URL must start with ws:// or wss://.")
        for name in ("BROWSER_HEADLESS", "VOICE_ENABLED"):
            if not isinstance(data[name], bool):
                raise ValueError(name + " must be true or false.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".json")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return data


class LauncherService:
    """Own exactly one launcher. Never discover or terminate unrelated processes."""

    def __init__(self, project_dir, port=8766):
        self.project_dir = Path(project_dir)
        self.port = port
        self.process = None
        self.ready = threading.Event()
        self.logs = queue.Queue(maxsize=2000)
        self._reader = None
        self._secrets = []

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, config):
        if self.running:
            raise RuntimeError("The launcher is already running.")
        if self._reader is not None:
            self._reader.join(timeout=2)
            if self._reader.is_alive():
                raise RuntimeError("The previous launcher is still shutting down.")
        self.ready.clear()
        self._secrets = [config.get("TOKEN", "")]
        command = [sys.executable, "-u", str(self.project_dir / "jarvis_launcher.py"),
                   "--desktop-managed", "--http-port", str(self.port)]
        if not config.get("VOICE_ENABLED", True):
            command.append("--no-voice")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.process = subprocess.Popen(
            command, cwd=self.project_dir, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **options,
        )
        self._reader = threading.Thread(target=self._read_logs, args=(self.process,), daemon=True)
        self._reader.start()

    def _read_logs(self, process):
        try:
            for line in process.stdout:
                if line.strip() == "JARVIS_DESKTOP_READY":
                    self.ready.set()
                    continue
                for secret in self._secrets:
                    if secret:
                        line = line.replace(secret, "[redacted]")
                try:
                    self.logs.put_nowait(line.rstrip())
                except queue.Full:
                    try:
                        self.logs.get_nowait()
                    except queue.Empty:
                        pass  # The UI may have drained the queue in the meantime.
                    self.logs.put_nowait(line.rstrip())
        finally:
            process.stdout.close()
            self.ready.clear()

    def stop(self, timeout=5):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            try:
                process.stdin.write("stop\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=timeout)
        if process.stdin:
            process.stdin.close()
        if self._reader is not None:
            self._reader.join(timeout=2)
        self.ready.clear()

    def request(self, path, payload=None):
        if not self.running or not self.ready.is_set():
            raise RuntimeError("Start the launcher and wait until it is ready.")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request("http://127.0.0.1:%s%s" % (self.port, path), data=body,
                      headers={"Content-Type": "application/json"})
        with build_opener(ProxyHandler({})).open(req, timeout=3) as response:
            return json.load(response)
