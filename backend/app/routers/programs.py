"""按年项目树：列表、嵌套树、管理员维护 programs / sub_programs / sub_projects。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.models_relational import Program, SubProgram, SubProject
from app.relational_api import get_program_for_year, get_sub_program_for_year, parse_year
from app.schemas_relational import (
    ProgramCreate,
    ProgramListItem,
    ProgramPatch,
    ProgramTreeResponse,
    SubProgramCreate,
    SubProgramPatch,
    SubProjectCreate,
    SubProjectPatch,
)

router = APIRouter(prefix="/programs", tags=["programs"])


def _sort_tree(programs: list[Program]) -> None:
    programs.sort(key=lambda p: (p.sort_order, p.id))
    for p in programs:
        p.sub_programs.sort(key=lambda sp: (sp.sort_order, sp.id))
        for sp in p.sub_programs:
            sp.sub_projects.sort(key=lambda sj: (sj.sort_order, sj.id))


def _build_program_tree(db: Session, y: int) -> ProgramTreeResponse:
    stmt = (
        select(Program)
        .where(Program.year == y)
        .options(
            selectinload(Program.sub_programs).selectinload(SubProgram.sub_projects),
        )
        .order_by(Program.sort_order, Program.id)
    )
    programs = list(db.scalars(stmt).unique().all())
    _sort_tree(programs)
    return ProgramTreeResponse(year=y, programs=programs)


@router.get("/tree", response_model=ProgramTreeResponse)
def get_program_tree(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _user
    y = parse_year(year)
    return _build_program_tree(db, y)


@router.get("", response_model=list[ProgramListItem])
def list_programs(
    _user: CurrentUser,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> list[Program]:
    _ = _user
    y = parse_year(year)
    stmt = select(Program).where(Program.year == y).order_by(Program.sort_order, Program.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ProgramListItem, status_code=status.HTTP_201_CREATED)
def create_program(
    _admin: AdminUser,
    body: ProgramCreate,
    db: Session = Depends(get_db),
) -> Program:
    _ = _admin
    y = parse_year(body.year)
    exists = db.scalar(select(Program.id).where(Program.year == y, Program.name == body.name.strip()))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="program name exists for this year")
    p = Program(year=y, name=body.name.strip(), sort_order=body.sort_order)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/{program_id}", response_model=ProgramListItem)
def patch_program(
    _admin: AdminUser,
    program_id: int,
    body: ProgramPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> Program:
    _ = _admin
    y = parse_year(year)
    p = get_program_for_year(db, program_id, y)
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(
            select(Program.id).where(Program.year == y, Program.name == name, Program.id != program_id)
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="program name exists for this year")
        p.name = name
    if body.sort_order is not None:
        p.sort_order = body.sort_order
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(
    _admin: AdminUser,
    program_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> None:
    _ = _admin
    y = parse_year(year)
    p = get_program_for_year(db, program_id, y)
    db.delete(p)
    db.commit()


@router.post("/{program_id}/sub-programs", response_model=ProgramTreeResponse, status_code=status.HTTP_201_CREATED)
def create_sub_program(
    _admin: AdminUser,
    program_id: int,
    body: SubProgramCreate,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    prog = get_program_for_year(db, program_id, y)
    exists = db.scalar(
        select(SubProgram.id).where(
            SubProgram.program_id == program_id,
            SubProgram.year == y,
            SubProgram.name == body.name.strip(),
        )
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_program name exists under this program")
    sp = SubProgram(program_id=prog.id, year=y, name=body.name.strip(), sort_order=body.sort_order)
    db.add(sp)
    db.commit()
    return _build_program_tree(db, y)


@router.patch("/sub-programs/{sub_program_id}", response_model=ProgramTreeResponse)
def patch_sub_program(
    _admin: AdminUser,
    sub_program_id: int,
    body: SubProgramPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    sp = get_sub_program_for_year(db, sub_program_id, y)
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(
            select(SubProgram.id).where(
                SubProgram.program_id == sp.program_id,
                SubProgram.year == y,
                SubProgram.name == name,
                SubProgram.id != sub_program_id,
            )
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_program name exists")
        sp.name = name
    if body.sort_order is not None:
        sp.sort_order = body.sort_order
    db.commit()
    return _build_program_tree(db, y)


@router.delete("/sub-programs/{sub_program_id}", response_model=ProgramTreeResponse)
def delete_sub_program(
    _admin: AdminUser,
    sub_program_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    sp = get_sub_program_for_year(db, sub_program_id, y)
    db.delete(sp)
    db.commit()
    return _build_program_tree(db, y)


@router.post(
    "/sub-programs/{sub_program_id}/sub-projects",
    response_model=ProgramTreeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sub_project(
    _admin: AdminUser,
    sub_program_id: int,
    body: SubProjectCreate,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    spg = get_sub_program_for_year(db, sub_program_id, y)
    exists = db.scalar(
        select(SubProject.id).where(
            SubProject.sub_program_id == sub_program_id,
            SubProject.year == y,
            SubProject.name == body.name.strip(),
        )
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_project name exists under this group")
    sj = SubProject(
        sub_program_id=spg.id,
        year=y,
        name=body.name.strip(),
        status=(body.status or "active").strip() or "active",
        sort_order=body.sort_order,
    )
    db.add(sj)
    db.commit()
    return _build_program_tree(db, y)


@router.patch("/sub-projects/{sub_project_id}", response_model=ProgramTreeResponse)
def patch_sub_project(
    _admin: AdminUser,
    sub_project_id: int,
    body: SubProjectPatch,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    sj = db.get(SubProject, sub_project_id)
    if sj is None or sj.year != y:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_project not found")
    if body.name is not None:
        name = body.name.strip()
        clash = db.scalar(
            select(SubProject.id).where(
                SubProject.sub_program_id == sj.sub_program_id,
                SubProject.year == y,
                SubProject.name == name,
                SubProject.id != sub_project_id,
            )
        )
        if clash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_project name exists")
        sj.name = name
    if body.status is not None:
        sj.status = body.status.strip() or sj.status
    if body.sort_order is not None:
        sj.sort_order = body.sort_order
    db.commit()
    return _build_program_tree(db, y)


@router.delete("/sub-projects/{sub_project_id}", response_model=ProgramTreeResponse)
def delete_sub_project(
    _admin: AdminUser,
    sub_project_id: int,
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> ProgramTreeResponse:
    _ = _admin
    y = parse_year(year)
    sj = db.get(SubProject, sub_project_id)
    if sj is None or sj.year != y:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_project not found")
    db.delete(sj)
    db.commit()
    return _build_program_tree(db, y)
