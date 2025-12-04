import os
import zipfile
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.user_log import UserLog
from app.core.backup_meta import MetaSessionLocal
from app.models.backup_meta import BackupMetaRecord


BACKUP_CONFIG_KEY = "data_backup"


def get_default_backup_config() -> Dict[str, Any]:
    """
    默认备份配置：
    - disabled
    - 每1天备份一次
    """
    return {
        "enabled": False,
        "mode": "days",  # hours | days
        "interval": 1,
        "last_run_at": None,
        "last_success_at": None,
    }


def load_backup_config(db: Session) -> Dict[str, Any]:
    """从 system_config 读取备份配置，若不存在则返回默认配置。"""
    row: Optional[SystemConfig] = (
        db.query(SystemConfig).filter(SystemConfig.key == BACKUP_CONFIG_KEY).first()
    )
    if not row or not isinstance(row.value, dict):
        return get_default_backup_config()

    config = get_default_backup_config()
    config.update(row.value or {})
    return config


def save_backup_config(db: Session, config: Dict[str, Any]) -> None:
    """将备份配置写回 system_config。"""
    row: Optional[SystemConfig] = (
        db.query(SystemConfig).filter(SystemConfig.key == BACKUP_CONFIG_KEY).first()
    )
    if not row:
        row = SystemConfig(key=BACKUP_CONFIG_KEY, value=config)
        db.add(row)
    else:
        row.value = config


def _get_backend_root_dir() -> str:
    """获取 backend 根目录（包含 site_manager.db 的目录）。"""
    # 当前文件在 backend/app/services/backup_service.py
    # dirname(__file__)              -> backend/app/services
    # dirname(dirname(__file__))     -> backend/app
    # dirname(dirname(dirname(...))) -> backend
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _collect_db_files() -> list[str]:
    """收集需要备份的数据库文件列表（当前 backend 目录下的 .db 文件）。"""
    backend_root = _get_backend_root_dir()
    db_files: list[str] = []

    for name in os.listdir(backend_root):
        if not name.endswith(".db"):
            continue
        full_path = os.path.join(backend_root, name)
        # 跳过不存在或空文件
        try:
            if not os.path.isfile(full_path):
                continue
            if os.path.getsize(full_path) <= 0:
                continue
        except OSError:
            continue
        db_files.append(full_path)

    return db_files


