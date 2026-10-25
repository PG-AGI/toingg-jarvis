"""
multipart_upload_manager.py — Multipart form-data file upload store and Playwright input_file resolver.

Provides:
- RFC-compliant `multipart/form-data` parsing using only the Python standard library
  (compatible with Python 3.10+ including Python 3.13+ where `cgi` was removed).
- Temporary file storage with cross-process token resolution (`upl_<uuid>`) so
  `jarvis_launcher.py` HTTP uploads can be consumed by `browserClient.py` WebSocket
  `input_file` actions or local Playwright tool actions.
- Automatic post-action cleanup and TTL expiration cleanup.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import tempfile
import time
import uuid
from email.parser import BytesParser
from email.policy import default as default_email_policy
from pathlib import Path
from typing import Any


DEFAULT_UPLOAD_TTL_SECONDS = 3600
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB default ceiling


class MultipartUploadError(ValueError):
    """Raised when a multipart upload or input_file payload is invalid."""


def get_upload_root(custom_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return and ensure the temporary directory used for staged uploads."""
    if custom_dir:
        root = Path(custom_dir).expanduser().resolve()
    else:
        env_dir = os.environ.get("JARVIS_UPLOAD_DIR", "").strip()
        if env_dir:
            root = Path(env_dir).expanduser().resolve()
        else:
            root = Path(tempfile.gettempdir()).resolve() / "jarvis_uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(filename: str | None, default_ext: str = ".bin") -> str:
    """Strip directory traversal components and unsafe characters from an uploaded filename."""
    raw = os.path.basename(str(filename or "").replace("\\", "/")).strip()
    if not raw or raw in {".", ".."}:
        return f"upload{default_ext}"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
    if not cleaned:
        return f"upload{default_ext}"
    return cleaned[:120]


def _meta_path(root: Path, token: str) -> Path:
    if not re.fullmatch(r"upl_[a-f0-9]{16,32}", str(token or "")):
        raise MultipartUploadError(f"Invalid file token: {token!r}")
    return root / f"{token}.json"


