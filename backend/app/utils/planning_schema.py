import json
from typing import Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


# 新版 LLD 模板中“新增/改名后扩展”的字段映射：
# - key：模型字段名（DB 列名）
# - value：Excel 表头候选名（已做过 _normalize_lld_column_name 规范化后的列名）
LLD_CELL_EXTRA_FIELD_CANDIDATES: Dict[str, List[str]] = {
    # 基本信息
    "excel_index": ["Index"],
    "province_region": ["Province Region"],
    "province": ["Province"],
    "city": ["City"],
    "county": ["County"],
    "address": ["Address"],
    "cluster": ["Cluster"],
    "sn": ["SN"],
    # 无线补充
    "work_mode": ["Work Mode"],
    "duplex_mode": ["Duplex Mode"],
    "mimo": ["MIMO"],
    "cell_id_in_file": ["Cell ID", "Cell id"],
    "sa": ["SA"],
    "ssp": ["SSP"],
    # 天线/硬件补充
    "total_tilt": ["Total Tilt"],
    "antenna_model": ["Antenna modle"],
    "antenna_gain": ["Antenna Gain"],
    "ret": ["RET"],
    "transmission_port": ["Transmission Port"],
    "lld_type": ["Type"],
    # 5G 补充
    "dl_bandwidth": ["DL Bandwidth"],
    "ul_bandwidth": ["UL Bandwidth"],
    "ssb_absolute_freq": ["SSB Absolute Freq"],
    "dl_subcarrier_spacing": ["DL SubCarrierSpacing"],
    # OAM IP
    "oam_ip_type": ["oam IP Type"],
    "oam_ip_address": ["oam Ip address"],
    "oam_ip_submask": ["oam Ip Submask"],
    "oam_ip_gateway": ["oam Ip Gateway"],
    "oam_ip_vlan": ["oam Ip VLAN"],
    "oam_ip_dns": ["oam Ip DNS"],
    "oam_binding_port": ["OAM Binding port"],
    # Control plane（模板里写的是 Control planet）
    "control_plane_ip_type": ["Control planet Ip Type"],
    "control_plane_address": ["Control planet address"],
    "control_plane_submask": ["Control planet Submask"],
    "control_plane_gateway": ["Control planet Gateway"],
    "control_plane_vlan": ["Control planet VLAN"],
    "control_plane_dns": ["Control planet DNS"],
    "control_plane_binding_port": ["Control planet binding port"],
    # User plane（模板里写的是 User planet）
    "user_plane_ip_type": ["User planet Ip Type"],
    "user_plane_address": ["User planet address"],
    "user_plane_submask": ["User planet Submask"],
    "user_plane_gateway": ["User planet Gateway"],
    "user_plane_vlan": ["User planet VLAN"],
    "user_plane_dns": ["User planet DNS"],
    "user_plane_binding_port": ["User planet binding port"],
    # X2（4G）
    "x2_ip_type": ["X2 Ip Type"],
    "x2_address": ["X2 address"],
    "x2_submask": ["X2 Submask"],
    "x2_gateway": ["X2 Gateway"],
    "x2_vlan": ["X2 VLAN"],
    "x2_dns": ["X2 DNS"],
    "x2_binding_port": ["X2 binding port"],
    # XN（5G）
    "xn_ip_type": ["XN Ip Type"],
    "xn_address": ["XN address"],
    "xn_submask": ["XN Submask"],
    "xn_gateway": ["XN Gateway"],
    "xn_vlan": ["XN VLAN"],
    "xn_dns": ["XN DNS"],
    "xn_binding_port": ["XN binding port"],
    # MME（4G）
    "mme_ip_1": ["MME IP 1"],
    "mme_ip_2": ["MME IP 2"],
    "mme_ip_3": ["MME IP 3"],
    "mme_ip_4": ["MME IP 4"],
    "mme_ip_5": ["MME IP 5"],
    "mme_ip_6": ["MME IP 6"],
    "mme_ip_7": ["MME IP 7"],
    "mme_ip_8": ["MME IP 8"],
}


def _to_clean_str(v) -> Optional[str]:
    """将任意单元格值转成“干净”的字符串（用于新增字段：统一按字符串保存）。"""
    if v is None:
        return None
    try:
        import pandas as pd

        if isinstance(v, float) and pd.isna(v):
            return None
    except Exception:
        pass

    # numpy scalar / pandas scalar
    if hasattr(v, "item") and callable(getattr(v, "item")):
        try:
            v = v.item()
        except Exception:
            pass

    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)

    s = str(v).strip()
    return s or None


def ensure_planning_schema(engine: Engine) -> None:
    """
    轻量级表结构迁移（SQLite 友好）：
    - Base.metadata.create_all 不会给旧表补列
    - 这里在启动时检查 site_planning_cells 缺失列并用 ALTER TABLE ADD COLUMN 补齐
    - 同时将历史 extra_params 中可识别的字段回填到新列（统一字符串），并从 extra_params 中移除
    """
    required_columns = {
        "site_planning_cells": {
            col_name: f"{col_name} TEXT"
            for col_name in LLD_CELL_EXTRA_FIELD_CANDIDATES.keys()
        }
    }

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            try:
                existing = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                continue

            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
                except Exception:
                    # 兼容并发启动/重复执行等场景：若已存在则忽略
                    continue

    # 回填历史数据：从 extra_params 搬运到新列，并清理 extra_params
    try:
        from app.models.planning import SitePlanningCell

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            rows = db.query(SitePlanningCell).filter(SitePlanningCell.extra_params.isnot(None)).all()
            changed = False
            for row in rows:
                payload = row.extra_params or {}
                if not isinstance(payload, dict) or not payload:
                    continue

                row_changed = False
                for field_name, candidates in LLD_CELL_EXTRA_FIELD_CANDIDATES.items():
                    # 如果列已经有值，也要把 payload 里重复 key 清掉，避免二次存储
                    if getattr(row, field_name, None) is not None:
                        for k in candidates:
                            if k in payload:
                                payload.pop(k, None)
                                row_changed = True
                        continue

                    hit_key = None
                    hit_val = None
                    for k in candidates:
                        if k in payload:
                            hit_key = k
                            hit_val = payload.pop(k, None)
                            row_changed = True
                            break
                    if hit_key is None:
                        continue

                    setattr(row, field_name, _to_clean_str(hit_val))

                    # 同一字段的其它别名也顺带清理
                    for k in candidates:
                        if k in payload:
                            payload.pop(k, None)
                            row_changed = True

                if row_changed:
                    row.extra_params = payload or None
                    changed = True

            if changed:
                db.commit()
        finally:
            db.close()
    except Exception:
        # 回填失败不影响业务
        pass

