"""项目信息聚合读写集成测试。"""

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
    import app.models_relational  # noqa: F401
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


def _create_tree(client, y: int = 2040) -> dict[str, int]:
    r = client.post("/api/v1/programs", json={"year": y, "name": "ProgInfo"})
    assert r.status_code == 201, r.text
    program_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/programs/{program_id}/sub-programs?year={y}",
        json={"name": "SetInfo"},
    )
    assert r2.status_code == 201, r2.text
    sub_program_id = r2.json()["id"]
    r3 = client.post(
        f"/api/v1/programs/sub-programs/{sub_program_id}/sub-projects?year={y}",
        json={"name": "LeafInfo"},
    )
    assert r3.status_code == 201, r3.text
    return {
        "program_id": program_id,
        "sub_program_id": sub_program_id,
        "sub_project_id": r3.json()["id"],
    }


def _manpower_group(client, y: int) -> int:
    g = client.post(
        "/api/v1/manpower-department-groups",
        json={"year": y, "name": "交付组", "first_column_name": "平台开发"},
    )
    assert g.status_code == 201, g.text
    return g.json()["columns"][0]["id"]


def _put_body(sub_project_id: int, column_id: int, y: int, period: str) -> dict:
    return {
        "sub_project": {
            "name": "LeafInfo-更新",
            "status": "active",
            "description": "描述文本",
            "key_goal": "RTO < 30min",
            "automation_rate_goal": "90%",
            "planned_start_date": f"{y}-03-01",
            "planned_end_date": f"{y}-07-07",
            "actual_start_date": f"{y}-03-03",
            "actual_end_date": None,
        },
        "milestones": [
            {
                "id": None,
                "name": "需求评审",
                "planned_date": f"{y}-03-15",
                "status": "completed",
                "description": "完成评审",
                "sort_order": 0,
            }
        ],
        "deleted_milestone_ids": [],
        "tasks": [
            {
                "id": None,
                "name": "需求调研",
                "phase": "需求与设计",
                "assignee": "张三",
                "start_date": f"{y}-03-01",
                "end_date": f"{y}-03-20",
                "progress": 100,
                "sort_order": 0,
            }
        ],
        "deleted_task_ids": [],
        "team_members": [
            {
                "id": None,
                "name": "李四",
                "team_column_id": column_id,
                "role": "项目负责人",
                "participation": "核心成员",
                "remark": "负责人",
                "sort_order": 0,
                "monthly_allocation": "0.25",
            }
        ],
        "deleted_team_member_ids": [],
        "risks": [
            {
                "id": None,
                "risk_category": "进度",
                "risk_source": "资源",
                "description": "资源紧张",
                "solution": "提前协调",
                "level": "中",
                "assignee": "王五",
                "resolution_date": None,
                "status": "Open",
            }
        ],
        "deleted_risk_ids": [],
        "manpower": {
            "period": period,
        },
    }


def test_get_empty_project_info(client) -> None:
    y = 2040
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    period = f"{y}-06"
    r = client.get(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}&period={period}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sub_project"]["name"] == "LeafInfo"
    assert body["milestones"] == []
    assert body["tasks"] == []
    assert body["team_members"] == []
    assert body["risks"] == []
    assert body["manpower"]["dept_groups"][0]["columns"][0]["id"] == col_id
    assert body["breadcrumb"]["program_name"] == "ProgInfo"


def test_put_and_get_project_info(client) -> None:
    y = 2041
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    period = f"{y}-06"
    put = client.put(
        f"/api/v1/project-info/{ids['sub_project_id']}?year={y}",
        json=_put_body(ids["sub_project_id"], col_id, y, period),
    )
    assert put.status_code == 200, put.text
    data = put.json()
    assert data["sub_project"]["name"] == "LeafInfo-更新"
    assert len(data["milestones"]) == 1
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["progress"] == 100
    assert len(data["team_members"]) == 1
    assert data["team_members"][0]["team_column_name"] == "平台开发"
    assert float(data["team_members"][0]["monthly_allocation"]) == 0.25
    assert float(data["project_monthly_total"]) == 0.25
    assert len(data["risks"]) == 1
    assert data["risks"][0]["status"] == "Open"
    assert "created_at" in data["risks"][0]
    assert float(data["manpower"]["cells"][0]["allocation"]) == 0.25

    milestone_id = data["milestones"][0]["id"]
    get2 = client.get(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}&period={period}")
    assert get2.status_code == 200
    assert get2.json()["milestones"][0]["id"] == milestone_id


