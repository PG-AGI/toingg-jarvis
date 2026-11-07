"""Playwright screenshot capture and multipart/form-data backend upload helpers."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import uuid


DEFAULT_SCREENSHOT_FILENAME = "screenshot.png"
DEFAULT_SCREENSHOT_FIELD_NAME = "file"
DEFAULT_LOCAL_UPLOAD_URL = "http://localhost:8766/upload"

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ScreenshotUploadError(RuntimeError):
    """Raised when capturing, encoding, or uploading a screenshot fails."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def sanitize_screenshot_filename(filename: str | None = None) -> str:
    raw = os.path.basename(str(filename or DEFAULT_SCREENSHOT_FILENAME).strip().replace("\\", "/"))
    if not raw or raw in {".", ".."}:
        raw = DEFAULT_SCREENSHOT_FILENAME
    stem, ext = os.path.splitext(raw)
    clean_stem = _SAFE_FILENAME_RE.sub("_", stem).strip("._-") or "screenshot"
    clean_ext = _SAFE_FILENAME_RE.sub("", ext.lower()) or ".png"
    if not clean_ext.startswith("."):
        clean_ext = f".{clean_ext}"
    return f"{clean_stem[:80]}{clean_ext[:12]}"


def derive_backend_upload_url_from_ws(ws_url: str | None) -> str | None:
    if not isinstance(ws_url, str) or not ws_url.strip():
        return None
    parsed = urlparse(ws_url.strip())
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        return None
    http_scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{http_scheme}://{parsed.netloc}/upload"


def _read_config_upload_settings(config_path: str | Path | None = None) -> tuple[str | None, str | None]:
    path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parent / "config.json"
    )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    if not isinstance(raw, dict):
        return None, None
    url = (
        raw.get("SCREENSHOT_UPLOAD_URL")
        or raw.get("UPLOAD_URL")
        or raw.get("screenshot_upload_url")
        or raw.get("upload_url")
    )
    token = raw.get("TOKEN") or raw.get("token")
    clean_url = str(url).strip() if isinstance(url, str) and url.strip() else None
    clean_token = str(token).strip() if isinstance(token, str) and token.strip() else None
    return clean_url, clean_token


