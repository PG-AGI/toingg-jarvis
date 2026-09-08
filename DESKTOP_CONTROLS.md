# Desktop controls

Run `python jarvis_desktop.py` from the same Python environment used for JARVIS.
The window uses Python's native Tk/ttk widgets. It adds no Python package dependencies.
On Debian/Ubuntu, install the distribution's `python3-tk` package if Tk is missing;
Windows and macOS Python installers normally include it. The existing launcher,
audio, browser and API prerequisites still apply.

## Start a session

1. Enter the Toingg API key, campaign ID and streaming URL in Settings.
2. Choose whether to enable the wake-word microphone listener and whether browser
   automation should run headlessly.
3. Click **Start**, wait for **Running — local controls ready**, then **Open terminal**.
4. Use **Stop** or **Restart** to manage the launcher started by this window.

The desktop saves settings to the existing `config.json`, preserves unrecognized
settings, and uses an atomic replacement so a failed save leaves the old file intact.
The API key is masked in the form and redacted from captured launcher logs.
Configuration remains a local plaintext file, as in the existing CLI flow.
Save and restart, then reopen the web terminal, to apply changes.

The current repository provides Toingg streaming and a Pipecat tool bridge; it does
not yet provide a standalone Pipecat audio backend. The window shows this explicitly
instead of presenting a nonfunctional provider selector. Model/voice selection is
currently configured in the Toingg campaign. A future backend can extend these controls
once its startup and configuration contract is available.

## Scheduled actions and files

Under Scheduled actions, enter an HTTP(S) URL and a delay in seconds. Refresh lists
the launcher's actual scheduled actions, including actions created elsewhere. Select
an action to cancel it. Schedules are kept in launcher memory and disappear on restart;
closing the app asks before stopping an active launcher.

Open project folder and Open local file use the existing native file-manager integration.
They require an explicit click; the app does not scan or open user files on startup.

## Process ownership and troubleshooting

The desktop owns only the child launcher it starts. It never kills another program to
reclaim port 8766. If that port is busy, startup fails and the reason is in Logs: stop
the existing launcher yourself or keep using it separately. Multiple desktop windows
cannot take over one another's backend.

Normal stop sends a command over the child process's stdin, allowing the HTTP server
and tracked browser processes to shut down. Closing the controlling pipe also stops
the managed launcher. If the launcher does not exit, the controller terminates only
its owned launcher process after a timeout. Its last-resort forced termination cannot
guarantee child-browser cleanup if the launcher itself is hung.

Logs and asynchronous operations are drained onto the Tk event loop; slow startup,
HTTP requests and shutdown do not block the window. Displayed logs are bounded to
2,000 lines. Start with wake-word listening disabled to inspect local controls without
opening the microphone. No network API calls are made merely by opening the desktop.

## Verification

`python -m unittest discover -v`

Tests exercise configuration preservation and failed writes, real managed-launcher
startup/shutdown/restart, loopback schedule creation/cancellation, port collision,
EOF shutdown, log redaction and headless-browser dispatch. Integration tests disable
voice, use a temporary directory, never open a browser and contact no external services.

Manual platform checks: launch the window, resize it, save settings, start/stop/restart,
open the web terminal with valid credentials, cancel a delayed action, open a chosen
file, and verify the close confirmation. Live Toingg audio, microphone permissions and
browser automation require the normal user environment and credentials.
