"""
claudeBot.py — Browser automation client for the Toingg personal AI assistant.

Connects to the backend WebSocket, receives Playwright-compatible commands from the LLM,
executes them in a real browser, and returns results.

Usage:
    python claudeBot.py --url ws://localhost:8002/api/v3/media/browser/default

Requirements:
    pip install websocket-client playwright
    playwright install chromium
"""

import argparse
import json
import logging
import subprocess
import sys
import threading
import time
import base64

try:
    import websocket
except ModuleNotFoundError:
    print("Missing dependency: websocket-client")
    print("Install it with: python -m pip install websocket-client")
    sys.exit(1)

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright, Page, Playwright
except ModuleNotFoundError:
    print("Missing dependency: playwright")
    print("Install it with: python -m pip install playwright")
    print("Then install Chromium with: python -m playwright install chromium")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BROWSER] %(message)s")
log = logging.getLogger(__name__)


def install_playwright_chromium() -> bool:
    """Download Playwright's Chromium browser for this Python environment."""
    log.info("Installing Playwright Chromium browser...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        log.error(f"Could not run Playwright installer: {e}")
        return False


class BrowserClient:
    def __init__(self, ws_url: str, headless: bool = False):
        self.ws_url = ws_url
        self.headless = headless
        self.ws: websocket.WebSocketApp | None = None
        self.page: Page | None = None
        self.playwright: Playwright | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # Playwright action dispatch
    # ------------------------------------------------------------------

    def _execute(self, action: str, params: dict) -> dict:
        """Execute a single Playwright action and return a result dict."""
        page = self.page
        if page is None:
            return {"success": False, "error": "Browser page not initialised"}

        try:
            if action == "navigate":
                url = params["url"]
                page.goto(url, timeout=params.get("timeout", 30000))
                return {"success": True, "result": f"Navigated to {url}"}

            elif action == "click":
                selector = params["selector"]
                page.click(selector, timeout=params.get("timeout", 10000))
                return {"success": True, "result": f"Clicked '{selector}'"}

            elif action == "fill":
                selector = params["selector"]
                value = params["value"]
                page.fill(selector, value, timeout=params.get("timeout", 10000))
                return {"success": True, "result": f"Filled '{selector}' with value"}

            elif action == "get_text":
                selector = params.get("selector")
                timeout = params.get("timeout", 10000)
                if selector:
                    locator = page.locator(selector)
                    try:
                        locator.first.wait_for(state="attached", timeout=timeout)
                    except Exception:
                        return {"success": False, "error": f"No elements matched selector: {selector}"}
                    texts = [text.strip() for text in locator.all_inner_texts() if text.strip()]
                    return {"success": True, "result": "\n".join(texts)}
                text = page.locator("body").inner_text(timeout=timeout)
                return {"success": True, "result": text or ""}

            elif action == "get_page_content":
                return {"success": True, "result": page.content()}

            elif action == "screenshot":
                path = params.get("path")
                if path:
                    page.screenshot(path=path, full_page=params.get("full_page", False))
                    return {"success": True, "result": f"Screenshot saved to {path}"}
                else:
                    img_bytes = page.screenshot(full_page=params.get("full_page", False))
                    encoded = base64.b64encode(img_bytes).decode()
                    return {"success": True, "result": f"data:image/png;base64,{encoded[:100]}... (truncated)"}

            elif action == "evaluate":
                expression = params["expression"]
                result = page.evaluate(expression)
                return {"success": True, "result": str(result)}

            elif action == "wait_for_selector":
                selector = params["selector"]
                state = params.get("state", "visible")
                page.wait_for_selector(selector, state=state, timeout=params.get("timeout", 30000))
                return {"success": True, "result": f"Selector '{selector}' is {state}"}

            elif action == "press":
                selector = params["selector"]
                key = params["key"]
                page.press(selector, key)
                return {"success": True, "result": f"Pressed '{key}' on '{selector}'"}

            elif action == "select":
                selector = params["selector"]
                value = params["value"]
                page.select_option(selector, value)
                return {"success": True, "result": f"Selected '{value}' in '{selector}'"}

            elif action == "scroll":
                x = params.get("x", 0)
                y = params.get("y", 0)
                page.evaluate(f"window.scrollBy({x}, {y})")
                return {"success": True, "result": f"Scrolled by ({x}, {y})"}

            elif action == "hover":
                selector = params["selector"]
                page.hover(selector, timeout=params.get("timeout", 10000))
                return {"success": True, "result": f"Hovered over '{selector}'"}

            elif action == "get_url":
                return {"success": True, "result": page.url}

            elif action == "go_back":
                page.go_back(timeout=params.get("timeout", 10000))
                return {"success": True, "result": "Navigated back"}

            elif action == "go_forward":
                page.go_forward(timeout=params.get("timeout", 10000))
                return {"success": True, "result": "Navigated forward"}

            elif action == "reload":
                page.reload(timeout=params.get("timeout", 30000))
                return {"success": True, "result": "Page reloaded"}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            log.error(f"Action '{action}' failed: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            print("Received: ", msg)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "connected":
            log.info(f"Connected to backend — session: {msg.get('session_id')}")

        elif msg_type == "command":
            command_id = msg.get("command_id")
            action = msg.get("action")
            params = msg.get("params", {})
            log.info(f"Received command '{action}' (id={command_id})")

            result = self._execute(action, params)
            result["type"] = "result"
            result["command_id"] = command_id
            ws.send(json.dumps(result))
            log.info(f"Sent result for '{action}': success={result['success']}")

        elif msg_type == "ping":
            ws.send(json.dumps({"type": "pong"}))

    def _on_error(self, ws, error):
        log.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        log.info(f"WebSocket closed: {close_status_code} {close_msg}")

    def _on_open(self, ws):
        log.info(f"WebSocket opened: {self.ws_url}")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        with sync_playwright() as pw:
            self.playwright = pw
            try:
                browser = pw.chromium.launch(headless=self.headless)
            except PlaywrightError as e:
                if "Executable doesn't exist" not in str(e):
                    raise
                log.warning("Playwright Chromium is missing. Downloading it now...")
                if not install_playwright_chromium():
                    raise
                browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context()
            self.page = context.new_page()
            log.info(f"Browser launched (headless={self.headless})")

            # Keep reconnecting until stopped
            while not self._stop.is_set():
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10)

                if not self._stop.is_set():
                    log.info("Reconnecting in 3 seconds...")
                    time.sleep(3)

            browser.close()
            log.info("Browser closed")


def main():
    parser = argparse.ArgumentParser(description="Toingg browser automation client")
    parser.add_argument(
        "--url",
        default="wss://prepodapi.toingg.com/api/v3/media/browser/default",
        help="Backend WebSocket URL (default: ws://prepodapi.toingg.com/api/v3/media/browser/default)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )
    args = parser.parse_args()

    client = BrowserClient(ws_url=args.url, headless=args.headless)
    try:
        client.run()
    except KeyboardInterrupt:
        log.info("Stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
