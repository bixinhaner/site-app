#!/usr/bin/env python3
"""
SQLite Migration Tool (67437911..a34375f)

Purpose
- Bring an existing database up to date with the latest schema as of 2025-10-23.
- Idempotent: safe to run multiple times; only missing pieces are applied.
- Non-interactive: no prompts; optional auto-backup.

What it covers (high level)
- New tables: user_logs, site_planning(+sectors/antenna_ports/switch_ports, planning_change_logs),
  site_surveys, site_survey_photos, equipment_binding_history.
- New columns: inspection_check_items(description, equipment_sn, fields), work_orders(activated_at),
  pickup_records(serial_number, mac_address_1, mac_address_2, equipment_instance_id, work_order_id),
  template_bindings(task_type).
- Indexes: for performance on the above.
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def index_exists(cur: sqlite3.Cursor, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,))
    return cur.fetchone() is not None


def columns(cur: sqlite3.Cursor, table: str) -> set:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def ensure_table(cur: sqlite3.Cursor, name: str, create_sql: str) -> bool:
    if not table_exists(cur, name):
        cur.execute(create_sql)
        print(f"  ✅ create table: {name}")
        return True
    print(f"  ⏭  table exists: {name}")
    return False


def ensure_index(cur: sqlite3.Cursor, name: str, table: str, cols: str) -> bool:
    if not index_exists(cur, name):
        cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({cols})")
        print(f"  ✅ create index: {name}")
        return True
    print(f"  ⏭  index exists: {name}")
    return False


def ensure_column(cur: sqlite3.Cursor, table: str, col: str, coltype: str) -> bool:
    if not table_exists(cur, table):
        print(f"  ⏭  table missing (skip): {table}")
        return False
    if col not in columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        print(f"  ✅ add column: {table}.{col}")
        return True
    print(f"  ⏭  column exists: {table}.{col}")
    return False


def backup(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{ts}"
    shutil.copy2(db_path, backup_path)
    print(f"🗄  backup created: {backup_path}")
    return backup_path


def run(db_path: str, do_backup: bool = True) -> int:
    if not os.path.exists(db_path):
        # If DB doesn't exist, nothing to migrate; app will create tables on start.
        print(f"⚠  database file not found: {db_path} (nothing to migrate)")
        return 0

    if do_backup:
        try:
            backup(db_path)
        except Exception as e:
            print(f"⚠  backup failed (continuing): {e}")

    conn = connect(db_path)
    cur = conn.cursor()
    applied = 0

    try:
        print("== Phase 1: create new tables ==")

        # user_logs
        applied += ensure_table(cur, "user_logs", """
            CREATE TABLE user_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(100) NOT NULL,
                user_id INTEGER,
                username VARCHAR(50),
                timestamp DATETIME NOT NULL,
                action VARCHAR(100) NOT NULL,
                level VARCHAR(20) DEFAULT 'INFO',
                page_route VARCHAR(200),
                page_options JSON,
                action_data JSON,
                device_platform VARCHAR(50),
                device_model VARCHAR(100),
                screen_width INTEGER,
                screen_height INTEGER,
                error_message TEXT,
                error_stack TEXT,
                error_context JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # site planning family
        applied += ensure_table(cur, "site_planning", """
            CREATE TABLE site_planning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                bands JSON,
                sector_count INTEGER DEFAULT 0,
                notes VARCHAR(500),
                is_current BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        applied += ensure_table(cur, "site_planning_sectors", """
            CREATE TABLE site_planning_sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planning_id INTEGER NOT NULL,
                sector_index INTEGER NOT NULL,
                azimuth_deg FLOAT,
                downtilt_deg FLOAT,
                bands JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
            )
        """)

        applied += ensure_table(cur, "site_antenna_ports", """
            CREATE TABLE site_antenna_ports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planning_id INTEGER NOT NULL,
                port_label VARCHAR(50) NOT NULL,
                sector_index INTEGER NOT NULL,
                band VARCHAR(20),
                mimo_chain VARCHAR(20),
                remarks VARCHAR(200),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
            )
        """)

        applied += ensure_table(cur, "site_switch_ports", """
            CREATE TABLE site_switch_ports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planning_id INTEGER NOT NULL,
                port_no VARCHAR(50) NOT NULL,
                vlan_ids JSON,
                is_uplink BOOLEAN DEFAULT FALSE,
                poe BOOLEAN DEFAULT FALSE,
                description VARCHAR(200),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (planning_id) REFERENCES site_planning(id) ON DELETE CASCADE
            )
        """)

        applied += ensure_table(cur, "planning_change_logs", """
            CREATE TABLE planning_change_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                planning_id INTEGER,
                operation VARCHAR(20) NOT NULL,
                actor_id INTEGER NOT NULL,
                summary VARCHAR(500),
                before_snapshot JSON,
                after_snapshot JSON,
                diff JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (planning_id) REFERENCES site_planning(id),
                FOREIGN KEY (actor_id) REFERENCES users(id)
            )
        """)

        # site surveys
        applied += ensure_table(cur, "site_surveys", """
            CREATE TABLE site_surveys (
                id VARCHAR(32) PRIMARY KEY,
                site_id INTEGER NOT NULL,
                survey_date DATETIME NOT NULL,
                surveyor_name VARCHAR(100) NOT NULL,
                surveyor_phone VARCHAR(30),
                latitude FLOAT,
                longitude FLOAT,
                address TEXT,
                gps_accuracy FLOAT,
                site_type VARCHAR(50),
                tower_type VARCHAR(50),
                available_height_m FLOAT,
                load_capacity_kg FLOAT,
                power_available BOOLEAN,
                power_distance_m FLOAT,
                power_capacity_kw FLOAT,
                earthing_feasible BOOLEAN,
                fiber_available BOOLEAN,
                fiber_distance_m FLOAT,
                duct_notes TEXT,
                microwave_los BOOLEAN,
                los_azimuth_deg FLOAT,
                los_distance_km FLOAT,
                sensitive_points TEXT,
                safety_notes TEXT,
                permits_constraints TEXT,
                owner_name VARCHAR(100),
                owner_phone VARCHAR(30),
                access_time_window VARCHAR(100),
                entry_constraints TEXT,
                feasibility VARCHAR(30),
                risks TEXT,
                recommendations TEXT,
                extra_data JSON,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        applied += ensure_table(cur, "site_survey_photos", """
            CREATE TABLE site_survey_photos (
                id VARCHAR(32) PRIMARY KEY,
                survey_id VARCHAR(32) NOT NULL,
                original_name VARCHAR(255),
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER,
                mime_type VARCHAR(100),
                category VARCHAR(50),
                sort_order INTEGER,
                exif JSON,
                latitude FLOAT,
                longitude FLOAT,
                gps_accuracy FLOAT,
                address TEXT,
                taken_at DATETIME,
                has_watermark BOOLEAN DEFAULT FALSE,
                watermark_data JSON,
                hash_value VARCHAR(64),
                uploaded_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (survey_id) REFERENCES site_surveys(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        """)

        # equipment binding history
        applied += ensure_table(cur, "equipment_binding_history", """
            CREATE TABLE equipment_binding_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id VARCHAR(32) NOT NULL,
                check_item_id VARCHAR(32) NOT NULL,
                site_id INTEGER NOT NULL,
                sector_id VARCHAR(10) NOT NULL,
                band VARCHAR(20) NOT NULL,
                cell_id VARCHAR(20) NOT NULL,
                equipment_sn VARCHAR(100) NOT NULL,
                equipment_type VARCHAR(50),
                equipment_model VARCHAR(100),
                action VARCHAR(10) NOT NULL,
                operator_id INTEGER NOT NULL,
                operated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                previous_equipment_sn VARCHAR(100),
                notes TEXT,
                latitude VARCHAR(50),
                longitude VARCHAR(50),
                gps_accuracy VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (check_item_id) REFERENCES inspection_check_items(id),
                FOREIGN KEY (inspection_id) REFERENCES site_inspections(id),
                FOREIGN KEY (operator_id) REFERENCES users(id),
                FOREIGN KEY (site_id) REFERENCES sites(id)
            )
        """)

        print("== Phase 2: add/alter columns ==")
        # inspection_check_items
        applied += ensure_column(cur, "inspection_check_items", "description", "TEXT")
        applied += ensure_column(cur, "inspection_check_items", "equipment_sn", "VARCHAR(100)")
        applied += ensure_column(cur, "inspection_check_items", "fields", "JSON")

        # work_orders
        applied += ensure_column(cur, "work_orders", "activated_at", "DATETIME")

        # pickup_records
        applied += ensure_column(cur, "pickup_records", "serial_number", "VARCHAR(100)")
        applied += ensure_column(cur, "pickup_records", "mac_address_1", "VARCHAR(50)")
        applied += ensure_column(cur, "pickup_records", "mac_address_2", "VARCHAR(50)")
        applied += ensure_column(cur, "pickup_records", "equipment_instance_id", "VARCHAR(32)")
        applied += ensure_column(cur, "pickup_records", "work_order_id", "VARCHAR(32)")

        # template_bindings
        if table_exists(cur, "template_bindings"):
            applied += ensure_column(cur, "template_bindings", "task_type", "VARCHAR(50)")

        print("== Phase 3: create indexes ==")
        # user_logs indexes
        applied += ensure_index(cur, "idx_user_logs_user_timestamp", "user_logs", "user_id, timestamp")
        applied += ensure_index(cur, "idx_user_logs_session_timestamp", "user_logs", "session_id, timestamp")
        applied += ensure_index(cur, "idx_user_logs_action_timestamp", "user_logs", "action, timestamp")
        applied += ensure_index(cur, "idx_user_logs_level_timestamp", "user_logs", "level, timestamp")
        applied += ensure_index(cur, "idx_user_logs_page_timestamp", "user_logs", "page_route, timestamp")

        # site planning indexes
        applied += ensure_index(cur, "idx_site_planning_site_id", "site_planning", "site_id")
        applied += ensure_index(cur, "idx_site_planning_is_current", "site_planning", "is_current")
        applied += ensure_index(cur, "idx_site_planning_sectors_planning_id", "site_planning_sectors", "planning_id")
        applied += ensure_index(cur, "idx_site_antenna_ports_planning_id", "site_antenna_ports", "planning_id")
        applied += ensure_index(cur, "idx_site_switch_ports_planning_id", "site_switch_ports", "planning_id")
        applied += ensure_index(cur, "idx_planning_change_logs_site_id", "planning_change_logs", "site_id")

        # surveys indexes
        applied += ensure_index(cur, "idx_site_surveys_site_id", "site_surveys", "site_id")
        applied += ensure_index(cur, "idx_site_surveys_survey_date", "site_surveys", "survey_date")
        applied += ensure_index(cur, "idx_site_surveys_feasibility", "site_surveys", "feasibility")
        applied += ensure_index(cur, "idx_site_survey_photos_survey_id", "site_survey_photos", "survey_id")

        # equipment binding history indexes
        applied += ensure_index(cur, "ix_equipment_binding_history_equipment_sn", "equipment_binding_history", "equipment_sn")
        applied += ensure_index(cur, "ix_equipment_binding_history_operated_at", "equipment_binding_history", "operated_at")
        applied += ensure_index(cur, "ix_equipment_binding_history_cell", "equipment_binding_history", "site_id, sector_id, band")

        # inspection_check_items helper indexes (only if columns exist)
        if table_exists(cur, "inspection_check_items"):
            ic_cols = columns(cur, "inspection_check_items")
            if "equipment_sn" in ic_cols:
                applied += ensure_index(cur, "ix_inspection_check_items_equipment_sn", "inspection_check_items", "equipment_sn")
            if {"sector_id", "band", "equipment_sn"}.issubset(ic_cols):
                applied += ensure_index(cur, "ix_inspection_check_items_cell", "inspection_check_items", "sector_id, band, equipment_sn")
            if {"inspection_id", "equipment_sn"}.issubset(ic_cols):
                applied += ensure_index(cur, "ix_inspection_check_items_inspection_equipment", "inspection_check_items", "inspection_id, equipment_sn")

        conn.commit()
        print("\n== Done ==")
        print(f"✔ applied changes: {applied}")
        return applied
    except Exception as e:
        conn.rollback()
        print(f"✖ migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = os.environ.get("DB_PATH", "site_manager.db")
    args = sys.argv[1:]
    if args:
        db_path = args[0]
    no_backup = any(a in ("--no-backup", "-n") for a in args)
    print(f"DB: {db_path}")
    run(db_path, do_backup=not no_backup)
