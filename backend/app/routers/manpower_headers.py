"""人力矩阵表头：一级部门分组与二级列维护。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import ManpowerColumn, ManpowerDepartmentGroup
from app.relational_api import parse_year
from app.schemas_relational import (
    ManpowerColumnCreate,
    ManpowerColumnPatch,
    ManpowerMatrixColumnOut,
    ManpowerDepartmentGroupCreate,
    ManpowerDepartmentGroupPatch,
    ManpowerMatrixGroupOut,
)

groups_router = APIRouter(prefix="/manpower-department-groups", tags=["manpower-headers"])
columns_router = APIRouter(prefix="/manpower-columns", tags=["manpower-headers"])


def _group_or_404(db: Session, group_id: int, year: int) -> ManpowerDepartmentGroup:
    group = db.get(ManpowerDepartmentGroup, group_id)
    if group is None or int(group.year) != year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="department group not found")
    return group


def _column_or_404(db: Session, column_id: int, year: int) -> ManpowerColumn:
    col = db.get(ManpowerColumn, column_id)
    if col is None or int(col.year) != year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="manpower column not found")
    return col


def _group_to_out(db: Session, group: ManpowerDepartmentGroup) -> ManpowerMatrixGroupOut:
    cols = list(
        db.scalars(
            select(ManpowerColumn)
            .where(ManpowerColumn.group_id == group.id)
            .order_by(ManpowerColumn.sort_order, ManpowerColumn.id)
        ).all()
    )
    return ManpowerMatrixGroupOut(
        id=group.id,
        name=group.name,
        sort_order=group.sort_order,
        columns=[ManpowerMatrixColumnOut(id=c.id, name=c.name, sort_order=c.sort_order) for c in cols],
    )


@groups_router.get("", response_model=list[ManpowerMatrixGroupOut])
def list_manpower_department_groups(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> list[ManpowerMatrixGroupOut]:
    _ = _user
    y = parse_year(year)
    groups = list(
        db.scalars(
            select(ManpowerDepartmentGroup)
            .where(ManpowerDepartmentGroup.year == y)
            .order_by(ManpowerDepartmentGroup.sort_order, ManpowerDepartmentGroup.id)
        ).all()
    )
    return [_group_to_out(db, g) for g in groups]


@groups_router.post("", response_model=ManpowerMatrixGroupOut, status_code=status.HTTP_201_CREATED)
def create_manpower_department_group(
    _admin: AdminUser,
    body: ManpowerDepartmentGroupCreate,
    db: Session = Depends(get_db),
) -> ManpowerMatrixGroupOut:
    _ = _admin
    y = parse_year(body.year)
    name = body.name.strip()
    exists = db.scalar(
        select(ManpowerDepartmentGroup.id).where(
            ManpowerDepartmentGroup.year == y,
            ManpowerDepartmentGroup.name == name,
        )
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="department group exists for this year")
    group = ManpowerDepartmentGroup(year=y, name=name, sort_order=body.sort_order)
    db.add(group)
    db.flush()
    first_col = (body.first_column_name or "").strip()
    if first_col:
        db.add(ManpowerColumn(group_id=group.id, year=y, name=first_col, sort_order=0))
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@groups_router.patch("/{group_id}", response_model=ManpowerMatrixGroupOut)
def patch_manpower_department_group(
    _admin: AdminUser,
    group_id: int,
    body: ManpowerDepartmentGroupPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ManpowerMatrixGroupOut:
    _ = _admin
    y = parse_year(year)
    group = _group_or_404(db, group_id, y)
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(
            select(ManpowerDepartmentGroup.id).where(
                ManpowerDepartmentGroup.year == y,
                ManpowerDepartmentGroup.name == name,
                ManpowerDepartmentGroup.id != group_id,
            )
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="department group exists for this year")
        group.name = name
    if body.sort_order is not None:
        group.sort_order = body.sort_order
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manpower_department_group(
    _admin: AdminUser,
    group_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> None:
    _ = _admin
    y = parse_year(year)
    group = _group_or_404(db, group_id, y)
    db.delete(group)
    db.commit()


@groups_router.post("/{group_id}/columns", response_model=ManpowerMatrixColumnOut, status_code=status.HTTP_201_CREATED)
def create_manpower_column(
    _admin: AdminUser,
    group_id: int,
    body: ManpowerColumnCreate,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ManpowerMatrixColumnOut:
    _ = _admin
    y = parse_year(year)
    group = _group_or_404(db, group_id, y)
    name = body.name.strip()
    exists = db.scalar(select(ManpowerColumn.id).where(ManpowerColumn.group_id == group.id, ManpowerColumn.name == name))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="column exists in this group")
    col = ManpowerColumn(group_id=group.id, year=y, name=name, sort_order=body.sort_order)
    db.add(col)
    db.commit()
    db.refresh(col)
    return ManpowerMatrixColumnOut(id=col.id, name=col.name, sort_order=col.sort_order)


@columns_router.patch("/{column_id}", response_model=ManpowerMatrixColumnOut)
def patch_manpower_column(
    _admin: AdminUser,
    column_id: int,
    body: ManpowerColumnPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ManpowerMatrixColumnOut:
    _ = _admin
    y = parse_year(year)
    col = _column_or_404(db, column_id, y)
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(
            select(ManpowerColumn.id).where(
                ManpowerColumn.group_id == col.group_id,
                ManpowerColumn.name == name,
                ManpowerColumn.id != column_id,
            )
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="column exists in this group")
        col.name = name
    if body.sort_order is not None:
        col.sort_order = body.sort_order
    db.commit()
    db.refresh(col)
    return ManpowerMatrixColumnOut(id=col.id, name=col.name, sort_order=col.sort_order)


@columns_router.delete("/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manpower_column(
    _admin: AdminUser,
    column_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> None:
    _ = _admin
    y = parse_year(year)
    col = _column_or_404(db, column_id, y)
    db.delete(col)
    db.commit()
