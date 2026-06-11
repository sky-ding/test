"""跨项目个人人力汇总与饱和度。"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import CurrentUser
from app.manpower_saturation import PERSON_MONTHLY_CAPACITY, saturation_level
from app.models_relational import SubProgram, SubProject, TeamMember, TeamMemberAllocation
from app.relational_api import assert_period_matches_year, parse_year
from app.schemas_relational import PersonSummaryProjectOut, PersonSummaryResponse, PersonSummaryRowOut

router = APIRouter(prefix="/manpower", tags=["manpower"])


@router.get("/person-summary", response_model=PersonSummaryResponse)
def person_summary(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> PersonSummaryResponse:
    _ = _user
    y = parse_year(year)
    p = assert_period_matches_year(period, y)

    rows = db.scalars(
        select(TeamMemberAllocation)
        .join(TeamMember, TeamMemberAllocation.team_member_id == TeamMember.id)
        .join(SubProject, SubProject.id == TeamMember.sub_project_id)
        .where(SubProject.year == y, TeamMemberAllocation.period == p)
        .options(
            joinedload(TeamMemberAllocation.team_member)
            .joinedload(TeamMember.sub_project)
            .joinedload(SubProject.sub_program)
            .joinedload(SubProgram.program)
        )
    ).all()

    by_name: dict[str, list[PersonSummaryProjectOut]] = defaultdict(list)
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for alloc_row in rows:
        member = alloc_row.team_member
        if member is None:
            continue
        amount = Decimal(alloc_row.allocation).quantize(Decimal("0.01"))
        if amount == Decimal("0.00"):
            continue
        sp = member.sub_project
        prog_name = ""
        if sp and sp.sub_program and sp.sub_program.program:
            prog_name = sp.sub_program.program.name
        name = member.name.strip()
        totals[name] += amount
        by_name[name].append(
            PersonSummaryProjectOut(
                sub_project_id=sp.id if sp else member.sub_project_id,
                sub_project_name=sp.name if sp else "",
                program_name=prog_name,
                allocation=amount,
            )
        )

    persons: list[PersonSummaryRowOut] = []
    for name in sorted(totals.keys()):
        total = totals[name].quantize(Decimal("0.01"))
        rate = (total / PERSON_MONTHLY_CAPACITY).quantize(Decimal("0.0001"))
        persons.append(
            PersonSummaryRowOut(
                name=name,
                total_allocation=total,
                saturation_rate=rate,
                saturation_level=saturation_level(rate),
                projects=sorted(by_name[name], key=lambda x: x.sub_project_name),
            )
        )

    return PersonSummaryResponse(
        year=y,
        period=p,
        capacity_per_person=PERSON_MONTHLY_CAPACITY,
        persons=persons,
    )
