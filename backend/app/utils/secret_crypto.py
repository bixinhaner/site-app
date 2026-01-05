import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _build_fernet() -> Fernet:
    raw = (settings.SECRET_KEY or "").encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None:
        return None
    value = str(plaintext)
    if value == "":
        return ""
    f = _build_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    value = str(token)
    if value == "":
        return ""
    f = _build_fernet()
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # 兼容历史误存明文的场景：无法解密时按明文返回
        return value


def mask_secret(secret: Optional[str]) -> str:
    s = str(secret or "")
    if not s:
        return ""
    tail = s[-4:] if len(s) >= 4 else s
    return f"****{tail}"

