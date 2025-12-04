import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 备份元数据单独存储在 backend/db/backup_meta.db，不参与还原

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
META_DB_DIR = os.path.join(BACKEND_ROOT, "db")
os.makedirs(META_DB_DIR, exist_ok=True)

META_DB_PATH = os.path.join(META_DB_DIR, "backup_meta.db")
META_DB_URL = f"sqlite:///{META_DB_PATH}"

engine = create_engine(
    META_DB_URL,
    connect_args={"check_same_thread": False},
)

MetaSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
MetaBase = declarative_base()

