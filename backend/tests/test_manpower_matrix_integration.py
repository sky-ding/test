"""关系型登记主链路冒烟测试（内存 SQLite）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["PM_AUTH_DISABLED"] = "true"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    import app.models  # noqa: F401 — 注册 ORM
    from app.models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    import app.db as dbm

    monkeypatch.setattr(dbm, "engine", engine, raising=True)
    monkeypatch.setattr(dbm, "SessionLocal", test_session_local, raising=True)

    Base.metadata.create_all(bind=engine)

    from app.db import get_db
    from app.main import app

    def _override_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


def _create_sub_project(client) -> int:
    y = 2035
    r = client.post("/api/v1/programs", json={"year": y, "name": "ProgMatrixTest"})
    assert r.status_code == 201, r.text
    program_id = r.json()["id"]

    r2 = client.post(
        f"/api/v1/programs/{program_id}/sub-programs?year={y}",
        json={"name": "SetA"},
    )
    assert r2.status_code == 201, r2.text
    tree = r2.json()
    sub_program_id = tree["programs"][0]["sub_programs"][0]["id"]

    r3 = client.post(
        f"/api/v1/programs/sub-programs/{sub_program_id}/sub-projects?year={y}",
        json={"name": "Leaf1"},
    )
    assert r3.status_code == 201, r3.text
    tree3 = r3.json()
    return tree3["programs"][0]["sub_programs"][0]["sub_projects"][0]["id"]


def test_relational_project_phase_risk_user_and_manpower_matrix_flow(client) -> None:
    y = 2035
    sub_project_id = _create_sub_project(client)

    group = client.post(
        "/api/v1/manpower-department-groups",
        json={"year": y, "name": "技术部", "first_column_name": "前端", "sort_order": 1},
    )
    assert group.status_code == 201, group.text
    group_body = group.json()
    group_id = group_body["id"]
    column_id = group_body["columns"][0]["id"]

    col2 = client.post(
        f"/api/v1/manpower-department-groups/{group_id}/columns?year={y}",
        json={"name": "后端", "sort_order": 2},
    )
    assert col2.status_code == 201, col2.text

    patched_group = client.patch(
        f"/api/v1/manpower-department-groups/{group_id}?year={y}",
        json={"name": "研发部"},
    )
    assert patched_group.status_code == 200

    patched_col = client.patch(
        f"/api/v1/manpower-columns/{column_id}?year={y}",
        json={"name": "前端开发"},
    )
    assert patched_col.status_code == 200

    mx_empty = client.get(f"/api/v1/manpower-allocations?year={y}&period={y}-01")
    assert mx_empty.status_code == 200, mx_empty.text
    assert mx_empty.json()["dept_groups"][0]["name"] == "研发部"
    assert mx_empty.json()["dept_groups"][0]["columns"][0]["name"] == "前端开发"

    put = client.put(
        f"/api/v1/manpower-allocations?year={y}&period={y}-01",
        json={"cells": [{"sub_project_id": sub_project_id, "column_id": column_id, "allocation": "9.00"}]},
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert len(body["cells"]) == 1
    assert float(body["cells"][0]["allocation"]) == 9.0

    legacy_shape = client.put(
        f"/api/v1/manpower-allocations?year={y}&sub_project_id={sub_project_id}&period={y}-01",
        json={"rows": [{"department": "研发部", "role": "前端开发", "allocation": "1"}]},
    )
    assert legacy_shape.status_code == 422

    assert client.get(f"/api/v2/manpower-matrix?year={y}&period={y}-01").status_code == 404

    phase = client.put(
        f"/api/v1/phase-assessments?year={y}",
        json={
            "sub_project_id": sub_project_id,
            "period": f"{y}-01",
            "goal": "交付目标",
            "planMatch": "partially",
        },
    )
    assert phase.status_code == 200, phase.text
    assert phase.json()["on_track"] == "partially"

    risk = client.post(
        f"/api/v1/project-risks?year={y}",
        json={
            "sub_project_id": sub_project_id,
            "risk_category": "外部依赖风险",
            "risk_source": "供应商与流程",
            "issue": "存在跨团队依赖",
            "solution": "每日跟进",
            "level": "中高",
            "owner": "负责人甲",
            "status": "Open",
        },
    )
    assert risk.status_code == 201, risk.text
    assert risk.json()["risk_category"] == "外部依赖风险"

    users = client.get("/api/v1/users")
    assert users.status_code == 200, users.text
    assert len(users.json()) >= 1
