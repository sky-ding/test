"""部门项目人力矩阵：项目树为行，部门分组/列为表头，月度单元格为事实表。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import ManpowerCell, ManpowerColumn, ManpowerDepartmentGroup, SubProject
from app.relational_api import assert_period_matches_year, assert_sub_project_year, parse_year
from app.schemas_relational import (
    ManpowerAllocationOut,
    ManpowerColumnOut,
    ManpowerDepartmentGroupIn,
    ManpowerDepartmentGroupOut,
    ManpowerMatrixResponse,
    ManpowerReplaceBody,
)

router = APIRouter(prefix="/manpower-allocations", tags=["manpower-allocations"])

DEFAULT_DEPT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("技术部", ("前端", "后端")),
    ("市场部", ("销售", "策划")),
)


def _ordered_groups(db: Session, year: int) -> list[ManpowerDepartmentGroup]:
    groups = list(
        db.scalars(
            select(ManpowerDepartmentGroup)
            .where(ManpowerDepartmentGroup.year == year)
            .options(selectinload(ManpowerDepartmentGroup.department_columns))
            .order_by(ManpowerDepartmentGroup.sort_order, ManpowerDepartmentGroup.id)
        )
        .unique()
        .all()
    )
    for group in groups:
        group.department_columns.sort(key=lambda col: (col.sort_order, col.id))
    return groups


def _ensure_default_groups(db: Session, year: int) -> list[ManpowerDepartmentGroup]:
    groups = _ordered_groups(db, year)
    if groups:
        return groups
    for gi, (group_name, column_names) in enumerate(DEFAULT_DEPT_GROUPS):
        group = ManpowerDepartmentGroup(year=year, name=group_name, sort_order=gi)
        db.add(group)
        db.flush()
        for ci, column_name in enumerate(column_names):
            db.add(ManpowerColumn(group_id=group.id, year=year, name=column_name, sort_order=ci))
    db.commit()
    return _ordered_groups(db, year)


def _group_out(group: ManpowerDepartmentGroup) -> ManpowerDepartmentGroupOut:
    return ManpowerDepartmentGroupOut(
        id=group.id,
        name=group.name,
        sort_order=group.sort_order,
        columns=[
            ManpowerColumnOut(id=column.id, name=column.name, sort_order=column.sort_order)
            for column in sorted(group.department_columns, key=lambda c: (c.sort_order, c.id))
        ],
    )


def _matrix_response(db: Session, year: int, period: str) -> ManpowerMatrixResponse:
    groups = _ensure_default_groups(db, year)
    stmt = (
        select(ManpowerCell, ManpowerColumn, ManpowerDepartmentGroup)
        .join(SubProject, ManpowerCell.sub_project_id == SubProject.id)
        .join(ManpowerColumn, ManpowerCell.column_id == ManpowerColumn.id)
        .join(ManpowerDepartmentGroup, ManpowerColumn.group_id == ManpowerDepartmentGroup.id)
        .where(SubProject.year == year, ManpowerCell.period == period, ManpowerDepartmentGroup.year == year)
        .order_by(
            ManpowerCell.sub_project_id,
            ManpowerDepartmentGroup.sort_order,
            ManpowerColumn.sort_order,
            ManpowerCell.id,
        )
    )
    rows = [
        ManpowerAllocationOut(
            id=cell.id,
            sub_project_id=cell.sub_project_id,
            period=cell.period,
            column_id=column.id,
            department=group.name,
            role=column.name,
            allocation=cell.allocation,
        )
        for cell, column, group in db.execute(stmt).all()
    ]
    return ManpowerMatrixResponse(
        year=year,
        period=period,
        dept_groups=[_group_out(group) for group in groups],
        rows=rows,
    )


def _column_specs(group_in: ManpowerDepartmentGroupIn) -> list[tuple[int | None, str]]:
    if group_in.columns is not None:
        specs = [(column.id, column.name.strip()) for column in group_in.columns if column.name.strip()]
        _assert_unique_column_names(group_in.name, [name for _, name in specs])
        return specs
    ids = group_in.column_ids or []
    specs: list[tuple[int | None, str]] = []
    for idx, name in enumerate(group_in.depts):
        clean_name = str(name).strip()
        if not clean_name:
            continue
        column_id = ids[idx] if idx < len(ids) else None
        specs.append((column_id, clean_name))
    _assert_unique_column_names(group_in.name, [name for _, name in specs])
    return specs


def _assert_unique_column_names(group_name: str, column_names: list[str]) -> None:
    seen: set[str] = set()
    for name in column_names:
        if name in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"duplicate manpower column in {group_name}: {name}",
            )
        seen.add(name)


def _sync_department_groups(
    db: Session,
    year: int,
    group_inputs: list[ManpowerDepartmentGroupIn] | None,
) -> list[ManpowerDepartmentGroup]:
    if not group_inputs:
        return _ensure_default_groups(db, year)

    existing_groups = _ordered_groups(db, year)
    groups_by_id = {group.id: group for group in existing_groups}
    groups_by_name = {group.name: group for group in existing_groups}
    kept_group_ids: set[int] = set()

    for gi, group_in in enumerate(group_inputs):
        group_name = group_in.name.strip()
        if not group_name:
            continue
        group = groups_by_id.get(group_in.id or 0) if group_in.id is not None else None
        if group is None:
            group = groups_by_name.get(group_name)
        if group is None:
            group = ManpowerDepartmentGroup(year=year, name=group_name, sort_order=gi)
            db.add(group)
            db.flush()
        group.name = group_name
        group.sort_order = gi
        kept_group_ids.add(group.id)

        existing_columns = list(group.department_columns)
        columns_by_id = {column.id: column for column in existing_columns}
        columns_by_name = {column.name: column for column in existing_columns}
        kept_column_ids: set[int] = set()
        for ci, (column_id, column_name) in enumerate(_column_specs(group_in)):
            column = columns_by_id.get(column_id or 0) if column_id is not None else None
            if column is None:
                column = columns_by_name.get(column_name)
            if column is None:
                column = ManpowerColumn(group_id=group.id, year=year, name=column_name, sort_order=ci)
                db.add(column)
                db.flush()
            column.group_id = group.id
            column.year = year
            column.name = column_name
            column.sort_order = ci
            kept_column_ids.add(column.id)

        for column in existing_columns:
            if column.id not in kept_column_ids:
                db.delete(column)

    for group in existing_groups:
        if group.id not in kept_group_ids:
            db.delete(group)

    db.flush()
    return _ordered_groups(db, year)


def _column_lookup(groups: list[ManpowerDepartmentGroup]) -> tuple[dict[int, ManpowerColumn], dict[tuple[str, str], ManpowerColumn]]:
    by_id: dict[int, ManpowerColumn] = {}
    by_names: dict[tuple[str, str], ManpowerColumn] = {}
    for group in groups:
        for column in group.department_columns:
            by_id[column.id] = column
            by_names[(group.name.strip(), column.name.strip())] = column
    return by_id, by_names


def _resolve_column(
    row_column_id: int | None,
    department: str | None,
    role: str | None,
    by_id: dict[int, ManpowerColumn],
    by_names: dict[tuple[str, str], ManpowerColumn],
) -> ManpowerColumn:
    if row_column_id is not None and row_column_id in by_id:
        return by_id[row_column_id]
    key = ((department or "").strip(), (role or "").strip())
    column = by_names.get(key)
    if column is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown manpower column: {key[0]} / {key[1]}",
        )
    return column


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
    return _matrix_response(db, y, p)


@router.put("", response_model=ManpowerMatrixResponse)
def replace_manpower_for_period(
    _admin: AdminUser,
    body: ManpowerReplaceBody,
    year: int = Query(..., ge=2000, le=2100),
    sub_project_id: int | None = Query(default=None, ge=1),
    period: str = Query(..., min_length=7, max_length=7),
    db: Session = Depends(get_db),
) -> ManpowerMatrixResponse:
    _ = _admin
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    groups = _sync_department_groups(db, y, body.dept_groups)
    by_id, by_names = _column_lookup(groups)

    if sub_project_id is not None:
        assert_sub_project_year(db, sub_project_id, y)
        target_project_ids = [sub_project_id]
    else:
        target_project_ids = list(db.scalars(select(SubProject.id).where(SubProject.year == y)).all())
        row_project_ids = {row.sub_project_id for row in body.rows if row.sub_project_id is not None}
        unknown_ids = sorted(row_project_ids.difference(target_project_ids))
        if unknown_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"sub_project_id not in requested year: {unknown_ids[0]}",
            )

    if target_project_ids:
        db.execute(
            delete(ManpowerCell).where(
                ManpowerCell.sub_project_id.in_(target_project_ids),
                ManpowerCell.period == p,
            )
        )

    for r in body.rows:
        row_sub_project_id = sub_project_id if sub_project_id is not None else r.sub_project_id
        if row_sub_project_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="rows[].sub_project_id is required for matrix replace",
            )
        column = _resolve_column(r.column_id, r.department, r.role, by_id, by_names)
        db.add(
            ManpowerCell(
                sub_project_id=row_sub_project_id,
                period=p,
                column_id=column.id,
                allocation=Decimal(r.allocation),
            )
        )
    db.commit()
    return _matrix_response(db, y, p)
