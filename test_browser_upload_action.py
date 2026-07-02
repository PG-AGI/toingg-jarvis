import tempfile
import unittest
from unittest.mock import Mock

from upload_store import (
    PendingUpload,
    UploadError,
    UploadStore,
    attach_uploaded_files,
)


class BrowserUploadActionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = UploadStore(self.tmpdir.name)
        self.page = Mock()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_input_file_resolves_tokens_and_consumes_them(self):
        first = self.store.save(PendingUpload("first.png", "image/png", b"one"))
        second = self.store.save(PendingUpload("second.jpg", "image/jpeg", b"two"))

        count = attach_uploaded_files(
            self.page,
            self.store,
            "input[type=file]",
            [first["token"], second["token"]],
            10000,
        )

        self.assertEqual(count, 2)
        paths = self.page.set_input_files.call_args.args[1]
        self.assertEqual([path.rsplit("/", 1)[-1] for path in paths], ["first.png", "second.jpg"])
        for token in (first["token"], second["token"]):
            with self.assertRaises(UploadError):
                self.store.resolve(token)

    def test_input_file_requires_upload_tokens(self):
        with self.assertRaisesRegex(UploadError, "requires token"):
            attach_uploaded_files(self.page, self.store, "input[type=file]", [], 10000)

    def test_input_file_cleans_up_when_playwright_fails(self):
        upload = self.store.save(PendingUpload("broken.png", "image/png", b"image"))
        self.page.set_input_files.side_effect = RuntimeError("browser rejected file")

        with self.assertRaisesRegex(RuntimeError, "browser rejected file"):
            attach_uploaded_files(
                self.page,
                self.store,
                "input[type=file]",
                [upload["token"]],
                10000,
            )
        with self.assertRaises(UploadError):
            self.store.resolve(upload["token"])


if __name__ == "__main__":
    unittest.main()
