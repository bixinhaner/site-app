from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.models.inspection import InspectionPhoto, SiteInspection
from app.models.site import Site
from app.models.user import User
from app.utils.timezone import to_utc_iso


DEFAULT_WINDOW_DAYS = 180
DEFAULT_PHASH_THRESHOLD = 4
DEFAULT_VECTOR_THRESHOLD = 0.985
DEFAULT_MAX_CANDIDATES = 4000

SIMILAR_SOURCE_TYPE = "inspection_photo"
SIMILAR_SOURCE_LABEL = "巡检检查项照片"


_CLIP_LOCK = threading.Lock()
_CLIP_PROCESSOR = None
_CLIP_MODEL = None
_CLIP_TORCH = None
_CLIP_FAILED = False


def _truthy(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off"):
        return False
    return default


def _clip_enabled() -> bool:
    return _truthy(os.getenv("PHOTO_SIMILARITY_USE_CLIP", "true"), default=True)


def _clip_model_name() -> str:
    return os.getenv("PHOTO_SIMILARITY_CLIP_MODEL", "openai/clip-vit-base-patch32").strip() or "openai/clip-vit-base-patch32"


def _max_candidates() -> int:
    raw = os.getenv("PHOTO_SIMILARITY_MAX_CANDIDATES", str(DEFAULT_MAX_CANDIDATES))
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_MAX_CANDIDATES
    return max(100, min(value, 20000))


def _build_site_display(site_name: Optional[str], site_id: Optional[int]) -> str:
    if site_name and site_id is not None:
        return f"{site_name}(ID:{site_id})"
    if site_name:
        return site_name
    if site_id is not None:
        return f"站点ID:{site_id}"
    return "未知站点"


def _build_uploader_display(uploader_name: Optional[str], uploader_id: Optional[int]) -> str:
    if uploader_name and uploader_id is not None:
        return f"{uploader_name}(ID:{uploader_id})"
    if uploader_name:
        return uploader_name
    if uploader_id is not None:
        return f"用户ID:{uploader_id}"
    return "未知用户"


def _get_clip_components():
    global _CLIP_PROCESSOR, _CLIP_MODEL, _CLIP_TORCH, _CLIP_FAILED
    if not _clip_enabled():
        return None, None, None
    if _CLIP_FAILED:
        return None, None, None
    if _CLIP_PROCESSOR is not None and _CLIP_MODEL is not None and _CLIP_TORCH is not None:
        return _CLIP_PROCESSOR, _CLIP_MODEL, _CLIP_TORCH

    with _CLIP_LOCK:
        if _CLIP_PROCESSOR is not None and _CLIP_MODEL is not None and _CLIP_TORCH is not None:
            return _CLIP_PROCESSOR, _CLIP_MODEL, _CLIP_TORCH
        try:
            import torch  # type: ignore
            from transformers import CLIPModel, CLIPProcessor  # type: ignore

            model_name = _clip_model_name()
            processor = CLIPProcessor.from_pretrained(model_name)
            model = CLIPModel.from_pretrained(model_name)
            model.eval()
            _CLIP_PROCESSOR = processor
            _CLIP_MODEL = model
            _CLIP_TORCH = torch
        except Exception as exc:
            _CLIP_FAILED = True
            print(f"[photo_similarity_guard] CLIP加载失败，回退到轻量向量: {exc}")
            return None, None, None

    return _CLIP_PROCESSOR, _CLIP_MODEL, _CLIP_TORCH


def _normalize_vector(vec: np.ndarray) -> Optional[np.ndarray]:
    if vec is None:
        return None
    if vec.size == 0:
        return None
    norm = float(np.linalg.norm(vec))
    if norm <= 0:
        return None
    return vec / norm


def _extract_content_region(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width <= 0 or height <= 0:
        return rgb

    # 规避左下角动态水印区域，取“中上部主体内容”
    left = int(width * 0.10)
    right = int(width * 0.90)
    top = int(height * 0.05)
    bottom = int(height * 0.75)
    if (right - left) >= 64 and (bottom - top) >= 64:
        return rgb.crop((left, top, right, bottom))

    short_edge = min(width, height)
    if short_edge <= 0:
        return rgb
    x0 = (width - short_edge) // 2
    y0 = (height - short_edge) // 2
    return rgb.crop((x0, y0, x0 + short_edge, y0 + short_edge))


_DCT_CACHE: Dict[int, np.ndarray] = {}


def _get_dct_matrix(size: int) -> np.ndarray:
    if size in _DCT_CACHE:
        return _DCT_CACHE[size]
    n = np.arange(size, dtype=np.float32)
    k = n.reshape((-1, 1))
    mat = np.sqrt(2.0 / size) * np.cos(np.pi * (2 * n + 1) * k / (2.0 * size))
    mat[0, :] = np.sqrt(1.0 / size)
    _DCT_CACHE[size] = mat
    return mat


def _dct2(values: np.ndarray) -> np.ndarray:
    h, w = values.shape
    dct_h = _get_dct_matrix(h)
    dct_w = _get_dct_matrix(w)
    return dct_h @ values @ dct_w.T


def _compute_phash(content_image: Image.Image) -> Optional[str]:
    try:
        img = content_image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
        values = np.asarray(img, dtype=np.float32)
        dct = _dct2(values)
        low = dct[:8, :8].flatten()
        if low.size == 0:
            return None
        median = float(np.median(low[1:])) if low.size > 1 else float(np.median(low))
        bits = (low > median).astype(np.uint8)
        bit_text = "".join("1" if int(b) else "0" for b in bits)
        if not bit_text:
            return None
        return f"{int(bit_text, 2):016x}"
    except Exception:
        return None


def _compute_fallback_embedding(content_image: Image.Image) -> Optional[np.ndarray]:
    try:
        img = content_image.convert("RGB").resize((160, 160), Image.Resampling.BICUBIC)
        arr = np.asarray(img, dtype=np.float32) / 255.0

        # 全图RGB直方图
        full_hist: List[float] = []
        for idx in range(3):
            h, _ = np.histogram(arr[:, :, idx], bins=16, range=(0.0, 1.0), density=True)
            full_hist.extend(h.tolist())

        # 中央区域RGB直方图
        h, w, _ = arr.shape
        y0, y1 = int(h * 0.25), int(h * 0.75)
        x0, x1 = int(w * 0.25), int(w * 0.75)
        center = arr[y0:y1, x0:x1, :]
        center_hist: List[float] = []
        for idx in range(3):
            h2, _ = np.histogram(center[:, :, idx], bins=16, range=(0.0, 1.0), density=True)
            center_hist.extend(h2.tolist())

        # 梯度分布
        gray = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114
        grad_x = np.diff(gray, axis=1, append=gray[:, -1:])
        grad_y = np.diff(gray, axis=0, append=gray[-1:, :])
        grad_mag = np.sqrt(grad_x * grad_x + grad_y * grad_y)
        edge_hist, _ = np.histogram(grad_mag, bins=16, range=(0.0, 1.5), density=True)

        vec = np.asarray(full_hist + center_hist + edge_hist.tolist(), dtype=np.float32)
        return _normalize_vector(vec)
    except Exception:
        return None


def _compute_clip_embedding(content_image: Image.Image) -> Optional[np.ndarray]:
    processor, model, torch = _get_clip_components()
    if processor is None or model is None or torch is None:
        return None
    try:
        inputs = processor(images=content_image, return_tensors="pt")
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        vec = features[0].detach().cpu().numpy().astype(np.float32)
        return _normalize_vector(vec)
    except Exception as exc:
        print(f"[photo_similarity_guard] CLIP向量提取失败，回退轻量向量: {exc}")
        return None


def extract_similarity_features(image_path: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "content_phash": None,
        "content_vector": None,
        "content_vector_backend": None,
    }
    if not image_path:
        return result
    if not os.path.exists(image_path):
        return result

    try:
        with Image.open(image_path) as image:
            content = _extract_content_region(image)
            phash = _compute_phash(content)
            result["content_phash"] = phash

            vector = _compute_clip_embedding(content)
            backend = "clip"
            if vector is None:
                vector = _compute_fallback_embedding(content)
                backend = "fallback"
            if vector is not None:
                result["content_vector"] = [float(v) for v in vector.tolist()]
                result["content_vector_backend"] = backend
    except Exception as exc:
        print(f"[photo_similarity_guard] 提取图片相似特征失败: {exc}")
    return result


def _parse_vector(raw: Any) -> Optional[np.ndarray]:
    if raw is None:
        return None
    data = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except Exception:
            return None
    if not isinstance(data, list):
        return None
    try:
        vec = np.asarray(data, dtype=np.float32)
    except Exception:
        return None
    return _normalize_vector(vec)


def _hamming_distance_hex(a: Optional[str], b: Optional[str]) -> Optional[int]:
    if not a or not b:
        return None
    try:
        return int(a, 16) ^ int(b, 16)
    except Exception:
        return None


def _calc_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> Optional[float]:
    if vec_a is None or vec_b is None:
        return None
    if vec_a.size == 0 or vec_b.size == 0:
        return None
    if vec_a.shape[0] != vec_b.shape[0]:
        return None
    return float(np.dot(vec_a, vec_b))


def _resolve_uploader_name(full_name: Optional[str], username: Optional[str]) -> Optional[str]:
    if full_name and str(full_name).strip():
        return str(full_name).strip()
    if username and str(username).strip():
        return str(username).strip()
    return None


def detect_similar_photo_warning(
    db: Session,
    *,
    content_phash: Optional[str],
    content_vector: Any,
    content_vector_backend: Optional[str],
    exclude_photo_id: Optional[str] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
    vector_threshold: float = DEFAULT_VECTOR_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    phash_text = str(content_phash or "").strip().lower()
    if not phash_text:
        return None

    query_vec = _parse_vector(content_vector)
    if query_vec is None:
        return None

    safe_window_days = max(1, min(int(window_days or DEFAULT_WINDOW_DAYS), 3650))
    safe_phash_threshold = max(0, min(int(phash_threshold or DEFAULT_PHASH_THRESHOLD), 64))
    safe_vector_threshold = float(vector_threshold if vector_threshold is not None else DEFAULT_VECTOR_THRESHOLD)
    safe_vector_threshold = max(0.0, min(safe_vector_threshold, 1.0))

    cutoff = datetime.utcnow() - timedelta(days=safe_window_days)
    candidate_query = (
        db.query(
            InspectionPhoto.id.label("photo_id"),
            InspectionPhoto.content_phash.label("content_phash"),
            InspectionPhoto.content_vector.label("content_vector"),
            InspectionPhoto.content_vector_backend.label("content_vector_backend"),
            InspectionPhoto.created_at.label("uploaded_at"),
            InspectionPhoto.inspection_id.label("inspection_id"),
            InspectionPhoto.check_item_id.label("check_item_id"),
            SiteInspection.site_id.label("site_id"),
            Site.site_name.label("site_name"),
            User.id.label("uploader_id"),
            User.full_name.label("uploader_full_name"),
            User.username.label("uploader_username"),
        )
        .join(SiteInspection, SiteInspection.id == InspectionPhoto.inspection_id)
        .outerjoin(Site, Site.id == SiteInspection.site_id)
        .outerjoin(User, User.id == InspectionPhoto.uploaded_by)
        .filter(
            InspectionPhoto.created_at >= cutoff,
            InspectionPhoto.content_phash.is_not(None),
            InspectionPhoto.content_vector.is_not(None),
        )
    )

    if exclude_photo_id:
        candidate_query = candidate_query.filter(InspectionPhoto.id != str(exclude_photo_id))
    if content_vector_backend:
        candidate_query = candidate_query.filter(InspectionPhoto.content_vector_backend == str(content_vector_backend))

    candidates = candidate_query.order_by(InspectionPhoto.created_at.desc()).limit(_max_candidates()).all()
    if not candidates:
        return None

    best = None
    best_score = -1.0
    best_distance = 999

    for row in candidates:
        xor_value = _hamming_distance_hex(phash_text, getattr(row, "content_phash", None))
        if xor_value is None:
            continue
        distance = int(xor_value).bit_count()
        if distance > safe_phash_threshold:
            continue

        candidate_vec = _parse_vector(getattr(row, "content_vector", None))
        score = _calc_cosine_similarity(query_vec, candidate_vec) if candidate_vec is not None else None
        if score is None:
            continue
        if score < safe_vector_threshold:
            continue

        if (score > best_score) or (score == best_score and distance < best_distance):
            best = row
            best_score = score
            best_distance = distance

    if best is None:
        return None

    site_id = getattr(best, "site_id", None)
    site_name = getattr(best, "site_name", None)
    uploader_id = getattr(best, "uploader_id", None)
    uploader_name = _resolve_uploader_name(
        getattr(best, "uploader_full_name", None),
        getattr(best, "uploader_username", None),
    )
    uploaded_at_text = to_utc_iso(getattr(best, "uploaded_at", None))

    detail = {
        "code": "SIMILAR_PHOTO",
        "message": (
            "检测到极度相似照片，可能存在历史照片复用风险。"
            f"相似来源：站点[{_build_site_display(site_name, site_id)}]，"
            f"上传人[{_build_uploader_display(uploader_name, uploader_id)}]，"
            f"时间[{uploaded_at_text or '-'}]，"
            f"来源[{SIMILAR_SOURCE_LABEL}]，"
            f"相似度[{best_score * 100:.2f}%]。"
        ),
        "similar": {
            "source_type": SIMILAR_SOURCE_TYPE,
            "source_type_label": SIMILAR_SOURCE_LABEL,
            "site_id": site_id,
            "site_name": site_name,
            "uploader_id": uploader_id,
            "uploader_name": uploader_name,
            "uploaded_at": uploaded_at_text,
            "site_display": _build_site_display(site_name, site_id),
            "uploader_display": _build_uploader_display(uploader_name, uploader_id),
            "matched_photo_id": getattr(best, "photo_id", None),
            "matched_inspection_id": getattr(best, "inspection_id", None),
            "matched_check_item_id": getattr(best, "check_item_id", None),
            "similarity_score": round(float(best_score), 6),
            "similarity_percent": round(float(best_score) * 100, 2),
            "phash_distance": int(best_distance),
            "phash_threshold": safe_phash_threshold,
            "vector_threshold": round(float(safe_vector_threshold), 6),
            "window_days": safe_window_days,
            "vector_backend": str(content_vector_backend or "unknown"),
        },
    }
    return detail
