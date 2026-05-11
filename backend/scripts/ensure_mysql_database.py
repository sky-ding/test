#!/usr/bin/env python3
"""
在未选择库的情况下连接 MySQL，若 PM_MYSQL_DATABASE 不存在则创建（utf8mb4）。

在 backend 目录、已配置 .env 且 venv 已安装依赖后：

  .\\.venv\\Scripts\\python.exe scripts/ensure_mysql_database.py
  .\\.venv\\Scripts\\python.exe scripts/ensure_mysql_database.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pymysql  # noqa: E402

from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只打印将要执行的 SQL，不连接、不建库")
    args = ap.parse_args()

    if not settings.uses_mysql:
        print("当前未启用 MySQL（.env 中 PM_MYSQL_HOST/USER/DATABASE 未齐），无需建库。")
        return 0

    db = (settings.mysql_database or "").strip()
    if not db:
        print("PM_MYSQL_DATABASE 为空")
        return 1

    sql = f"CREATE DATABASE IF NOT EXISTS `{db.replace('`', '``')}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    if args.dry_run:
        print(sql)
        return 0

    try:
        conn = pymysql.connect(
            host=settings.mysql_host.strip(),
            port=int(settings.mysql_port),
            user=settings.mysql_user.strip(),
            password=settings.mysql_password or "",
            charset="utf8mb4",
        )
    except pymysql.err.OperationalError as e:
        print("连接失败（未选库）:", e, file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()

    print(f"已确保数据库存在: {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
