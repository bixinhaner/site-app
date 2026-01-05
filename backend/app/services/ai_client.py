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

    def _is_azure_openai(self) -> bool:
        return "openai.azure.com" in (self.base_url or "").lower()

    @staticmethod
    def _should_use_max_completion_tokens(model: str) -> bool:
        """
        OpenAI/Azure 部分新模型（如 gpt-5-*）在 chat.completions 中不支持 max_tokens，
        需改用 max_completion_tokens。
        """
        m = (model or "").strip().lower()
        if not m:
            return False
        # GPT-5 系列
        if m.startswith("gpt-5"):
            return True
        # 推理模型（常见命名：o1/o3/o4）
        if m.startswith(("o1", "o3", "o4")):
            return True
        return False

    def _join_url(self, path: str) -> str:
        base = self.base_url.rstrip("/")
        p = (path or "").strip()
        if not p.startswith("/"):
            p = f"/{p}"
        # 避免 base_url 已包含 /v1 时重复拼接 /v1
        if base.endswith("/v1") and p.startswith("/v1/"):
            p = p[len("/v1") :]
        return f"{base}{p}"

    @staticmethod
    def _extract_error_message(resp: requests.Response) -> str:
        try:
            data = resp.json()
        except Exception:
            return (resp.text or "").strip()
        if not isinstance(data, dict):
            return (resp.text or "").strip()
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err.get("message") or "").strip()
        return (resp.text or "").strip()

    def create_chat_completion(
        self,
        *,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        content, _usage, _raw = self.create_chat_completion_with_meta(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return content

    def create_chat_completion_raw(
        self,
        *,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        url = self._join_url(self.chat_completions_path)
        headers = {"Content-Type": "application/json"}
        if self._is_azure_openai():
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        # 兼容：部分新模型改用 max_completion_tokens
        token_key = "max_completion_tokens" if self._should_use_max_completion_tokens(model) else "max_tokens"
        payload[token_key] = max_tokens
        try:
            resp = self.session.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
        except Exception as exc:
            raise RuntimeError(f"AI 请求失败: {url} ({exc})") from exc

        if resp.status_code >= 400:
            err_msg = self._extract_error_message(resp)
            # 兼容兜底：若供应商不支持当前 token 参数名，则自动重试一次切换参数名
            if resp.status_code == 400:
                retry_payload = None
                if token_key == "max_tokens" and "max_completion_tokens" in (err_msg or ""):
                    retry_payload = dict(payload)
                    retry_payload.pop("max_tokens", None)
                    retry_payload["max_completion_tokens"] = max_tokens
                elif token_key == "max_completion_tokens" and "max_tokens" in (err_msg or ""):
                    retry_payload = dict(payload)
                    retry_payload.pop("max_completion_tokens", None)
                    retry_payload["max_tokens"] = max_tokens

                if retry_payload is not None:
                    try:
                        resp2 = self.session.post(url, json=retry_payload, headers=headers, timeout=self.timeout_seconds)
                    except Exception as exc:
                        raise RuntimeError(f"AI 请求失败: {url} ({exc})") from exc
                    if resp2.status_code < 400:
                        try:
                            data2 = resp2.json()
                        except json.JSONDecodeError:
                            text = resp2.text or ""
                            raise RuntimeError(f"AI 返回非 JSON 响应: {text[:200]}")
                        if not isinstance(data2, dict):
                            raise RuntimeError(f"AI 返回非对象 JSON: {data2}")
                        return data2
                    err_msg = self._extract_error_message(resp2)

            raise RuntimeError(f"AI 返回错误: HTTP {resp.status_code} - {err_msg[:200]}")

        try:
            data = resp.json()
        except json.JSONDecodeError:
            text = resp.text or ""
            raise RuntimeError(f"AI 返回非 JSON 响应: {text[:200]}")

        if not isinstance(data, dict):
            raise RuntimeError(f"AI 返回非对象 JSON: {data}")
        return data

    def create_chat_completion_with_meta(
        self,
        *,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> tuple[str, Dict[str, Any], Dict[str, Any]]:
        data = self.create_chat_completion_raw(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = _get_chat_completion_content(data)
        if not content:
            raise RuntimeError(f"AI 响应缺少 content: {data}")
        usage = _get_chat_completion_usage(data) or {}
        return str(content), usage, data


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


def _get_chat_completion_usage(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return usage
