import logging
import time
from typing import Any, Awaitable, Callable, Dict

from app.core.config import settings


logger = logging.getLogger("app.performance")

Scope = Dict[str, Any]
Message = Dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class RequestTimingMiddleware:
    """记录通用 HTTP 请求耗时，并为客户端提供 Server-Timing。"""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        status_code = 500

        async def send_with_timing(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                headers = list(message.get("headers") or [])
                headers.append((b"server-timing", f"app;dur={elapsed_ms:.1f}".encode("ascii")))
                headers.append((b"x-process-time-ms", f"{elapsed_ms:.1f}".encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        except Exception:
            self._log_if_slow(scope, status_code, started_at)
            raise
        else:
            self._log_if_slow(scope, status_code, started_at)

    @staticmethod
    def _log_if_slow(scope: Scope, status_code: int, started_at: float) -> None:
        if not settings.SLOW_REQUEST_LOG_ENABLED:
            return

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        threshold_ms = max(0, int(settings.SLOW_REQUEST_THRESHOLD_MS))
        if elapsed_ms < threshold_ms:
            return

        logger.warning(
            "slow_request method=%s path=%s status=%s elapsed_ms=%.1f threshold_ms=%s",
            scope.get("method") or "-",
            scope.get("path") or "-",
            status_code,
            elapsed_ms,
            threshold_ms,
        )
