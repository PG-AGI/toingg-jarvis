"""
Cross-platform Desktop GUI Controller for Toingg Jarvis.

Provides both a headless-testable controller (`DesktopGuiController`) and a
cross-platform native desktop window (`launch_desktop_gui`) for:
- Starting, stopping, and restarting backend services
- Configuring API keys and model settings
- Selecting the backend provider (Toingg or Pipecat)
- Managing browser automation settings
- Viewing live logs and status indicators
- Controlling scheduled events
- Opening generated files and project directories
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from native_file_manager import execute_file_action

SUPPORTED_PROVIDERS = ("toingg", "pipecat")
MANAGED_SERVICES = ("launcher", "browser_client", "visual_window", "web_backend")

DEFAULT_GUI_CONFIG: Dict[str, Any] = {
    "TOKEN": "",
    "GEMINI_API_KEY": "",
    "PROVIDER": "toingg",
    "MODEL": "gemini-2.5-flash",
    "BROWSER_SETTINGS": {
        "headless": False,
        "window_width": 1280,
        "window_height": 800,
        "ws_url": "ws://localhost:3000/ws",
    },
}


class DesktopGuiConfigError(ValueError):
    """Raised when desktop GUI configuration or service parameters are invalid."""


class DesktopGuiController:
    """State and process controller backing the cross-platform Jarvis desktop GUI."""

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        project_dir: Optional[str | Path] = None,
        process_factory: Optional[Callable[..., Any]] = None,
        schedule_handlers: Optional[Dict[str, Callable[..., Any]]] = None,
    ) -> None:
        base_dir = Path(project_dir) if project_dir else Path(__file__).resolve().parent
        self.project_dir = base_dir.resolve()
        self.config_path = (
            Path(config_path).resolve()
            if config_path
            else self.project_dir / "config.json"
        )
        self._process_factory = process_factory or subprocess.Popen
        self._processes: Dict[str, Any] = {}
        self._logs: List[Dict[str, str]] = []
        self._lock = threading.Lock()
        self._schedule_handlers = schedule_handlers or {}
        self.config = self.load_config()

    def append_log(self, message: str, level: str = "INFO") -> Dict[str, str]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "message": str(message),
        }
        with self._lock:
            self._logs.append(entry)
        return entry

    def get_logs(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        with self._lock:
            items = list(self._logs)
        if limit is not None and limit >= 0:
            return items[-limit:]
        return items

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()

    def load_config(self) -> Dict[str, Any]:
        merged = json.loads(json.dumps(DEFAULT_GUI_CONFIG))
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    browser_cfg = raw.get("BROWSER_SETTINGS")
                    merged.update(
                        {k: v for k, v in raw.items() if k != "BROWSER_SETTINGS"}
                    )
                    if isinstance(browser_cfg, dict):
                        merged["BROWSER_SETTINGS"].update(browser_cfg)
            except Exception as exc:
                self.append_log(f"Failed to read config.json: {exc}", level="WARN")

        provider = str(merged.get("PROVIDER", "toingg")).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            provider = "toingg"
        merged["PROVIDER"] = provider
        self.config = merged
        return merged

    def save_config(self, updates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if updates:
            if not isinstance(updates, dict):
                raise DesktopGuiConfigError("Configuration updates must be a dictionary")
            browser_updates = updates.get("BROWSER_SETTINGS")
            for key, value in updates.items():
                if key == "BROWSER_SETTINGS" and isinstance(browser_updates, dict):
                    self.config.setdefault("BROWSER_SETTINGS", {}).update(
                        browser_updates
                    )
                else:
                    self.config[key] = value

        provider = str(self.config.get("PROVIDER", "toingg")).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise DesktopGuiConfigError(
                f"Provider must be one of: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        self.config["PROVIDER"] = provider

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self.config, indent=2), encoding="utf-8"
        )
        self.append_log("Configuration saved to disk")
        return dict(self.config)

    def set_provider(self, provider: str) -> Dict[str, Any]:
        if not isinstance(provider, str):
            raise DesktopGuiConfigError("Provider must be a string")
        normalized = provider.strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            raise DesktopGuiConfigError(
                f"Unsupported provider '{provider}'. Choose from: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        self.append_log(f"Switched backend provider to {normalized}")
        return self.save_config({"PROVIDER": normalized})

    def update_api_keys(
        self,
        toingg_token: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {}
        if toingg_token is not None:
            if not isinstance(toingg_token, str):
                raise DesktopGuiConfigError("Toingg token must be a string")
            updates["TOKEN"] = toingg_token.strip()
        if gemini_api_key is not None:
            if not isinstance(gemini_api_key, str):
                raise DesktopGuiConfigError("Gemini API key must be a string")
            updates["GEMINI_API_KEY"] = gemini_api_key.strip()
        if model is not None:
            if not isinstance(model, str) or not model.strip():
                raise DesktopGuiConfigError("Model name must be a non-empty string")
            updates["MODEL"] = model.strip()

        self.append_log("Updated API keys and model configuration")
        return self.save_config(updates)

    def update_browser_settings(
        self,
        headless: Optional[bool] = None,
        window_width: Optional[int] = None,
        window_height: Optional[int] = None,
        ws_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        browser_cfg = dict(
            self.config.get(
                "BROWSER_SETTINGS", DEFAULT_GUI_CONFIG["BROWSER_SETTINGS"]
            )
        )

        if headless is not None:
            if not isinstance(headless, bool):
                raise DesktopGuiConfigError("headless must be a boolean")
            browser_cfg["headless"] = headless

        if window_width is not None:
            if (
                isinstance(window_width, bool)
                or not isinstance(window_width, int)
                or window_width < 320
            ):
                raise DesktopGuiConfigError(
                    "window_width must be an integer >= 320"
                )
            browser_cfg["window_width"] = window_width

        if window_height is not None:
            if (
                isinstance(window_height, bool)
                or not isinstance(window_height, int)
                or window_height < 240
            ):
                raise DesktopGuiConfigError(
                    "window_height must be an integer >= 240"
                )
            browser_cfg["window_height"] = window_height

        if ws_url is not None:
            if not isinstance(ws_url, str) or not ws_url.strip().startswith(
                ("ws://", "wss://")
            ):
                raise DesktopGuiConfigError(
                    "ws_url must start with ws:// or wss://"
                )
            browser_cfg["ws_url"] = ws_url.strip()

        self.append_log("Updated browser automation settings")
        return self.save_config({"BROWSER_SETTINGS": browser_cfg})

    def _service_command(self, service_name: str) -> List[str]:
        if service_name not in MANAGED_SERVICES:
            raise DesktopGuiConfigError(
                f"Unknown service '{service_name}'. Expected one of: {', '.join(MANAGED_SERVICES)}"
            )
        if service_name == "browser_client":
            return [sys.executable, str(self.project_dir / "browserClient.py")]
        return [sys.executable, str(self.project_dir / "jarvis_launcher.py")]

    def _is_process_running(self, proc: Any) -> bool:
        if proc is None:
            return False
        poll = getattr(proc, "poll", None)
        if callable(poll):
            return poll() is None
        return False

    def start_service(self, service_name: str) -> Dict[str, Any]:
        cmd = self._service_command(service_name)
        with self._lock:
            existing = self._processes.get(service_name)
            if self._is_process_running(existing):
                self.append_log(f"Service '{service_name}' is already running")
                return {
                    "service": service_name,
                    "status": "running",
                    "pid": getattr(existing, "pid", None),
                }

            proc = self._process_factory(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._processes[service_name] = proc

        self.append_log(f"Started service '{service_name}'")
        return {
            "service": service_name,
            "status": "running",
            "pid": getattr(proc, "pid", None),
            "command": cmd,
        }

    def stop_service(self, service_name: str) -> Dict[str, Any]:
        if service_name not in MANAGED_SERVICES:
            raise DesktopGuiConfigError(
                f"Unknown service '{service_name}'. Expected one of: {', '.join(MANAGED_SERVICES)}"
            )
        with self._lock:
            proc = self._processes.pop(service_name, None)

        if proc and self._is_process_running(proc):
            terminate = getattr(proc, "terminate", None)
            if callable(terminate):
                terminate()
            self.append_log(f"Stopped service '{service_name}'")
        else:
            self.append_log(f"Service '{service_name}' was already stopped")

        return {
            "service": service_name,
            "status": "stopped",
        }

    def restart_service(self, service_name: str) -> Dict[str, Any]:
        self.stop_service(service_name)
        started = self.start_service(service_name)
        self.append_log(f"Restarted service '{service_name}'")
        return started

    def get_service_statuses(self) -> Dict[str, str]:
        statuses: Dict[str, str] = {}
        with self._lock:
            for name in MANAGED_SERVICES:
                proc = self._processes.get(name)
                statuses[name] = (
                    "running" if self._is_process_running(proc) else "stopped"
                )
        return statuses

    def get_status_summary(self) -> Dict[str, Any]:
        statuses = self.get_service_statuses()
        any_running = any(state == "running" for state in statuses.values())
        return {
            "overall": "online" if any_running else "idle",
            "provider": self.config.get("PROVIDER", "toingg"),
            "model": self.config.get("MODEL", "gemini-2.5-flash"),
            "services": statuses,
            "log_count": len(self._logs),
        }

    def schedule_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        create_fn = self._schedule_handlers.get("create")
        if create_fn is None:
            from jarvis_launcher import create_scheduled_action

            create_fn = create_scheduled_action
        item = create_fn(payload)
        self.append_log(f"Scheduled event '{item.get('name', item.get('id'))}'")
        return item

    def list_scheduled_events(self) -> List[Dict[str, Any]]:
        list_fn = self._schedule_handlers.get("list")
        if list_fn is None:
            from jarvis_launcher import list_scheduled_actions

            list_fn = list_scheduled_actions
        return list_fn()

    def cancel_scheduled_event(self, action_id: str) -> bool:
        cancel_fn = self._schedule_handlers.get("cancel")
        if cancel_fn is None:
            from jarvis_launcher import cancel_scheduled_action

            cancel_fn = cancel_scheduled_action
        cancelled = bool(cancel_fn(action_id))
        if cancelled:
            self.append_log(f"Cancelled scheduled event '{action_id}'")
        return cancelled

    def open_project_directory(
        self, path: Optional[str | Path] = None, dry_run: bool = False
    ) -> Dict[str, Any]:
        target = str(Path(path).resolve() if path else self.project_dir)
        plan = execute_file_action("open_directory", target, dry_run=dry_run)
        self.append_log(f"Opened directory: {target}")
        return plan

    def open_generated_file(
        self, path: str | Path, reveal: bool = False, dry_run: bool = False
    ) -> Dict[str, Any]:
        action = "reveal_file" if reveal else "open_file"
        target = str(Path(path).resolve())
        plan = execute_file_action(action, target, dry_run=dry_run)
        self.append_log(f"Executed {action} on: {target}")
        return plan


def launch_desktop_gui(controller: Optional[DesktopGuiController] = None) -> None:
    """Launch the cross-platform Tkinter desktop control interface."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    ctrl = controller or DesktopGuiController()
    root = tk.Tk()
    root.title("Toingg J.A.R.V.I.S - Desktop Control Center")
    root.geometry("820x620")

    status_var = tk.StringVar(value="Status: IDLE")
    provider_var = tk.StringVar(value=ctrl.config.get("PROVIDER", "toingg"))
    token_var = tk.StringVar(value=ctrl.config.get("TOKEN", ""))
    gemini_var = tk.StringVar(value=ctrl.config.get("GEMINI_API_KEY", ""))
    model_var = tk.StringVar(value=ctrl.config.get("MODEL", "gemini-2.5-flash"))

    browser_cfg = ctrl.config.get("BROWSER_SETTINGS", {})
    headless_var = tk.BooleanVar(value=bool(browser_cfg.get("headless", False)))
    width_var = tk.StringVar(value=str(browser_cfg.get("window_width", 1280)))
    height_var = tk.StringVar(value=str(browser_cfg.get("window_height", 800)))
    ws_var = tk.StringVar(
        value=str(browser_cfg.get("ws_url", "ws://localhost:3000/ws"))
    )

    header = ttk.Frame(root, padding=12)
    header.pack(fill=tk.X)
    ttk.Label(
        header,
        text="J.A.R.V.I.S Desktop Control Center",
        font=("Segoe UI", 14, "bold"),
    ).pack(side=tk.LEFT)
    ttk.Label(header, textvariable=status_var).pack(side=tk.RIGHT)

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

    # Services Tab
    services_tab = ttk.Frame(notebook, padding=12)
    notebook.add(services_tab, text="Services & Logs")

    btn_frame = ttk.Frame(services_tab)
    btn_frame.pack(fill=tk.X, pady=(0, 8))

    log_box = tk.Text(services_tab, height=16, state=tk.DISABLED)
    log_box.pack(fill=tk.BOTH, expand=True)

    def refresh_ui() -> None:
        summary = ctrl.get_status_summary()
        status_var.set(
            f"Status: {summary['overall'].upper()} | Provider: {summary['provider']}"
        )
        log_box.configure(state=tk.NORMAL)
        log_box.delete("1.0", tk.END)
        for item in ctrl.get_logs(limit=100):
            log_box.insert(
                tk.END,
                f"[{item['timestamp']}] [{item['level']}] {item['message']}\n",
            )
        log_box.configure(state=tk.DISABLED)

    for svc in ("launcher", "browser_client"):
        ttk.Button(
            btn_frame,
            text=f"Start {svc}",
            command=lambda s=svc: (ctrl.start_service(s), refresh_ui()),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_frame,
            text=f"Stop {svc}",
            command=lambda s=svc: (ctrl.stop_service(s), refresh_ui()),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_frame,
            text=f"Restart {svc}",
            command=lambda s=svc: (ctrl.restart_service(s), refresh_ui()),
        ).pack(side=tk.LEFT, padx=4)

    # Settings Tab
    settings_tab = ttk.Frame(notebook, padding=12)
    notebook.add(settings_tab, text="Provider & API Keys")

    ttk.Label(settings_tab, text="Backend Provider:").grid(
        row=0, column=0, sticky=tk.W, pady=4
    )
    provider_combo = ttk.Combobox(
        settings_tab,
        textvariable=provider_var,
        values=list(SUPPORTED_PROVIDERS),
        state="readonly",
    )
    provider_combo.grid(row=0, column=1, sticky=tk.EW, pady=4)

    ttk.Label(settings_tab, text="Toingg API Token:").grid(
        row=1, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(settings_tab, textvariable=token_var, width=48).grid(
        row=1, column=1, sticky=tk.EW, pady=4
    )

    ttk.Label(settings_tab, text="Gemini API Key:").grid(
        row=2, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(settings_tab, textvariable=gemini_var, width=48).grid(
        row=2, column=1, sticky=tk.EW, pady=4
    )

    ttk.Label(settings_tab, text="Model Name:").grid(
        row=3, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(settings_tab, textvariable=model_var, width=48).grid(
        row=3, column=1, sticky=tk.EW, pady=4
    )

    def save_settings() -> None:
        try:
            ctrl.set_provider(provider_var.get())
            ctrl.update_api_keys(
                toingg_token=token_var.get(),
                gemini_api_key=gemini_var.get(),
                model=model_var.get(),
            )
            ctrl.update_browser_settings(
                headless=headless_var.get(),
                window_width=int(width_var.get()),
                window_height=int(height_var.get()),
                ws_url=ws_var.get(),
            )
            refresh_ui()
            messagebox.showinfo("Saved", "Settings saved to config.json")
        except Exception as exc:
            messagebox.showerror("Validation Error", str(exc))

    ttk.Button(settings_tab, text="Save Configuration", command=save_settings).grid(
        row=4, column=1, sticky=tk.E, pady=12
    )

    # Browser & Files Tab
    browser_tab = ttk.Frame(notebook, padding=12)
    notebook.add(browser_tab, text="Browser & Files")

    ttk.Checkbutton(
        browser_tab, text="Headless Browser Automation", variable=headless_var
    ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=4)
    ttk.Label(browser_tab, text="Window Width:").grid(
        row=1, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(browser_tab, textvariable=width_var, width=20).grid(
        row=1, column=1, sticky=tk.W, pady=4
    )
    ttk.Label(browser_tab, text="Window Height:").grid(
        row=2, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(browser_tab, textvariable=height_var, width=20).grid(
        row=2, column=1, sticky=tk.W, pady=4
    )
    ttk.Label(browser_tab, text="Playwright WS URL:").grid(
        row=3, column=0, sticky=tk.W, pady=4
    )
    ttk.Entry(browser_tab, textvariable=ws_var, width=40).grid(
        row=3, column=1, sticky=tk.W, pady=4
    )

    ttk.Button(
        browser_tab,
        text="Open Project Directory",
        command=lambda: (ctrl.open_project_directory(), refresh_ui()),
    ).grid(row=4, column=0, sticky=tk.W, pady=12)

    def browse_and_open_file() -> None:
        chosen = filedialog.askopenfilename(initialdir=str(ctrl.project_dir))
        if chosen:
            ctrl.open_generated_file(chosen)
            refresh_ui()

    ttk.Button(
        browser_tab, text="Open Generated File...", command=browse_and_open_file
    ).grid(row=4, column=1, sticky=tk.W, pady=12)

    refresh_ui()
    root.mainloop()


if __name__ == "__main__":
    launch_desktop_gui()
