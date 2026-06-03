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
    import app.models_relational  # noqa: F401 — register relational ORM tables
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


def _create_project_tree(
    client,
    y: int = 2035,
    program_name: str = "ProgMatrixTest",
    sub_program_name: str = "SetA",
    sub_project_name: str = "Leaf1",
) -> dict[str, int]:
    r = client.post("/api/v1/programs", json={"year": y, "name": program_name})
    assert r.status_code == 201, r.text
    program_id = r.json()["id"]

    r2 = client.post(
        f"/api/v1/programs/{program_id}/sub-programs?year={y}",
        json={"name": sub_program_name},
    )
    assert r2.status_code == 201, r2.text
    tree = r2.json()
    sub_program_id = tree["programs"][0]["sub_programs"][0]["id"]

    r3 = client.post(
        f"/api/v1/programs/sub-programs/{sub_program_id}/sub-projects?year={y}",
        json={"name": sub_project_name},
    )
    assert r3.status_code == 201, r3.text
    tree3 = r3.json()
    sub_project_id = tree3["programs"][0]["sub_programs"][0]["sub_projects"][0]["id"]
    return {
        "program_id": program_id,
        "sub_program_id": sub_program_id,
        "sub_project_id": sub_project_id,
    }


def _create_sub_project(client) -> int:
    return _create_project_tree(client)["sub_project_id"]


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


def test_project_tree_crud_persists_and_business_routes_use_created_sub_project(client) -> None:
    y = 2036
    ids = _create_project_tree(
        client,
        y=y,
        program_name="稳定性项目集",
        sub_program_name="容灾子项目集",
        sub_project_name="商城容灾子项目",
    )

    tree = client.get(f"/api/v1/programs/tree?year={y}")
    assert tree.status_code == 200, tree.text
    body = tree.json()
    assert body["programs"][0]["name"] == "稳定性项目集"
    assert body["programs"][0]["sub_programs"][0]["name"] == "容灾子项目集"
    assert body["programs"][0]["sub_programs"][0]["sub_projects"][0]["name"] == "商城容灾子项目"

    patched_program = client.patch(
        f"/api/v1/programs/{ids['program_id']}?year={y}",
        json={"name": "稳定性项目集-更新"},
    )
    assert patched_program.status_code == 200, patched_program.text
    patched_sub_program = client.patch(
        f"/api/v1/programs/sub-programs/{ids['sub_program_id']}?year={y}",
        json={"name": "容灾子项目集-更新"},
    )
    assert patched_sub_program.status_code == 200, patched_sub_program.text
    patched_sub_project = client.patch(
        f"/api/v1/programs/sub-projects/{ids['sub_project_id']}?year={y}",
        json={"name": "商城容灾子项目-更新"},
    )
    assert patched_sub_project.status_code == 200, patched_sub_project.text

    tree_after_patch = client.get(f"/api/v1/programs/tree?year={y}")
    assert tree_after_patch.status_code == 200, tree_after_patch.text
    patched_tree = tree_after_patch.json()["programs"][0]
    assert patched_tree["name"] == "稳定性项目集-更新"
    assert patched_tree["sub_programs"][0]["name"] == "容灾子项目集-更新"
    assert patched_tree["sub_programs"][0]["sub_projects"][0]["name"] == "商城容灾子项目-更新"

    group = client.post(
        "/api/v1/manpower-department-groups",
        json={"year": y, "name": "研发交付", "first_column_name": "后端"},
    )
    assert group.status_code == 201, group.text
    column_id = group.json()["columns"][0]["id"]
    manpower = client.put(
        f"/api/v1/manpower-allocations?year={y}&period={y}-05",
        json={
            "cells": [
                {
                    "sub_project_id": ids["sub_project_id"],
                    "column_id": column_id,
                    "allocation": "3.50",
                }
            ]
        },
    )
    assert manpower.status_code == 200, manpower.text
    assert manpower.json()["cells"][0]["sub_project_id"] == ids["sub_project_id"]

    phase = client.put(
        f"/api/v1/phase-assessments?year={y}",
        json={
            "sub_project_id": ids["sub_project_id"],
            "period": f"{y}-05",
            "goal": "完成容灾演练",
            "deliver": "已完成",
        },
    )
    assert phase.status_code == 200, phase.text
    assert phase.json()["delivery_target"] == "完成容灾演练"

    risk = client.post(
        f"/api/v1/project-risks?year={y}",
        json={
            "sub_project_id": ids["sub_project_id"],
            "risk_category": "进度",
            "risk_source": "资源",
            "issue": "资源窗口冲突",
            "owner": "负责人乙",
            "status": "open",
        },
    )
    assert risk.status_code == 201, risk.text
    assert risk.json()["sub_project_id"] == ids["sub_project_id"]

    deleted = client.delete(f"/api/v1/programs/{ids['program_id']}?year={y}")
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/programs/tree?year={y}").json()["programs"] == []


