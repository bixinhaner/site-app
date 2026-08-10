import asyncio
import logging
import unittest
from unittest.mock import patch

from app.middleware.request_timing import RequestTimingMiddleware


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


class RequestTimingMiddlewareTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_adds_timing_headers_and_logs_slow_request(self):
        async def slow_app(scope, receive, send):
            await asyncio.sleep(0.01)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        messages = []

        async def send(message):
            messages.append(message)

        middleware = RequestTimingMiddleware(slow_app)
        scope = {"type": "http", "method": "GET", "path": "/api/example"}

        with patch("app.middleware.request_timing.settings.SLOW_REQUEST_LOG_ENABLED", True), patch(
            "app.middleware.request_timing.settings.SLOW_REQUEST_THRESHOLD_MS", 1
        ), self.assertLogs("app.performance", logging.WARNING) as logs:
            await middleware(scope, _receive, send)

        headers = dict(messages[0]["headers"])
        self.assertIn(b"server-timing", headers)
        self.assertIn(b"x-process-time-ms", headers)
        self.assertIn("path=/api/example", logs.output[0])
        self.assertIn("status=200", logs.output[0])

    async def test_does_not_log_requests_below_threshold(self):
        async def fast_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def send(message):
            return None

        middleware = RequestTimingMiddleware(fast_app)
        scope = {"type": "http", "method": "GET", "path": "/health"}

        with patch("app.middleware.request_timing.settings.SLOW_REQUEST_LOG_ENABLED", True), patch(
            "app.middleware.request_timing.settings.SLOW_REQUEST_THRESHOLD_MS", 1000
        ), self.assertNoLogs("app.performance", logging.WARNING):
            await middleware(scope, _receive, send)


if __name__ == "__main__":
    unittest.main()
