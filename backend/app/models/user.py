from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


ROLE_PRIORITY = (
    "admin",
    "manager",
    "warehouse_manager",
    "planner",
    "reviewer",
    "inspector",
    "surveyor",
    "user",
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    avatar = Column(String(255))
    department = Column(String(100))
    position = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    role_links = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")

    @property
    def role_codes(self):
        """RBAC 角色编码列表（按预设优先级排序）。"""
        codes = []
        for link in self.role_links or []:
            role = getattr(link, "role", None)
            if not role:
                continue
            if getattr(role, "is_active", True) is False:
                continue
            code = str(getattr(role, "code", "") or "").strip()
            if code:
                codes.append(code)
        uniq = sorted(set(codes))
        priority = {name: idx for idx, name in enumerate(ROLE_PRIORITY)}
        return sorted(uniq, key=lambda c: (priority.get(c, 999), c))

    @property
    def roles(self):
        """兼容前端字段：返回用户角色编码数组。"""
        return self.role_codes

    @property
    def role(self):
        """兼容旧代码：返回主角色编码（按优先级取第一项）。"""
        codes = self.role_codes
        return codes[0] if codes else None

    def has_role(self, role_code: str) -> bool:
        return str(role_code or "").strip() in set(self.role_codes)

    @property
    def is_admin(self) -> bool:
        return self.has_role("admin")
