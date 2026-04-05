from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.site_payment_service import (
    get_site_payment_currency_options,
    get_site_payment_milestone_options,
    load_site_payment_settings,
    normalize_site_payment_currency,
    normalize_site_payment_rule,
    save_site_payment_settings,
)

router = APIRouter()


class SitePaymentRulePayload(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)
    milestone_code: str
    enabled: bool = True
    amount_type: str = Field(..., pattern="^(ratio|fixed)$")
    amount_value: float = Field(..., ge=0)
    requires_work_order_approved: bool = False
    warning_discount_enabled: bool = False
    warning_discount_ratio: float = Field(100, ge=0, le=100)
    sort_order: int = 10
    remark: Optional[str] = None


class SitePaymentSettingsPayload(BaseModel):
    config_version: int = Field(1, ge=1)
    currency: str = Field("USD", min_length=1, max_length=20)
    rules: List[SitePaymentRulePayload] = Field(default_factory=list)


class SitePaymentSettingsResponse(BaseModel):
    config_version: int
    currency: str
    rules: List[Dict[str, Any]]
    milestone_options: List[Dict[str, str]]
    currency_options: List[Dict[str, str]]


def _ensure_admin(user: User) -> None:
    if user.role == "admin" or user.has_role("admin"):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以管理站点付款规则")


@router.get("/site-payment-settings", response_model=SitePaymentSettingsResponse)
def get_site_payment_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    settings = load_site_payment_settings(db)
    return SitePaymentSettingsResponse(
        config_version=int(settings["config_version"]),
        currency=str(settings["currency"]),
        rules=list(settings["rules"]),
        milestone_options=get_site_payment_milestone_options(),
        currency_options=get_site_payment_currency_options(),
    )


@router.put("/site-payment-settings", response_model=SitePaymentSettingsResponse)
def update_site_payment_settings(
    payload: SitePaymentSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)
    normalized_rules = [
        normalize_site_payment_rule(rule.model_dump(), index)
        for index, rule in enumerate(payload.rules or [])
    ]
    settings = save_site_payment_settings(
        db,
        {
            "config_version": int(payload.config_version),
            "currency": normalize_site_payment_currency(payload.currency),
            "rules": normalized_rules,
        },
    )
    return SitePaymentSettingsResponse(
        config_version=int(settings["config_version"]),
        currency=str(settings["currency"]),
        rules=list(settings["rules"]),
        milestone_options=get_site_payment_milestone_options(),
        currency_options=get_site_payment_currency_options(),
    )
