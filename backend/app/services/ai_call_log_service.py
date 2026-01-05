import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.ai_call_log import AiCallLog


def _extract_usage_fields(usage: Any) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if not isinstance(usage, dict):
        return None, None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    try:
        prompt_i = int(prompt) if prompt is not None else None
    except Exception:
        prompt_i = None
    try:
        completion_i = int(completion) if completion is not None else None
    except Exception:
        completion_i = None
    try:
        total_i = int(total) if total is not None else None
    except Exception:
        total_i = None
    return prompt_i, completion_i, total_i


def _redact_messages(messages: Any) -> Any:
    """
    对 messages 进行“图片 data_url 脱敏”，以避免将 base64 大图写入日志。
    """
    if not isinstance(messages, list):
        return messages

    out = []
    for msg in messages:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        new_msg = dict(msg)
        content = new_msg.get("content")

        if isinstance(content, list):
            new_content = []
            for part in content:
                if not isinstance(part, dict):
                    new_content.append(part)
                    continue
                if part.get("type") == "image_url":
                    img = part.get("image_url") or {}
                    if isinstance(img, dict):
                        url = str(img.get("url") or "")
                        if url.startswith("data:image/"):
                            img = dict(img)
                            img["url"] = "data:image/<omitted>"
                            new_part = dict(part)
                            new_part["image_url"] = img
                            new_content.append(new_part)
                            continue
                new_content.append(part)
            new_msg["content"] = new_content

        out.append(new_msg)
    return out


def create_ai_call_log(
    db: Session,
    *,
    operator_id: Optional[int],
    operation: str,
    mode: str,
    model: Optional[str],
    base_url: Optional[str],
    success: bool,
    duration_ms: Optional[int],
    messages: Any,
    request_input: Any,
    response_content: Optional[str],
    response_raw: Any,
    usage: Any,
    error: Optional[str],
    context: Optional[Dict[str, Any]] = None,
) -> AiCallLog:
    prompt_tokens, completion_tokens, total_tokens = _extract_usage_fields(usage)

    row = AiCallLog(
        id=uuid.uuid4().hex[:32],
        operator_id=operator_id,
        operation=str(operation or ""),
        mode=str(mode or ""),
        model=(str(model) if model is not None else None),
        base_url=(str(base_url) if base_url is not None else None),
        success=bool(success),
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_messages=_redact_messages(messages),
        request_input=request_input,
        response_content=response_content,
        response_raw=response_raw,
        error=error,
        context=context or None,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row

