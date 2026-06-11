"""个人人力饱和度（人月，容量 1.0/月）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models_relational import SubProject, TeamMember, TeamMemberAllocation

PERSON_MONTHLY_CAPACITY = Decimal("1.00")


def saturation_level(rate: Decimal) -> str:
    if rate > Decimal("1"):
        return "over"
    if rate >= Decimal("0.8"):
        return "normal"
    return "low"


def person_totals_by_name(db: Session, *, year: int, period: str) -> dict[str, Decimal]:
    rows = db.execute(
        select(TeamMember.name, func.sum(TeamMemberAllocation.allocation))
        .join(TeamMemberAllocation, TeamMemberAllocation.team_member_id == TeamMember.id)
        .join(SubProject, SubProject.id == TeamMember.sub_project_id)
        .where(SubProject.year == year, TeamMemberAllocation.period == period)
        .group_by(TeamMember.name)
    ).all()
    result: dict[str, Decimal] = {}
    for name, total in rows:
        key = str(name).strip()
        if not key:
            continue
        val = total if total is not None else Decimal("0")
        result[key] = Decimal(val).quantize(Decimal("0.01"))
    return result


def person_saturation_fields(
    db: Session, *, year: int, period: str, name: str
) -> tuple[Decimal, Decimal, str]:
    totals = person_totals_by_name(db, year=year, period=period)
    total = totals.get(name.strip(), Decimal("0.00"))
    rate = (total / PERSON_MONTHLY_CAPACITY).quantize(Decimal("0.0001"))
    return total, rate, saturation_level(rate)
