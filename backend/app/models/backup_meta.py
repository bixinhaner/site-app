from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func

from app.core.backup_meta import MetaBase, engine


class BackupMetaRecord(MetaBase):
    """
    备份 / 恢复元数据记录表（仅用于历史展示，不参与还原）。

    kind:
      - backup  : 备份操作
      - restore : 恢复操作
    """

    __tablename__ = "backup_meta_records"

    id = Column(Integer, primary_key=True, index=True)

    kind = Column(String(20), nullable=False)  # backup | restore
    # 对于 kind='backup'：backup_record_id 通常等于自身 id，便于引用
    # 对于 kind='restore'：backup_record_id 指向对应的备份记录（kind='backup'）的 id
    backup_record_id = Column(Integer, nullable=True)
    trigger_type = Column(String(20), nullable=True)  # manual | scheduled

    user_id = Column(Integer, nullable=True)
    username = Column(String(50), nullable=True)

    status = Column(String(20), nullable=True)  # success | failed
    backup_file = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    extra = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# 在导入模型时确保表存在
MetaBase.metadata.create_all(bind=engine)
