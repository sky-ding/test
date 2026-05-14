#!/usr/bin/env python3
"""
将 manpower_allocations（department + role 行存）迁入矩阵三表：
manpower_department_groups / manpower_columns / manpower_cells。

幂等：已存在的 group（year+name）、column（group_id+name）、cell（sub_project_id+period+column_id）
会复用并更新 allocation。

在 backend 目录、已 create_all 或执行 migrations/002 后：

  python scripts/migrate_manpower_allocations_to_matrix.py
  python scripts/migrate_manpower_allocations_to_matrix.py --verify

--verify：仅对比各 period 全库 allocation 总和（旧表 vs 新表），不写库。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import MetaData, Table, func, inspect, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine  # noqa: E402
from app.models_relational import (  # noqa: E402
    ManpowerCell,
    ManpowerColumn,
    ManpowerDepartmentGroup,
    SubProject,
)

_legacy_table: Table | None = None


def _legacy_allocations_table() -> Table | None:
    global _legacy_table
    if _legacy_table is not None:
        return _legacy_table
    if "manpower_allocations" not in inspect(engine).get_table_names():
        return None
    metadata = MetaData()
    _legacy_table = Table("manpower_allocations", metadata, autoload_with=engine)
    return _legacy_table


def _next_group_sort(session: Session, year: int) -> int:
    m = session.scalar(
        select(func.max(ManpowerDepartmentGroup.sort_order)).where(ManpowerDepartmentGroup.year == year)
    )
    return int(m or 0) + 1


def _next_column_sort(session: Session, group_id: int) -> int:
    m = session.scalar(select(func.max(ManpowerColumn.sort_order)).where(ManpowerColumn.group_id == group_id))
    return int(m or 0) + 1


def _ensure_group(session: Session, year: int, dept: str) -> ManpowerDepartmentGroup:
    dept = dept.strip()
    g = session.scalar(
        select(ManpowerDepartmentGroup).where(
            ManpowerDepartmentGroup.year == year,
            ManpowerDepartmentGroup.name == dept,
        )
    )
    if g is None:
        g = ManpowerDepartmentGroup(year=year, name=dept, sort_order=_next_group_sort(session, year))
        session.add(g)
        session.flush()
    return g


def _ensure_column(session: Session, year: int, group: ManpowerDepartmentGroup, role: str) -> ManpowerColumn:
    role = role.strip()
    c = session.scalar(
        select(ManpowerColumn).where(ManpowerColumn.group_id == group.id, ManpowerColumn.name == role)
    )
    if c is None:
        c = ManpowerColumn(
            group_id=group.id,
            year=year,
            name=role,
            sort_order=_next_column_sort(session, group.id),
        )
        session.add(c)
        session.flush()
    return c


def migrate(session: Session) -> tuple[int, int, int]:
    """Returns (new_groups, new_columns, cells_written)."""
    ma = _legacy_allocations_table()
    if ma is None:
        print("legacy manpower_allocations table not found; nothing to migrate")
        return 0, 0, 0

    new_groups = new_columns = 0
    cells_written = 0

    stmt = (
        select(
            ma.c.id,
            ma.c.sub_project_id,
            ma.c.period,
            ma.c.department,
            ma.c.role,
            ma.c.allocation,
            SubProject.year,
        )
        .join(SubProject, ma.c.sub_project_id == SubProject.id)
        .order_by(ma.c.id)
    )
    rows = session.execute(stmt).all()

    seen_groups: set[tuple[int, str]] = set()
    seen_cols: set[tuple[int, str, str]] = set()

    for row in rows:
        year = row.year
        year = int(year)
        dept = (row.department or "").strip()
        role = (row.role or "").strip()
        if not dept or not role:
            continue

        gkey = (year, dept)
        if gkey not in seen_groups:
            before = session.scalar(
                select(ManpowerDepartmentGroup.id).where(
                    ManpowerDepartmentGroup.year == year,
                    ManpowerDepartmentGroup.name == dept,
                )
            )
            g = _ensure_group(session, year, dept)
            if before is None:
                new_groups += 1
            seen_groups.add(gkey)
        else:
            g = session.scalar(
                select(ManpowerDepartmentGroup).where(
                    ManpowerDepartmentGroup.year == year,
                    ManpowerDepartmentGroup.name == dept,
                )
            )
            if g is None:
                continue

        ckey = (year, dept, role)
        if ckey not in seen_cols:
            before_c = session.scalar(
                select(ManpowerColumn.id).where(ManpowerColumn.group_id == g.id, ManpowerColumn.name == role)
            )
            col = _ensure_column(session, year, g, role)
            if before_c is None:
                new_columns += 1
            seen_cols.add(ckey)
        else:
            col = session.scalar(
                select(ManpowerColumn).where(ManpowerColumn.group_id == g.id, ManpowerColumn.name == role)
            )
            if col is None:
                continue

        cell = session.scalar(
            select(ManpowerCell).where(
                ManpowerCell.sub_project_id == row.sub_project_id,
                ManpowerCell.period == row.period,
                ManpowerCell.column_id == col.id,
            )
        )
        if cell is None:
            cell = ManpowerCell(
                sub_project_id=row.sub_project_id,
                period=row.period,
                column_id=col.id,
                allocation=row.allocation,
            )
            session.add(cell)
        else:
            cell.allocation = row.allocation
        cells_written += 1

    session.commit()
    return new_groups, new_columns, cells_written


def verify(session: Session) -> bool:
    ma = _legacy_allocations_table()
    if ma is None:
        leg_map: dict[str, float] = {}
    else:
        legacy = session.execute(select(ma.c.period, func.sum(ma.c.allocation)).group_by(ma.c.period)).all()
        leg_map = {str(p): float(s or 0) for p, s in legacy}

    cell_sum = session.execute(
        select(ManpowerCell.period, func.sum(ManpowerCell.allocation)).group_by(ManpowerCell.period)
    ).all()
    cell_map = {str(p): float(s or 0) for p, s in cell_sum}

    ok = True
    for p in sorted(set(leg_map) | set(cell_map), key=lambda x: x):
        a, b = leg_map.get(p, 0.0), cell_map.get(p, 0.0)
        if abs(a - b) > 0.02:
            print(f"MISMATCH period={p!r} legacy_sum={a:.2f} cells_sum={b:.2f}")
            ok = False
    if ok:
        print("verify: OK (per-period allocation sums match)")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="只校验总和，不写库")
    args = parser.parse_args()

    with SessionLocal() as session:
        if args.verify:
            return 0 if verify(session) else 1
        g, c, n = migrate(session)
        print(f"new_groups: {g}, new_columns: {c}, cells_upserted: {n}")
        verify(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
