#!/usr/bin/env python3
"""从物料申请单备注中解析目标站点，回填 material_requests.site_id 及其关联出入库记录。

背景：目标站点字段上线前，领料人把站点写在备注里（如 “34YYK_0076 DMT_BLPT_...”、“33smg 0192”），
盘库时出入库记录找不到站点。本脚本只处理 site_id 为空的申请单：
  - 备注中能唯一匹配到一个站点（站点ID，或长度足够的站点名）→ 回填申请单与其出入库记录（仅空值）
  - 匹配到多个站点 / 站点ID不在站点表 / 没写站点 → 不改，写入 CSV 供仓库人工确认

只使用 sqlite3，不导入 app（导入 app.main 会在目标库上执行迁移）。
默认只预览，加 --apply 才写入（单事务）。

用法：
  python3 scripts/backfill_material_request_sites.py --db backend/site_manager.db --report /tmp/unresolved.csv
  python3 scripts/backfill_material_request_sites.py --db backend/site_manager.db --report /tmp/unresolved.csv --apply
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys

# 站点ID形如 33SMG_0192 / 34YYK_0076；备注里常见 “33smg 0192”、“34SMN 0119”、“33PWT-121”
CODE_PATTERN = re.compile(r"(?<![0-9A-Za-z])(\d{2})\s*([A-Za-z]{3})[\s_-]*(\d{3,4})(?![0-9])")
# 站点名过短容易误匹配到普通单词，只用足够长的站点名兜底（仅在备注里没有站点ID时使用）
MIN_NAME_LEN = 10


def normalize_code(value: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(value or "").upper())


def load_sites(con: sqlite3.Connection):
    by_code: dict[str, int] = {}
    by_name: dict[str, int] = {}
    labels: dict[int, str] = {}
    for site_id, code, name in con.execute("SELECT id, site_code, site_name FROM sites"):
        labels[site_id] = f"{code} {name}"
        if code:
            by_code[normalize_code(code)] = site_id
        if name and len(name.strip()) >= MIN_NAME_LEN:
            by_name[name.strip().upper()] = site_id
    return by_code, by_name, labels


def match_notes(notes: str, by_code: dict[str, int], by_name: dict[str, int]):
    """返回 (匹配到的站点ID集合, 备注中出现但站点表里没有的站点ID列表)。"""
    found: set[int] = set()
    unknown: list[str] = []
    for prefix, letters, number in CODE_PATTERN.findall(notes):
        key = f"{prefix}{letters.upper()}{number.zfill(4)}"
        if key in by_code:
            found.add(by_code[key])
        else:
            unknown.append(f"{prefix}{letters.upper()}_{number.zfill(4)}")
    if not found:
        upper = notes.upper()
        for name, site_id in by_name.items():
            if re.search(r"(?<![0-9A-Z])" + re.escape(name) + r"(?![0-9A-Z])", upper):
                found.add(site_id)
    return found, unknown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="SQLite 数据库路径")
    parser.add_argument("--report", help="未能自动回填的申请单 CSV 输出路径")
    parser.add_argument("--apply", action="store_true", help="实际写入（默认只预览）")
    args = parser.parse_args()

    con = sqlite3.connect(args.db, timeout=60)
    by_code, by_name, labels = load_sites(con)

    rows = con.execute(
        """
        SELECT r.id, r.request_no, r.created_at, r.status, COALESCE(u.full_name, u.username, ''), r.notes
        FROM material_requests r LEFT JOIN users u ON u.id = r.requester_id
        WHERE r.site_id IS NULL
        ORDER BY r.created_at
        """
    ).fetchall()

    resolved: list[tuple[str, str, int]] = []
    unresolved: list[dict] = []
    for req_id, request_no, created_at, status, requester, notes in rows:
        text = str(notes or "").strip()
        found, unknown = match_notes(text, by_code, by_name) if text else (set(), [])
        if len(found) == 1:
            resolved.append((req_id, request_no, next(iter(found))))
            continue
        if len(found) > 1:
            reason = "备注包含多个站点"
            candidates = "; ".join(labels[x] for x in sorted(found))
        elif unknown:
            reason = "站点ID不在站点表"
            candidates = "; ".join(unknown)
        elif text:
            reason = "备注中未识别到站点"
            candidates = ""
        else:
            reason = "备注为空"
            candidates = ""
        unresolved.append(
            {
                "申请单号": request_no,
                "创建时间": created_at,
                "状态": status,
                "申请人": requester,
                "原因": reason,
                "候选站点": candidates,
                "备注": text,
            }
        )

    tx_counts = {}
    for req_id, _, _ in resolved:
        tx_counts[req_id] = con.execute(
            "SELECT COUNT(*) FROM stock_transactions WHERE material_request_id = ? AND site_id IS NULL", (req_id,)
        ).fetchone()[0]

    print(f"待处理申请单（site_id 为空）：{len(rows)}")
    print(f"  可自动回填：{len(resolved)}（关联出入库记录 {sum(tx_counts.values())} 条）")
    print(f"  需人工确认：{len(unresolved)}")
    reasons: dict[str, int] = {}
    for item in unresolved:
        reasons[item["原因"]] = reasons.get(item["原因"], 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    - {reason}：{count}")
    for req_id, request_no, site_id in resolved[:10]:
        print(f"  示例 {request_no} → {labels[site_id]}（出入库 {tx_counts[req_id]} 条）")

    if args.report:
        with open(args.report, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=["申请单号", "创建时间", "状态", "申请人", "原因", "候选站点", "备注"])
            writer.writeheader()
            writer.writerows(unresolved)
        print(f"人工确认清单：{args.report}")

    if not args.apply:
        print("预览模式，未写入。确认无误后加 --apply 执行。")
        return 0

    with con:
        for req_id, _, site_id in resolved:
            con.execute("UPDATE material_requests SET site_id = ? WHERE id = ? AND site_id IS NULL", (site_id, req_id))
            con.execute(
                "UPDATE stock_transactions SET site_id = ? WHERE material_request_id = ? AND site_id IS NULL",
                (site_id, req_id),
            )
    print(f"已回填申请单 {len(resolved)} 张、出入库记录 {sum(tx_counts.values())} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
