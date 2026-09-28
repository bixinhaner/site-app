"""接口报错按客户端界面语言翻译。

客户端通过请求头 X-App-Locale（zh-CN / en-US / id-ID）声明界面语言；
未携带该请求头时，报错保持原样返回，兼容旧客户端；
声明中文时，仅把后端以英文书写的报错翻译为中文。

翻译表：
- stock_messages：EXACT（中文 → (en, id)）+ PATTERNS（正则，命名分组）
- 其余模块：ENTRIES = [(中文, en, id)]；中文中的 {0} {1} 为参数占位，
  自动转换为匹配规则，参数内容会再递归翻译一次（嵌套报错）。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Pattern, Tuple

from app.i18n import (
    inspection_messages,
    response_messages,
    site_messages,
    stock_messages,
    system_messages,
    work_order_messages,
)
from app.utils.archive_pdf import normalize_locale

logger = logging.getLogger(__name__)

LOCALE_HEADER = "x-app-locale"

# 结构化报错中需要翻译的文本字段
_TEXT_FIELDS = ("message", "title", "reason", "suggestion", "msg")

_CJK = re.compile(r"[一-鿿]")
_PLACEHOLDER = re.compile(r"\{(\d+)\}")

_ENTRY_MODULES = (work_order_messages, inspection_messages, site_messages, system_messages, response_messages)


def _compile_template(template: str) -> Pattern[str]:
    parts = _PLACEHOLDER.split(template)
    regex = "^"
    for idx, part in enumerate(parts):
        regex += re.escape(part) if idx % 2 == 0 else f"(?P<p{part}>.+?)"
    return re.compile(regex + "$", re.S)


def _to_named(text: str) -> str:
    return _PLACEHOLDER.sub(lambda m: "{p" + m.group(1) + "}", text)


def _build_catalog() -> Tuple[Dict[str, Tuple[str, str]], List[Tuple[Pattern[str], str, str]]]:
    exact: Dict[str, Tuple[str, str]] = dict(stock_messages.EXACT)
    templated: List[Tuple[str, str, str]] = []
    for module in _ENTRY_MODULES:
        for zh, en, id_text in module.ENTRIES:
            if _PLACEHOLDER.search(zh):
                templated.append((zh, en, id_text))
            else:
                exact.setdefault(zh, (en, id_text))
    # 固定文字越长越具体，优先匹配，避免 “{0} 不能为空” 这类通用模板抢先命中
    templated.sort(key=lambda x: len(_PLACEHOLDER.sub("", x[0])), reverse=True)
    patterns: List[Tuple[Pattern[str], str, str]] = list(stock_messages.PATTERNS)
    patterns += [(_compile_template(zh), _to_named(en), _to_named(id_text)) for zh, en, id_text in templated]
    return exact, patterns


EXACT, PATTERNS = _build_catalog()

# 英文原文报错：English → (zh, id)
_EN_EXACT: Dict[str, Tuple[str, str]] = {}
_EN_PATTERNS: List[Tuple[Pattern[str], str, str]] = []
for _en, _zh, _id in system_messages.ENGLISH_ENTRIES:
    if _PLACEHOLDER.search(_en):
        _EN_PATTERNS.append((_compile_template(_en), _to_named(_zh), _to_named(_id)))
    else:
        _EN_EXACT[_en] = (_zh, _id)


def _localize_english_source(text: str, locale: str) -> Optional[str]:
    idx = 1 if locale == "id-ID" else 0
    exact = _EN_EXACT.get(text)
    if exact:
        return exact[idx]
    for pattern, zh, id_text in _EN_PATTERNS:
        match = pattern.match(text)
        if match:
            return (id_text if idx else zh).format(**match.groupdict())
    return None


_reported_untranslated: set = set()


def get_request_locale(headers: Any) -> Optional[str]:
    raw = headers.get(LOCALE_HEADER) if headers is not None else None
    if not raw:
        return None
    return normalize_locale(raw)


def localize_text(text: str, locale: Optional[str], _depth: int = 0) -> str:
    if not isinstance(text, str) or not locale:
        return text
    stripped = text.strip()
    if locale != "en-US" and not _CJK.search(stripped):
        translated = _localize_english_source(stripped, locale)
        if translated is not None:
            return translated
    if locale == "zh-CN":
        return text
    idx = 1 if locale == "id-ID" else 0
    exact = EXACT.get(stripped)
    if exact:
        return exact[idx]
    for pattern, en, id_text in PATTERNS:
        match = pattern.match(stripped)
        if match:
            params = match.groupdict()
            if _depth < 2:
                params = {k: localize_text(v, locale, _depth + 1) for k, v in params.items()}
            return (id_text if idx else en).format(**params)
    if _depth == 0 and _CJK.search(stripped) and stripped not in _reported_untranslated:
        _reported_untranslated.add(stripped)
        logger.warning("未收录的报错译文（%s）：%s", locale, stripped[:200])
    return text


def localize_detail(detail: Any, locale: Optional[str]) -> Any:
    if not locale:
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


# 成功响应中需要翻译的位置：顶层 message，以下列表中各项的 message，以及顶层字典值（下一层）的 message。
# 不做深层递归，避免误改日志等业务数据中的 message 字段。
_RESPONSE_LIST_KEYS = ("errors", "warnings", "issues", "failures")


def localize_response_payload(payload: Any, locale: Optional[str]) -> Any:
    if not locale or not isinstance(payload, dict):
        return payload
    changed = False
    result = dict(payload)
    for key in ("message", "msg"):
        value = result.get(key)
        if isinstance(value, str):
            translated = localize_text(value, locale)
            if translated != value:
                result[key] = translated
                changed = True
    for key, value in payload.items():
        if key in _RESPONSE_LIST_KEYS and isinstance(value, list):
            new_list = [localize_detail(item, locale) if isinstance(item, (dict, str)) else item for item in value]
            if new_list != value:
                result[key] = new_list
                changed = True
        elif isinstance(value, dict) and isinstance(value.get("message"), str):
            translated = localize_text(value["message"], locale)
            if translated != value["message"]:
                result[key] = {**value, "message": translated}
                changed = True
    return result if changed else payload
