#!/usr/bin/env python3
"""
验证当前配置能否连接数据库，并打印 users 与关系型业务表行数（团队部署冒烟用）。

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
from app.models import User  # noqa: E402
from app.models_relational import (  # noqa: E402
    ManpowerCell,
    ManpowerColumn,
    ManpowerDepartmentGroup,
    PhaseAssessment,
    Program,
    ProjectRisk,
    SubProgram,
    SubProject,
)


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
        print("users rows:", uc)
        for label, model in (
            ("programs rows", Program),
            ("sub_programs rows", SubProgram),
            ("sub_projects rows", SubProject),
            ("phase_assessments rows", PhaseAssessment),
            ("manpower_department_groups rows", ManpowerDepartmentGroup),
            ("manpower_columns rows", ManpowerColumn),
            ("manpower_cells rows", ManpowerCell),
            ("project_risks rows", ProjectRisk),
        ):
            try:
                n = s.scalar(select(func.count()).select_from(model)) or 0
            except Exception:
                n = "(no table: start app once for create_all, or apply migrations/001_relational_schema.sql)"
            print(f"{label}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