def resolve_screenshot_upload_url(
    params: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    default_url: str | None = None,
    ws_url: str | None = None,
) -> str | None:
    payload = params if isinstance(params, dict) else {}

    if payload.get("upload") is False:
        return None

    for key in ("upload_url", "endpoint", "api_url"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    for env_key in ("JARVIS_SCREENSHOT_UPLOAD_URL", "TOINGG_SCREENSHOT_UPLOAD_URL"):
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            return env_val

    cfg_url, _ = _read_config_upload_settings(config_path=config_path)
    if cfg_url:
        return cfg_url

    if isinstance(default_url, str) and default_url.strip():
        return default_url.strip()

    if bool(payload.get("upload", False)):
        derived = derive_backend_upload_url_from_ws(ws_url)
        return derived or DEFAULT_LOCAL_UPLOAD_URL

    return None


def build_multipart_form_data(
    file_bytes: bytes,
    filename: str = DEFAULT_SCREENSHOT_FILENAME,
    field_name: str = DEFAULT_SCREENSHOT_FIELD_NAME,
    content_type: str = "image/png",
    extra_fields: dict[str, Any] | None = None,
    boundary: str | None = None,
) -> tuple[str, bytes]:
    if not isinstance(file_bytes, (bytes, bytearray)) or len(file_bytes) == 0:
        raise ScreenshotUploadError("screenshot byte payload must not be empty")

    safe_filename = sanitize_screenshot_filename(filename)
    clean_field = str(field_name or DEFAULT_SCREENSHOT_FIELD_NAME).strip() or DEFAULT_SCREENSHOT_FIELD_NAME
    active_boundary = boundary or f"----JarvisScreenshotBoundary{uuid.uuid4().hex}"

    parts: list[bytes] = []
    for k, v in (extra_fields or {}).items():
        if v is None:
            continue
        key_str = str(k).replace('"', "")
        val_str = str(v)
        parts.append(f"--{active_boundary}\r\n".encode("utf-8"))
        parts.append(
            f'Content-Disposition: form-data; name="{key_str}"\r\n\r\n{val_str}\r\n'.encode("utf-8")
        )

    parts.append(f"--{active_boundary}\r\n".encode("utf-8"))
    parts.append(
        (
            f'Content-Disposition: form-data; name="{clean_field}"; filename="{safe_filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(bytes(file_bytes))
    parts.append(b"\r\n")
    parts.append(f"--{active_boundary}--\r\n".encode("utf-8"))

    header_value = f"multipart/form-data; boundary={active_boundary}"
    return header_value, b"".join(parts)


def upload_screenshot_bytes(
    image_bytes: bytes,
    upload_url: str,
    filename: str = DEFAULT_SCREENSHOT_FILENAME,
    field_name: str = DEFAULT_SCREENSHOT_FIELD_NAME,
    content_type: str = "image/png",
    headers: dict[str, str] | None = None,
    extra_fields: dict[str, Any] | None = None,
    timeout: float = 15.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(upload_url, str) or not upload_url.strip():
        raise ScreenshotUploadError("upload_url must be a non-empty string")

    safe_filename = sanitize_screenshot_filename(filename)
    multipart_ctype, body = build_multipart_form_data(
        file_bytes=image_bytes,
        filename=safe_filename,
        field_name=field_name,
        content_type=content_type,
        extra_fields=extra_fields,
    )

    request_headers = {
        "Content-Type": multipart_ctype,
        "Content-Length": str(len(body)),
        "Accept": "application/json, text/plain, */*",
    }
    if isinstance(headers, dict):
        for k, v in headers.items():
            if k and v is not None:
                request_headers[str(k)] = str(v)

    req = request.Request(
        upload_url.strip(),
        data=body,
        headers=request_headers,
        method="POST",
    )
    open_fn = opener or request.urlopen

    try:
        with open_fn(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode() or 200
            raw_body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise ScreenshotUploadError(
            f"screenshot upload failed with HTTP {exc.code}: {err_body or exc.reason}",
            status_code=int(exc.code),
        ) from exc
    except URLError as exc:
        raise ScreenshotUploadError(
            f"screenshot upload failed: {exc.reason}",
            status_code=502,
        ) from exc

    parsed_response: Any
    if raw_body:
        try:
            parsed_response = json.loads(raw_body)
        except json.JSONDecodeError:
            parsed_response = {"text": raw_body}
    else:
        parsed_response = {}

    return {
        "uploaded": 200 <= int(status) < 300,
        "upload_url": upload_url.strip(),
        "status": int(status),
        "filename": safe_filename,
        "field_name": field_name,
        "size": len(image_bytes),
        "response": parsed_response,
    }


def parse_multipart_upload(
    content_type: str,
    body: bytes,
    upload_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Parse an incoming multipart/form-data POST /upload request and store the file."""
    if not isinstance(content_type, str) or "multipart/form-data" not in content_type.lower():
        raise ScreenshotUploadError("Content-Type must be multipart/form-data", status_code=415)
    if "boundary=" not in content_type.lower():
        raise ScreenshotUploadError("multipart/form-data is missing boundary", status_code=400)
    if not isinstance(body, (bytes, bytearray)) or len(body) == 0:
        raise ScreenshotUploadError("multipart request body is empty", status_code=400)

    raw_message = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + bytes(body)
    )
    msg = BytesParser(policy=policy.default).parsebytes(raw_message)
    if not msg.is_multipart():
        raise ScreenshotUploadError("invalid multipart/form-data payload", status_code=400)

    file_part = None
    fields: dict[str, str] = {}
    for part in msg.iter_parts():
        if (part.get_content_disposition() or "").lower() != "form-data":
            continue
        field_name = part.get_param("name", header="content-disposition") or "file"
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if payload is None:
            raw_payload = part.get_payload()
            payload = raw_payload.encode("utf-8") if isinstance(raw_payload, str) else b""

        if filename is not None or field_name in {"file", "screenshot", "image"}:
            if file_part is None:
                file_part = {
                    "field_name": str(field_name),
                    "filename": sanitize_screenshot_filename(filename or DEFAULT_SCREENSHOT_FILENAME),
                    "content_type": part.get_content_type() or "image/png",
                    "data": bytes(payload),
                }
        else:
            fields[str(field_name)] = bytes(payload).decode("utf-8", errors="replace")

    if file_part is None or len(file_part["data"]) == 0:
        raise ScreenshotUploadError("no non-empty file part found in multipart upload", status_code=400)

    target_dir = (
        Path(upload_dir)
        if upload_dir is not None
        else Path(tempfile.gettempdir()) / "jarvis_screenshots"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / f"{uuid.uuid4().hex[:10]}_{file_part['filename']}").resolve()
    target_path.write_bytes(file_part["data"])

    return {
        "ok": True,
        "filename": file_part["filename"],
        "field_name": file_part["field_name"],
        "content_type": file_part["content_type"],
        "size": len(file_part["data"]),
        "path": str(target_path),
        "fields": fields,
    }


def capture_and_handle_screenshot(
    page: Any,
    params: dict[str, Any] | None = None,
    default_upload_url: str | None = None,
    ws_url: str | None = None,
    config_path: str | Path | None = None,
    opener: Callable[..., Any] | None = None,
    default_full_page: bool = False,
) -> dict[str, Any]:
    """Capture a Playwright screenshot and upload it as multipart/form-data when configured."""
    payload = params if isinstance(params, dict) else {}
    full_page = bool(payload.get("full_page", default_full_page))
    local_path = payload.get("path")
    filename = sanitize_screenshot_filename(
        payload.get("filename")
        or (os.path.basename(str(local_path)) if isinstance(local_path, str) and local_path.strip() else None)
        or DEFAULT_SCREENSHOT_FILENAME
    )
    field_name = str(payload.get("field_name") or DEFAULT_SCREENSHOT_FIELD_NAME).strip() or DEFAULT_SCREENSHOT_FIELD_NAME

    upload_url = resolve_screenshot_upload_url(
        payload,
        config_path=config_path,
        default_url=default_upload_url,
        ws_url=ws_url,
    )

    screenshot_kwargs: dict[str, Any] = {"full_page": full_page}
    if isinstance(local_path, str) and local_path.strip():
        screenshot_kwargs["path"] = local_path.strip()

    img_bytes = page.screenshot(**screenshot_kwargs)
    if not isinstance(img_bytes, (bytes, bytearray)) and isinstance(local_path, str) and local_path.strip():
        p = Path(local_path.strip())
        if p.is_file():
            img_bytes = p.read_bytes()

    if upload_url:
        headers: dict[str, str] = {}
        if isinstance(payload.get("headers"), dict):
            headers.update({str(k): str(v) for k, v in payload["headers"].items()})
        _, cfg_token = _read_config_upload_settings(config_path=config_path)
        token = payload.get("token") or payload.get("auth_token") or cfg_token
        if isinstance(token, str) and token.strip() and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token.strip()}"

        extra_fields = payload.get("form_fields") if isinstance(payload.get("form_fields"), dict) else None
        upload_info = upload_screenshot_bytes(
            image_bytes=bytes(img_bytes),
            upload_url=upload_url,
            filename=filename,
            field_name=field_name,
            headers=headers,
            extra_fields=extra_fields,
            timeout=float(payload.get("upload_timeout", 15.0)),
            opener=opener,
        )
        result = {
            **upload_info,
            "bytes": bytes(img_bytes),
        }
        if isinstance(local_path, str) and local_path.strip():
            result["path"] = local_path.strip()
        return result

    return {
        "uploaded": False,
        "filename": filename,
        "size": len(img_bytes) if isinstance(img_bytes, (bytes, bytearray)) else 0,
        "path": local_path.strip() if isinstance(local_path, str) and local_path.strip() else None,
        "bytes": bytes(img_bytes) if isinstance(img_bytes, (bytes, bytearray)) else b"",
    }
