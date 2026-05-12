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
from app.models_relational import (  # noqa: E402
    ManpowerAllocation,
    PhaseAssessment,
    Program,
    ProjectRisk,
    SubProgram,
    SubProject,
)
from app.registry_store import KEY_MANPOWER, KEY_PHASE, KEY_RISK  # noqa: E402


def _core_len_for_key(key: str, payload: object) -> int | None:
    """与 registry 空状态判定一致的核心列表长度（manpower/phase/risk）。"""
    if not isinstance(payload, dict):
        return None
    if key == KEY_MANPOWER:
        d = payload.get("data")
        return len(d) if isinstance(d, list) else None
    if key == KEY_PHASE:
        d = payload.get("phaseData")
        return len(d) if isinstance(d, list) else None
    if key == KEY_RISK:
        d = payload.get("riskRows")
        return len(d) if isinstance(d, list) else None
    return None


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
        registry_payloads: dict[str, dict] = {}
        for row in s.scalars(select(RegistryEntry).order_by(RegistryEntry.key)):
            registry_payloads[row.key] = dict(row.payload) if isinstance(row.payload, dict) else {}
        print("users rows:", uc)
        print("registry rows:", rc)
        for label, model in (
            ("programs rows", Program),
            ("sub_programs rows", SubProgram),
            ("sub_projects rows", SubProject),
            ("phase_assessments rows", PhaseAssessment),
            ("manpower_allocations rows", ManpowerAllocation),
            ("project_risks rows", ProjectRisk),
        ):
            try:
                n = s.scalar(select(func.count()).select_from(model)) or 0
            except Exception:
                n = "(no table: start app once for create_all, or apply migrations/001_relational_schema.sql)"
            print(f"{label}: {n}")
        print("registry keys:", keys if keys else "(empty)")
        for k in (KEY_MANPOWER, KEY_PHASE, KEY_RISK):
            if k in registry_payloads:
                n = _core_len_for_key(k, registry_payloads[k])
                field = "len(data)" if k == KEY_MANPOWER else "len(phaseData)" if k == KEY_PHASE else "len(riskRows)"
                print(f"  {k}: {field}={n if n is not None else '(missing or bad type)'}")
            else:
                print(f"  {k}: (no row)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
