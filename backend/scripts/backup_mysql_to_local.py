#!/usr/bin/env python3
"""
将指定 MySQL 库导出到本机目录（调用 mysqldump），可选 gzip 与按天数清理旧文件。

依赖：本机 PATH 中可找到 **mysqldump**（安装 MySQL Client / Server 后通常自带）。
在 backend 目录执行，默认读取 backend/.env 中的 PM_MYSQL_*（与主应用一致）。

用法：
  cd backend
  python scripts/backup_mysql_to_local.py
  python scripts/backup_mysql_to_local.py --out-dir D:/backup/ipd-pmo --keep-days 30
  python scripts/backup_mysql_to_local.py --dry-run
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_env_file_into_environ(path: Path) -> None:
    """在首次 import app.config 之前执行，将 PM_* 写入环境变量（用于 --env-file 指向专用备份凭据）。"""
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key.startswith("PM_"):
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        os.environ[key] = val


def load_mysql_config_from_environ() -> tuple[str, int, str, str, str]:
    """从环境变量读取 PM_MYSQL_*（须已先 load_env_file_into_environ）。"""
    host = (os.environ.get("PM_MYSQL_HOST") or "").strip()
    port_s = (os.environ.get("PM_MYSQL_PORT") or "3306").strip()
    try:
        port = int(port_s)
    except ValueError:
        port = 3306
    user = (os.environ.get("PM_MYSQL_USER") or "").strip()
    password = os.environ.get("PM_MYSQL_PASSWORD") or ""
    database = (os.environ.get("PM_MYSQL_DATABASE") or "").strip()
    return host, port, user, password, database


def _find_mysqldump() -> str | None:
    return shutil.which("mysqldump")


def _write_client_cnf(
    path: Path,
    host: str,
    port: int,
    user: str,
    password: str,
) -> None:
    # 避免密码出现在进程列表；mysqldump 支持 --defaults-extra-file
    lines = [
        "[client]",
        f"host={host}",
        f"port={port}",
        f"user={user}",
        f"password={password}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _cleanup_old_backups(out_dir: Path, keep_days: int, name_prefix: str) -> None:
    if keep_days <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    pat = re.compile(re.escape(name_prefix) + r"-backup-\d{8}-\d{6}\.sql(\.gz)?$")
    for p in out_dir.iterdir():
        if not p.is_file() or not pat.match(p.name):
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                p.unlink()
                print(f"已删除过期备份: {p.name}")
            except OSError as e:
                print(f"删除失败 {p}: {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="在读取配置前加载该文件中的 PM_*（可指向仅含 ipd-pmo 凭据的文件，不必覆盖本机 backend/.env）",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=BACKEND_ROOT / "data" / "mysql-backups",
        help="备份文件目录（默认 backend/data/mysql-backups）",
    )
    ap.add_argument(
        "--database",
        type=str,
        default="",
        help="库名；默认取 .env 中 PM_MYSQL_DATABASE",
    )
    ap.add_argument("--keep-days", type=int, default=14, help="保留最近 N 天备份，0 表示不清理")
    ap.add_argument("--no-gzip", action="store_true", help="不压缩，保留 .sql")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的命令，不写文件")
    args = ap.parse_args()

    dotenv = BACKEND_ROOT / ".env"
    if dotenv.is_file():
        load_env_file_into_environ(dotenv)
    if args.env_file is not None:
        ef = args.env_file.expanduser().resolve()
        if not ef.is_file():
            print(f"--env-file 不存在：{ef}", file=sys.stderr)
            return 1
        load_env_file_into_environ(ef)

    host, port, user, password, database = load_mysql_config_from_environ()
    if not (host and user and database):
        print(
            "缺少 PM_MYSQL_HOST / PM_MYSQL_USER / PM_MYSQL_DATABASE。"
            "请在 backend/.env 中配置，或使用 --env-file 指向含上述变量的文件。",
            file=sys.stderr,
        )
        return 1

    db = (args.database or database).strip()
    if not db:
        print("数据库名为空", file=sys.stderr)
        return 1

    mysqldump = _find_mysqldump()
    if not mysqldump and not args.dry_run:
        print(
            "未在 PATH 中找到 mysqldump。请安装 MySQL Client（或完整 Server），"
            "并把 bin 目录加入系统 PATH 后重试。",
            file=sys.stderr,
        )
        return 1

    out_dir = args.out_dir.expanduser().resolve()
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_prefix = db.replace("`", "")
    sql_name = f"{safe_prefix}-backup-{ts}.sql"
    sql_path = out_dir / sql_name
    gz_path = out_dir / (sql_name + ".gz")

    if args.dry_run:
        print("mysqldump:", mysqldump or "(PATH 中未找到，正式备份前请安装 MySQL 客户端)")
        print("参数:", "--single-transaction --skip-lock-tables --databases", db, "--result-file", sql_path)
        print("输出目录:", out_dir)
        return 0

    cnf_file: Path | None = None
    fd, cnf_path = tempfile.mkstemp(suffix="-pm-backup.cnf", text=True)
    cnf_file = Path(cnf_path)
    try:
        os.close(fd)
        _write_client_cnf(cnf_file, host, port, user, password)
        # Windows 上 mysqldump 对路径中的空格敏感，使用绝对路径
        real_cmd = [
            mysqldump,
            f"--defaults-extra-file={cnf_file.as_posix()}",
            "--single-transaction",
            "--skip-lock-tables",
            "--databases",
            db,
            "--result-file",
            str(sql_path.resolve()),
        ]
        r = subprocess.run(real_cmd, capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            print(r.stderr or r.stdout or "mysqldump 失败", file=sys.stderr)
            if sql_path.exists():
                try:
                    sql_path.unlink()
                except OSError:
                    pass
            return r.returncode or 1
    finally:
        if cnf_file is not None:
            try:
                cnf_file.unlink(missing_ok=True)
            except TypeError:
                if cnf_file.exists():
                    cnf_file.unlink()

    if not sql_path.is_file() or sql_path.stat().st_size == 0:
        print("备份文件未生成或为空", file=sys.stderr)
        return 1

    if not args.no_gzip:
        with open(sql_path, "rb") as f_in:
            with gzip.open(gz_path, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        sql_path.unlink()
        final_path = gz_path
    else:
        final_path = sql_path

    print(f"备份完成: {final_path}（约 {final_path.stat().st_size // 1024} KiB）")

    _cleanup_old_backups(out_dir, args.keep_days, safe_prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