def test_member_allocation_rollups_to_manpower_cells(client) -> None:
    y = 2045
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    period = f"{y}-06"
    body = _put_body(ids["sub_project_id"], col_id, y, period)
    body["team_members"] = [
        {
            "id": None,
            "name": "张三",
            "team_column_id": col_id,
            "role": "开发",
            "participation": "核心成员",
            "remark": None,
            "sort_order": 0,
            "monthly_allocation": "0.30",
        },
        {
            "id": None,
            "name": "李四",
            "team_column_id": col_id,
            "role": "测试",
            "participation": "核心成员",
            "remark": None,
            "sort_order": 1,
            "monthly_allocation": "0.20",
        },
    ]
    put = client.put(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}", json=body)
    assert put.status_code == 200, put.text
    assert float(put.json()["manpower"]["cells"][0]["allocation"]) == 0.5
    assert float(put.json()["project_monthly_total"]) == 0.5


def test_manpower_put_is_read_only(client) -> None:
    y = 2046
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    resp = client.put(
        f"/api/v1/manpower-allocations?year={y}&period={y}-01",
        json={
            "cells": [
                {
                    "sub_project_id": ids["sub_project_id"],
                    "column_id": col_id,
                    "allocation": "1.00",
                }
            ]
        },
    )
    assert resp.status_code == 403


def test_put_invalid_dates_rolls_back(client) -> None:
    y = 2042
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    period = f"{y}-06"
    body = _put_body(ids["sub_project_id"], col_id, y, period)
    body["sub_project"]["planned_end_date"] = f"{y}-01-01"
    put = client.put(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}", json=body)
    assert put.status_code == 422

    get_r = client.get(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}&period={period}")
    assert get_r.json()["sub_project"]["name"] == "LeafInfo"
    assert get_r.json()["milestones"] == []


def test_put_deletes_milestones(client) -> None:
    y = 2043
    ids = _create_tree(client, y=y)
    col_id = _manpower_group(client, y)
    period = f"{y}-06"
    body = _put_body(ids["sub_project_id"], col_id, y, period)
    saved = client.put(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}", json=body)
    mid = saved.json()["milestones"][0]["id"]

    body2 = _put_body(ids["sub_project_id"], col_id, y, period)
    body2["milestones"] = []
    body2["deleted_milestone_ids"] = [mid]
    body2["tasks"] = saved.json()["tasks"]
    body2["team_members"] = [
        {
            "id": saved.json()["team_members"][0]["id"],
            "name": "李四",
            "team_column_id": col_id,
            "role": "项目负责人",
            "participation": "核心成员",
            "remark": None,
            "sort_order": 0,
            "monthly_allocation": "0.25",
        }
    ]
    body2["risks"] = [
        {
            "id": saved.json()["risks"][0]["id"],
            "risk_category": "进度",
            "risk_source": "资源",
            "description": "资源紧张",
            "solution": None,
            "level": "中",
            "assignee": "王五",
            "resolution_date": None,
            "status": "Close",
        }
    ]
    upd = client.put(f"/api/v1/project-info/{ids['sub_project_id']}?year={y}", json=body2)
    assert upd.status_code == 200, upd.text
    assert upd.json()["milestones"] == []
    assert upd.json()["risks"][0]["status"] == "Close"


def test_get_sub_project_detail(client) -> None:
    y = 2044
    ids = _create_tree(client, y=y)
    r = client.get(f"/api/v1/programs/sub-projects/{ids['sub_project_id']}?year={y}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ids["sub_project_id"]
