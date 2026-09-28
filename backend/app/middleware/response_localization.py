"""成功响应提示按客户端界面语言（X-App-Locale）翻译。

只处理携带 X-App-Locale 请求头、且为不超过 256KB 的 JSON 响应；
其余响应（文件下载、大列表、流式响应等）原样透传。
"""

from __future__ import annotations

import json
import logging

from app.i18n.error_localization import get_request_locale, localize_response_payload

logger = logging.getLogger(__name__)

MAX_LOCALIZE_BYTES = 256 * 1024


class ResponseLocalizationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
        locale = get_request_locale(headers)
        if not locale:
            await self.app(scope, receive, send)
            return

        start_message = None
        passthrough = False

        async def send_wrapper(message):
            nonlocal start_message, passthrough
            if passthrough:
                await send(message)
                return
            if message["type"] == "http.response.start":
                resp_headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in message.get("headers") or []}
                content_type = resp_headers.get("content-type", "")
                content_length = resp_headers.get("content-length")
                too_large = content_length is not None and content_length.isdigit() and int(content_length) > MAX_LOCALIZE_BYTES
                if "application/json" not in content_type or too_large:
                    passthrough = True
                    await send(message)
                    return
                start_message = message
                return
            if message["type"] == "http.response.body" and start_message is not None:
                body = message.get("body", b"")
                if message.get("more_body") or len(body) > MAX_LOCALIZE_BYTES:
                    # 分块或超大响应：不改写，原样发出
                    passthrough = True
                    await send(start_message)
                    await send(message)
                    return
                new_body = body
                try:
                    payload = json.loads(body) if body else None
                    localized = localize_response_payload(payload, locale)
                    if localized is not payload:
                        new_body = json.dumps(localized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                except Exception:  # 翻译失败不影响正常响应
                    logger.debug("response localization skipped", exc_info=True)
                    new_body = body
                if new_body is not body:
                    raw_headers = [
                        (k, v) for k, v in start_message.get("headers") or [] if k.decode("latin-1").lower() != "content-length"
                    ]
                    raw_headers.append((b"content-length", str(len(new_body)).encode("latin-1")))
                    start_message = {**start_message, "headers": raw_headers}
                await send(start_message)
                await send({**message, "body": new_body})
                return
            await send(message)

        await self.app(scope, receive, send_wrapper)
