"""Simple in-memory rate limiter middleware.

Standard endpoints: 100 req/min per user (identified by JWT sub or IP).
Heavy endpoints (PDF parsing, optimization): 5 req/min per user.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

HEAVY_PATHS = {"/bid-periods": "POST", "/optimize": "POST"}

# Disable rate limiting during tests
_TESTING = os.environ.get("TESTING", "").lower() in ("1", "true", "yes")

STANDARD_LIMIT = 100_000 if _TESTING else 100
STANDARD_WINDOW = 60

HEAVY_LIMIT = 100_000 if _TESTING else 5
HEAVY_WINDOW = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # key -> list of timestamps
        self._standard: dict[str, list[float]] = defaultdict(list)
        self._heavy: dict[str, list[float]] = defaultdict(list)

    def _get_key(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # Use token hash as key (cheap identifier)
            return f"tok:{hash(auth)}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _is_heavy(self, request: Request) -> bool:
        path = request.url.path
        method = request.method
        if method == "POST" and (path.endswith("/optimize") or path == "/bid-periods"):
            return True
        return False

    def _check_limit(self, bucket: dict[str, list[float]], key: str, limit: int, window: int) -> Tuple[bool, int]:
        now = time.time()
        timestamps = bucket[key]
        # Remove expired entries
        timestamps[:] = [t for t in timestamps if now - t < window]
        if len(timestamps) >= limit:
            return False, limit - len(timestamps)
        timestamps.append(now)
        return True, limit - len(timestamps)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check
        if request.url.path == "/":
            return await call_next(request)

        key = self._get_key(request)

        if self._is_heavy(request):
            allowed, remaining = self._check_limit(self._heavy, key, HEAVY_LIMIT, HEAVY_WINDOW)
        else:
            allowed, remaining = self._check_limit(self._standard, key, STANDARD_LIMIT, STANDARD_WINDOW)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMITED",
                    "message": "Too many requests. Please try again later.",
                    "details": {},
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response
