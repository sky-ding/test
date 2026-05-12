"""规范化项目树与登记表（按年 programs → sub_programs → sub_projects + 业务表）。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Program(Base):
    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("year", "name", name="uk_year_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    sub_programs: Mapped[list[SubProgram]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
    )


class SubProgram(Base):
    __tablename__ = "sub_programs"
    __table_args__ = (
        UniqueConstraint("program_id", "year", "name", name="uk_prog_year_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    program: Mapped[Program] = relationship(back_populates="sub_programs")
    sub_projects: Mapped[list[SubProject]] = relationship(
        back_populates="sub_program",
        cascade="all, delete-orphan",
    )


class SubProject(Base):
    __tablename__ = "sub_projects"
    __table_args__ = (
        UniqueConstraint("sub_program_id", "year", "name", name="uk_spg_year_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_program_id: Mapped[int] = mapped_column(
        ForeignKey("sub_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_program: Mapped[SubProgram] = relationship(back_populates="sub_projects")
    phase_assessments: Mapped[list[PhaseAssessment]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    manpower_allocations: Mapped[list[ManpowerAllocation]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    project_risks: Mapped[list[ProjectRisk]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )


class PhaseAssessment(Base):
    __tablename__ = "phase_assessments"
    __table_args__ = (UniqueConstraint("sub_project_id", "period", name="uk_project_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    delivery_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_track: Mapped[str | None] = mapped_column(String(4), nullable=True)
    actual_delivery: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="phase_assessments")


class ManpowerAllocation(Base):
    __tablename__ = "manpower_allocations"
    __table_args__ = (
        UniqueConstraint(
            "sub_project_id", "period", "department", "role", name="uk_prj_period_dept_role"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    allocation: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="manpower_allocations")


class ProjectRisk(Base):
    __tablename__ = "project_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    risk_source: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(4), nullable=False, default="中", index=True)
    assignee: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resolution_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="Open", index=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="project_risks")
