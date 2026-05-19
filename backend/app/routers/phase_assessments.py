"""阶段评估：按 year + period 列表查询；按 sub_project_id + period upsert。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import PhaseAssessment, SubProject
from app.relational_api import assert_period_matches_year, assert_sub_project_year, parse_year
from app.schemas_relational import PhaseAssessmentOut, PhaseAssessmentUpsert

router = APIRouter(prefix="/phase-assessments", tags=["phase-assessments"])


@router.get("", response_model=list[PhaseAssessmentOut])
def list_phase_assessments(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> list[PhaseAssessment]:
    _ = _user
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    stmt = (
        select(PhaseAssessment)
        .join(SubProject, PhaseAssessment.sub_project_id == SubProject.id)
        .where(SubProject.year == y, PhaseAssessment.period == p)
        .order_by(PhaseAssessment.sub_project_id)
    )
    return list(db.scalars(stmt).all())


@router.put("", response_model=PhaseAssessmentOut)
def upsert_phase_assessment(
    _admin: AdminUser,
    body: PhaseAssessmentUpsert,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> PhaseAssessment:
    _ = _admin
    y = parse_year(year)
    p = assert_period_matches_year(body.period, y)
    assert_sub_project_year(db, body.sub_project_id, y)
    row = db.scalar(
        select(PhaseAssessment).where(
            PhaseAssessment.sub_project_id == body.sub_project_id,
            PhaseAssessment.period == p,
        )
    )
    if row is None:
        row = PhaseAssessment(sub_project_id=body.sub_project_id, period=p)
        db.add(row)
    row.delivery_target = body.delivery_target
    row.on_track = body.on_track
    row.actual_delivery = body.actual_delivery
    row.execution_analysis = body.execution_analysis
    row.problem_analysis = body.problem_analysis
    row.improvement_plan = body.improvement_plan
    db.commit()
    db.refresh(row)
    return row
