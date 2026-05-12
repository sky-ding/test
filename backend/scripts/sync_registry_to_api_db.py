#!/usr/bin/env python3
"""
将「源库」中的 registry 登记（manpower / phase / risk）同步到「当前 .env 配置的库」——
即与运行 API 时 `app.config.settings.database_url` 相同的目标库。

典型场景：你在另一套 MySQL（或本机 SQLite）里执行了 import_registry_data.py，
而线上/本机 API 连接的是 .env 里的 PM_MYSQL_*；用本脚本把三行 registry 拷过去。

在 backend 目录、已激活 venv：

  # 也可把 PM_SOURCE_MYSQL_* 写在 backend/.env 中（与 PM_MYSQL_* 并存，分别表示源库与 API 目标库）

  set PM_SOURCE_MYSQL_HOST=导入数据所在主机
  set PM_SOURCE_MYSQL_USER=...
  set PM_SOURCE_MYSQL_PASSWORD=...
  set PM_SOURCE_MYSQL_DATABASE=...
  python scripts/sync_registry_to_api_db.py --dry-run
  python scripts/sync_registry_to_api_db.py --force

  # 或显式传参（密码可空）
  python scripts/sync_registry_to_api_db.py ^
    --source-host 10.x.x.x --source-user root --source-password secret --source-database pm_imported

  # 源为本地 SQLite（例如另一份 app.db）
  python scripts/sync_registry_to_api_db.py --source-sqlite D:\\path\\to\\app.db --force

目标库始终读取当前目录下的 .env 中的 PM_MYSQL_*（或默认 SQLite）。
若目标某键已有非空登记且未加 --force，该键会跳过（与 import_registry_data 行为一致）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.models import Base, RegistryEntry  # noqa: E402
from app.registry_store import (  # noqa: E402
    KEY_MANPOWER,
    KEY_PHASE,
    KEY_RISK,
    put_json,
)

REGISTRY_KEYS = (KEY_MANPOWER, KEY_PHASE, KEY_RISK)


def _mysql_url(host: str, port: int, user: str, password: str, database: str, charset: str) -> str:
    u = quote_plus(user.strip())
    p = quote_plus(password or "")
    h = host.strip()
    d = database.strip()
    cs = (charset or "utf8mb4").strip() or "utf8mb4"
    return f"mysql+pymysql://{u}:{p}@{h}:{int(port)}/{d}?charset={quote_plus(cs)}"


def _registry_core_array_empty(key: str, payload: object) -> bool:
    if not isinstance(payload, dict):
        return True
    if key == KEY_MANPOWER:
        d = payload.get("data")
        return not isinstance(d, list) or len(d) == 0
    if key == KEY_PHASE:
        d = payload.get("phaseData")
        return not isinstance(d, list) or len(d) == 0
    if key == KEY_RISK:
        d = payload.get("riskRows")
        return not isinstance(d, list) or len(d) == 0
    return True


def _load_source_mysql_from_dotenv_file() -> None:
    """将 .env 中的 PM_SOURCE_MYSQL_* 读入 os.environ（不设则 pydantic 不会自动注入）。"""
    path = BACKEND_ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        if not key.startswith("PM_SOURCE_MYSQL_"):
            continue
        if key in os.environ:
            continue
        val = val.strip().strip('"').strip("'")
        os.environ[key] = val


def _source_mysql_from_env() -> tuple[str, int, str, str, str, str] | None:
    h = (os.environ.get("PM_SOURCE_MYSQL_HOST") or "").strip()
    u = (os.environ.get("PM_SOURCE_MYSQL_USER") or "").strip()
    d = (os.environ.get("PM_SOURCE_MYSQL_DATABASE") or "").strip()
    if not (h and u and d):
        return None
    port = int(os.environ.get("PM_SOURCE_MYSQL_PORT") or "3306")
    pw = os.environ.get("PM_SOURCE_MYSQL_PASSWORD") or ""
    charset = (os.environ.get("PM_SOURCE_MYSQL_CHARSET") or "utf8mb4").strip() or "utf8mb4"
    return (h, port, u, pw, d, charset)


def _redacted_mysql_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        creds, tail = rest.split("@", 1)
        if ":" in creds:
            user, _ = creds.split(":", 1)
            return f"{scheme}://{user}:***@{tail}"
        return f"{scheme}://***@{tail}"
    except ValueError:
        return url


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy registry (manpower/phase/risk) from source DB to API .env target DB",
    )
    parser.add_argument(
        "--source-sqlite",
        metavar="PATH",
        default="",
        help="源库为 SQLite 文件路径（与源 MySQL 二选一）",
    )
    parser.add_argument(
        "--source-host",
        default="",
        help="源 MySQL 主机（须与 --source-user、--source-database 同用；也可仅用环境变量 PM_SOURCE_MYSQL_*）",
    )
    parser.add_argument("--source-port", type=int, default=3306, help="源 MySQL 端口")
    parser.add_argument("--source-user", default="", help="源 MySQL 用户")
    parser.add_argument("--source-password", default="", help="源 MySQL 密码")
    parser.add_argument("--source-database", default="", help="源 MySQL 库名")
    parser.add_argument(
        "--source-charset",
        default="utf8mb4",
        help="源 MySQL charset（默认 utf8mb4）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖目标库中已有非空登记；否则仅覆盖占位空行或插入新行",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将执行的操作，不写目标库",
    )
    args = parser.parse_args()

    _load_source_mysql_from_dotenv_file()

    if (args.source_sqlite or "").strip() and (args.source_host or "").strip():
        print("错误：请只指定一种源库：--source-sqlite 或源 MySQL（参数或 PM_SOURCE_MYSQL_*）。")
        return 1

    # --- 源 URL ---
    if (args.source_sqlite or "").strip():
        sqlite_path = Path((args.source_sqlite or "").strip()).expanduser().resolve()
        if not sqlite_path.is_file():
            print(f"源 SQLite 不存在：{sqlite_path}")
            return 1
        source_url = f"sqlite:///{sqlite_path.as_posix()}"
        source_engine = create_engine(source_url, connect_args={"check_same_thread": False})
    else:
        env_mysql = _source_mysql_from_env()
        if env_mysql:
            h, port, u, pw, d, charset = env_mysql
            source_url = _mysql_url(h, port, u, pw, d, charset)
        elif (args.source_host or "").strip() and (args.source_user or "").strip() and (args.source_database or "").strip():
            source_url = _mysql_url(
                args.source_host,
                args.source_port,
                args.source_user,
                args.source_password or "",
                args.source_database,
                args.source_charset,
            )
        else:
            print(
                "请指定源库：\n"
                "  --source-sqlite PATH\n"
                "  或 --source-host / --source-user / --source-database（及可选密码）\n"
                "  或设置环境变量 PM_SOURCE_MYSQL_HOST、PM_SOURCE_MYSQL_USER、PM_SOURCE_MYSQL_DATABASE（及密码等）。"
            )
            return 1
        source_engine = create_engine(source_url, pool_pre_ping=True)

    # --- 目标 URL（与 API 相同）---
    target_url = settings.database_url
    target_engine = create_engine(
        target_url,
        connect_args={"check_same_thread": False} if not settings.uses_mysql else {},
        pool_pre_ping=bool(settings.uses_mysql),
    )

    print("source:", _redacted_mysql_url(source_url) if source_url.startswith("mysql") else source_url)
    print("target:", _redacted_mysql_url(target_url) if target_url.startswith("mysql") else target_url)

    if source_url == target_url:
        print("错误：源与目标数据库 URL 相同，无需同步。")
        return 1

    init_db()
    Base.metadata.create_all(bind=target_engine)

    payloads_from_source: dict[str, dict] = {}
    with Session(source_engine) as src_sess:
        try:
            src_sess.execute(text("SELECT 1"))
        except Exception as e:
            print("连接源库失败：", e)
            return 1
        for key in REGISTRY_KEYS:
            row = src_sess.get(RegistryEntry, key)
            if row is None:
                print(f"源库无 registry 行：{key}（跳过）")
                continue
            payloads_from_source[key] = dict(row.payload) if isinstance(row.payload, dict) else {}

    if not payloads_from_source:
        print("源库未找到任何 manpower/phase/risk 的 registry 行，退出。")
        return 1

    with Session(target_engine) as dst_sess:
        try:
            dst_sess.execute(text("SELECT 1"))
        except Exception as e:
            print("连接目标库失败：", e)
            return 1

        for key, payload in payloads_from_source.items():
            row = dst_sess.get(RegistryEntry, key)
            exists = row is not None
            has_real = exists and not _registry_core_array_empty(key, row.payload)
            if exists and not args.force and has_real:
                print(f"跳过 {key}：目标已有非空登记，请加 --force 覆盖。")
                continue
            if exists and not args.force and not has_real:
                print(f"将覆盖目标占位空记录：{key}")
            elif not exists:
                print(f"将插入：{key}")
            else:
                print(f"将覆盖（--force）：{key}")

            if args.dry_run:
                continue
            put_json(dst_sess, key, payload)

    if args.dry_run:
        print("Dry-run 结束，未写入目标库。")
    else:
        print("同步完成。可在目标环境执行 python scripts/check_db.py 验证。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
