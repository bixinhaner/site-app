from typing import Iterable, List

from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.models.user import User
from app.services.authz_service import user_has_any_permission, user_has_permission


def require_permission(permission_code: str):
    code = str(permission_code or "").strip()

    def _dep(current_user: User = Depends(get_current_user)):
        if not user_has_permission(current_user, code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足: {code}",
            )
        return current_user

    return _dep


def require_any_permission(permission_codes: Iterable[str]):
    codes: List[str] = [str(c or "").strip() for c in (permission_codes or []) if str(c or "").strip()]

    def _dep(current_user: User = Depends(get_current_user)):
        if not user_has_any_permission(current_user, codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足: 需要任一权限 {', '.join(codes)}",
            )
        return current_user

    return _dep
