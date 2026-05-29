"""项目风险：按年或子项目查询；单条增删改。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import ProjectRisk, SubProject
from app.relational_api import assert_sub_project_year, parse_year
from app.schemas_relational import ProjectRiskCreate, ProjectRiskOut, ProjectRiskPatch

router = APIRouter(prefix="/project-risks", tags=["project-risks"])


@router.get("", response_model=list[ProjectRiskOut])
def list_project_risks(
    _user: CurrentUser,
    year: int | None = Query(default=None, ge=2000, le=2100),
    sub_project_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[ProjectRisk]:
    _ = _user
    if year is not None and sub_project_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provide only one of year or sub_project_id",
        )
    if year is None and sub_project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="year or sub_project_id is required",
        )
    if sub_project_id is not None:
        stmt = (
            select(ProjectRisk)
            .where(ProjectRisk.sub_project_id == sub_project_id)
            .order_by(ProjectRisk.id)
        )
        return list(db.scalars(stmt).all())
    assert year is not None
    y = parse_year(year)
    stmt = (
        select(ProjectRisk)
        .join(SubProject, ProjectRisk.sub_project_id == SubProject.id)
        .where(SubProject.year == y)
        .order_by(ProjectRisk.sub_project_id, ProjectRisk.id)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=ProjectRiskOut, status_code=status.HTTP_201_CREATED)
def create_project_risk(
    _admin: AdminUser,
    body: ProjectRiskCreate,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProjectRisk:
    _ = _admin
    y = parse_year(year)
    assert_sub_project_year(db, body.sub_project_id, y)
    row = ProjectRisk(
        sub_project_id=body.sub_project_id,
        risk_category=body.risk_category.strip(),
        risk_source=body.risk_source.strip(),
        description=(body.description or "").strip(),
        solution=(body.solution or "").strip() or None,
        level=(body.level or "中").strip(),
        assignee=(body.assignee or "").strip(),
        resolution_date=body.resolution_date,
        status=(body.status or "Open").strip(),
    )
    if row.status.lower() in ("close", "closed", "关闭"):
        row.closed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{risk_id}", response_model=ProjectRiskOut)
def patch_project_risk(
    _admin: AdminUser,
    risk_id: int,
    body: ProjectRiskPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProjectRisk:
    _ = _admin
    y = parse_year(year)
    row = db.get(ProjectRisk, risk_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    assert_sub_project_year(db, row.sub_project_id, y)
    if body.sub_project_id is not None:
        assert_sub_project_year(db, body.sub_project_id, y)
        row.sub_project_id = body.sub_project_id
    if body.risk_category is not None:
        row.risk_category = body.risk_category.strip()
    if body.risk_source is not None:
        row.risk_source = body.risk_source.strip()
    if body.description is not None:
        row.description = body.description.strip()
    if body.solution is not None:
        row.solution = body.solution.strip() or None
    if body.level is not None:
        row.level = body.level.strip()
    if body.assignee is not None:
        row.assignee = body.assignee.strip()
    if body.resolution_date is not None or body.closeTime is not None:
        row.resolution_date = body.resolution_date
    if body.status is not None:
        row.status = body.status.strip()
        if row.status.lower() in ("close", "closed", "关闭"):
            row.closed_at = datetime.now(timezone.utc)
        else:
            row.closed_at = None
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_risk(
    _admin: AdminUser,
    risk_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> None:
    _ = _admin
    y = parse_year(year)
    row = db.get(ProjectRisk, risk_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    assert_sub_project_year(db, row.sub_project_id, y)
    db.delete(row)
    db.commit()
