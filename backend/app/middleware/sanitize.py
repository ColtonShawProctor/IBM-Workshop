"""Input sanitization middleware.

Strips HTML tags and null bytes from string values in JSON request bodies.
This prevents stored XSS when user-provided strings are rendered in the frontend.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_NULL_BYTE_RE = re.compile(r"\x00")


def _sanitize_value(val: Any) -> Any:
    if isinstance(val, str):
        val = _NULL_BYTE_RE.sub("", val)
        val = _HTML_TAG_RE.sub("", val)
        return val
    if isinstance(val, dict):
        return {k: _sanitize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_sanitize_value(v) for v in val]
    return val


class SanitizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.json()
                    sanitized = _sanitize_value(body)
                    # Replace the body with sanitized version
                    import json
                    sanitized_bytes = json.dumps(sanitized).encode("utf-8")

                    async def receive():
                        return {"type": "http.request", "body": sanitized_bytes}

                    request._receive = receive
                except Exception:
                    pass  # Not valid JSON, let the endpoint handle the error

        return await call_next(request)
