import json
from typing import Any, Dict, List, Optional

import requests


class OpenAICompatChatClient:
    """OpenAI 兼容 Chat Completions 客户端（基于 requests，同步调用）。

    适配 Deepseek 等 OpenAI-compat 提供方：
    - base_url 可为 https://api.deepseek.com 或 https://api.deepseek.com/v1
    - path 默认为 /v1/chat/completions，可通过配置覆盖
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_completions_path: str = "/v1/chat/completions",
        timeout_seconds: int = 60,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.chat_completions_path = chat_completions_path or "/v1/chat/completions"
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _join_url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        p = (path or "").strip()
        if not p.startswith("/"):
            p = f"/{p}"
        # 避免 base_url 已包含 /v1 时重复拼接 /v1
        if base.endswith("/v1") and p.startswith("/v1/"):
            p = p[len("/v1") :]
        return f"{base}{p}"

    def create_chat_completion(
        self,
        *,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        url = self._join_url(self.chat_completions_path)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self.session.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        except Exception as exc:
            raise RuntimeError(f"AI 请求失败: {url} ({exc})") from exc

        if resp.status_code >= 400:
            text = resp.text or ""
            raise RuntimeError(f"AI 返回错误: HTTP {resp.status_code} - {text[:200]}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            text = resp.text or ""
            raise RuntimeError(f"AI 返回非 JSON 响应: {text[:200]}")

        content = _get_chat_completion_content(data)
        if not content:
            raise RuntimeError(f"AI 响应缺少 content: {data}")
        return str(content)


def _get_chat_completion_content(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices, list):
        return None
    first = choices[0] if isinstance(choices[0], dict) else None
    if not first:
        return None
    msg = first.get("message")
    if isinstance(msg, dict) and msg.get("content") is not None:
        return str(msg.get("content"))
    if first.get("text") is not None:
        return str(first.get("text"))
    return None
