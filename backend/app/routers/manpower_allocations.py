"""人力矩阵：按 year+period 返回表头与单元格（只读；写入请走项目信息 API）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import (
    ManpowerCell,
    ManpowerColumn,
    ManpowerDepartmentGroup,
    SubProject,
)
from app.relational_api import assert_period_matches_year, parse_year
from app.schemas_relational import (
    ManpowerMatrixCellOut,
    ManpowerMatrixColumnOut,
    ManpowerMatrixGroupOut,
    ManpowerMatrixPutBody,
    ManpowerMatrixResponse,
)

router = APIRouter(prefix="/manpower-allocations", tags=["manpower-allocations"])


def build_manpower_matrix_response(db: Session, y: int, p: str) -> ManpowerMatrixResponse:
    groups = list(
        db.scalars(
            select(ManpowerDepartmentGroup)
            .where(ManpowerDepartmentGroup.year == y)
            .order_by(ManpowerDepartmentGroup.sort_order, ManpowerDepartmentGroup.id)
        ).all()
    )
    dept_groups: list[ManpowerMatrixGroupOut] = []
    for g in groups:
        cols = list(
            db.scalars(
                select(ManpowerColumn)
                .where(ManpowerColumn.group_id == g.id)
                .order_by(ManpowerColumn.sort_order, ManpowerColumn.id)
            ).all()
        )
        dept_groups.append(
            ManpowerMatrixGroupOut(
                id=g.id,
                name=g.name,
                sort_order=g.sort_order,
                columns=[
                    ManpowerMatrixColumnOut(id=c.id, name=c.name, sort_order=c.sort_order) for c in cols
                ],
            )
        )

    cells_q = (
        select(ManpowerCell)
        .join(SubProject, ManpowerCell.sub_project_id == SubProject.id)
        .where(SubProject.year == y, ManpowerCell.period == p)
        .order_by(ManpowerCell.sub_project_id, ManpowerCell.column_id)
    )
    cells = [
        ManpowerMatrixCellOut(
            sub_project_id=c.sub_project_id,
            period=c.period,
            column_id=c.column_id,
            allocation=c.allocation,
        )
        for c in db.scalars(cells_q).all()
    ]
    return ManpowerMatrixResponse(year=y, period=p, dept_groups=dept_groups, cells=cells)


@router.get("", response_model=ManpowerMatrixResponse)
def list_manpower_allocations(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> ManpowerMatrixResponse:
    _ = _user
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    return build_manpower_matrix_response(db, y, p)


@router.put("", response_model=ManpowerMatrixResponse)
def replace_manpower_for_period(
    _admin: AdminUser,
    body: ManpowerMatrixPutBody,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> ManpowerMatrixResponse:
    _ = _admin
    _ = body
    _ = year
    _ = period
    _ = db
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="部门人力登记为只读汇总，请在「项目信息」页维护成员投入（人月）",
    )
