"""Native desktop controls. Run with: python jarvis_desktop.py."""

from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser

from desktop_runtime import ConfigStore, LauncherService


class DesktopApp:
    def __init__(self, root, project_dir=None):
        self.root = root
        self.project_dir = Path(project_dir or Path(__file__).resolve().parent)
        self.store = ConfigStore(self.project_dir / "config.json")
        self.service = LauncherService(self.project_dir)
        self.results = queue.Queue()
        self.busy = False
        self.closing = False
        self.root.title("JARVIS — Desktop controls")
        self.root.geometry("880x680")
        self.root.minsize(720, 580)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="JARVIS", font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Stopped")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(4, 12))
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 14))
        self.buttons = []
        for title, command in (("Start", self.start), ("Stop", self.stop),
                               ("Restart", self.restart), ("Open terminal", self.open_terminal)):
            button = ttk.Button(controls, text=title, command=command)
            button.pack(side="left", padx=(0, 8))
            self.buttons.append(button)
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="both", expand=True)
        self.settings_tab = ttk.Frame(tabs, padding=16)
        self.schedule_tab = ttk.Frame(tabs, padding=16)
        logs_tab = ttk.Frame(tabs, padding=8)
        tabs.add(self.settings_tab, text="Settings")
        tabs.add(self.schedule_tab, text="Scheduled actions")
        tabs.add(logs_tab, text="Logs")
        self._settings()
        self._schedules()
        self.log = ScrolledText(logs_tab, wrap="word", state="disabled", height=14)
        self.log.pack(fill="both", expand=True)
        ttk.Button(logs_tab, text="Clear logs", command=self.clear_logs).pack(anchor="e", pady=(8, 0))
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="Open project folder", command=self.open_project).pack(side="left")
        ttk.Button(footer, text="Open local file…", command=self.open_file).pack(side="left", padx=8)
        self.load_settings()
        self.root.after(150, self.tick)

    def _settings(self):
        tab = self.settings_tab
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="Backend").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=6)
        ttk.Label(tab, text="Toingg").grid(row=0, column=1, sticky="w")
        ttk.Label(tab, text="Pipecat has a tool bridge only in this version; a standalone backend is not yet available.",
                  wraplength=600).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.values = {}
        for row, (key, label) in enumerate((("TOKEN", "API key"), ("CAMP_ID", "Campaign ID"),
                                             ("WS_URL", "Streaming URL")), start=2):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=8)
            self.values[key] = tk.StringVar()
            entry = ttk.Entry(tab, textvariable=self.values[key], show="•" if key == "TOKEN" else "")
            entry.grid(row=row, column=1, sticky="ew")
        ttk.Label(tab, text="Model and voice settings are managed by your Toingg campaign.", wraplength=600).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=8)
        self.voice = tk.BooleanVar(value=True)
        self.headless = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab, text="Listen for the wake word (uses microphone)", variable=self.voice).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Checkbutton(tab, text="Run browser automation without a visible browser", variable=self.headless).grid(
            row=7, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(tab, text="Save settings, then restart the launcher and reopen the web terminal to apply changes.",
                  wraplength=600).grid(row=8, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(tab, text="Save settings", command=self.save_settings).grid(row=9, column=1, sticky="e")

    def _schedules(self):
        tab = self.schedule_tab
        ttk.Label(tab, text="Open a URL later. Actions live in launcher memory and are cleared on restart.",
                  wraplength=650).pack(anchor="w", pady=(0, 10))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        self.schedule_url = tk.StringVar()
        self.delay = tk.StringVar(value="60")
        ttk.Label(form, text="URL").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.schedule_url).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(form, text="Delay (seconds)").grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.delay, width=12).grid(row=1, column=1, sticky="w", pady=4)
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text="Schedule", command=self.schedule).grid(row=1, column=2, padx=8)
        self.events = ttk.Treeview(tab, columns=("name", "time", "status"), show="headings", height=9)
        for name, label, width in (("name", "Action", 230), ("time", "Scheduled for", 220), ("status", "Status", 110)):
            self.events.heading(name, text=label)
            self.events.column(name, width=width)
        self.events.pack(fill="both", expand=True, pady=12)
        actions = ttk.Frame(tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Refresh", command=self.refresh_events).pack(side="left")
        ttk.Button(actions, text="Cancel selected", command=self.cancel_event).pack(side="left", padx=8)

    def load_settings(self):
        try:
            config = self.store.load()
            for key, value in self.values.items():
                value.set(config[key])
            self.voice.set(config["VOICE_ENABLED"])
            self.headless.set(config["BROWSER_HEADLESS"])
        except (OSError, ValueError) as exc:
            messagebox.showerror("Cannot read settings", str(exc), parent=self.root)

    def save_settings(self):
        try:
            self.store.save({**{key: value.get().strip() for key, value in self.values.items()},
                             "VOICE_ENABLED": self.voice.get(), "BROWSER_HEADLESS": self.headless.get()})
            self.status.set("Settings saved. Restart to apply changes.")
            return True
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("Cannot save settings", str(exc), parent=self.root)
            return False

    def run_job(self, work, done=None):
        if self.busy:
            return
        self.busy = True
        def run():
            try:
                self.results.put((done, work(), None))
            except Exception as exc:
                self.results.put((done, None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def start(self):
        if not self.busy and self.save_settings():
            config = self.store.load()
            self.run_job(lambda: self.service.start(config))

    def stop(self):
        self.run_job(self.service.stop)

    def restart(self):
        if not self.busy and self.save_settings():
            config = self.store.load()
            def restart():
                self.service.stop()
                self.service.start(config)
            self.run_job(restart)

    def open_terminal(self):
        if self.service.running and self.service.ready.is_set():
            webbrowser.open("http://localhost:8766/")
        else:
            messagebox.showinfo("Launcher stopped", "Start the launcher first.", parent=self.root)

    def refresh_events(self):
        self.run_job(lambda: self.service.request("/scheduled_actions"), self.show_events)

    def show_events(self, result):
        self.events.delete(*self.events.get_children())
        for item in result.get("items", []):
            self.events.insert("", "end", iid=item["id"], values=(item["name"], item["scheduled_for"], item["status"]))

    def schedule(self):
        from urllib.parse import urlsplit
        url = self.schedule_url.get().strip()
        try:
            delay = int(self.delay.get())
            parsed = urlsplit(url)
            if delay < 1 or parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid action", "Enter an http(s) URL and a positive whole-number delay.", parent=self.root)
            return
        payload = {"name": url, "trigger": {"delay_seconds": delay}, "actions": [{"type": "open_url", "url": url}]}
        self.run_job(lambda: self.service.request("/schedule_action", payload), lambda _: self.refresh_events())

    def cancel_event(self):
        selected = self.events.selection()
        if selected:
            self.run_job(lambda: self.service.request("/cancel_scheduled_action", {"id": selected[0]}),
                         lambda _: self.refresh_events())

    def open_project(self):
        self.open_path(self.project_dir)

    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root, initialdir=self.project_dir)
        if path:
            self.open_path(Path(path))

    def open_path(self, path):
        from native_file_manager import handle_file_action_payload
        action = "open_directory" if path.is_dir() else "open_file"
        self.run_job(lambda: handle_file_action_payload({"action": action, "path": str(path)}))

    def clear_logs(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def tick(self):
        try:
            done, result, error = self.results.get_nowait()
            self.busy = False
            if error:
                if self.closing:
                    self.closing = False
                messagebox.showerror("JARVIS", error, parent=self.root)
            elif done:
                done(result)
                if self.closing:
                    return
        except queue.Empty:
            pass
        self.log.configure(state="normal")
        for _ in range(100):
            try:
                self.log.insert("end", self.service.logs.get_nowait() + "\n")
            except queue.Empty:
                break
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 2000:
            self.log.delete("1.0", "%d.0" % (lines - 2000))
        self.log.configure(state="disabled")
        running = self.service.running
        ready = running and self.service.ready.is_set()
        for index, button in enumerate(self.buttons):
            enabled = not self.busy and ((not running) if index == 0 else (ready if index == 3 else running))
            button.configure(state="normal" if enabled else "disabled")
        if self.busy:
            self.status.set("Working…")
        elif running:
            self.status.set("Running — local controls ready" if ready else "Starting…")
        elif self.service.process is not None:
            self.status.set("Stopped (exit code %s)" % self.service.process.returncode)
        self.root.after(150, self.tick)

    def close(self):
        if self.busy:
            self.root.after(150, self.close)
            return
        if self.service.running and not messagebox.askokcancel(
                "Exit JARVIS", "Stop the launcher and close desktop controls? Scheduled actions will be cleared.", parent=self.root):
            return
        self.closing = True
        self.run_job(self.service.stop, lambda _: self.root.destroy())


def main():
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
