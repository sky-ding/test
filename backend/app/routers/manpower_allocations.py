"""人力行存：按 year+period 列表；按 sub_project_id+period 整批替换。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import ManpowerAllocation, SubProject
from app.relational_api import assert_period_matches_year, assert_sub_project_year, parse_year
from app.schemas_relational import ManpowerAllocationOut, ManpowerReplaceBody

router = APIRouter(prefix="/manpower-allocations", tags=["manpower-allocations"])


@router.get("", response_model=list[ManpowerAllocationOut])
def list_manpower_allocations(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> list[ManpowerAllocation]:
    _ = _user
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    stmt = (
        select(ManpowerAllocation)
        .join(SubProject, ManpowerAllocation.sub_project_id == SubProject.id)
        .where(SubProject.year == y, ManpowerAllocation.period == p)
        .order_by(ManpowerAllocation.sub_project_id, ManpowerAllocation.department, ManpowerAllocation.role)
    )
    return list(db.scalars(stmt).all())


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
    return out
