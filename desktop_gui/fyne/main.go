// Package main provides a native Fyne v2 cross-platform desktop GUI for Toingg JARVIS.
//
// Build & Run:
//   cd desktop_gui/fyne
//   go mod tidy
//   go run .
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/widget"
)

type BrowserConfig struct {
	Headless         bool   `json:"headless"`
	UserDataDir      string `json:"user_data_dir"`
	PreferredMonitor string `json:"preferred_monitor"`
	WindowSize       string `json:"window_size"`
	Position         string `json:"position"`
}

type JarvisConfig struct {
	WSURL        string        `json:"WS_URL"`
	Token        string        `json:"TOKEN"`
	CampID       string        `json:"CAMP_ID"`
	Provider     string        `json:"PROVIDER"`
	GeminiAPIKey string        `json:"GEMINI_API_KEY"`
	Model        string        `json:"MODEL"`
	Browser      BrowserConfig `json:"browser"`
}

func main() {
	a := app.NewWithID("com.toingg.jarvis.desktop")
	w := a.NewWindow("TOINGG // J.A.R.V.I.S. — Fyne v2 Control Center")
	w.Resize(fyne.NewSize(960, 640))

	repoRoot, _ := filepath.Abs("../..")
	cfgPath := filepath.Join(repoRoot, "config.json")

	var mu sync.Mutex
	procs := map[string]*exec.Cmd{}
	logEntry := widget.NewMultiLineEntry()
	logEntry.SetMinRowsVisible(14)

	appendLog := func(msg string) {
		ts := time.Now().Format("15:04:05")
		logEntry.SetText(logEntry.Text + fmt.Sprintf("[%s] %s\n", ts, msg))
	}

	startSvc := func(name, script string) {
		mu.Lock()
		defer mu.Unlock()
		if existing, ok := procs[name]; ok && existing != nil && existing.Process != nil {
			appendLog(name + " is already running")
			return
		}
		cmd := exec.Command("python", filepath.Join(repoRoot, script))
		cmd.Dir = repoRoot
		if err := cmd.Start(); err != nil {
			appendLog("Failed to start " + name + ": " + err.Error())
			return
		}
		procs[name] = cmd
		appendLog(fmt.Sprintf("Started %s (PID %d)", name, cmd.Process.Pid))
	}

	stopSvc := func(name string) {
		mu.Lock()
		defer mu.Unlock()
		if existing, ok := procs[name]; ok && existing != nil && existing.Process != nil {
			_ = existing.Process.Kill()
			procs[name] = nil
			appendLog("Stopped " + name)
		}
	}

	providerSelect := widget.NewSelect([]string{"toingg", "pipecat_gemini"}, nil)
	providerSelect.SetSelected("toingg")
	tokenEntry := widget.NewPasswordEntry()
	geminiEntry := widget.NewPasswordEntry()
	modelEntry := widget.NewEntry()
	modelEntry.SetText("gemini-2.5-flash")
	monitorEntry := widget.NewEntry()
	monitorEntry.SetText("active")
	winSizeEntry := widget.NewEntry()
	winSizeEntry.SetText("860x580")
	posSelect := widget.NewSelect([]string{"grid", "center", "top-left", "top-right", "bottom-left", "bottom-right"}, nil)
	posSelect.SetSelected("grid")

	saveCfgBtn := widget.NewButton("Save Configuration", func() {
		cfg := JarvisConfig{
			WSURL:        "wss://prepodapi.toingg.com/api/v3/media/streaming",
			Token:        tokenEntry.Text,
			Provider:     providerSelect.Selected,
			GeminiAPIKey: geminiEntry.Text,
			Model:        modelEntry.Text,
			Browser: BrowserConfig{
				UserDataDir:      ".browser-profile",
				PreferredMonitor: monitorEntry.Text,
				WindowSize:       winSizeEntry.Text,
				Position:         posSelect.Selected,
			},
		}
		raw, _ := json.MarshalIndent(cfg, "", "  ")
		_ = os.WriteFile(cfgPath, raw, 0o644)
		appendLog("Configuration saved to " + cfgPath)
	})

	fileTargetEntry := widget.NewEntry()
	fileTargetEntry.SetText(repoRoot)
	openDirBtn := widget.NewButton("Open Directory", func() {
		body, _ := json.Marshal(map[string]any{"action": "open_directory", "path": fileTargetEntry.Text})
		resp, err := http.Post("http://localhost:8766/file_action", "application/json", bytes.NewReader(body))
		if err != nil {
			appendLog("File action error: " + err.Error())
			return
		}
		defer resp.Body.Close()
		out, _ := io.ReadAll(resp.Body)
		appendLog("File action response: " + string(out))
	})

	tabs := container.NewAppTabs(
		container.NewTabItem("Services & Logs", container.NewVBox(
			container.NewHBox(
				widget.NewButton("Start Launcher", func() { startSvc("launcher", "jarvis_launcher.py") }),
				widget.NewButton("Stop Launcher", func() { stopSvc("launcher") }),
				widget.NewButton("Start Browser Client", func() { startSvc("browser_client", "browserClient.py") }),
				widget.NewButton("Stop Browser Client", func() { stopSvc("browser_client") }),
			),
			logEntry,
		)),
		container.NewTabItem("Provider, API Keys & Browser", container.NewVBox(
			widget.NewForm(
				widget.NewFormItem("Backend Provider", providerSelect),
				widget.NewFormItem("Toingg API Key", tokenEntry),
				widget.NewFormItem("Gemini API Key", geminiEntry),
				widget.NewFormItem("LLM Model", modelEntry),
				widget.NewFormItem("Preferred Monitor", monitorEntry),
				widget.NewFormItem("Window Size", winSizeEntry),
				widget.NewFormItem("Window Position", posSelect),
			),
			saveCfgBtn,
		)),
		container.NewTabItem("Files & Output", container.NewVBox(
			fileTargetEntry,
			openDirBtn,
		)),
	)

	w.SetContent(tabs)
	w.ShowAndRun()
}
