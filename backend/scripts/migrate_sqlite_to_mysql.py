#!/usr/bin/env python3
"""
将 backend/data/app.db（SQLite）中的 users、registry 表复制到 PM_MYSQL_* 配置的 MySQL。

用法（在 backend 目录下）：
  pip install -r requirements.txt
  set PM_MYSQL_HOST=... （及 user、password、database 等）
  python scripts/migrate_sqlite_to_mysql.py

若目标库中已有 users 或 registry 数据，默认会退出；可加 --force 清空两表后再导入。

建议：先配置好 MySQL 并确保能连接，再运行本脚本；表不存在时会自动 create_all。
迁移完成后请执行 `python scripts/check_db.py` 并做一次管理员 GET/PUT 冒烟（见 backend/README.md）。
若已启动过应用且 seed 写入了 Sky，需使用 --force 或先手动清空表。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import DATA_DIR, settings  # noqa: E402
from app.models import Base, RegistryEntry, User  # noqa: E402


def _sqlite_url() -> str:
    sqlite_path = (DATA_DIR / "app.db").as_posix()
    return f"sqlite:///{sqlite_path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite app.db to MySQL")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete all rows in users and registry on MySQL before import",
    )
    args = parser.parse_args()

    if not settings.uses_mysql:
        print("未配置 MySQL：请设置环境变量 PM_MYSQL_HOST、PM_MYSQL_USER、PM_MYSQL_DATABASE（及密码等）。")
        return 1

    sqlite_path = DATA_DIR / "app.db"
    if not sqlite_path.is_file():
        print(f"未找到 SQLite 文件：{sqlite_path}")
        return 1

    src_engine = create_engine(_sqlite_url(), connect_args={"check_same_thread": False})
    dst_engine = create_engine(settings.database_url, pool_pre_ping=True)

    Base.metadata.create_all(bind=dst_engine)

    with Session(src_engine) as src_sess, Session(dst_engine) as dst_sess:
        if not args.force:
            uc = dst_sess.scalar(select(func.count()).select_from(User)) or 0
            rc = dst_sess.scalar(select(func.count()).select_from(RegistryEntry)) or 0
            if uc > 0 or rc > 0:
                print(
                    "目标 MySQL 中 users 或 registry 已有数据。若确认覆盖，请使用 --force。"
                    f"（当前 users={uc}, registry={rc}）"
                )
                return 1
        else:
            dst_sess.execute(text("DELETE FROM registry"))
            dst_sess.execute(text("DELETE FROM users"))
            dst_sess.commit()

        users = list(src_sess.scalars(select(User).order_by(User.id)))
        rows_reg = list(src_sess.scalars(select(RegistryEntry).order_by(RegistryEntry.key)))

        for u in users:
            dst_sess.add(
                User(
                    id=u.id,
                    username=u.username,
                    password_hash=u.password_hash,
                    role=u.role,
                    is_active=u.is_active,
                    external_subject=u.external_subject,
                    auth_source=u.auth_source,
                    created_at=u.created_at,
                )
            )

        for r in rows_reg:
            dst_sess.add(
                RegistryEntry(
                    key=r.key,
                    payload=dict(r.payload) if r.payload is not None else {},
                    updated_at=r.updated_at,
                )
            )

        dst_sess.commit()

        max_id = dst_sess.scalar(select(func.max(User.id))) or 0
        if max_id:
            dst_sess.execute(
                text("ALTER TABLE users AUTO_INCREMENT = :next_id"),
                {"next_id": int(max_id) + 1},
            )
            dst_sess.commit()

    print(f"迁移完成：users {len(users)} 行，registry {len(rows_reg)} 行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
