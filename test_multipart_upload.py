import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jarvis_launcher
from multipart_upload_manager import (
    MultipartUploadError,
    cleanup_expired_uploads,
    cleanup_uploaded_token,
    get_uploaded_file_metadata,
    parse_multipart_form_data,
    resolve_input_files,
    store_uploaded_bytes,
)


def _build_multipart_body(boundary: str, parts: list[dict]) -> bytes:
    chunks: list[bytes] = []
    for part in parts:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        name = part.get("name", "file")
        filename = part.get("filename")
        ctype = part.get("content_type", "image/png")
        if filename is not None:
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
            )
            chunks.append(f"Content-Type: {ctype}\r\n\r\n".encode("utf-8"))
        else:
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        data = part.get("data", b"")
        if isinstance(data, str):
            data = data.encode("utf-8")
        chunks.append(data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


class MultipartUploadManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.tmpdir.name)
        self.sample_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR-mock-image-bytes"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_multipart_form_data_stores_image_and_returns_token(self):
        boundary = "----JarvisUploadBoundary9912"
        body = _build_multipart_body(
            boundary,
            [
                {
                    "name": "file",
                    "filename": "../../avatar_photo.png",
                    "content_type": "image/png",
                    "data": self.sample_png,
                },
                {
                    "name": "selector",
                    "data": "input[type=file]",
                },
            ],
        )

        result = parse_multipart_form_data(
            body,
            f"multipart/form-data; boundary={boundary}",
            upload_dir=self.upload_dir,
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["file_token"].startswith("upl_"))
        self.assertEqual(result["filename"], "avatar_photo.png")
        self.assertEqual(result["content_type"], "image/png")
        self.assertEqual(result["size"], len(self.sample_png))
        self.assertEqual(result["fields"].get("selector"), "input[type=file]")
        self.assertTrue(Path(result["path"]).is_file())
        self.assertEqual(Path(result["path"]).read_bytes(), self.sample_png)

    def test_resolve_input_files_by_token_and_auto_cleanup(self):
        meta = store_uploaded_bytes(
            self.sample_png,
            filename="banner.png",
            content_type="image/png",
            upload_dir=self.upload_dir,
        )
        token = meta["file_token"]

        paths, cleanup_tokens = resolve_input_files(
            {"selector": "#upload", "file_token": token},
            upload_dir=self.upload_dir,
        )

        self.assertEqual(paths, [meta["path"]])
        self.assertEqual(cleanup_tokens, [token])
        self.assertTrue(cleanup_uploaded_token(token, upload_dir=self.upload_dir))
        with self.assertRaises(MultipartUploadError):
            get_uploaded_file_metadata(token, upload_dir=self.upload_dir)

    def test_expired_tokens_are_cleaned_up_automatically(self):
        meta = store_uploaded_bytes(
            self.sample_png,
            filename="temp.png",
            content_type="image/png",
            upload_dir=self.upload_dir,
            ttl_seconds=5,
        )
        token = meta["file_token"]
        cleaned = cleanup_expired_uploads(
            upload_dir=self.upload_dir,
            now=meta["expires_at"] + 10,
        )
        self.assertEqual(cleaned, 1)
        with self.assertRaises(MultipartUploadError):
            get_uploaded_file_metadata(token, upload_dir=self.upload_dir)

    def test_resolve_inline_base64_and_existing_local_file(self):
        local_file = self.upload_dir / "direct.jpg"
        local_file.write_bytes(b"jpeg-content")

        encoded = base64.b64encode(self.sample_png).decode("ascii")
        paths, cleanup_tokens = resolve_input_files(
            {
                "files": [
                    str(local_file),
                    {"base64": f"data:image/png;base64,{encoded}", "filename": "inline.png"},
                ]
            },
            upload_dir=self.upload_dir,
        )

        self.assertEqual(len(paths), 2)
        self.assertEqual(Path(paths[0]).resolve(), local_file.resolve())
        self.assertTrue(Path(paths[1]).is_file())
        self.assertEqual(len(cleanup_tokens), 1)

    def test_launcher_playwright_input_file_sets_files_and_cleans_up_token(self):
        meta = store_uploaded_bytes(
            self.sample_png,
            filename="upload_target.png",
            content_type="image/png",
            upload_dir=self.upload_dir,
        )
        token = meta["file_token"]
        fake_page = mock.Mock()

        with mock.patch.object(jarvis_launcher, "_get_playwright_tool_page", return_value=fake_page):
            res = jarvis_launcher.execute_playwright_tool_action(
                {
                    "action": "input_file",
                    "selector": "input[type='file']",
                    "file_token": token,
                    "upload_dir": str(self.upload_dir),
                }
            )

        fake_page.set_input_files.assert_called_once_with(
            "input[type='file']",
            [meta["path"]],
            timeout=30000,
        )
        self.assertEqual(res["action"], "input_file")
        self.assertEqual(res["files"], ["upload_target.png"])
        self.assertFalse(Path(meta["path"]).exists())

    def test_validation_rejects_missing_boundary_and_empty_uploads(self):
        with self.assertRaises(MultipartUploadError):
            parse_multipart_form_data(b"abc", "application/json", upload_dir=self.upload_dir)
        with self.assertRaises(MultipartUploadError):
            parse_multipart_form_data(b"abc", "multipart/form-data", upload_dir=self.upload_dir)
        with self.assertRaises(MultipartUploadError):
            store_uploaded_bytes(b"", filename="empty.png", upload_dir=self.upload_dir)


if __name__ == "__main__":
    unittest.main()
