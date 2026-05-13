"""人力矩阵 v2 与 v1 读合成 / 写停用的冒烟集成测试（内存 SQLite）。"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
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


def test_v2_put_get_v1_list_synthesis_and_v1_put_gone(client) -> None:
    from app.db import SessionLocal
    from app.models_relational import ManpowerCell, ManpowerColumn, ManpowerDepartmentGroup

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
    sub_project_id = tree3["programs"][0]["sub_programs"][0]["sub_projects"][0]["id"]

    db = SessionLocal()
    try:
        g = ManpowerDepartmentGroup(year=y, name="技术部", sort_order=1)
        db.add(g)
        db.flush()
        col = ManpowerColumn(group_id=g.id, year=y, name="前端", sort_order=1)
        db.add(col)
        db.flush()
        db.add(
            ManpowerCell(
                sub_project_id=sub_project_id,
                period=f"{y}-01",
                column_id=col.id,
                allocation=Decimal("3.50"),
            )
        )
        db.commit()
        column_id = col.id
    finally:
        db.close()

    mx = client.get(f"/api/v2/manpower-matrix?year={y}&period={y}-01")
    assert mx.status_code == 200, mx.text
    mj = mx.json()
    assert len(mj["dept_groups"]) == 1
    assert mj["dept_groups"][0]["name"] == "技术部"
    assert len(mj["cells"]) == 1

    v1 = client.get(f"/api/v1/manpower-allocations?year={y}&period={y}-01")
    assert v1.status_code == 200, v1.text
    rows = v1.json()
    assert len(rows) == 1
    assert rows[0]["department"] == "技术部"
    assert rows[0]["role"] == "前端"
    assert rows[0]["sub_project_id"] == sub_project_id
    assert float(rows[0]["allocation"]) == 3.5

    gone = client.put(
        f"/api/v1/manpower-allocations?year={y}&sub_project_id={sub_project_id}&period={y}-01",
        json={"rows": [{"department": "技术部", "role": "前端", "allocation": "1"}]},
    )
    assert gone.status_code == 410

    put = client.put(
        f"/api/v2/manpower-matrix?year={y}&period={y}-01",
        json={
            "cells": [{"sub_project_id": sub_project_id, "column_id": column_id, "allocation": "9.00"}]
        },
    )
    assert put.status_code == 200, put.text
    v1b = client.get(f"/api/v1/manpower-allocations?year={y}&period={y}-01")
    assert v1b.status_code == 200
    rows_b = v1b.json()
    assert len(rows_b) == 1
    assert float(rows_b[0]["allocation"]) == 9.0
