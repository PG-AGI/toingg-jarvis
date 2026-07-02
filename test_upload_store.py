import tempfile
import unittest
from pathlib import Path

from upload_store import (
    MAX_UPLOAD_BYTES,
    PendingUpload,
    UploadError,
    UploadStore,
    parse_multipart_images,
)


def multipart_body(boundary, files):
    chunks = []
    for field, filename, content_type, data in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                ).encode(),
                f"Content-Type: {content_type}\r\n\r\n".encode(),
                data,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)


class UploadStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = UploadStore(self.tmpdir.name, ttl_seconds=60)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_multiple_images(self):
        boundary = "jarvis-test"
        uploads = parse_multipart_images(
            f"multipart/form-data; boundary={boundary}",
            multipart_body(
                boundary,
                [
                    ("files", "first.png", "image/png", b"png-data"),
                    ("files", "second.jpg", "image/jpeg", b"jpeg-data"),
                ],
            ),
        )

        self.assertEqual([upload.filename for upload in uploads], ["first.png", "second.jpg"])
        self.assertEqual(uploads[1].data, b"jpeg-data")

    def test_parse_rejects_non_images_empty_files_and_oversized_files(self):
        boundary = "jarvis-test"
        cases = [
            ("notes.txt", "text/plain", b"text"),
            ("empty.png", "image/png", b""),
            ("large.png", "image/png", b"x" * (MAX_UPLOAD_BYTES + 1)),
        ]
        for filename, content_type, data in cases:
            with self.subTest(filename=filename), self.assertRaises(UploadError):
                parse_multipart_images(
                    f"multipart/form-data; boundary={boundary}",
                    multipart_body(boundary, [("file", filename, content_type, data)]),
                )

    def test_save_uses_opaque_token_and_sanitizes_filename(self):
        metadata = self.store.save(
            PendingUpload("../../screenshot.png", "image/png", b"image"), now=100
        )

        path = self.store.resolve(metadata["token"], now=120)
        self.assertEqual(path.name, "screenshot.png")
        self.assertEqual(path.read_bytes(), b"image")
        self.assertEqual(path.parent.parent, Path(self.tmpdir.name))

    def test_resolve_rejects_invalid_and_expired_tokens(self):
        with self.assertRaises(UploadError):
            self.store.resolve("../../etc/passwd")

        metadata = self.store.save(PendingUpload("old.png", "image/png", b"image"), now=100)
        with self.assertRaises(UploadError):
            self.store.resolve(metadata["token"], now=161)
        self.assertFalse((Path(self.tmpdir.name) / metadata["token"]).exists())

    def test_consume_removes_upload(self):
        metadata = self.store.save(PendingUpload("once.png", "image/png", b"image"))
        self.store.consume(metadata["token"])

        with self.assertRaises(UploadError):
            self.store.resolve(metadata["token"])


if __name__ == "__main__":
    unittest.main()
