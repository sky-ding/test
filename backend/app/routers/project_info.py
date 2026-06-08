"""项目信息：按子项目聚合读取与事务保存。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.project_info_service import (
    build_project_info_response,
    default_period_for_year,
    save_project_info,
)
from app.relational_api import parse_year
from app.schemas_relational import ProjectInfoGetResponse, ProjectInfoPutBody

router = APIRouter(prefix="/project-info", tags=["project-info"])


@router.get("/{sub_project_id}", response_model=ProjectInfoGetResponse)
def get_project_info(
    _user: CurrentUser,
    sub_project_id: int,
    year: int = Query(..., ge=2000, le=2100),
    period: str | None = Query(default=None, min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> ProjectInfoGetResponse:
    _ = _user
    y = parse_year(year)
    p = period.strip() if period else default_period_for_year(y)
    return build_project_info_response(db, sub_project_id=sub_project_id, year=y, period=p)


@router.put("/{sub_project_id}", response_model=ProjectInfoGetResponse)
def put_project_info(
    _admin: AdminUser,
    sub_project_id: int,
    body: ProjectInfoPutBody,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProjectInfoGetResponse:
    _ = _admin
    y = parse_year(year)
    try:
        result = save_project_info(db, sub_project_id=sub_project_id, year=y, body=body)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to save project info",
        ) from exc
