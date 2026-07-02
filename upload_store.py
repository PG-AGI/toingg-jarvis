"""Temporary, token-addressed storage for browser file uploads."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_REQUEST_BYTES = 25 * 1024 * 1024
UPLOAD_TTL_SECONDS = 60 * 60


class UploadError(ValueError):
    """Raised when an upload cannot be accepted or resolved."""


@dataclass(frozen=True)
class PendingUpload:
    filename: str
    content_type: str
    data: bytes


def parse_multipart_images(content_type: str, body: bytes) -> list[PendingUpload]:
    """Parse image file fields from a bounded multipart request body."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise UploadError("Content-Type must be multipart/form-data")

    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\n"
        b"MIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise UploadError("Malformed multipart/form-data body")

    uploads = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        content_type = part.get_content_type().lower()
        if not content_type.startswith("image/"):
            raise UploadError(f"Unsupported file type for {filename!r}: {content_type}")
        data = part.get_payload(decode=True) or b""
        if not data:
            raise UploadError(f"Uploaded file {filename!r} is empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadError(
                f"Uploaded file {filename!r} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit"
            )
        uploads.append(PendingUpload(filename, content_type, data))

    if not uploads:
        raise UploadError("No image files were included in the request")
    return uploads


class UploadStore:
    """Store uploads under opaque UUID tokens shared by launcher and browser client."""

    def __init__(self, root: str | os.PathLike[str] | None = None, ttl_seconds: int = UPLOAD_TTL_SECONDS):
        configured_root = root or os.environ.get("JARVIS_UPLOAD_DIR")
        self.root = Path(configured_root or Path(tempfile.gettempdir()) / "jarvis_uploads")
        self.ttl_seconds = ttl_seconds

    def save(self, upload: PendingUpload, now: float | None = None) -> dict:
        self.cleanup_expired(now=now)
        token = str(uuid.uuid4())
        directory = self.root / token
        directory.mkdir(parents=True, exist_ok=False)
        filename = Path(upload.filename).name or "upload"
        path = directory / filename
        path.write_bytes(upload.data)
        created_at = time.time() if now is None else now
        metadata = {
            "token": token,
            "filename": filename,
            "content_type": upload.content_type,
            "size": len(upload.data),
            "created_at": created_at,
        }
        (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return metadata

    def resolve(self, token: str, now: float | None = None) -> Path:
        token = str(token).strip()
        try:
            normalized = str(uuid.UUID(token))
        except (ValueError, AttributeError) as exc:
            raise UploadError("Invalid upload token") from exc
        if normalized != token.lower():
            raise UploadError("Invalid upload token")

        directory = self.root / normalized
        metadata_path = directory / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            raise UploadError("Upload token was not found or has expired") from exc

        current_time = time.time() if now is None else now
        if current_time - float(metadata["created_at"]) > self.ttl_seconds:
            shutil.rmtree(directory, ignore_errors=True)
            raise UploadError("Upload token was not found or has expired")

        path = directory / metadata["filename"]
        if not path.is_file():
            raise UploadError("Uploaded file is no longer available")
        return path

    def consume(self, token: str) -> None:
        try:
            normalized = str(uuid.UUID(str(token).strip()))
        except (ValueError, AttributeError):
            return
        shutil.rmtree(self.root / normalized, ignore_errors=True)

    def cleanup_expired(self, now: float | None = None) -> None:
        if not self.root.exists():
            return
        current_time = time.time() if now is None else now
        for directory in self.root.iterdir():
            if not directory.is_dir():
                continue
            try:
                metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
                expired = current_time - float(metadata["created_at"]) > self.ttl_seconds
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
                expired = True
            if expired:
                shutil.rmtree(directory, ignore_errors=True)


def attach_uploaded_files(page, store: UploadStore, selector: str, tokens: list[str], timeout: int) -> int:
    """Resolve upload tokens, attach their files, and remove them after the attempt."""
    if not isinstance(tokens, list) or not tokens:
        raise UploadError("input_file requires token or a non-empty tokens list")
    paths = [str(store.resolve(token)) for token in tokens]
    try:
        page.set_input_files(selector, paths, timeout=timeout)
    finally:
        for token in tokens:
            store.consume(token)
    return len(paths)