def store_uploaded_bytes(
    data: bytes,
    filename: str | None = None,
    content_type: str | None = None,
    *,
    upload_dir: str | os.PathLike[str] | None = None,
    ttl_seconds: int = DEFAULT_UPLOAD_TTL_SECONDS,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> dict[str, Any]:
    """Persist uploaded file bytes in the temporary upload store and return token metadata."""
    if not isinstance(data, (bytes, bytearray)):
        raise MultipartUploadError("Uploaded file content must be bytes")
    raw_bytes = bytes(data)
    if len(raw_bytes) == 0:
        raise MultipartUploadError("Uploaded file cannot be empty")
    if len(raw_bytes) > max_bytes:
        raise MultipartUploadError(
            f"Uploaded file size ({len(raw_bytes)} bytes) exceeds limit ({max_bytes} bytes)"
        )

    cleanup_expired_uploads(upload_dir=upload_dir)

    guessed_ext = mimetypes.guess_extension(content_type or "") or ".bin"
    safe_name = sanitize_filename(filename, default_ext=guessed_ext)
    resolved_ctype = (
        content_type
        or mimetypes.guess_type(safe_name)[0]
        or "application/octet-stream"
    )

    root = get_upload_root(upload_dir)
    token = f"upl_{uuid.uuid4().hex[:24]}"
    token_dir = root / token
    token_dir.mkdir(parents=True, exist_ok=True)
    stored_path = token_dir / safe_name
    stored_path.write_bytes(raw_bytes)

    now = time.time()
    expires_at = now + max(1, int(ttl_seconds))
    metadata = {
        "file_token": token,
        "filename": safe_name,
        "content_type": resolved_ctype,
        "size": len(raw_bytes),
        "path": str(stored_path),
        "created_at": now,
        "expires_at": expires_at,
    }
    _meta_path(root, token).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def parse_multipart_form_data(
    body: bytes,
    content_type_header: str,
    *,
    upload_dir: str | os.PathLike[str] | None = None,
    ttl_seconds: int = DEFAULT_UPLOAD_TTL_SECONDS,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> dict[str, Any]:
    """Parse an HTTP `multipart/form-data` body, store uploaded files, and return tokens + fields."""
    if not isinstance(content_type_header, str) or "multipart/form-data" not in content_type_header.lower():
        raise MultipartUploadError("Content-Type must be multipart/form-data with a boundary")
    if "boundary=" not in content_type_header.lower():
        raise MultipartUploadError("multipart/form-data header is missing boundary parameter")
    if not body:
        raise MultipartUploadError("Request body is empty")

    mime_blob = (
        f"Content-Type: {content_type_header}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body

    msg = BytesParser(policy=default_email_policy).parsebytes(mime_blob)
    if not msg.is_multipart():
        raise MultipartUploadError("Failed to parse multipart/form-data payload")

    files: list[dict[str, Any]] = []
    fields: dict[str, str] = {}

    for part in msg.iter_parts():
        disposition = part.get_content_disposition()
        if disposition != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition") or "file"
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        part_ctype = part.get_content_type() or "application/octet-stream"

        if filename is not None:
            record = store_uploaded_bytes(
                payload,
                filename=filename,
                content_type=part_ctype,
                upload_dir=upload_dir,
                ttl_seconds=ttl_seconds,
                max_bytes=max_bytes,
            )
            record["field_name"] = field_name
            files.append(record)
        else:
            fields[str(field_name)] = payload.decode("utf-8", errors="replace")

    if not files:
        raise MultipartUploadError("No file part found in multipart/form-data request")

    primary = files[0]
    return {
        "ok": True,
        "file_token": primary["file_token"],
        "filename": primary["filename"],
        "content_type": primary["content_type"],
        "size": primary["size"],
        "path": primary["path"],
        "expires_at": primary["expires_at"],
        "files": files,
        "fields": fields,
    }


def get_uploaded_file_metadata(
    token: str,
    *,
    upload_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Look up an uploaded file token and verify that it has not expired or been removed."""
    root = get_upload_root(upload_dir)
    meta_file = _meta_path(root, token)
    if not meta_file.exists():
        raise MultipartUploadError(f"Unknown or expired file token: {token}")

    try:
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MultipartUploadError(f"Corrupted metadata for token: {token}") from exc

    now = time.time()
    if float(metadata.get("expires_at", 0)) < now:
        cleanup_uploaded_token(token, upload_dir=upload_dir)
        raise MultipartUploadError(f"File token has expired: {token}")

    file_path = Path(metadata.get("path", ""))
    if not file_path.exists() or not file_path.is_file():
        cleanup_uploaded_token(token, upload_dir=upload_dir)
        raise MultipartUploadError(f"Staged upload file is missing for token: {token}")

    return metadata


def cleanup_uploaded_token(
    token: str,
    *,
    upload_dir: str | os.PathLike[str] | None = None,
) -> bool:
    """Delete both the staged file and its metadata JSON for a given token."""
    root = get_upload_root(upload_dir)
    meta_file = _meta_path(root, token)
    removed = False
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            staged = Path(meta.get("path", ""))
            if staged.exists():
                staged.unlink()
                removed = True
        except Exception:
            pass
        try:
            meta_file.unlink()
            removed = True
        except Exception:
            pass

    token_dir = root / token
    if token_dir.exists() and token_dir.is_dir():
        for child in list(token_dir.iterdir()):
            try:
                child.unlink()
                removed = True
            except Exception:
                pass
        try:
            token_dir.rmdir()
            removed = True
        except Exception:
            pass
    for leftover in root.glob(f"{token}_*"):
        try:
            leftover.unlink()
            removed = True
        except Exception:
            pass
    return removed


def cleanup_expired_uploads(
    *,
    upload_dir: str | os.PathLike[str] | None = None,
    now: float | None = None,
) -> int:
    """Remove all expired upload tokens and return the count of cleaned tokens."""
    root = get_upload_root(upload_dir)
    current = time.time() if now is None else float(now)
    cleaned = 0
    for meta_file in list(root.glob("upl_*.json")):
        token = meta_file.stem
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            expires_at = float(meta.get("expires_at", 0))
            staged = Path(meta.get("path", ""))
            if expires_at < current or not staged.exists():
                if cleanup_uploaded_token(token, upload_dir=upload_dir):
                    cleaned += 1
        except Exception:
            if cleanup_uploaded_token(token, upload_dir=upload_dir):
                cleaned += 1
    return cleaned


def _decode_inline_base64(data_str: str) -> bytes:
    text = str(data_str or "").strip()
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise MultipartUploadError("Invalid base64 file content") from exc


def resolve_input_files(
    params: dict[str, Any],
    *,
    upload_dir: str | os.PathLike[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Resolve `input_file` parameters into a list of existing local file paths and a list of
    temporary tokens that should be cleaned up after `page.set_input_files(...)` completes.

    Supported parameter shapes:
    - `file_token` / `token` / `file_tokens` / `tokens`
    - `file_path` / `path` / `files` (containing either tokens `upl_...` or local file paths)
    - `base64` / `content_base64` (+ optional `filename`, `content_type`)
    """
    if not isinstance(params, dict):
        raise MultipartUploadError("input_file params must be a JSON object")

    cleanup_expired_uploads(upload_dir=upload_dir)

    resolved_paths: list[str] = []
    tokens_to_cleanup: list[str] = []

    def _add_token(tok: str) -> None:
        meta = get_uploaded_file_metadata(tok, upload_dir=upload_dir)
        resolved_paths.append(meta["path"])
        if tok not in tokens_to_cleanup:
            tokens_to_cleanup.append(tok)

    def _add_token_or_path(item: Any) -> None:
        if isinstance(item, dict):
            if item.get("file_token") or item.get("token"):
                _add_token(str(item.get("file_token") or item.get("token")).strip())
                return
            if item.get("base64") or item.get("content_base64"):
                raw = _decode_inline_base64(item.get("base64") or item.get("content_base64"))
                meta = store_uploaded_bytes(
                    raw,
                    filename=item.get("filename"),
                    content_type=item.get("content_type"),
                    upload_dir=upload_dir,
                )
                resolved_paths.append(meta["path"])
                tokens_to_cleanup.append(meta["file_token"])
                return
            item = item.get("file_path") or item.get("path")

        if not isinstance(item, str) or not item.strip():
            raise MultipartUploadError("File reference must be a non-empty string")
        text = item.strip()
        if re.fullmatch(r"upl_[a-f0-9]{16,32}", text):
            _add_token(text)
            return

        candidate = Path(os.path.expandvars(os.path.expanduser(text))).resolve()
        if not candidate.exists() or not candidate.is_file():
            raise MultipartUploadError(f"Input file does not exist: {text}")
        resolved_paths.append(str(candidate))

    # 1. Explicit tokens
    for key in ("file_token", "token"):
        val = params.get(key)
        if val is not None:
            _add_token(str(val).strip())

    for key in ("file_tokens", "tokens"):
        val = params.get(key)
        if val is not None:
            if not isinstance(val, list) or not val:
                raise MultipartUploadError(f"{key} must be a non-empty list")
            for tok in val:
                _add_token(str(tok).strip())

    # 2. Inline base64 upload fallback
    if params.get("base64") or params.get("content_base64"):
        raw = _decode_inline_base64(params.get("base64") or params.get("content_base64"))
        meta = store_uploaded_bytes(
            raw,
            filename=params.get("filename"),
            content_type=params.get("content_type"),
            upload_dir=upload_dir,
        )
        resolved_paths.append(meta["path"])
        tokens_to_cleanup.append(meta["file_token"])

    # 3. Direct paths or mixed `files` array
    for key in ("file_path", "path"):
        val = params.get(key)
        if val is not None and not resolved_paths:
            _add_token_or_path(val)

    if params.get("files") is not None:
        files_val = params.get("files")
        if isinstance(files_val, (str, dict)):
            _add_token_or_path(files_val)
        elif isinstance(files_val, list) and files_val:
            for entry in files_val:
                _add_token_or_path(entry)
        else:
            raise MultipartUploadError("files must be a non-empty list or string")

    if not resolved_paths:
        raise MultipartUploadError(
            "input_file requires file_token, file_tokens, files, file_path, or base64"
        )

    return resolved_paths, tokens_to_cleanup
