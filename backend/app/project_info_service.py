"""项目信息聚合读写的业务逻辑（事务内同步子表）。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models_relational import (
    ManpowerColumn,
    Milestone,
    ProjectRisk,
    SubProgram,
    SubProject,
    Task,
    TeamMember,
)
from app.relational_api import assert_period_matches_year, parse_year
from app.routers.manpower_allocations import build_manpower_matrix_response
from app.schemas_relational import (
    ManpowerMatrixCellOut,
    MilestoneOut,
    ProjectInfoBreadcrumb,
    ProjectInfoGetResponse,
    ProjectInfoManpowerOut,
    ProjectInfoPutBody,
    ProjectRiskDetailOut,
    SubProjectDetailOut,
    TaskOut,
    TeamMemberOut,
)


def default_period_for_year(year: int) -> str:
    now = datetime.now()
    if year == now.year:
        return f"{year:04d}-{now.month:02d}"
    if year < now.year:
        return f"{year:04d}-12"
    return f"{year:04d}-01"


def _load_sub_project(db: Session, sub_project_id: int, year: int) -> SubProject:
    sp = (
        db.scalar(
            select(SubProject)
            .where(SubProject.id == sub_project_id, SubProject.year == year)
            .options(
                joinedload(SubProject.sub_program).joinedload(SubProgram.program),
            )
        )
    )
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_project not found")
    return sp


def _breadcrumb(sp: SubProject) -> ProjectInfoBreadcrumb:
    spg = sp.sub_program
    prog = spg.program
    return ProjectInfoBreadcrumb(
        program_id=prog.id,
        program_name=prog.name,
        sub_program_id=spg.id,
        sub_program_name=spg.name,
        sub_project_id=sp.id,
        sub_project_name=sp.name,
    )


def _team_members_out(db: Session, sub_project_id: int) -> list[TeamMemberOut]:
    rows = list(
        db.scalars(
            select(TeamMember)
            .where(TeamMember.sub_project_id == sub_project_id)
            .order_by(TeamMember.sort_order, TeamMember.id)
        ).all()
    )
    col_names: dict[int, str] = {}
    if rows:
        col_ids = {r.team_column_id for r in rows}
        cols = db.scalars(select(ManpowerColumn).where(ManpowerColumn.id.in_(col_ids))).all()
        col_names = {c.id: c.name for c in cols}
    return [
        TeamMemberOut(
            id=r.id,
            name=r.name,
            team_column_id=r.team_column_id,
            team_column_name=col_names.get(r.team_column_id, ""),
            role=r.role,
            participation=r.participation,
            remark=r.remark,
            sort_order=r.sort_order,
        )
        for r in rows
    ]


def build_project_info_response(
    db: Session,
    *,
    sub_project_id: int,
    year: int,
    period: str,
) -> ProjectInfoGetResponse:
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    sp = _load_sub_project(db, sub_project_id, y)

    milestones = list(
        db.scalars(
            select(Milestone)
            .where(Milestone.sub_project_id == sub_project_id)
            .order_by(Milestone.sort_order, Milestone.id)
        ).all()
    )
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.sub_project_id == sub_project_id)
            .order_by(Task.sort_order, Task.id)
        ).all()
    )
    risks = list(
        db.scalars(
            select(ProjectRisk)
            .where(ProjectRisk.sub_project_id == sub_project_id)
            .order_by(ProjectRisk.id)
        ).all()
    )

    matrix = build_manpower_matrix_response(db, y, p)
    cells = [c for c in matrix.cells if c.sub_project_id == sub_project_id]

    return ProjectInfoGetResponse(
        year=y,
        period=p,
        sub_project=SubProjectDetailOut.model_validate(sp),
        milestones=[MilestoneOut.model_validate(m) for m in milestones],
        tasks=[TaskOut.model_validate(t) for t in tasks],
        team_members=_team_members_out(db, sub_project_id),
        risks=[ProjectRiskDetailOut.model_validate(r) for r in risks],
        manpower=ProjectInfoManpowerOut(
            period=p,
            dept_groups=matrix.dept_groups,
            cells=cells,
        ),
        breadcrumb=_breadcrumb(sp),
    )


def _assert_owned_ids(db: Session, model, sub_project_id: int, ids: list[int], label: str) -> None:
    if not ids:
        return
    found = set(
        db.scalars(
            select(model.id).where(model.id.in_(ids), model.sub_project_id == sub_project_id)
        ).all()
    )
    missing = set(ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} id(s) not found for sub_project: {sorted(missing)}",
        )


def _validate_column_year(db: Session, column_id: int, year: int) -> ManpowerColumn:
    col = db.get(ManpowerColumn, column_id)
    if col is None or int(col.year) != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid column_id {column_id} for year {year}",
        )
    return col


def _apply_risk_status(row: ProjectRisk, status_value: str) -> None:
    row.status = status_value
    if row.status == "Close":
        if row.closed_at is None:
            row.closed_at = datetime.now(timezone.utc)
    else:
        row.closed_at = None


def save_project_info(
    db: Session,
    *,
    sub_project_id: int,
    year: int,
    body: ProjectInfoPutBody,
) -> ProjectInfoGetResponse:
    y = parse_year(year)
    sp = _load_sub_project(db, sub_project_id, y)
    p = assert_period_matches_year(body.manpower.period, y)

    name = body.sub_project.name.strip()
    clash = db.scalar(
        select(SubProject.id).where(
            SubProject.sub_program_id == sp.sub_program_id,
            SubProject.year == y,
            SubProject.name == name,
            SubProject.id != sub_project_id,
        )
    )
    if clash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_project name exists")

    sp.name = name
    sp.status = body.sub_project.status
    sp.description = (body.sub_project.description or "").strip() or None
    sp.key_goal = (body.sub_project.key_goal or "").strip() or None
    sp.automation_rate_goal = (body.sub_project.automation_rate_goal or "").strip() or None
    sp.planned_start_date = body.sub_project.planned_start_date
    sp.planned_end_date = body.sub_project.planned_end_date
    sp.actual_start_date = body.sub_project.actual_start_date
    sp.actual_end_date = body.sub_project.actual_end_date

    _assert_owned_ids(db, Milestone, sub_project_id, body.deleted_milestone_ids, "milestone")
    for mid in body.deleted_milestone_ids:
        db.delete(db.get(Milestone, mid))

    for item in body.milestones:
        if item.id is None:
            db.add(
                Milestone(
                    sub_project_id=sub_project_id,
                    name=item.name.strip(),
                    planned_date=item.planned_date,
                    status=item.status,
                    description=(item.description or "").strip() or None,
                    sort_order=item.sort_order,
                )
            )
        else:
            row = db.get(Milestone, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid milestone id")
            row.name = item.name.strip()
            row.planned_date = item.planned_date
            row.status = item.status
            row.description = (item.description or "").strip() or None
            row.sort_order = item.sort_order

    _assert_owned_ids(db, Task, sub_project_id, body.deleted_task_ids, "task")
    for tid in body.deleted_task_ids:
        db.delete(db.get(Task, tid))

    for item in body.tasks:
        if item.id is None:
            db.add(
                Task(
                    sub_project_id=sub_project_id,
                    name=item.name.strip(),
                    phase=item.phase,
                    assignee=(item.assignee or "").strip() or None,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    progress=item.progress,
                    sort_order=item.sort_order,
                )
            )
        else:
            row = db.get(Task, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid task id")
            row.name = item.name.strip()
            row.phase = item.phase
            row.assignee = (item.assignee or "").strip() or None
            row.start_date = item.start_date
            row.end_date = item.end_date
            row.progress = item.progress
            row.sort_order = item.sort_order

    _assert_owned_ids(db, TeamMember, sub_project_id, body.deleted_team_member_ids, "team_member")
    for tid in body.deleted_team_member_ids:
        db.delete(db.get(TeamMember, tid))

    for item in body.team_members:
        _validate_column_year(db, item.team_column_id, y)
        if item.id is None:
            db.add(
                TeamMember(
                    sub_project_id=sub_project_id,
                    name=item.name.strip(),
                    team_column_id=item.team_column_id,
                    role=item.role.strip(),
                    participation=item.participation,
                    remark=(item.remark or "").strip() or None,
                    sort_order=item.sort_order,
                )
            )
        else:
            row = db.get(TeamMember, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid team_member id")
            row.name = item.name.strip()
            row.team_column_id = item.team_column_id
            row.role = item.role.strip()
            row.participation = item.participation
            row.remark = (item.remark or "").strip() or None
            row.sort_order = item.sort_order

    _assert_owned_ids(db, ProjectRisk, sub_project_id, body.deleted_risk_ids, "risk")
    for rid in body.deleted_risk_ids:
        db.delete(db.get(ProjectRisk, rid))

    for item in body.risks:
        if item.id is None:
            row = ProjectRisk(
                sub_project_id=sub_project_id,
                risk_category=item.risk_category.strip(),
                risk_source=item.risk_source.strip(),
                description=item.description.strip(),
                solution=(item.solution or "").strip() or None,
                level=item.level.strip(),
                assignee=item.assignee.strip(),
                resolution_date=item.resolution_date,
                status=item.status,
            )
            _apply_risk_status(row, item.status)
            db.add(row)
        else:
            row = db.get(ProjectRisk, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid risk id")
            row.risk_category = item.risk_category.strip()
            row.risk_source = item.risk_source.strip()
            row.description = item.description.strip()
            row.solution = (item.solution or "").strip() or None
            row.level = item.level.strip()
            row.assignee = item.assignee.strip()
            row.resolution_date = item.resolution_date
            _apply_risk_status(row, item.status)

    from app.models_relational import ManpowerCell
    from decimal import Decimal

    for cell in body.manpower.cells:
        _validate_column_year(db, cell.column_id, y)
        alloc = Decimal(cell.allocation).quantize(Decimal("0.01"))
        row = db.scalar(
            select(ManpowerCell).where(
                ManpowerCell.sub_project_id == sub_project_id,
                ManpowerCell.period == p,
                ManpowerCell.column_id == cell.column_id,
            )
        )
        if row is None:
            db.add(
                ManpowerCell(
                    sub_project_id=sub_project_id,
                    period=p,
                    column_id=cell.column_id,
                    allocation=alloc,
                )
            )
        else:
            row.allocation = alloc

    db.flush()
    return build_project_info_response(db, sub_project_id=sub_project_id, year=y, period=p)
