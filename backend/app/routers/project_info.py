"""项目信息：按子项目聚合读取与事务保存。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.goal_service import build_goal_summary, build_phase_monthly_data
from app.project_info_service import (
    build_project_info_response,
    default_period_for_year,
    save_project_info,
)
from app.relational_api import parse_year, assert_sub_project_year
from app.schemas_relational import (
    GoalSummaryOut,
    PhaseMonthlyDataOut,
    ProjectInfoGetResponse,
    ProjectInfoPutBody,
)

router = APIRouter(prefix="/project-info", tags=["project-info"])


# 批量目标摘要路由必须放在 /{sub_project_id}/... 之前，避免 FastAPI 把 "goal-summary-batch" 解析为 sub_project_id
@router.get("/goal-summary-batch", response_model=list[GoalSummaryOut])
def get_goal_summary_batch(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    sub_project_ids: str = Query(..., description="逗号分隔的子项目 ID"),
    db: Session = Depends(get_db),
) -> list[GoalSummaryOut]:
    """批量获取多个子项目的目标摘要，一次请求返回所有结果。"""
    _ = _user
    y = parse_year(year)
    ids = [int(x) for x in sub_project_ids.split(",") if x.strip().isdigit()]
    if not ids:
        return []
    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="最多支持 100 个子项目")

    all_summaries: list[dict] = []
    for sp_id in ids:
        try:
            assert_sub_project_year(db, sp_id, y)
            summaries = build_goal_summary(db, sp_id, y)
            all_summaries.extend(summaries)
        except HTTPException:
            pass  # 跳过无效的子项目
    return [GoalSummaryOut(**s) for s in all_summaries]


# phase-monthly-data 路由必须放在 /{sub_project_id}/... 之前
@router.get("/phase-monthly-data", response_model=list[PhaseMonthlyDataOut])
def get_phase_monthly_data(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    sub_project_ids: str = Query(..., description="逗号分隔的子项目 ID"),
    db: Session = Depends(get_db),
) -> list[PhaseMonthlyDataOut]:
    """获取多个子项目的月度自动填充数据。"""
    _ = _user
    y = parse_year(year)
    ids = [int(x) for x in sub_project_ids.split(",") if x.strip().isdigit()]
    if not ids or len(ids) > 100:
        return []

    results = []
    for sp_id in ids:
        try:
            data = build_phase_monthly_data(db, sp_id, y, month)
            results.append(PhaseMonthlyDataOut(**data))
        except Exception:
            pass
    return results





@router.get("/{sub_project_id}/goal-summary", response_model=list[GoalSummaryOut])
def get_goal_summary(
    _user: CurrentUser,
    sub_project_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> list[GoalSummaryOut]:
    """为项目阶段状态页提供目标进展摘要(只读)。"""
    _ = _user
    y = parse_year(year)
    assert_sub_project_year(db, sub_project_id, y)
    summaries = build_goal_summary(db, sub_project_id, y)
    return [GoalSummaryOut(**s) for s in summaries]


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
