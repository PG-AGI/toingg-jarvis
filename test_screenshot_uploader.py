import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jarvis_launcher
from screenshot_uploader import (
    ScreenshotUploadError,
    build_multipart_screenshot_payload,
    receive_multipart_screenshot,
    resolve_screenshot_upload_url,
    upload_screenshot_bytes,
)


class FakeHTTPResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ScreenshotUploaderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR-screenshot-bytes"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_build_and_receive_multipart_screenshot_payload(self):
        body, ctype = build_multipart_screenshot_payload(
            self.png_bytes,
            filename="screenshot.png",
            field_name="file",
            extra_fields={"session_id": "sess-42"},
        )
        self.assertIn("multipart/form-data; boundary=", ctype)
        self.assertIn(b'name="file"; filename="screenshot.png"', body)

        received = receive_multipart_screenshot(body, ctype, save_dir=self.root)
        self.assertTrue(received["ok"])
        self.assertEqual(received["filename"], "screenshot.png")
        self.assertEqual(received["size"], len(self.png_bytes))
        self.assertEqual(Path(received["path"]).read_bytes(), self.png_bytes)

    def test_upload_screenshot_bytes_sends_multipart_post_request(self):
        captured_requests = []

        def fake_urlopen(req, timeout=20):
            captured_requests.append((req, timeout))
            return FakeHTTPResponse({"ok": True, "file_url": "https://cdn.example.com/screenshot.png"})

        res = upload_screenshot_bytes(
            self.png_bytes,
            "https://api.example.com/upload",
            filename="screenshot.png",
            urlopen_fn=fake_urlopen,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["size"], len(self.png_bytes))
        self.assertEqual(res["response"]["file_url"], "https://cdn.example.com/screenshot.png")
        self.assertEqual(len(captured_requests), 1)
        req_obj, _ = captured_requests[0]
        self.assertEqual(req_obj.full_url, "https://api.example.com/upload")
        self.assertIn("multipart/form-data", req_obj.get_header("Content-type"))

    def test_launcher_playwright_screenshot_uploads_directly_when_upload_url_configured(self):
        fake_page = mock.Mock()
        fake_page.screenshot.return_value = self.png_bytes

        with mock.patch.object(jarvis_launcher, "_get_playwright_tool_page", return_value=fake_page), \
             mock.patch("screenshot_uploader.urllib.request.urlopen") as urlopen_mock:
            urlopen_mock.return_value = FakeHTTPResponse({"ok": True, "id": "scr-99"})
            res = jarvis_launcher.execute_playwright_tool_action(
                {
                    "action": "screenshot",
                    "upload_url": "https://api.example.com/upload",
                    "filename": "screenshot.png",
                }
            )

        fake_page.screenshot.assert_called_once_with(full_page=True)
        self.assertEqual(res["action"], "screenshot")
        self.assertTrue(res["uploaded"])
        self.assertEqual(res["upload_url"], "https://api.example.com/upload")
        self.assertEqual(res["response"]["id"], "scr-99")

    def test_resolve_screenshot_upload_url_from_params_env_and_config(self):
        cfg_file = self.root / "config.json"
        cfg_file.write_text(json.dumps({"SCREENSHOT_UPLOAD_URL": "https://cfg.example.com/upload"}), encoding="utf-8")

        self.assertEqual(
            resolve_screenshot_upload_url({}, config_path=cfg_file, environ={}),
            "https://cfg.example.com/upload",
        )
        self.assertEqual(
            resolve_screenshot_upload_url(
                {},
                config_path=cfg_file,
                environ={"JARVIS_SCREENSHOT_UPLOAD_URL": "https://env.example.com/upload"},
            ),
            "https://env.example.com/upload",
        )
        self.assertEqual(
            resolve_screenshot_upload_url(
                {"upload_url": "https://param.example.com/upload"},
                config_path=cfg_file,
                environ={"JARVIS_SCREENSHOT_UPLOAD_URL": "https://env.example.com/upload"},
            ),
            "https://param.example.com/upload",
        )


if __name__ == "__main__":
    unittest.main()
