"""人力行存：按 year+period 列表；按 sub_project_id+period 整批替换。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent_debug_log import agent_dbg
from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import (
    ManpowerAllocation,
    ManpowerCell,
    ManpowerColumn,
    ManpowerDepartmentGroup,
    SubProject,
)
from app.relational_api import assert_period_matches_year, assert_sub_project_year, parse_year
from app.schemas_relational import ManpowerAllocationOut, ManpowerReplaceBody

router = APIRouter(prefix="/manpower-allocations", tags=["manpower-allocations"])


def _year_has_manpower_matrix(db: Session, y: int) -> bool:
    n = db.scalar(
        select(func.count()).select_from(ManpowerDepartmentGroup).where(ManpowerDepartmentGroup.year == y)
    )
    return bool(n and n > 0)


def _synthesize_allocations_from_matrix(db: Session, y: int, p: str) -> list[ManpowerAllocationOut]:
    stmt = (
        select(ManpowerCell, ManpowerColumn.name, ManpowerDepartmentGroup.name)
        .join(ManpowerColumn, ManpowerCell.column_id == ManpowerColumn.id)
        .join(ManpowerDepartmentGroup, ManpowerColumn.group_id == ManpowerDepartmentGroup.id)
        .join(SubProject, ManpowerCell.sub_project_id == SubProject.id)
        .where(SubProject.year == y, ManpowerCell.period == p)
        .order_by(
            ManpowerCell.sub_project_id,
            ManpowerDepartmentGroup.sort_order,
            ManpowerDepartmentGroup.id,
            ManpowerColumn.sort_order,
            ManpowerColumn.id,
        )
    )
    out: list[ManpowerAllocationOut] = []
    for cell, role_name, dept_name in db.execute(stmt).all():
        out.append(
            ManpowerAllocationOut(
                id=cell.id,
                sub_project_id=cell.sub_project_id,
                period=cell.period,
                department=dept_name,
                role=role_name,
                allocation=cell.allocation,
            )
        )
    return out


@router.get("", response_model=list[ManpowerAllocationOut])
def list_manpower_allocations(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> list[ManpowerAllocationOut]:
    _ = _user
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    if _year_has_manpower_matrix(db, y):
        rows = _synthesize_allocations_from_matrix(db, y, p)
    else:
        stmt = (
            select(ManpowerAllocation)
            .join(SubProject, ManpowerAllocation.sub_project_id == SubProject.id)
            .where(SubProject.year == y, ManpowerAllocation.period == p)
            .order_by(ManpowerAllocation.sub_project_id, ManpowerAllocation.department, ManpowerAllocation.role)
        )
        rows = list(db.scalars(stmt).all())
    # region agent log
    agent_dbg(
        "H1",
        "manpower_allocations.py:list",
        "list_manpower_allocations",
        {"year": y, "period": p, "row_count": len(rows), "sub_project_ids": list({r.sub_project_id for r in rows})[:20]},
    )
    # endregion
    return rows


@router.put("", response_model=list[ManpowerAllocationOut])
def replace_manpower_for_period(
    _admin: AdminUser,
    body: ManpowerReplaceBody,
    year: int = Query(..., ge=2000, le=2100),
    sub_project_id: int = Query(..., ge=1),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> list[ManpowerAllocation]:
    _ = _admin
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    if _year_has_manpower_matrix(db, y):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="人力已切换为矩阵表存储，请使用 PUT /api/v2/manpower-matrix 批量写入单元格。",
        )
    assert_sub_project_year(db, sub_project_id, y)
    db.execute(
        delete(ManpowerAllocation).where(
            ManpowerAllocation.sub_project_id == sub_project_id,
            ManpowerAllocation.period == p,
        )
    )
    out: list[ManpowerAllocation] = []
    for r in body.rows:
        row = ManpowerAllocation(
            sub_project_id=sub_project_id,
            period=p,
            department=r.department.strip(),
            role=r.role.strip(),
            allocation=Decimal(r.allocation),
        )
        db.add(row)
        out.append(row)
    db.commit()
    for row in out:
        db.refresh(row)
    # region agent log
    agent_dbg(
        "H2",
        "manpower_allocations.py:put",
        "replace_manpower_for_period",
        {
            "year": y,
            "period": p,
            "sub_project_id": sub_project_id,
            "rows_written": len(out),
            "sum_alloc": float(sum(float(r.allocation) for r in out)) if out else 0.0,
        },
    )
    # endregion
    return out
