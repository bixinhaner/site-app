from pydantic_settings import BaseSettings
from typing import List, Union
import os

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "站点信息管理系统"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./site_manager.db"  # 开发环境使用 SQLite
    
    # JWT 配置
    # 短期 Access Token 过期时间（分钟）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    # 长期 Refresh Token 过期时间（天）
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES_STR: str = "jpg,jpeg,png,pdf"
    
    # CORS 配置
    ALLOWED_HOSTS_STR: str = "*"
    
    # 动态属性
    @property
    def ALLOWED_FILE_TYPES(self) -> List[str]:
        return [item.strip() for item in self.ALLOWED_FILE_TYPES_STR.split(',')]
    
    @property 
    def ALLOWED_HOSTS(self) -> List[str]:
        return [item.strip() for item in self.ALLOWED_HOSTS_STR.split(',')]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
