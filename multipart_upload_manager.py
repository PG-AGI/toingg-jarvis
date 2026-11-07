"""Multipart form-data upload staging and Playwright input_file resolution."""

from __future__ import annotations

import base64
from email import policy
from email.parser import BytesParser
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any
import uuid


DEFAULT_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB
DEFAULT_UPLOAD_TTL_SECONDS = 900.0  # 15 minutes

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "image/bmp",
    "image/avif",
}

ALLOWED_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".bmp",
    ".avif",
    ".pdf",
    ".txt",
    ".csv",
    ".json",
}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_UPLOAD_STORE: dict[str, dict[str, Any]] = {}
_UPLOAD_LOCK = threading.Lock()


class MultipartUploadError(ValueError):
    """Raised when multipart upload parsing, validation, or lookup fails."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _default_upload_dir(upload_dir: str | Path | None = None) -> Path:
    target = (
        Path(upload_dir)
        if upload_dir is not None
        else Path(tempfile.gettempdir()) / "jarvis_multipart_uploads"
    )
    target.mkdir(parents=True, exist_ok=True)
    return target


def sanitize_upload_filename(filename: str) -> str:
    raw = os.path.basename(str(filename or "").strip().replace("\\", "/"))
    if not raw or raw in {".", ".."}:
        raise MultipartUploadError("uploaded file must have a valid filename")
    stem, ext = os.path.splitext(raw)
    clean_stem = _SAFE_FILENAME_RE.sub("_", stem).strip("._-") or "upload"
    clean_ext = _SAFE_FILENAME_RE.sub("", ext.lower())
    if clean_ext and not clean_ext.startswith("."):
        clean_ext = f".{clean_ext}"
    return f"{clean_stem[:80]}{clean_ext[:16]}"


def cleanup_expired_uploads(now: float | None = None) -> int:
    current_time = time.time() if now is None else float(now)
    expired_tokens: list[tuple[str, str]] = []
    with _UPLOAD_LOCK:
        for token, entry in list(_UPLOAD_STORE.items()):
            if float(entry.get("expires_at", 0)) <= current_time:
                _UPLOAD_STORE.pop(token, None)
                expired_tokens.append((token, str(entry.get("path", ""))))

    removed = 0
    for _, path_str in expired_tokens:
        if path_str:
            try:
                Path(path_str).unlink(missing_ok=True)
            except OSError:
                pass
        removed += 1
    return removed


def cleanup_uploaded_token(file_token: str) -> bool:
    if not isinstance(file_token, str) or not file_token.strip():
        return False
    token = file_token.strip()
    with _UPLOAD_LOCK:
        entry = _UPLOAD_STORE.pop(token, None)
    if not entry:
        return False
    path_str = str(entry.get("path", ""))
    if path_str:
        try:
            Path(path_str).unlink(missing_ok=True)
        except OSError:
            pass
    return True


def clear_all_uploads() -> int:
    with _UPLOAD_LOCK:
        entries = list(_UPLOAD_STORE.values())
        _UPLOAD_STORE.clear()
    for entry in entries:
        path_str = str(entry.get("path", ""))
        if path_str:
            try:
                Path(path_str).unlink(missing_ok=True)
            except OSError:
                pass
    return len(entries)


def store_uploaded_file(
    filename: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    ttl_seconds: float = DEFAULT_UPLOAD_TTL_SECONDS,
    upload_dir: str | Path | None = None,
    images_only: bool = False,
    allowed_extensions: set[str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    cleanup_expired_uploads(now=now)

    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise MultipartUploadError("uploaded file payload must not be empty")

    safe_name = sanitize_upload_filename(filename)
    ext = Path(safe_name).suffix.lower()
    permitted_exts = allowed_extensions if allowed_extensions is not None else ALLOWED_UPLOAD_EXTENSIONS
    if permitted_exts and ext not in permitted_exts:
        raise MultipartUploadError(
            f"unsupported file extension '{ext or '(none)'}'; allowed: {', '.join(sorted(permitted_exts))}",
            status_code=415,
        )

    normalized_ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized_ctype or normalized_ctype == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(safe_name)
        normalized_ctype = (guessed or "application/octet-stream").lower()

    if images_only and normalized_ctype not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise MultipartUploadError(
            f"unsupported image content type '{normalized_ctype}'",
            status_code=415,
        )

    target_dir = _default_upload_dir(upload_dir)
    file_token = f"upl_{uuid.uuid4().hex[:16]}"
    target_path = (target_dir / f"{file_token}_{safe_name}").resolve()
    target_path.write_bytes(bytes(data))

    current_time = time.time() if now is None else float(now)
    expires_at = current_time + max(1.0, float(ttl_seconds))
    metadata = {
        "file_token": file_token,
        "path": str(target_path),
        "filename": safe_name,
        "content_type": normalized_ctype,
        "size": len(data),
        "created_at": current_time,
        "expires_at": expires_at,
    }
    with _UPLOAD_LOCK:
        _UPLOAD_STORE[file_token] = metadata
    return dict(metadata)


def get_uploaded_file(file_token: str, now: float | None = None) -> dict[str, Any]:
    cleanup_expired_uploads(now=now)
    if not isinstance(file_token, str) or not file_token.strip():
        raise MultipartUploadError("file_token must be a non-empty string")
    token = file_token.strip()
    with _UPLOAD_LOCK:
        entry = _UPLOAD_STORE.get(token)
        if entry is not None:
            entry = dict(entry)

    if entry is None:
        raise MultipartUploadError(
            f"unknown or expired file_token: {token}",
            status_code=404,
        )

    path_obj = Path(entry["path"])
    if not path_obj.exists() or not path_obj.is_file():
        with _UPLOAD_LOCK:
            _UPLOAD_STORE.pop(token, None)
        raise MultipartUploadError(
            f"uploaded file for token {token} is no longer available",
            status_code=404,
        )
    return entry


def parse_multipart_form_data(
    content_type: str,
    body: bytes,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not isinstance(content_type, str) or "multipart/form-data" not in content_type.lower():
        raise MultipartUploadError(
            "Content-Type must be multipart/form-data with a boundary",
            status_code=415,
        )
    if "boundary=" not in content_type.lower():
        raise MultipartUploadError(
            "multipart/form-data header is missing boundary parameter",
            status_code=400,
        )
    if not isinstance(body, (bytes, bytearray)) or len(body) == 0:
        raise MultipartUploadError("multipart request body is empty", status_code=400)
    if max_bytes and len(body) > max_bytes:
        raise MultipartUploadError(
            f"upload exceeds maximum allowed size of {max_bytes} bytes",
            status_code=413,
        )

    mime_blob = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + bytes(body)
    )
    message = BytesParser(policy=policy.default).parsebytes(mime_blob)
    if not message.is_multipart():
        raise MultipartUploadError("failed to parse multipart/form-data payload", status_code=400)

    files: list[dict[str, Any]] = []
    fields: dict[str, str] = {}

    for part in message.iter_parts():
        disposition = (part.get_content_disposition() or "").lower()
        if disposition != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition") or "file"
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if payload is None:
            raw_payload = part.get_payload()
            payload = (
                raw_payload.encode("utf-8")
                if isinstance(raw_payload, str)
                else b""
            )

        if filename is not None:
            if not str(filename).strip():
                raise MultipartUploadError("multipart file part has an empty filename", status_code=400)
            files.append(
                {
                    "field_name": str(field_name),
                    "filename": str(filename),
                    "content_type": part.get_content_type() or "application/octet-stream",
                    "data": bytes(payload),
                    "size": len(payload),
                }
            )
        else:
            fields[str(field_name)] = bytes(payload).decode("utf-8", errors="replace")

    if not files:
        raise MultipartUploadError(
            "no file part found in multipart/form-data payload",
            status_code=400,
        )
    return files, fields


def handle_multipart_upload_request(
    content_type: str,
    body: bytes,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ttl_seconds: float = DEFAULT_UPLOAD_TTL_SECONDS,
    upload_dir: str | Path | None = None,
    images_only: bool = False,
    allowed_extensions: set[str] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    parsed_files, fields = parse_multipart_form_data(
        content_type=content_type,
        body=body,
        max_bytes=max_bytes,
    )
    effective_ttl = float(fields.get("ttl_seconds", ttl_seconds))
    effective_images_only = images_only or str(fields.get("images_only", "")).lower() in {"1", "true", "yes"}

    stored_files = [
        store_uploaded_file(
            filename=item["filename"],
            data=item["data"],
            content_type=item["content_type"],
            ttl_seconds=effective_ttl,
            upload_dir=upload_dir,
            images_only=effective_images_only,
            allowed_extensions=allowed_extensions,
            now=now,
        )
        for item in parsed_files
    ]
    primary = stored_files[0]
    return {
        "ok": True,
        "file_token": primary["file_token"],
        "path": primary["path"],
        "filename": primary["filename"],
        "content_type": primary["content_type"],
        "size": primary["size"],
        "expires_at": primary["expires_at"],
        "files": stored_files,
        "fields": fields,
    }


def _decode_inline_file(
    raw_b64: str,
    filename: str = "upload.png",
    upload_dir: str | Path | None = None,
) -> str:
    text = raw_b64.strip()
    inferred_ext = ""
    if text.startswith("data:"):
        header, _, encoded = text.partition(",")
        if not encoded:
            raise MultipartUploadError("invalid data URL for input_file")
        mime_part = header[5:].split(";", 1)[0].strip().lower()
        inferred_ext = mimetypes.guess_extension(mime_part) or ""
        text = encoded
    try:
        binary = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise MultipartUploadError("invalid base64 payload for input_file") from exc

    if not binary:
        raise MultipartUploadError("decoded base64 file payload is empty")

    if inferred_ext and not Path(filename).suffix:
        filename = f"{filename}{inferred_ext}"
    safe_name = sanitize_upload_filename(filename)
    target_dir = _default_upload_dir(upload_dir)
    temp_path = (target_dir / f"inline_{uuid.uuid4().hex[:12]}_{safe_name}").resolve()
    temp_path.write_bytes(binary)
    return str(temp_path)


def resolve_playwright_input_files(
    params: dict[str, Any],
    upload_dir: str | Path | None = None,
    now: float | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Resolve input_file parameters into local file paths.

    Returns (resolved_paths, consumed_tokens, ephemeral_paths).
    """
    if not isinstance(params, dict):
        raise MultipartUploadError("input_file parameters must be a JSON object")

    cleanup_expired_uploads(now=now)

    resolved_paths: list[str] = []
    consumed_tokens: list[str] = []
    ephemeral_paths: list[str] = []

    raw_tokens: list[Any] = []
    for key in ("file_token", "token", "upload_token"):
        val = params.get(key)
        if val is not None:
            if isinstance(val, list):
                raw_tokens.extend(val)
            else:
                raw_tokens.append(val)
    for key in ("file_tokens", "tokens", "upload_tokens"):
        val = params.get(key)
        if val is not None:
            if not isinstance(val, list):
                raise MultipartUploadError(f"{key} must be a list of token strings")
            raw_tokens.extend(val)

    for token_item in raw_tokens:
        if not isinstance(token_item, str) or not token_item.strip():
            raise MultipartUploadError("file_token must be a non-empty string")
        entry = get_uploaded_file(token_item.strip(), now=now)
        resolved_paths.append(entry["path"])
        consumed_tokens.append(entry["file_token"])

    raw_files: list[Any] = []
    for key in ("files", "file_paths", "paths"):
        val = params.get(key)
        if val is not None:
            if isinstance(val, list):
                raw_files.extend(val)
            else:
                raw_files.append(val)
    for key in ("file_path", "path", "file"):
        val = params.get(key)
        if val is not None:
            if isinstance(val, list):
                raw_files.extend(val)
            else:
                raw_files.append(val)
    if not raw_tokens and not raw_files and params.get("value") is not None:
        val = params.get("value")
        if isinstance(val, list):
            raw_files.extend(val)
        else:
            raw_files.append(val)

    for item in raw_files:
        if isinstance(item, dict):
            if item.get("file_token") or item.get("token"):
                tok = str(item.get("file_token") or item.get("token")).strip()
                entry = get_uploaded_file(tok, now=now)
                resolved_paths.append(entry["path"])
                consumed_tokens.append(entry["file_token"])
                continue
            if item.get("base64") or item.get("data"):
                b64_data = str(item.get("base64") or item.get("data"))
                fname = str(item.get("filename") or item.get("name") or "upload.png")
                inline_path = _decode_inline_file(b64_data, filename=fname, upload_dir=upload_dir)
                resolved_paths.append(inline_path)
                ephemeral_paths.append(inline_path)
                continue
            if item.get("path") or item.get("file_path"):
                item = item.get("path") or item.get("file_path")
            else:
                raise MultipartUploadError(
                    "file object must contain file_token, path, or base64"
                )

        if not isinstance(item, str) or not item.strip():
            raise MultipartUploadError("file path must be a non-empty string")
        text = item.strip()

        if text.startswith("upl_"):
            try:
                entry = get_uploaded_file(text, now=now)
                resolved_paths.append(entry["path"])
                consumed_tokens.append(entry["file_token"])
                continue
            except MultipartUploadError:
                if not Path(text).exists():
                    raise

        if text.startswith("data:"):
            fname = str(params.get("filename") or "upload.png")
            inline_path = _decode_inline_file(text, filename=fname, upload_dir=upload_dir)
            resolved_paths.append(inline_path)
            ephemeral_paths.append(inline_path)
            continue

        candidate = Path(os.path.expandvars(os.path.expanduser(text))).resolve()
        if not candidate.exists() or not candidate.is_file():
            raise MultipartUploadError(f"input_file path does not exist or is not a file: {text}")
        resolved_paths.append(str(candidate))

    inline_b64 = (
        params.get("base64")
        or params.get("file_base64")
        or params.get("content_base64")
    )
    if inline_b64 is not None:
        if not isinstance(inline_b64, str) or not inline_b64.strip():
            raise MultipartUploadError("base64 payload must be a non-empty string")
        fname = str(params.get("filename") or "upload.png")
        inline_path = _decode_inline_file(inline_b64, filename=fname, upload_dir=upload_dir)
        resolved_paths.append(inline_path)
        ephemeral_paths.append(inline_path)

    if not resolved_paths:
        raise MultipartUploadError(
            "input_file requires file_token, path, file_path, files, or base64"
        )

    return resolved_paths, consumed_tokens, ephemeral_paths


def finalize_playwright_input_files(
    consumed_tokens: list[str],
    ephemeral_paths: list[str],
    keep_uploaded: bool = False,
) -> None:
    if not keep_uploaded:
        for token in consumed_tokens:
            cleanup_uploaded_token(token)
    for temp_path in ephemeral_paths:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass
