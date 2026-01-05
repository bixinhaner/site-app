import json
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.services.ai_client import OpenAICompatChatClient


class AiTranslateService:
    def __init__(self):
        self._client = OpenAICompatChatClient(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            chat_completions_path=settings.AI_CHAT_COMPLETIONS_PATH,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _normalize_locale(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        lowered = s.lower().replace("_", "-")
        if lowered in ["zh-cn", "zh-hans", "zh"]:
            return "zh"
        if lowered in ["en-us", "en-gb", "en"]:
            return "en"
        if lowered in ["id-id", "id"]:
            return "id"
        return s

    def translate(self, *, text: str, target_locale: str, source_locale: Optional[str] = None) -> str:
        src = self._normalize_locale(source_locale) or "auto"
        tgt = self._normalize_locale(target_locale) or target_locale
        content = self._client.create_chat_completion(
            messages=_build_single_messages(text=text, source_locale=src, target_locale=tgt),
            model=_ensure_ai_model(),
            temperature=settings.AI_TEMPERATURE,
            max_tokens=settings.AI_MAX_TOKENS,
        )
        obj = _extract_json_object(content)
        translation = _coerce_translation(obj)
        if translation is None:
            raise RuntimeError(f"AI 翻译解析失败: {content[:200]}")
        return translation

    def translate_with_trace(
        self,
        *,
        text: str,
        target_locale: str,
        source_locale: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        src = self._normalize_locale(source_locale) or "auto"
        tgt = self._normalize_locale(target_locale) or target_locale
        messages = _build_single_messages(text=text, source_locale=src, target_locale=tgt)
        started = time.time()
        content, usage, raw = self._client.create_chat_completion_with_meta(
            messages=messages,
            model=_ensure_ai_model(),
            temperature=settings.AI_TEMPERATURE,
            max_tokens=settings.AI_MAX_TOKENS,
        )
        duration_ms = int((time.time() - started) * 1000)

        obj = _extract_json_object(content)
        translation = _coerce_translation(obj)
        if translation is None:
            raise RuntimeError(f"AI 翻译解析失败: {content[:200]}")

        trace = {
            "duration_ms": duration_ms,
            "messages": messages,
            "usage": usage,
            "raw": raw,
            "content": content,
            "input": {
                "text": text,
                "source_locale": src,
                "target_locale": tgt,
            },
        }
        return translation, trace

    def translate_batch(
        self,
        *,
        items: Sequence[Tuple[str, str, Optional[str], Optional[str]]],
        chunk_size: Optional[int] = None,
    ) -> List[str]:
        """批量翻译。

        items: [(text, target_locale, source_locale, key), ...]
        返回与输入等长的 translations 列表。
        """
        if not items:
            return []
        size = int(chunk_size or settings.AI_BATCH_CHUNK_SIZE or 20)
        if size <= 0:
            size = 20

        out: List[Optional[str]] = [None] * len(items)
        model = _ensure_ai_model()

        for chunk in _chunk_items(list(enumerate(items)), size):
            payload_items = []
            for idx, (text, target_locale, source_locale, key) in chunk:
                payload_items.append(
                    {
                        "id": idx,
                        "key": key,
                        "source_locale": self._normalize_locale(source_locale) or "auto",
                        "target_locale": self._normalize_locale(target_locale) or target_locale,
                        "text": text,
                    }
                )
            content = self._client.create_chat_completion(
                messages=_build_batch_messages(payload_items),
                model=model,
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
            )
            obj = _extract_json_object(content)
            mapping = _coerce_batch_translations(obj)
            if mapping is None:
                raise RuntimeError(f"AI 批量翻译解析失败: {content[:200]}")
            for idx, trans in mapping.items():
                if 0 <= idx < len(out):
                    out[idx] = trans

        missing = [i for i, v in enumerate(out) if not v and v != ""]
        if missing:
            raise RuntimeError(f"AI 批量翻译缺少结果: {missing[:20]}")
        return [v or "" for v in out]

    def translate_batch_with_traces(
        self,
        *,
        items: Sequence[Tuple[str, str, Optional[str], Optional[str]]],
        chunk_size: Optional[int] = None,
    ) -> tuple[List[str], List[Dict[str, Any]]]:
        """批量翻译（附带每个分段请求的 trace 列表）。"""
        if not items:
            return [], []
        size = int(chunk_size or settings.AI_BATCH_CHUNK_SIZE or 20)
        if size <= 0:
            size = 20

        out: List[Optional[str]] = [None] * len(items)
        model = _ensure_ai_model()
        traces: List[Dict[str, Any]] = []

        chunks = _chunk_items(list(enumerate(items)), size)
        for chunk_index, chunk in enumerate(chunks, start=1):
            payload_items = []
            for idx, (text, target_locale, source_locale, key) in chunk:
                payload_items.append(
                    {
                        "id": idx,
                        "key": key,
                        "source_locale": self._normalize_locale(source_locale) or "auto",
                        "target_locale": self._normalize_locale(target_locale) or target_locale,
                        "text": text,
                    }
                )
            messages = _build_batch_messages(payload_items)
            started = time.time()
            content, usage, raw = self._client.create_chat_completion_with_meta(
                messages=messages,
                model=model,
                temperature=settings.AI_TEMPERATURE,
                max_tokens=settings.AI_MAX_TOKENS,
            )
            duration_ms = int((time.time() - started) * 1000)

            obj = _extract_json_object(content)
            mapping = _coerce_batch_translations(obj)
            if mapping is None:
                raise RuntimeError(f"AI 批量翻译解析失败: {content[:200]}")
            for idx, trans in mapping.items():
                if 0 <= idx < len(out):
                    out[idx] = trans

            traces.append(
                {
                    "duration_ms": duration_ms,
                    "messages": messages,
                    "usage": usage,
                    "raw": raw,
                    "content": content,
                    "input": {
                        "chunk_index": chunk_index,
                        "chunk_total": len(chunks),
                        "items": payload_items,
                    },
                }
            )

        missing = [i for i, v in enumerate(out) if not v and v != ""]
        if missing:
            raise RuntimeError(f"AI 批量翻译缺少结果: {missing[:20]}")
        return [v or "" for v in out], traces


def _ensure_ai_model() -> str:
    model = (settings.AI_MODEL or "").strip()
    if not model:
        raise RuntimeError("AI_MODEL 未配置")
    return model


def _build_system_prompt() -> str:
    domain = (settings.AI_DOMAIN_HINT or "").strip() or "无线通信行业（站点巡检/工单系统）"
    return (
        "你是一个专业的翻译与本地化助手，擅长无线通信行业的术语与现场巡检/工单系统 UI 文案。"
        f"请以“{domain}”语境进行翻译。"
        "要求：保持缩写/型号/单位/数字不被错误改写；保留原有换行与符号；不要添加多余解释。"
        "只输出 JSON，不要输出 Markdown。"
    )


def _build_single_messages(*, text: str, source_locale: str, target_locale: str) -> List[Dict[str, str]]:
    user_prompt = (
        f"将以下文本从 {source_locale} 翻译为 {target_locale}。\n"
        "输出严格 JSON：{\"translation\": \"...\"}\n"
        "注意：若原文包含换行，请在 JSON 字符串中用 \\n 表示换行，保证 JSON 合法。\n"
        "原文：\n"
        f"{text}"
    )
    return [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def _build_batch_messages(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    user_prompt = (
        "你将收到一个 JSON 数组 items，每个元素包含 id、source_locale、target_locale、text。\n"
        "请逐条翻译，并输出严格 JSON：{\"items\": [{\"id\": 0, \"translation\": \"...\"}]}\n"
        "注意：保持 items 顺序与 id 对应；若原文包含换行，请在 JSON 字符串中用 \\n 表示换行。\n"
        f"输入：\n{json.dumps({'items': items}, ensure_ascii=False)}"
    )
    return [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_prompt},
    ]


def _chunk_items(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = _strip_code_fences(text)
    # 1) 直接 JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # 2) 尝试从文本中提取第一个完整的 JSON 对象（支持前后夹杂）
    candidates = _extract_braced_segments(raw)
    for seg in candidates:
        try:
            obj = json.loads(seg)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    # 3) 尝试弱解析 translation 字段（兼容 JSON 字符串中出现未转义换行导致 loads 失败）
    m = re.search(r"\"translation\"\\s*:\\s*\"(.*?)\"\\s*[}\\,]", raw, re.S)
    if m:
        return {"translation": _unescape_relaxed(m.group(1))}

    raise RuntimeError("无法从 AI 响应中提取 JSON")


def _extract_braced_segments(text: str) -> List[str]:
    segs: List[str] = []
    depth = 0
    start: Optional[int] = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                segs.append(text[start : i + 1])
                start = None
    return segs


def _unescape_relaxed(value: str) -> str:
    # 兼容常见转义序列，保留原样以免误伤
    s = value.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    s = s.replace('\\"', '"')
    return s


def _coerce_translation(obj: Dict[str, Any]) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    v = obj.get("translation")
    if v is None:
        return None
    return str(v)


def _coerce_batch_translations(obj: Dict[str, Any]) -> Optional[Dict[int, str]]:
    if not isinstance(obj, dict):
        return None
    items = obj.get("items")
    if not isinstance(items, list):
        return None
    mapping: Dict[int, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = it.get("id")
        trans = it.get("translation")
        if idx is None or trans is None:
            continue
        try:
            mapping[int(idx)] = str(trans)
        except Exception:
            continue
    return mapping
