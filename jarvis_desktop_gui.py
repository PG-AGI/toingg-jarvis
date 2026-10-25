"""
jarvis_desktop_gui.py — Cross-platform desktop GUI for JARVIS terminal & backend controls.

Provides a unified control center (`JarvisDesktopController`) and native desktop GUI window
for Windows, macOS, and Linux to:
1. Start, stop, and restart backend services (`jarvis_launcher.py`, `browserClient.py`).
2. Configure API keys (`TOKEN`, `GEMINI_API_KEY`), campaign ID, and model settings.
3. Select the active backend provider (`toingg` vs `pipecat_gemini`).
4. Manage browser automation settings (headless mode, profile dir, monitor, window size, position).
5. View live logs and service status (`/state` & process health).
6. Control scheduled events/tasks (`/scheduled_actions`, `/schedule_action`, `/cancel_scheduled_action`).
7. Open generated files or output directories via `native_file_manager.py`.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from native_file_manager import execute_file_action


SUPPORTED_PROVIDERS = ("toingg", "pipecat_gemini")
SUPPORTED_SERVICES = ("launcher", "browser_client")

DEFAULT_GUI_CONFIG: dict[str, Any] = {
    "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
    "TOKEN": "",
    "CAMP_ID": "",
    "PROVIDER": "toingg",
    "GEMINI_API_KEY": "",
    "MODEL": "gemini-2.5-flash",
    "browser": {
        "headless": False,
        "user_data_dir": ".browser-profile",
        "ws_url": "wss://prepodapi.toingg.com/api/v3/media/browser/default",
        "preferred_monitor": "active",
        "window_size": "860x580",
        "position": "grid",
    },
}


class JarvisGuiConfigError(ValueError):
    """Raised when desktop GUI configuration or control parameters are invalid."""


class JarvisDesktopController:
    """Headless-testable controller backing the cross-platform JARVIS desktop GUI."""

    def __init__(
        self,
        *,
        base_dir: str | os.PathLike[str] | None = None,
        config_path: str | os.PathLike[str] | None = None,
        launcher_url: str = "http://localhost:8766",
        popen_factory: Callable[..., Any] | None = None,
        http_requester: Callable[[str, str, dict[str, Any] | None], dict[str, Any]] | None = None,
        max_log_lines: int = 500,
    ) -> None:
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent)
        self.config_path = Path(config_path) if config_path else (self.base_dir / "config.json")
        self.launcher_url = launcher_url.rstrip("/")
        self._popen = popen_factory or subprocess.Popen
        self._http_requester = http_requester or self._default_http_request
        self._processes: dict[str, Any] = {"launcher": None, "browser_client": None}
        self._logs: collections.deque[str] = collections.deque(maxlen=max_log_lines)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Logging & Status
    # ------------------------------------------------------------------

    def append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self._lock:
            self._logs.append(line)

    def get_logs(self, limit: int = 200) -> list[str]:
        with self._lock:
            items = list(self._logs)
        return items[-max(1, int(limit)) :]

    # ------------------------------------------------------------------
    # Configuration & Provider Selection
    # ------------------------------------------------------------------

    def load_config(self) -> dict[str, Any]:
        merged = json.loads(json.dumps(DEFAULT_GUI_CONFIG))
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if k == "browser" and isinstance(v, dict):
                            merged["browser"].update(v)
                        else:
                            merged[k] = v
            except Exception as exc:
                self.append_log(f"Warning: could not parse {self.config_path.name}: {exc}")
        return merged

    def save_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict):
            raise JarvisGuiConfigError("Configuration updates must be a JSON object")

        cfg = self.load_config()
        if "PROVIDER" in updates:
            provider = str(updates["PROVIDER"]).strip().lower()
            if provider not in SUPPORTED_PROVIDERS:
                raise JarvisGuiConfigError(
                    f"Unsupported provider {provider!r}; expected one of {SUPPORTED_PROVIDERS}"
                )
            cfg["PROVIDER"] = provider

        for top_key in ("WS_URL", "TOKEN", "CAMP_ID", "GEMINI_API_KEY", "MODEL"):
            if top_key in updates and updates[top_key] is not None:
                cfg[top_key] = str(updates[top_key]).strip()

        if "browser" in updates:
            if not isinstance(updates["browser"], dict):
                raise JarvisGuiConfigError("browser settings must be a dictionary")
            browser_cfg = dict(cfg.get("browser") or {})
            for b_key in (
                "headless",
                "user_data_dir",
                "ws_url",
                "preferred_monitor",
                "window_size",
                "position",
            ):
                if b_key in updates["browser"] and updates["browser"][b_key] is not None:
                    val = updates["browser"][b_key]
                    browser_cfg[b_key] = bool(val) if b_key == "headless" else val
            cfg["browser"] = browser_cfg

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        self.append_log(f"Saved configuration (provider={cfg['PROVIDER']}, model={cfg['MODEL']})")
        return cfg

    # ------------------------------------------------------------------
    # Service Lifecycle (Start / Stop / Restart)
    # ------------------------------------------------------------------

    def _build_service_command(self, service: str) -> list[str]:
        if service not in SUPPORTED_SERVICES:
            raise JarvisGuiConfigError(
                f"Unknown service {service!r}; expected one of {SUPPORTED_SERVICES}"
            )
        cfg = self.load_config()
        browser_cfg = cfg.get("browser", {})

        if service == "launcher":
            script = str(self.base_dir / "jarvis_launcher.py")
            return [sys.executable, script]

        script = str(self.base_dir / "browserClient.py")
        cmd = [
            sys.executable,
            script,
            "--url",
            str(browser_cfg.get("ws_url") or DEFAULT_GUI_CONFIG["browser"]["ws_url"]),
            "--user-data-dir",
            str(browser_cfg.get("user_data_dir") or ".browser-profile"),
        ]
        if browser_cfg.get("headless"):
            cmd.append("--headless")
        return cmd

    def is_service_running(self, service: str) -> bool:
        proc = self._processes.get(service)
        return bool(proc is not None and proc.poll() is None)

    def start_service(self, service: str) -> dict[str, Any]:
        if service not in SUPPORTED_SERVICES:
            raise JarvisGuiConfigError(f"Unsupported service: {service!r}")
        if self.is_service_running(service):
            proc = self._processes[service]
            return {"service": service, "status": "running", "pid": getattr(proc, "pid", None)}

        cmd = self._build_service_command(service)
        env = os.environ.copy()
        cfg = self.load_config()
        env["JARVIS_PROVIDER"] = str(cfg.get("PROVIDER", "toingg"))
        env["JARVIS_MODEL"] = str(cfg.get("MODEL", "gemini-2.5-flash"))

        proc = self._popen(
            cmd,
            cwd=str(self.base_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._processes[service] = proc
        self.append_log(f"Started {service} (pid={getattr(proc, 'pid', 'n/a')})")

        if getattr(proc, "stdout", None) is not None:
            threading.Thread(
                target=self._stream_process_output,
                args=(service, proc),
                daemon=True,
            ).start()

        return {"service": service, "status": "running", "pid": getattr(proc, "pid", None), "command": cmd}

    def _stream_process_output(self, service: str, proc: Any) -> None:
        try:
            for raw_line in proc.stdout:
                line = str(raw_line).rstrip()
                if line:
                    self.append_log(f"[{service}] {line}")
        except Exception:
            pass

    def stop_service(self, service: str) -> dict[str, Any]:
        if service not in SUPPORTED_SERVICES:
            raise JarvisGuiConfigError(f"Unsupported service: {service!r}")
        proc = self._processes.get(service)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                if hasattr(proc, "wait"):
                    proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._processes[service] = None
        self.append_log(f"Stopped {service}")
        return {"service": service, "status": "stopped"}

    def restart_service(self, service: str) -> dict[str, Any]:
        self.stop_service(service)
        return self.start_service(service)

    def get_service_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "services": {
                svc: {
                    "running": self.is_service_running(svc),
                    "pid": getattr(self._processes.get(svc), "pid", None)
                    if self.is_service_running(svc)
                    else None,
                }
                for svc in SUPPORTED_SERVICES
            },
            "launcher_state": {"state": "offline", "status": "OFFLINE"},
        }
        try:
            remote_state = self._http_requester("GET", "/state", None)
            if isinstance(remote_state, dict):
                status["launcher_state"] = remote_state
        except Exception:
            pass
        return status

    # ------------------------------------------------------------------
    # Scheduled Events & Browser / File Actions
    # ------------------------------------------------------------------

    def _default_http_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.launcher_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": True}

    def list_scheduled_events(self) -> list[dict[str, Any]]:
        res = self._http_requester("GET", "/scheduled_actions", None)
        return list(res.get("items", [])) if isinstance(res, dict) else []

    def schedule_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise JarvisGuiConfigError("Schedule payload must be a JSON object")
        res = self._http_requester("POST", "/schedule_action", payload)
        self.append_log(f"Scheduled task: {payload.get('name', 'unnamed')}")
        return res

    def cancel_scheduled_event(self, action_id: str) -> dict[str, Any]:
        if not isinstance(action_id, str) or not action_id.strip():
            raise JarvisGuiConfigError("action_id must be a non-empty string")
        res = self._http_requester("POST", "/cancel_scheduled_action", {"id": action_id.strip()})
        self.append_log(f"Cancelled scheduled task: {action_id.strip()}")
        return res

    def trigger_file_action(
        self,
        action: str,
        path: str,
        *,
        dry_run: bool = False,
        system: str | None = None,
    ) -> dict[str, Any]:
        result = execute_file_action(action, path, dry_run=dry_run, system=system)
        self.append_log(f"File action: {result['action']} -> {result['path']}")
        return result


def launch_tkinter_gui(controller: JarvisDesktopController) -> None:
    """Launch the cross-platform Tkinter desktop window for JARVIS controls."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("TOINGG // J.A.R.V.I.S. — Cross-Platform Control Center")
    root.geometry("980x680")
    root.configure(bg="#0d1117")

    cfg = controller.load_config()
    browser_cfg = cfg.get("browser", {})

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=12, pady=12)

    # 1. Services & Status Tab
    svc_frame = ttk.Frame(notebook, padding=16)
    notebook.add(svc_frame, text="Services & Live Logs")

    status_var = tk.StringVar(value="Launcher: stopped | Browser Client: stopped")
    ttk.Label(svc_frame, textvariable=status_var, font=("Consolas", 11, "bold")).pack(anchor="w", pady=(0, 10))

    btn_row = ttk.Frame(svc_frame)
    btn_row.pack(fill="x", pady=6)

    def _refresh_status() -> None:
        st = controller.get_service_status()
        l_run = "running" if st["services"]["launcher"]["running"] else "stopped"
        b_run = "running" if st["services"]["browser_client"]["running"] else "stopped"
        remote = st["launcher_state"].get("status", "OFFLINE")
        status_var.set(f"Launcher: {l_run} ({remote}) | Browser Client: {b_run}")
        log_box.delete("1.0", tk.END)
        log_box.insert(tk.END, "\n".join(controller.get_logs(150)))

    for svc_label, svc_key in (("Launcher", "launcher"), ("Browser Client", "browser_client")):
        ttk.Button(
            btn_row,
            text=f"Start {svc_label}",
            command=lambda s=svc_key: (controller.start_service(s), _refresh_status()),
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row,
            text=f"Stop {svc_label}",
            command=lambda s=svc_key: (controller.stop_service(s), _refresh_status()),
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row,
            text=f"Restart {svc_label}",
            command=lambda s=svc_key: (controller.restart_service(s), _refresh_status()),
        ).pack(side="left", padx=4)

    ttk.Button(btn_row, text="Refresh Status", command=_refresh_status).pack(side="right", padx=4)

    log_box = tk.Text(svc_frame, height=22, bg="#161b22", fg="#c9d1d9", font=("Consolas", 10))
    log_box.pack(fill="both", expand=True, pady=8)

    # 2. Provider, API Keys & Browser Settings Tab
    cfg_frame = ttk.Frame(notebook, padding=16)
    notebook.add(cfg_frame, text="Provider, API Keys & Browser")

    provider_var = tk.StringVar(value=str(cfg.get("PROVIDER", "toingg")))
    token_var = tk.StringVar(value=str(cfg.get("TOKEN", "")))
    gemini_var = tk.StringVar(value=str(cfg.get("GEMINI_API_KEY", "")))
    model_var = tk.StringVar(value=str(cfg.get("MODEL", "gemini-2.5-flash")))
    camp_var = tk.StringVar(value=str(cfg.get("CAMP_ID", "")))
    ws_var = tk.StringVar(value=str(cfg.get("WS_URL", "")))
    monitor_var = tk.StringVar(value=str(browser_cfg.get("preferred_monitor", "active")))
    winsize_var = tk.StringVar(value=str(browser_cfg.get("window_size", "860x580")))
    pos_var = tk.StringVar(value=str(browser_cfg.get("position", "grid")))
    headless_var = tk.BooleanVar(value=bool(browser_cfg.get("headless", False)))

    fields = [
        ("Backend Provider (toingg / pipecat_gemini):", provider_var),
        ("Toingg API Key (TOKEN):", token_var),
        ("Gemini API Key (GEMINI_API_KEY):", gemini_var),
        ("LLM Model:", model_var),
        ("Campaign ID (CAMP_ID):", camp_var),
        ("Streaming WebSocket URL:", ws_var),
        ("Preferred Monitor (active / primary / 0 / 1):", monitor_var),
        ("New Tab Window Size (e.g. 1280x800):", winsize_var),
        ("Window Position (grid / center / top-left / x=...,y=...):", pos_var),
    ]
    for idx, (label_text, var) in enumerate(fields):
        ttk.Label(cfg_frame, text=label_text).grid(row=idx, column=0, sticky="w", pady=4, padx=6)
        ttk.Entry(cfg_frame, textvariable=var, width=54).grid(row=idx, column=1, sticky="ew", pady=4, padx=6)

    ttk.Checkbutton(cfg_frame, text="Run Playwright Browser in Headless Mode", variable=headless_var).grid(
        row=len(fields), column=1, sticky="w", pady=6
    )

    def _save_gui_config() -> None:
        try:
            controller.save_config(
                {
                    "PROVIDER": provider_var.get(),
                    "TOKEN": token_var.get(),
                    "GEMINI_API_KEY": gemini_var.get(),
                    "MODEL": model_var.get(),
                    "CAMP_ID": camp_var.get(),
                    "WS_URL": ws_var.get(),
                    "browser": {
                        "preferred_monitor": monitor_var.get(),
                        "window_size": winsize_var.get(),
                        "position": pos_var.get(),
                        "headless": headless_var.get(),
                    },
                }
            )
            _refresh_status()
            messagebox.showinfo("Saved", "Configuration saved to config.json")
        except Exception as exc:
            messagebox.showerror("Validation Error", str(exc))

    ttk.Button(cfg_frame, text="Save Configuration", command=_save_gui_config).grid(
        row=len(fields) + 1, column=1, sticky="e", pady=10
    )

    # 3. Scheduled Tasks & Native File Actions Tab
    ops_frame = ttk.Frame(notebook, padding=16)
    notebook.add(ops_frame, text="Scheduled Tasks & File Manager")

    sched_name_var = tk.StringVar(value="Open Dashboard")
    sched_url_var = tk.StringVar(value="https://prepodapp.toingg.com")
    sched_delay_var = tk.StringVar(value="30")

    ttk.Label(ops_frame, text="Schedule Task Name:").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(ops_frame, textvariable=sched_name_var, width=40).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(ops_frame, text="Target URL:").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(ops_frame, textvariable=sched_url_var, width=40).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(ops_frame, text="Delay Seconds:").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(ops_frame, textvariable=sched_delay_var, width=16).grid(row=2, column=1, sticky="w", pady=4)

    def _queue_task() -> None:
        try:
            controller.schedule_event(
                {
                    "name": sched_name_var.get(),
                    "trigger": {"delay_seconds": float(sched_delay_var.get() or 0)},
                    "actions": [{"type": "open_url", "url": sched_url_var.get()}],
                }
            )
            _refresh_status()
        except Exception as exc:
            messagebox.showerror("Schedule Error", str(exc))

    ttk.Button(ops_frame, text="Schedule Open URL Task", command=_queue_task).grid(row=3, column=1, sticky="w", pady=8)

    file_target_var = tk.StringVar(value=str(controller.base_dir))
    ttk.Label(ops_frame, text="File / Output Directory Path:").grid(row=4, column=0, sticky="w", pady=12)
    ttk.Entry(ops_frame, textvariable=file_target_var, width=50).grid(row=4, column=1, sticky="w", pady=12)

    file_btns = ttk.Frame(ops_frame)
    file_btns.grid(row=5, column=1, sticky="w")
    ttk.Button(
        file_btns,
        text="Browse Folder",
        command=lambda: file_target_var.set(filedialog.askdirectory() or file_target_var.get()),
    ).pack(side="left", padx=4)
    for act in ("open_directory", "open_file", "reveal_file"):
        ttk.Button(
            file_btns,
            text=act,
            command=lambda a=act: controller.trigger_file_action(a, file_target_var.get()),
        ).pack(side="left", padx=4)

    _refresh_status()
    root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-platform desktop GUI for JARVIS terminal controls")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--launcher-url", default="http://localhost:8766", help="JARVIS Launcher HTTP URL")
    parser.add_argument("--headless-check", action="store_true", help="Print controller status JSON and exit")
    args = parser.parse_args(argv)

    controller = JarvisDesktopController(
        config_path=args.config,
        launcher_url=args.launcher_url,
    )
    if args.headless_check:
        print(json.dumps(controller.get_service_status(), indent=2))
        return 0

    launch_tkinter_gui(controller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
