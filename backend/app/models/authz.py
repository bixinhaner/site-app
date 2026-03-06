from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user_links = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    permission_links = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    data_scope_links = relationship("RoleDataScope", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    module = Column(String(64), nullable=False, default="general")
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    role_links = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="role_links")
    role = relationship("Role", back_populates="user_links")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    role = relationship("Role", back_populates="permission_links")
    permission = relationship("Permission", back_populates="role_links")


class RoleDataScope(Base):
    __tablename__ = "role_data_scopes"
    __table_args__ = (
        UniqueConstraint("role_id", "resource_code", name="uq_role_data_scopes_role_resource"),
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_code = Column(String(64), nullable=False, index=True)
    scope_code = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    role = relationship("Role", back_populates="data_scope_links")
