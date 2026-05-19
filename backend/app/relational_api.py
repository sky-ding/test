"""按年项目树与业务行的通用校验（供 v1 路由复用）。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models_relational import Program, SubProgram, SubProject

_YEAR_MIN = 2000
_YEAR_MAX = 2100
_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


def parse_year(year: int) -> int:
    if year < _YEAR_MIN or year > _YEAR_MAX:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"year must be between {_YEAR_MIN} and {_YEAR_MAX}",
        )
    return year


def parse_period(period: str) -> str:
    m = _PERIOD_RE.match(period.strip())
    if not m:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be YYYY-MM",
        )
    y, mo = int(m.group(1)), int(m.group(2))
    if mo < 1 or mo > 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid month in period",
        )
    return f"{y:04d}-{mo:02d}"


def period_year(period: str) -> int:
    return int(parse_period(period)[:4])


def require_sub_project(db: Session, sub_project_id: int) -> "SubProject":
    from app.models_relational import SubProject

    sp = db.get(SubProject, sub_project_id)
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_project not found")
    return sp


def assert_sub_project_year(db: Session, sub_project_id: int, year: int) -> None:
    sp = require_sub_project(db, sub_project_id)
    if sp.year != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sub_project year does not match requested year",
        )


def assert_period_matches_year(period: str, year: int) -> str:
    p = parse_period(period)
    if period_year(p) != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period year must match query year",
        )
    return p


def get_program_for_year(db: Session, program_id: int, year: int) -> "Program":
    from app.models_relational import Program

    prog = db.get(Program, program_id)
    if prog is None or prog.year != year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="program not found")
    return prog


def get_sub_program_for_year(db: Session, sub_program_id: int, year: int) -> "SubProgram":
    from app.models_relational import SubProgram

    spg = db.get(SubProgram, sub_program_id)
    if spg is None or spg.year != year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_program not found")
    return spg
