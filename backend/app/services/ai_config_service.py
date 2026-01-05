from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.system_config import SystemConfig
from app.utils.secret_crypto import decrypt_secret, encrypt_secret


AI_CONFIG_KEY = "ai_config"


def load_ai_config(db: Session) -> Dict[str, Any]:
    row = db.query(SystemConfig).filter(SystemConfig.key == AI_CONFIG_KEY).first()
    if not row or not row.value:
        return {}
    data = row.value or {}
    if not isinstance(data, dict):
        return {}
    return data


def save_ai_config(db: Session, value: Dict[str, Any]) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == AI_CONFIG_KEY).first()
    if not row:
        row = SystemConfig(key=AI_CONFIG_KEY, value=value)
        db.add(row)
    else:
        row.value = value
        flag_modified(row, "value")
    db.commit()


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def apply_ai_config_to_settings(config: Dict[str, Any]) -> None:
    """
    将 DB 中的 AI 配置应用到运行中的 settings（热更新）。

    - 未提供的字段不覆盖（保持当前 settings 值）
    - API Key 在 DB 中以加密字段存储，本函数会解密后写入 settings
    """
    if not isinstance(config, dict):
        return

    text = config.get("text") or {}
    if isinstance(text, dict):
        if "base_url" in text:
            settings.AI_BASE_URL = str(text.get("base_url") or "")
        if "model" in text:
            settings.AI_MODEL = str(text.get("model") or "")
        if "chat_completions_path" in text:
            settings.AI_CHAT_COMPLETIONS_PATH = str(text.get("chat_completions_path") or "")
        if "timeout_seconds" in text:
            settings.AI_TIMEOUT_SECONDS = _coerce_int(text.get("timeout_seconds"), settings.AI_TIMEOUT_SECONDS)
        if "temperature" in text:
            settings.AI_TEMPERATURE = _coerce_float(text.get("temperature"), settings.AI_TEMPERATURE)
        if "max_tokens" in text:
            settings.AI_MAX_TOKENS = _coerce_int(text.get("max_tokens"), settings.AI_MAX_TOKENS)
        if "batch_chunk_size" in text:
            settings.AI_BATCH_CHUNK_SIZE = _coerce_int(text.get("batch_chunk_size"), settings.AI_BATCH_CHUNK_SIZE)
        if "domain_hint" in text:
            settings.AI_DOMAIN_HINT = str(text.get("domain_hint") or "")

        if "api_key_enc" in text:
            settings.AI_API_KEY = decrypt_secret(text.get("api_key_enc")) or ""

    vision = config.get("vision") or {}
    if isinstance(vision, dict):
        if "base_url" in vision:
            settings.AI_VISION_BASE_URL = str(vision.get("base_url") or "")
        if "model" in vision:
            settings.AI_VISION_MODEL = str(vision.get("model") or "")
        if "chat_completions_path" in vision:
            settings.AI_VISION_CHAT_COMPLETIONS_PATH = str(vision.get("chat_completions_path") or "")
        if "timeout_seconds" in vision:
            settings.AI_VISION_TIMEOUT_SECONDS = _coerce_int(vision.get("timeout_seconds"), settings.AI_VISION_TIMEOUT_SECONDS)
        if "temperature" in vision:
            settings.AI_VISION_TEMPERATURE = _coerce_float(vision.get("temperature"), settings.AI_VISION_TEMPERATURE)
        if "max_tokens" in vision:
            settings.AI_VISION_MAX_TOKENS = _coerce_int(vision.get("max_tokens"), settings.AI_VISION_MAX_TOKENS)

        if "api_key_enc" in vision:
            settings.AI_VISION_API_KEY = decrypt_secret(vision.get("api_key_enc")) or ""


def upsert_ai_config(
    db: Session,
    *,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    更新并保存 AI 配置（写 DB），并同步热更新 settings。

    payload 结构：
    - text: {..., api_key: Optional[str]}
    - vision: {..., api_key: Optional[str]}
    - pricing: {...}
    """
    existing = load_ai_config(db)
    new_value: Dict[str, Any] = dict(existing or {})

    text_payload = payload.get("text")
    if isinstance(text_payload, dict):
        new_text = dict(new_value.get("text") or {}) if isinstance(new_value.get("text"), dict) else {}
        for key in [
            "base_url",
            "model",
            "chat_completions_path",
            "timeout_seconds",
            "temperature",
            "max_tokens",
            "batch_chunk_size",
            "domain_hint",
        ]:
            if key in text_payload:
                new_text[key] = text_payload.get(key)

        if "api_key" in text_payload:
            api_key_val = text_payload.get("api_key")
            if api_key_val is None:
                pass
            else:
                api_key_str = str(api_key_val)
                if api_key_str == "":
                    new_text["api_key_enc"] = ""
                else:
                    new_text["api_key_enc"] = encrypt_secret(api_key_str)

        new_value["text"] = new_text

    vision_payload = payload.get("vision")
    if isinstance(vision_payload, dict):
        new_vision = dict(new_value.get("vision") or {}) if isinstance(new_value.get("vision"), dict) else {}
        for key in [
            "base_url",
            "model",
            "chat_completions_path",
            "timeout_seconds",
            "temperature",
            "max_tokens",
        ]:
            if key in vision_payload:
                new_vision[key] = vision_payload.get(key)

        if "api_key" in vision_payload:
            api_key_val = vision_payload.get("api_key")
            if api_key_val is None:
                pass
            else:
                api_key_str = str(api_key_val)
                if api_key_str == "":
                    new_vision["api_key_enc"] = ""
                else:
                    new_vision["api_key_enc"] = encrypt_secret(api_key_str)

        new_value["vision"] = new_vision

    if "pricing" in payload:
        new_value["pricing"] = payload.get("pricing")

    save_ai_config(db, new_value)
    apply_ai_config_to_settings(new_value)
    return new_value


def get_pricing_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    pricing = config.get("pricing")
    if not isinstance(pricing, dict):
        return {}
    return pricing

