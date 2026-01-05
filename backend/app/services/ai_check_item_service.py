import base64
import hashlib
import io
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inspection import InspectionCheckItem, InspectionPhoto
from app.services.ai_call_log_service import create_ai_call_log
from app.services.ai_client import OpenAICompatChatClient
from app.services.ai_translate_service import _extract_json_object


class AiCheckItemService:
    """检查项 AI 检查服务（输出为结构化 JSON 建议；需人工确认采纳）。"""

    PROMPT_VERSION = "check_item_v1"

    def __init__(self):
        self._text_client = OpenAICompatChatClient(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            chat_completions_path=settings.AI_CHAT_COMPLETIONS_PATH,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )
        self._vision_client = OpenAICompatChatClient(
            base_url=settings.AI_VISION_BASE_URL,
            api_key=settings.AI_VISION_API_KEY,
            chat_completions_path=settings.AI_VISION_CHAT_COMPLETIONS_PATH,
            timeout_seconds=settings.AI_VISION_TIMEOUT_SECONDS,
        )

    @staticmethod
    def is_text_configured() -> bool:
        return bool((settings.AI_BASE_URL or "").strip() and (settings.AI_API_KEY or "").strip() and (settings.AI_MODEL or "").strip())

    @staticmethod
    def is_vision_configured() -> bool:
        return bool(
            (settings.AI_VISION_BASE_URL or "").strip()
            and (settings.AI_VISION_API_KEY or "").strip()
            and (settings.AI_VISION_MODEL or "").strip()
        )

    def analyze_check_item(
        self,
        *,
        db: Session,
        check_item: InspectionCheckItem,
        mode: str = "auto",
        force: bool = False,
        max_images: int = 5,
        image_detail: str = "low",
        operator_user_id: Optional[int] = None,
    ) -> Tuple[str, str, str, Dict[str, Any]]:
        """生成检查项 AI 建议并落库。

        返回：(ai_mode_used, ai_model_used, ai_input_hash, ai_result)
        """
        start = time.time()
        photos = self._load_item_photos(db=db, check_item_id=check_item.id, max_images=max_images)
        ai_mode, ai_model = self._decide_mode_and_model(mode=mode, has_photos=bool(photos))

        input_payload = self._build_input_payload(check_item=check_item, photos=photos, ai_mode=ai_mode, ai_model=ai_model)
        input_hash = self._calc_input_hash(input_payload)

        if not force:
            if (check_item.ai_status or "") == "done" and check_item.ai_input_hash == input_hash and check_item.ai_result:
                return ai_mode, ai_model, input_hash, dict(check_item.ai_result or {})

        check_item.ai_status = "running"
        check_item.ai_mode = ai_mode
        check_item.ai_model = ai_model
        check_item.ai_input_hash = input_hash
        check_item.ai_error = None
        check_item.ai_checked_by = operator_user_id
        check_item.ai_checked_at = datetime.utcnow()
        check_item.updated_at = datetime.utcnow()
        db.commit()

        try:
            messages = self._build_messages(input_payload=input_payload, ai_mode=ai_mode, photos=photos, image_detail=image_detail)
            call_started = time.time()
            if ai_mode == "vision":
                content, usage, raw = self._vision_client.create_chat_completion_with_meta(
                    messages=messages,
                    model=ai_model,
                    temperature=settings.AI_VISION_TEMPERATURE,
                    max_tokens=settings.AI_VISION_MAX_TOKENS,
                )
                base_url = settings.AI_VISION_BASE_URL
            else:
                content, usage, raw = self._text_client.create_chat_completion_with_meta(
                    messages=messages,
                    model=ai_model,
                    temperature=settings.AI_TEMPERATURE,
                    max_tokens=settings.AI_MAX_TOKENS,
                )
                base_url = settings.AI_BASE_URL
            duration_ms = int((time.time() - call_started) * 1000)
            result = _extract_json_object(content)
            result = self._normalize_result(result, elapsed_ms=int((time.time() - start) * 1000))

            check_item.ai_status = "done"
            check_item.ai_result = result
            check_item.ai_error = None
            check_item.updated_at = datetime.utcnow()
            db.commit()

            try:
                create_ai_call_log(
                    db,
                    operator_id=operator_user_id,
                    operation="check_item_analyze",
                    mode=ai_mode,
                    model=ai_model,
                    base_url=base_url,
                    success=True,
                    duration_ms=duration_ms,
                    messages=messages,
                    request_input=input_payload,
                    response_content=content,
                    response_raw=raw,
                    usage=usage,
                    error=None,
                    context={"check_item_id": check_item.id, "inspection_id": check_item.inspection_id},
                )
            except Exception:
                pass

            return ai_mode, ai_model, input_hash, result
        except Exception as exc:
            check_item.ai_status = "failed"
            check_item.ai_result = None
            check_item.ai_error = str(exc)[:500]
            check_item.updated_at = datetime.utcnow()
            db.commit()

            try:
                create_ai_call_log(
                    db,
                    operator_id=operator_user_id,
                    operation="check_item_analyze",
                    mode=ai_mode,
                    model=ai_model,
                    base_url=(settings.AI_VISION_BASE_URL if ai_mode == "vision" else settings.AI_BASE_URL),
                    success=False,
                    duration_ms=None,
                    messages=messages if "messages" in locals() else None,
                    request_input=input_payload,
                    response_content=(locals().get("content") if "content" in locals() else None),
                    response_raw=(locals().get("raw") if "raw" in locals() else None),
                    usage=(locals().get("usage") if "usage" in locals() else None),
                    error=str(exc)[:500],
                    context={"check_item_id": check_item.id, "inspection_id": check_item.inspection_id},
                )
            except Exception:
                pass
            raise

    def _decide_mode_and_model(self, *, mode: str, has_photos: bool) -> Tuple[str, str]:
        m = (mode or "auto").strip().lower()
        if m not in {"auto", "text", "vision"}:
            m = "auto"

        if m == "vision":
            if not self.is_vision_configured():
                raise RuntimeError("AI 未配置：视觉模型（AI_VISION_BASE_URL/AI_VISION_API_KEY/AI_VISION_MODEL）不完整")
            return "vision", (settings.AI_VISION_MODEL or "").strip()

        if m == "text":
            if not self.is_text_configured():
                raise RuntimeError("AI 未配置：文本模型（AI_BASE_URL/AI_API_KEY/AI_MODEL）不完整")
            return "text", (settings.AI_MODEL or "").strip()

        # auto
        if has_photos and self.is_vision_configured():
            return "vision", (settings.AI_VISION_MODEL or "").strip()
        if not self.is_text_configured():
            raise RuntimeError("AI 未配置：文本模型（AI_BASE_URL/AI_API_KEY/AI_MODEL）不完整")
        return "text", (settings.AI_MODEL or "").strip()

    def _build_system_prompt(self) -> str:
        domain = (settings.AI_DOMAIN_HINT or "").strip() or "无线通信行业（站点巡检/工单系统）"
        return (
            "你是无线通信行业现场巡检/工单系统的质检审核助手。"
            f"请以“{domain}”语境进行分析。"
            "目标：基于输入的检查项、字段值、校验结果、现场备注以及（可选）现场图片，给出结构化审核建议。"
            "要求："
            "1) 不要编造不存在的字段/照片内容；若证据不足请明确说明缺失证据；"
            "2) 输出严格 JSON（不要输出 Markdown/代码块）；"
            "3) 建议项包含：建议审核结果(pass/warning/fail)、建议分数(0-100)、摘要、分析要点、缺材料清单。"
        )

    def _build_messages(
        self,
        *,
        input_payload: Dict[str, Any],
        ai_mode: str,
        photos: List[InspectionPhoto],
        image_detail: str,
    ) -> List[Dict[str, Any]]:
        user_instruction = (
            "请根据输入数据给出审核建议。输出严格 JSON，结构如下：\n"
            "{\n"
            '  "suggested_review_status": "pass|warning|fail",\n'
            '  "suggested_score": 0,\n'
            '  "summary": "...",\n'
            '  "analysis": ["..."],\n'
            '  "missing_evidence": ["..."],\n'
            '  "field_findings": [{"field_id":"", "label":"", "value": null, "issue":"", "suggestion":""}],\n'
            '  "photo_findings": [{"photo_id":"", "field_id":"", "issue":"", "suggestion":""}],\n'
            '  "confidence": 0\n'
            "}\n"
            "说明："
            "- suggested_review_status 与 suggested_score 为“建议项”，最终以人工审核为准；\n"
            "- 若无法判断，请输出 missing_evidence 并降低 confidence；\n"
            "- 若是 text 模式，无法查看图片内容，只能基于字段与照片元数据给建议。\n"
            "\n"
            f"输入：{json.dumps(input_payload, ensure_ascii=False)}"
        )

        if ai_mode != "vision":
            return [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": user_instruction},
            ]

        content: List[Dict[str, Any]] = [{"type": "text", "text": user_instruction}]
        detail = "high" if (image_detail or "").strip().lower() == "high" else "low"
        for p in photos:
            data_url = self._photo_to_data_url(p.file_path)
            content.append({"type": "image_url", "image_url": {"url": data_url, "detail": detail}})

        return [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": content},
        ]

    def _load_item_photos(self, *, db: Session, check_item_id: str, max_images: int) -> List[InspectionPhoto]:
        limit = max(0, min(int(max_images or 0), 5))
        if limit <= 0:
            return []
        return (
            db.query(InspectionPhoto)
            .filter(InspectionPhoto.check_item_id == check_item_id)
            .order_by(InspectionPhoto.taken_at.desc())
            .limit(limit)
            .all()
        )

    def _build_input_payload(
        self,
        *,
        check_item: InspectionCheckItem,
        photos: List[InspectionPhoto],
        ai_mode: str,
        ai_model: str,
    ) -> Dict[str, Any]:
        photo_meta = []
        for p in photos:
            photo_meta.append(
                {
                    "photo_id": p.id,
                    "field_id": getattr(p, "field_id", None),
                    "taken_at": p.taken_at.isoformat() if getattr(p, "taken_at", None) else None,
                    "latitude": getattr(p, "latitude", None),
                    "longitude": getattr(p, "longitude", None),
                    "address": getattr(p, "address", None),
                    "has_watermark": getattr(p, "has_watermark", None),
                    "hash_value": getattr(p, "hash_value", None),
                    "review_status": getattr(p, "review_status", None),
                }
            )

        return {
            "prompt_version": self.PROMPT_VERSION,
            "ai_mode": ai_mode,
            "ai_model": ai_model,
            "check_item": {
                "id": check_item.id,
                "item_id": check_item.item_id,
                "item_name": check_item.item_name,
                "description": check_item.description,
                "category_id": check_item.category_id,
                "category_name": check_item.category_name,
                "required_type": check_item.required_type,
                "status": getattr(check_item.status, "value", check_item.status),
                "notes": check_item.notes,
                "data_value": check_item.data_value,
                "fields": check_item.fields,
                "validation_result": check_item.validation_result,
            },
            "photos": photo_meta,
        }

    @staticmethod
    def _calc_input_hash(payload: Dict[str, Any]) -> str:
        s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    @staticmethod
    def _photo_to_data_url(file_path: str) -> str:
        if not file_path:
            raise RuntimeError("图片路径为空")

        path = file_path
        if not os.path.exists(path):
            # 兼容相对路径/工作目录差异
            path = os.path.join(os.getcwd(), file_path)
        if not os.path.exists(path):
            raise RuntimeError(f"图片文件不存在: {file_path}")

        with Image.open(path) as img:
            img = img.convert("RGB")
            img = _resize_image_keep_ratio(img, max_side=1280)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"

    @staticmethod
    def _normalize_result(result: Dict[str, Any], *, elapsed_ms: int) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise RuntimeError("AI 返回非 JSON 对象")
        out = dict(result)
        out.setdefault("analysis", [])
        out.setdefault("missing_evidence", [])
        out.setdefault("field_findings", [])
        out.setdefault("photo_findings", [])
        out.setdefault("confidence", 0)
        out.setdefault("suggested_review_status", "warning")
        out.setdefault("suggested_score", 0)
        out.setdefault("summary", "")
        out.setdefault("_meta", {})
        if isinstance(out.get("_meta"), dict):
            out["_meta"].setdefault("elapsed_ms", elapsed_ms)
        return out


def _resize_image_keep_ratio(img: Image.Image, *, max_side: int) -> Image.Image:
    if not img or not getattr(img, "size", None):
        return img
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    max_wh = max(w, h)
    if max_wh <= max_side:
        return img
    ratio = max_side / max_wh
    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
    return img.resize(new_size, Image.LANCZOS)
