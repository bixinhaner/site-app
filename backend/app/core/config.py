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
    # 默认与 .env 示例保持一致：4320 分钟（3 天）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 4320
    # 长期 Refresh Token 过期时间（天）
    # 默认 3 天，无操作超过 3 天需要重新登录
    REFRESH_TOKEN_EXPIRE_DAYS: int = 3
    ALGORITHM: str = "HS256"

    # Baidu Map API
    BAIDU_MAP_AK: str = os.getenv("BAIDU_MAP_AK", "")

    # Google Maps Platform API（Geocoding / Reverse Geocoding）
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Google 逆地理 Relay（用于部署在中国境内的后端无法直连 Google 的场景）
    # - 配置 GOOGLE_GEOCODE_RELAY_URL 后，Google 逆地理将优先通过 Relay 转发（后端无需配置 GOOGLE_MAPS_API_KEY）
    # - Relay 侧需配置 GOOGLE_MAPS_API_KEY，并通过 Token + 防火墙白名单限制访问
    GOOGLE_GEOCODE_RELAY_URL: str = os.getenv("GOOGLE_GEOCODE_RELAY_URL", "")
    GOOGLE_GEOCODE_RELAY_TOKEN: str = os.getenv("GOOGLE_GEOCODE_RELAY_TOKEN", "")
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES_STR: str = "jpg,jpeg,png,pdf"
    
    # CORS 配置
    ALLOWED_HOSTS_STR: str = "*"

    # Mock OMC 代理配置（用于前端无法直连 9000 的部署场景）
    MOCK_OMC_BASE_URL: str = os.getenv("MOCK_OMC_BASE_URL", "http://127.0.0.1:9000")
    MOCK_OMC_TIMEOUT_SECONDS: int = int(os.getenv("MOCK_OMC_TIMEOUT_SECONDS", "10"))
    
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
