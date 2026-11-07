import base64
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from multipart_upload_manager import (
    MultipartUploadError,
    cleanup_expired_uploads,
    clear_all_uploads,
    finalize_playwright_input_files,
    get_uploaded_file,
    handle_multipart_upload_request,
    resolve_playwright_input_files,
)
import jarvis_launcher


PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _build_multipart_body(
    boundary: str,
    files: list[tuple[str, str, str, bytes]],
    fields: dict[str, str] | None = None,
) -> tuple[str, bytes]:
    chunks: list[bytes] = []
    for name, value in (fields or {}).items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    for field_name, filename, content_type, data in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


class FakePlaywrightPage:
    def __init__(self, fail_first_selector: bool = False):
        self.url = "https://example.com/upload"
        self.calls: list[tuple[str, object, int]] = []
        self.fail_first_selector = fail_first_selector

    def is_closed(self) -> bool:
        return False

    def set_input_files(self, selector: str, files: object, timeout: int = 30000) -> None:
        if self.fail_first_selector:
            self.fail_first_selector = False
            raise RuntimeError(f"strict selector failed: {selector}")
        # Verify the file exists on disk at the moment Playwright reads it
        paths = [files] if isinstance(files, str) else list(files)
        for p in paths:
            if not Path(p).is_file():
                raise AssertionError(f"Expected staged file to exist during set_input_files: {p}")
        self.calls.append((selector, files, timeout))


class MultipartUploadManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.tmpdir.name)
        clear_all_uploads()

    def tearDown(self):
        clear_all_uploads()
        self.tmpdir.cleanup()

    def test_multipart_upload_stores_image_and_returns_token_and_metadata(self):
        ctype, body = _build_multipart_body(
            "----JarvisBoundary123",
            [("file", "avatar photo.png", "image/png", PNG_1X1_BYTES)],
            fields={"source": "websocket"},
        )
        response = handle_multipart_upload_request(
            ctype,
            body,
            upload_dir=self.upload_dir,
            now=1000.0,
            ttl_seconds=120.0,
        )

        self.assertTrue(response["ok"])
        self.assertTrue(response["file_token"].startswith("upl_"))
        self.assertEqual(response["filename"], "avatar_photo.png")
        self.assertEqual(response["content_type"], "image/png")
        self.assertEqual(response["size"], len(PNG_1X1_BYTES))
        self.assertEqual(response["expires_at"], 1120.0)
        self.assertTrue(Path(response["path"]).is_file())

        stored = get_uploaded_file(response["file_token"], now=1050.0)
        self.assertEqual(stored["path"], response["path"])

    def test_expired_uploads_are_cleaned_up_automatically(self):
        ctype, body = _build_multipart_body(
            "----JarvisBoundaryExp",
            [("file", "temp.png", "image/png", PNG_1X1_BYTES)],
        )
        response = handle_multipart_upload_request(
            ctype,
            body,
            upload_dir=self.upload_dir,
            now=500.0,
            ttl_seconds=30.0,
        )
        staged_path = Path(response["path"])
        self.assertTrue(staged_path.exists())

        removed = cleanup_expired_uploads(now=531.0)
        self.assertEqual(removed, 1)
        self.assertFalse(staged_path.exists())

        with self.assertRaises(MultipartUploadError) as ctx:
            get_uploaded_file(response["file_token"], now=531.0)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_multipart_validation_rejects_bad_headers_oversized_and_bad_extensions(self):
        with self.assertRaises(MultipartUploadError) as bad_ct:
            handle_multipart_upload_request("application/json", b"{}", upload_dir=self.upload_dir)
        self.assertEqual(bad_ct.exception.status_code, 415)

        ctype, body = _build_multipart_body(
            "----JarvisBoundarySize",
            [("file", "large.png", "image/png", b"x" * 256)],
        )
        with self.assertRaises(MultipartUploadError) as too_large:
            handle_multipart_upload_request(
                ctype,
                body,
                max_bytes=64,
                upload_dir=self.upload_dir,
            )
        self.assertEqual(too_large.exception.status_code, 413)

        ctype_exe, body_exe = _build_multipart_body(
            "----JarvisBoundaryExt",
            [("file", "payload.exe", "application/octet-stream", b"MZ")],
        )
        with self.assertRaises(MultipartUploadError) as bad_ext:
            handle_multipart_upload_request(ctype_exe, body_exe, upload_dir=self.upload_dir)
        self.assertEqual(bad_ext.exception.status_code, 415)

    def test_resolve_and_finalize_inline_base64_and_data_url(self):
        data_url = "data:image/png;base64," + base64.b64encode(PNG_1X1_BYTES).decode("ascii")
        resolved, tokens, ephemeral = resolve_playwright_input_files(
            {"selector": "#file", "value": data_url, "filename": "inline_pic.png"},
            upload_dir=self.upload_dir,
        )
        self.assertEqual(len(resolved), 1)
        self.assertEqual(tokens, [])
        self.assertEqual(len(ephemeral), 1)
        self.assertTrue(Path(resolved[0]).is_file())

        finalize_playwright_input_files(tokens, ephemeral)
        self.assertFalse(Path(resolved[0]).exists())

    def test_launcher_execute_playwright_input_file_consumes_token_and_cleans_up(self):
        ctype, body = _build_multipart_body(
            "----JarvisBoundaryLauncher",
            [("file", "banner.png", "image/png", PNG_1X1_BYTES)],
        )
        upload_res = handle_multipart_upload_request(ctype, body, upload_dir=self.upload_dir)
        token = upload_res["file_token"]
        staged_path = Path(upload_res["path"])

        fake_page = FakePlaywrightPage()
        with mock.patch.object(jarvis_launcher, "_get_playwright_tool_page", return_value=fake_page):
            result = jarvis_launcher.execute_playwright_tool_action(
                {
                    "action": "input_file",
                    "selector": "input[type=file]",
                    "file_token": token,
                    "timeout": 12000,
                }
            )

        self.assertEqual(result["action"], "input_file")
        self.assertEqual(result["selector"], "input[type=file]")
        self.assertEqual(result["file_tokens"], [token])
        self.assertEqual(len(fake_page.calls), 1)
        self.assertEqual(fake_page.calls[0][0], "input[type=file]")
        self.assertEqual(fake_page.calls[0][1], str(staged_path))
        self.assertEqual(fake_page.calls[0][2], 12000)
        # Staged temporary file should be cleaned up after set_input_files completes
        self.assertFalse(staged_path.exists())

    def test_browser_client_websocket_input_file_action_and_selector_repair(self):
        # Provide lightweight stubs if websocket or playwright are not installed in test env
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

            ctype, body = _build_multipart_body(
                "----JarvisBoundaryWS",
                [("file", " reference.png ", "image/png", PNG_1X1_BYTES)],
            )
            upload_res = handle_multipart_upload_request(ctype, body, upload_dir=self.upload_dir)
            token = upload_res["file_token"]
            staged_path = Path(upload_res["path"])

            client = browserClient.BrowserClient(ws_url="ws://localhost:8002/ws", headless=True)
            fake_page = FakePlaywrightPage(fail_first_selector=True)
            client.page = fake_page
            client._select_active_page = lambda: fake_page
            client._human_delay = lambda *args, **kwargs: None

            sent_messages: list[dict] = []

            class DummyWS:
                def send(self, raw_payload: str):
                    sent_messages.append(json.loads(raw_payload))

            ws_Command = {
                "type": "command",
                "command_id": "cmd-upload-1",
                "action": "input_file",
                "params": {
                    "selector": "input.p-2.5.file-uploader",
                    "file_token": token,
                    "timeout": 9000,
                },
            }
            client._on_message(DummyWS(), json.dumps(ws_Command))

            self.assertEqual(len(sent_messages), 1)
            reply = sent_messages[0]
            self.assertTrue(reply["success"])
            self.assertEqual(reply["command_id"], "cmd-upload-1")
            self.assertEqual(reply["file_tokens"], [token])
            self.assertEqual(len(fake_page.calls), 1)
            self.assertEqual(
                fake_page.calls[0][0],
                'input[class~="p-2.5"][class~="file-uploader"]',
            )
            self.assertEqual(fake_page.calls[0][1], str(staged_path))
            self.assertFalse(staged_path.exists())


if __name__ == "__main__":
    unittest.main()
