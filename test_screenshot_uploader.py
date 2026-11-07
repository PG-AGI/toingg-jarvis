import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

import jarvis_launcher
from screenshot_uploader import (
    ScreenshotUploadError,
    build_multipart_form_data,
    capture_and_handle_screenshot,
    derive_backend_upload_url_from_ws,
    parse_multipart_upload,
    resolve_screenshot_upload_url,
    upload_screenshot_bytes,
)


PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeHTTPResponse:
    def __init__(self, body: bytes = b'{"ok":true,"id":"scr_01"}', status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeScreenshotPage:
    def __init__(self, payload: bytes = PNG_1X1_BYTES):
        self.url = "https://example.com/dashboard"
        self.payload = payload
        self.calls: list[dict] = []

    def is_closed(self) -> bool:
        return False

    def screenshot(self, **kwargs) -> bytes:
        self.calls.append(kwargs)
        path = kwargs.get("path")
        if path:
            Path(path).write_bytes(self.payload)
        return self.payload


class ScreenshotUploaderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_build_and_parse_multipart_form_data_round_trip(self):
        content_type, body = build_multipart_form_data(
            PNG_1X1_BYTES,
            filename="screenshot.png",
            field_name="file",
            extra_fields={"session_id": "sess-42"},
        )
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        self.assertIn(b'Content-Disposition: form-data; name="file"; filename="screenshot.png"', body)
        self.assertIn(b"Content-Type: image/png", body)

        parsed = parse_multipart_upload(content_type, body, upload_dir=self.root)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["filename"], "screenshot.png")
        self.assertEqual(parsed["field_name"], "file")
        self.assertEqual(parsed["content_type"], "image/png")
        self.assertEqual(parsed["size"], len(PNG_1X1_BYTES))
        self.assertEqual(parsed["fields"]["session_id"], "sess-42")
        self.assertEqual(Path(parsed["path"]).read_bytes(), PNG_1X1_BYTES)

    def test_upload_screenshot_bytes_sends_multipart_post_request(self):
        captured = {}

        def fake_opener(req, timeout=15.0):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.header_items())
            captured["body"] = req.data
            captured["timeout"] = timeout
            return FakeHTTPResponse(b'{"ok":true,"file_url":"https://cdn.example.com/screenshot.png"}', 201)

        res = upload_screenshot_bytes(
            PNG_1X1_BYTES,
            upload_url="https://api.example.com/upload",
            filename="screenshot.png",
            headers={"Authorization": "Bearer secret-token"},
            opener=fake_opener,
        )

        self.assertTrue(res["uploaded"])
        self.assertEqual(res["status"], 201)
        self.assertEqual(res["filename"], "screenshot.png")
        self.assertEqual(res["response"]["file_url"], "https://cdn.example.com/screenshot.png")
        self.assertEqual(captured["url"], "https://api.example.com/upload")
        self.assertEqual(captured["method"], "POST")

        ctype_header = next(
            v for k, v in captured["headers"].items() if k.lower() == "content-type"
        )
        parsed = parse_multipart_upload(ctype_header, captured["body"], upload_dir=self.root)
        self.assertEqual(parsed["filename"], "screenshot.png")
        self.assertEqual(parsed["size"], len(PNG_1X1_BYTES))

    def test_upload_screenshot_bytes_raises_on_http_and_url_errors(self):
        def failing_http_opener(req, timeout=15.0):
            raise HTTPError(
                req.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=io.BytesIO(b'{"error":"storage failure"}'),
            )

        with self.assertRaises(ScreenshotUploadError) as http_ctx:
            upload_screenshot_bytes(
                PNG_1X1_BYTES,
                upload_url="https://api.example.com/upload",
                opener=failing_http_opener,
            )
        self.assertEqual(http_ctx.exception.status_code, 500)

        def failing_url_opener(req, timeout=15.0):
            raise URLError("connection refused")

        with self.assertRaises(ScreenshotUploadError) as url_ctx:
            upload_screenshot_bytes(
                PNG_1X1_BYTES,
                upload_url="https://api.example.com/upload",
                opener=failing_url_opener,
            )
        self.assertEqual(url_ctx.exception.status_code, 502)

    def test_resolve_screenshot_upload_url_precedence(self):
        cfg_file = self.root / "config.json"
        cfg_file.write_text(
            json.dumps({"SCREENSHOT_UPLOAD_URL": "https://cfg.example.com/upload", "TOKEN": "tok-1"}),
            encoding="utf-8",
        )

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_SCREENSHOT_UPLOAD_URL", None)
            os.environ.pop("TOINGG_SCREENSHOT_UPLOAD_URL", None)

            # 1. Explicit param overrides config
            self.assertEqual(
                resolve_screenshot_upload_url(
                    {"upload_url": "https://param.example.com/upload"},
                    config_path=cfg_file,
                ),
                "https://param.example.com/upload",
            )

            # 2. Config fallback
            self.assertEqual(
                resolve_screenshot_upload_url({}, config_path=cfg_file),
                "https://cfg.example.com/upload",
            )

            # 3. upload=False disables upload even when config is set
            self.assertIsNone(
                resolve_screenshot_upload_url({"upload": False}, config_path=cfg_file)
            )

            # 4. upload=True derives /upload from ws_url when no config/env is present
            empty_cfg = self.root / "empty_config.json"
            empty_cfg.write_text("{}", encoding="utf-8")
            self.assertEqual(
                resolve_screenshot_upload_url(
                    {"upload": True},
                    config_path=empty_cfg,
                    ws_url="wss://prepodapi.toingg.com/api/v3/media/browser/default",
                ),
                "https://prepodapi.toingg.com/upload",
            )

        self.assertEqual(
            derive_backend_upload_url_from_ws("ws://localhost:8002/api/v3/media/browser/default"),
            "http://localhost:8002/upload",
        )

    def test_launcher_execute_playwright_screenshot_uploads_or_saves_locally(self):
        fake_page = FakeScreenshotPage()

        with mock.patch.object(jarvis_launcher, "_get_playwright_tool_page", return_value=fake_page):
            with mock.patch(
                "screenshot_uploader.request.urlopen",
                side_effect=lambda req, timeout=15.0: FakeHTTPResponse(
                    b'{"ok":true,"filename":"screenshot.png"}', 200
                ),
            ):
                uploaded_res = jarvis_launcher.execute_playwright_tool_action(
                    {
                        "action": "screenshot",
                        "upload_url": "http://localhost:8766/upload",
                        "full_page": False,
                    }
                )

            self.assertEqual(uploaded_res["action"], "screenshot")
            self.assertTrue(uploaded_res["uploaded"])
            self.assertEqual(uploaded_res["upload_url"], "http://localhost:8766/upload")
            self.assertEqual(uploaded_res["filename"], "screenshot.png")
            # Direct upload should not pass a local path to page.screenshot
            self.assertNotIn("path", fake_page.calls[-1])

            local_file = self.root / "local-shot.png"
            with mock.patch.dict(os.environ, {"JARVIS_SCREENSHOT_UPLOAD_URL": ""}, clear=False):
                local_res = jarvis_launcher.execute_playwright_tool_action(
                    {
                        "action": "screenshot",
                        "path": str(local_file),
                        "upload": False,
                    }
                )
            self.assertEqual(local_res, {"action": "screenshot", "path": str(local_file)})
            self.assertTrue(local_file.is_file())

    def test_browser_client_screenshot_uploads_directly_to_backend(self):
        fake_ws_mod = sys.modules.get("websocket") or types.ModuleType("websocket")
        if not hasattr(fake_ws_mod, "WebSocketApp"):
            fake_ws_mod.WebSocketApp = object
        fake_pw_sync = types.ModuleType("playwright.sync_api")
        fake_pw_sync.sync_playwright = lambda: None
        fake_pw_sync.Page = object
        fake_pw_sync.Playwright = object
        fake_pw_pkg = types.ModuleType("playwright")
        fake_pw_pkg.sync_api = fake_pw_sync

        with mock.patch.dict(
            sys.modules,
            {
                "websocket": fake_ws_mod,
                "playwright": fake_pw_pkg,
                "playwright.sync_api": fake_pw_sync,
            },
        ):
            import importlib
            import browserClient

            importlib.reload(browserClient)

            fake_page = FakeScreenshotPage()
            client = browserClient.BrowserClient(
                ws_url="ws://localhost:8002/api/v3/media/browser/default",
                headless=True,
                upload_url="http://localhost:8002/upload",
            )
            client.page = fake_page
            client._select_active_page = lambda: fake_page

            with mock.patch(
                "screenshot_uploader.request.urlopen",
                side_effect=lambda req, timeout=15.0: FakeHTTPResponse(
                    b'{"ok":true,"url":"http://localhost:8002/files/screenshot.png"}', 200
                ),
            ):
                res = client._execute("screenshot", {"full_page": True})

            self.assertTrue(res["success"])
            self.assertEqual(res["upload_url"], "http://localhost:8002/upload")
            self.assertEqual(res["filename"], "screenshot.png")
            self.assertEqual(fake_page.calls[-1], {"full_page": True})

            # Fallback to base64 when upload=False and no path is given
            b64_res = client._execute("screenshot", {"upload": False})
            self.assertTrue(b64_res["success"])
            self.assertTrue(b64_res["result"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