def test_business_routes_reject_missing_or_wrong_year_sub_project(client) -> None:
    y = 2037
    ids = _create_project_tree(client, y=y, program_name="YearGuard")
    wrong_year = y + 1

    missing_phase = client.put(
        f"/api/v1/phase-assessments?year={y}",
        json={"sub_project_id": 999999, "period": f"{y}-01", "goal": "x"},
    )
    assert missing_phase.status_code == 404

    wrong_year_phase = client.put(
        f"/api/v1/phase-assessments?year={wrong_year}",
        json={"sub_project_id": ids["sub_project_id"], "period": f"{wrong_year}-01", "goal": "x"},
    )
    assert wrong_year_phase.status_code == 400

    group = client.post(
        "/api/v1/manpower-department-groups",
        json={"year": y, "name": "测试组", "first_column_name": "测试列"},
    )
    assert group.status_code == 201, group.text
    column_id = group.json()["columns"][0]["id"]
    missing_manpower = client.put(
        f"/api/v1/manpower-allocations?year={y}&period={y}-01",
        json={"cells": [{"sub_project_id": 999999, "column_id": column_id, "allocation": "1"}]},
    )
    assert missing_manpower.status_code == 404

    missing_risk = client.post(
        f"/api/v1/project-risks?year={y}",
        json={
            "sub_project_id": 999999,
            "risk_category": "进度",
            "risk_source": "资源",
            "issue": "缺少子项目",
            "owner": "负责人丙",
        },
    )
    assert missing_risk.status_code == 404


def test_patch_project_risk_updates_sub_project_id(client) -> None:
    y = 2038
    ids = _create_project_tree(
        client,
        y=y,
        program_name="RiskMoveProg",
        sub_program_name="RiskMoveSet",
        sub_project_name="个性化提效",
    )
    tree2 = client.post(
        f"/api/v1/programs/sub-programs/{ids['sub_program_id']}/sub-projects?year={y}",
        json={"name": "GPU精细化管理"},
    )
    assert tree2.status_code == 201, tree2.text
    other_sub_project_id = (
        tree2.json()["programs"][0]["sub_programs"][0]["sub_projects"][-1]["id"]
    )

    created = client.post(
        f"/api/v1/project-risks?year={y}",
        json={
            "sub_project_id": ids["sub_project_id"],
            "risk_category": "进度",
            "risk_source": "资源",
            "issue": "基架团队优先投入 AI 项目",
            "owner": "李维进",
            "status": "close",
        },
    )
    assert created.status_code == 201, created.text
    risk_id = created.json()["id"]
    assert created.json()["sub_project_id"] == ids["sub_project_id"]

    patched = client.patch(
        f"/api/v1/project-risks/{risk_id}?year={y}",
        json={"sub_project_id": other_sub_project_id},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["sub_project_id"] == other_sub_project_id

    listed = client.get(f"/api/v1/project-risks?year={y}")
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json() if r["id"] == risk_id)
    assert row["sub_project_id"] == other_sub_project_id
