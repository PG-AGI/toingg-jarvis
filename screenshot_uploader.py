"""
screenshot_uploader.py — Direct Playwright screenshot capture & multipart/form-data backend upload.

Implements Issue #3:
- Captures screenshots in memory via Playwright (`page.screenshot(...)`).
- Packages the PNG bytes as a `multipart/form-data` file upload (`file: screenshot.png`).
- Uploads directly to the configured backend API endpoint (`POST /upload` or custom `upload_url`).
- Also provides a server-side `multipart/form-data` receiver for `POST /upload` in `jarvis_launcher.py`.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.request
import uuid
from email.parser import BytesParser
from email.policy import default as default_email_policy
from pathlib import Path
from typing import Any, Callable


class ScreenshotUploadError(ValueError):
    """Raised when screenshot packaging or backend upload fails."""


def build_multipart_screenshot_payload(
    image_bytes: bytes,
    *,
    filename: str = "screenshot.png",
    field_name: str = "file",
    content_type: str = "image/png",
    extra_fields: dict[str, str] | None = None,
    boundary: str | None = None,
) -> tuple[bytes, str]:
    """
    Build an RFC 2046 `multipart/form-data` request body and `Content-Type` header
    containing the screenshot file part (`file: screenshot.png`).
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
        raise ScreenshotUploadError("Screenshot image_bytes must be non-empty bytes")

    chosen_boundary = boundary or f"----JarvisScreenshotBoundary{uuid.uuid4().hex[:20]}"
    safe_filename = os.path.basename(str(filename or "screenshot.png").replace("\\", "/")) or "screenshot.png"
    safe_field = str(field_name or "file").replace('"', "")

    parts: list[bytes] = []
    if extra_fields:
        for k, v in extra_fields.items():
            if v is None:
                continue
            parts.append(f"--{chosen_boundary}\r\n".encode("utf-8"))
            parts.append(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
            parts.append(f"{v}\r\n".encode("utf-8"))

    parts.append(f"--{chosen_boundary}\r\n".encode("utf-8"))
    parts.append(
        f'Content-Disposition: form-data; name="{safe_field}"; filename="{safe_filename}"\r\n'.encode("utf-8")
    )
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    parts.append(bytes(image_bytes))
    parts.append(b"\r\n")
    parts.append(f"--{chosen_boundary}--\r\n".encode("utf-8"))

    body = b"".join(parts)
    header = f"multipart/form-data; boundary={chosen_boundary}"
    return body, header


def resolve_screenshot_upload_url(
    params: dict[str, Any] | None = None,
    *,
    config_path: str | os.PathLike[str] | None = None,
    environ: dict[str, str] | None = None,
) -> str | None:
    """Resolve the target backend upload URL from action params, env vars, or `config.json`."""
    p = params if isinstance(params, dict) else {}
    env = environ if environ is not None else os.environ

    direct = p.get("upload_url") or p.get("endpoint") or p.get("api_url")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    env_url = env.get("JARVIS_SCREENSHOT_UPLOAD_URL") or env.get("SCREENSHOT_UPLOAD_URL")
    if isinstance(env_url, str) and env_url.strip():
        return env_url.strip()

    if config_path and Path(config_path).exists():
        try:
            cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                cfg_url = cfg.get("SCREENSHOT_UPLOAD_URL") or cfg.get("UPLOAD_URL")
                if isinstance(cfg_url, str) and cfg_url.strip():
                    return cfg_url.strip()
        except Exception:
            pass

    if p.get("upload") is True:
        return "http://localhost:8766/upload"

    return None


def upload_screenshot_bytes(
    image_bytes: bytes,
    upload_url: str,
    *,
    filename: str = "screenshot.png",
    field_name: str = "file",
    headers: dict[str, str] | None = None,
    extra_fields: dict[str, str] | None = None,
    timeout: int = 20,
    urlopen_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Upload screenshot bytes as `multipart/form-data` (`file: screenshot.png`) to `upload_url`."""
    if not isinstance(upload_url, str) or not upload_url.strip():
        raise ScreenshotUploadError("upload_url must be a non-empty string")

    body, content_type_header = build_multipart_screenshot_payload(
        image_bytes,
        filename=filename,
        field_name=field_name,
        extra_fields=extra_fields,
    )

    req_headers = {
        "Content-Type": content_type_header,
        "Content-Length": str(len(body)),
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(
        upload_url.strip(),
        data=body,
        headers=req_headers,
        method="POST",
    )

    opener = urlopen_fn or urllib.request.urlopen
    with opener(req, timeout=timeout) as resp:
        status = getattr(resp, "status", 200)
        raw_resp = resp.read().decode("utf-8", errors="replace")

    parsed_resp: Any
    try:
        parsed_resp = json.loads(raw_resp) if raw_resp else {}
    except json.JSONDecodeError:
        parsed_resp = {"raw": raw_resp}

    return {
        "ok": 200 <= int(status) < 300,
        "status": int(status),
        "upload_url": upload_url.strip(),
        "filename": filename,
        "size": len(image_bytes),
        "response": parsed_resp,
    }


def receive_multipart_screenshot(
    body: bytes,
    content_type_header: str,
    *,
    save_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Parse an incoming `POST /upload` `multipart/form-data` request and store the screenshot."""
    if not isinstance(content_type_header, str) or "multipart/form-data" not in content_type_header.lower():
        raise ScreenshotUploadError("Content-Type must be multipart/form-data")
    if "boundary=" not in content_type_header.lower():
        raise ScreenshotUploadError("multipart/form-data is missing boundary")
    if not body:
        raise ScreenshotUploadError("Empty upload body")

    mime_bytes = (
        f"Content-Type: {content_type_header}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body

    msg = BytesParser(policy=default_email_policy).parsebytes(mime_bytes)
    if not msg.is_multipart():
        raise ScreenshotUploadError("Malformed multipart/form-data body")

    for part in msg.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is not None and payload:
            safe_name = os.path.basename(filename.replace("\\", "/")) or "screenshot.png"
            target_dir = Path(save_dir) if save_dir else (Path(tempfile.gettempdir()) / "jarvis_screenshots")
            target_dir.mkdir(parents=True, exist_ok=True)
            out_path = target_dir / f"{uuid.uuid4().hex[:10]}_{safe_name}"
            out_path.write_bytes(payload)
            return {
                "ok": True,
                "filename": safe_name,
                "content_type": part.get_content_type() or "image/png",
                "size": len(payload),
                "path": str(out_path),
            }

    raise ScreenshotUploadError("No screenshot file found in multipart/form-data body")
