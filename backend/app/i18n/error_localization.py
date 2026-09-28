"""接口报错按客户端界面语言翻译。

客户端通过请求头 X-App-Locale（zh-CN / en-US / id-ID）声明界面语言；
未携带该请求头或为中文时，报错保持原样返回，兼容旧客户端。
"""

from __future__ import annotations

from typing import Any, Optional

from app.i18n import stock_messages
from app.utils.archive_pdf import normalize_locale

LOCALE_HEADER = "x-app-locale"

# 结构化报错中需要翻译的文本字段
_TEXT_FIELDS = ("message", "title", "reason", "suggestion", "msg")


def get_request_locale(headers: Any) -> Optional[str]:
    raw = headers.get(LOCALE_HEADER) if headers is not None else None
    if not raw:
        return None
    return normalize_locale(raw)


def localize_text(text: str, locale: Optional[str]) -> str:
    if not isinstance(text, str) or not locale or locale == "zh-CN":
        return text
    idx = 1 if locale == "id-ID" else 0
    stripped = text.strip()
    exact = stock_messages.EXACT.get(stripped)
    if exact:
        return exact[idx]
    for pattern, en, id_text in stock_messages.PATTERNS:
        match = pattern.match(stripped)
        if match:
            return (id_text if idx else en).format(**match.groupdict())
    return text


def localize_detail(detail: Any, locale: Optional[str]) -> Any:
    if not locale or locale == "zh-CN":
        return detail
    if isinstance(detail, str):
        return localize_text(detail, locale)
    if isinstance(detail, dict):
        result = dict(detail)
        for key in _TEXT_FIELDS:
            if isinstance(result.get(key), str):
                result[key] = localize_text(result[key], locale)
        return result
    if isinstance(detail, list):
        return [localize_detail(item, locale) for item in detail]
    return detail
