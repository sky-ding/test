#!/usr/bin/env python3
"""
验证当前配置能否连接数据库，并打印 users / registry 行数（团队部署冒烟用）。

在 backend 目录、已激活 venv 后：
  python scripts/check_db.py

依赖与主应用相同：未配置 MySQL 时使用 SQLite app.db。
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.models import RegistryEntry, User  # noqa: E402


def main() -> int:
    print("uses_mysql:", settings.uses_mysql)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("connect: OK")
    except Exception as e:
        print("connect: FAILED", e)
        return 1

    from app.db import SessionLocal

    with SessionLocal() as s:
        uc = s.scalar(select(func.count()).select_from(User)) or 0
        rc = s.scalar(select(func.count()).select_from(RegistryEntry)) or 0
        keys = list(s.scalars(select(RegistryEntry.key).order_by(RegistryEntry.key)))
    print("users rows:", uc)
    print("registry rows:", rc)
    print("registry keys:", keys if keys else "(empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