def restore_backup(
    db: Session,
    backup_meta_id: int,
    trigger_user: Optional[User] = None,
) -> None:
    """
    从指定备份记录恢复数据库文件。

    恢复流程完全基于 backup_meta.db 中的元数据：
    - 通过 BackupMetaRecord(kind='backup') 查找备份文件路径
    - 使用 zip 覆盖 backend 根目录下的 .db 文件
    - 恢复成功/失败都会在 UserLog 和 backup_meta.db 中记录一条 restore 记录
    """
    backup_meta: Optional[BackupMetaRecord] = None

    # 先从 meta 库中读取备份记录
    try:
        meta_db = MetaSessionLocal()
        try:
            backup_meta = (
                meta_db.query(BackupMetaRecord)
                .filter(
                    BackupMetaRecord.id == backup_meta_id,
                    BackupMetaRecord.kind == "backup",
                )
                .first()
            )
        finally:
            meta_db.close()
    except Exception:
        backup_meta = None

    if not backup_meta:
        raise ValueError(f"备份元记录不存在: {backup_meta_id}")
    if backup_meta.status != "success":
        raise ValueError("只能恢复状态为 success 的备份记录")
    if not backup_meta.backup_file:
        raise ValueError("备份记录缺少备份文件路径")

    backend_root = _get_backend_root_dir()
    if os.path.isabs(backup_meta.backup_file):
        zip_path = backup_meta.backup_file
    else:
        zip_path = os.path.join(backend_root, backup_meta.backup_file)

    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"备份文件不存在: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if not info.filename.endswith(".db"):
                    continue
                # 备份中存的是文件名，恢复时覆盖 backend 根目录下同名 .db
                src_name = os.path.basename(info.filename)
                target_path = os.path.join(backend_root, src_name)

                # 解压到 backend 根目录，再移动覆盖
                zf.extract(info, path=backend_root)
                extracted_path = os.path.join(backend_root, info.filename)
                if extracted_path != target_path:
                    os.replace(extracted_path, target_path)

        # 恢复成功时写一条 INFO 日志
        try:
            log = UserLog(
                session_id="system-backup-restore",
                user_id=getattr(trigger_user, "id", None),
                username=getattr(trigger_user, "username", None),
                timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
                action="data_backup_restore_success",
                level="INFO",
                page_route="web-admin/system/backup",
                page_options=None,
                action_data={
                    "record_id": backup_meta.id,
                    "backup_file": backup_meta.backup_file,
                },
                device_platform="backend",
                device_model="server",
                screen_width=None,
                screen_height=None,
                error_message=None,
                error_stack=None,
                error_context=None,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

        # 元数据记录（restore 成功）
        try:
            meta_db = MetaSessionLocal()
            try:
                meta = BackupMetaRecord(
                    kind="restore",
                    backup_record_id=backup_meta.id,
                    trigger_type="manual",
                    user_id=getattr(trigger_user, "id", None),
                    username=getattr(trigger_user, "username", None),
                    status="success",
                    backup_file=backup_meta.backup_file,
                    error_message=None,
                    extra=None,
                )
                meta_db.add(meta)
                meta_db.commit()
            finally:
                meta_db.close()
        except Exception:
            # 元数据失败不影响主流程
            pass

    except Exception as exc:
        # 写入失败日志
        try:
            log = UserLog(
                session_id="system-backup-restore",
                user_id=getattr(trigger_user, "id", None),
                username=getattr(trigger_user, "username", None),
                timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
                action="data_backup_restore_failed",
                level="ERROR",
                page_route="web-admin/system/backup",
                page_options=None,
                action_data={
                    "record_id": backup_meta.id if backup_meta else backup_meta_id,
                    "backup_file": getattr(backup_meta, "backup_file", None),
                    "error": str(exc),
                },
                device_platform="backend",
                device_model="server",
                screen_width=None,
                screen_height=None,
                error_message=str(exc),
                error_stack=None,
                error_context=None,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

        # 元数据记录（restore 失败）
        try:
            meta_db = MetaSessionLocal()
            try:
                meta = BackupMetaRecord(
                    kind="restore",
                    backup_record_id=backup_meta.id if backup_meta else backup_meta_id,
                    trigger_type="manual",
                    user_id=getattr(trigger_user, "id", None),
                    username=getattr(trigger_user, "username", None),
                    status="failed",
                    backup_file=getattr(backup_meta, "backup_file", None),
                    error_message=str(exc),
                    extra=None,
                )
                meta_db.add(meta)
                meta_db.commit()
            finally:
                meta_db.close()
        except Exception:
            pass

        raise exc


def perform_backup(
    db: Session,
    trigger_type: str,
    trigger_user: Optional[User] = None,
) -> Dict[str, Any]:
    """
    执行一次数据库备份。

    - 仅备份 backend 根目录下的 .db 文件
    - 将其打包为 zip 文件，存放在 backend/db-backups/ 目录下
    - 备份历史仅写入独立的 backup_meta.db
    - 失败时写入 UserLog（action=data_backup_failed）
    """
    backend_root = _get_backend_root_dir()
    backup_dir = os.path.join(backend_root, "db-backups")
    os.makedirs(backup_dir, exist_ok=True)

    config_snapshot = load_backup_config(db)

    started_at = datetime.utcnow()
    finished_at: Optional[datetime] = None
    error: Optional[Exception] = None
    backup_rel_path: Optional[str] = None

    try:
        db_files = _collect_db_files()
        if not db_files:
            raise RuntimeError("未找到任何可备份的数据库文件 (*.db)")

        ts = started_at.strftime("%Y%m%d_%H%M%S")
        zip_name = f"db_backup_{ts}.zip"
        zip_path = os.path.join(backup_dir, zip_name)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in db_files:
                arcname = os.path.basename(path)
                zf.write(path, arcname=arcname)

        # 记录备份文件相对路径（相对 backend 根目录，便于展示）
        backup_rel_path = os.path.relpath(zip_path, backend_root)

    except Exception as exc:
        error = exc

        # 写入系统日志（UserLog），方便在日志中心排查
        try:
            log = UserLog(
                session_id="system-backup",
                user_id=getattr(trigger_user, "id", None),
                username=getattr(trigger_user, "username", None),
                timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
                action="data_backup_failed",
                level="ERROR",
                page_route="web-admin/system/backup",
                page_options=None,
                action_data={
                    "trigger_type": trigger_type,
                    "backup_file": backup_rel_path,
                    "error": str(exc),
                },
                device_platform="backend",
                device_model="server",
                screen_width=None,
                screen_height=None,
                error_message=str(exc),
                error_stack=None,
                error_context=None,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()
    finally:
        finished_at = datetime.utcnow()

    # 将备份元数据写入独立的 meta 库（不参与还原）
    status = "failed" if error else "success"
    meta_id: Optional[int] = None
    try:
        meta_db = MetaSessionLocal()
        try:
            duration_seconds: Optional[float] = None
            if started_at and finished_at:
                duration_seconds = (finished_at - started_at).total_seconds()

            extra: Dict[str, Any] = {
                "config_snapshot": config_snapshot,
                "started_at": started_at.replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "finished_at": finished_at.replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "duration_seconds": duration_seconds,
            }

            meta = BackupMetaRecord(
                kind="backup",
                backup_record_id=None,
                trigger_type=trigger_type,
                user_id=getattr(trigger_user, "id", None),
                username=getattr(trigger_user, "username", None),
                status=status,
                backup_file=backup_rel_path,
                error_message=str(error) if error else None,
                extra=extra,
            )
            meta_db.add(meta)
            meta_db.commit()
            meta_db.refresh(meta)

            # 将 backup_record_id 规范化为自身 ID，便于恢复记录关联
            meta.backup_record_id = meta.id
            meta_db.commit()
            meta_id = meta.id
        finally:
            meta_db.close()
    except Exception:
        # 元数据记录失败不影响主流程
        pass

    if error:
        # 将异常抛出给调用方，便于前端提示
        raise error

    return {
        "id": meta_id,
        "status": status,
        "backup_file": backup_rel_path,
        "error_message": str(error) if error else None,
        "started_at": started_at,
        "finished_at": finished_at,
        "config_snapshot": config_snapshot,
    }
