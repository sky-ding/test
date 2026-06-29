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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_rate_goal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_program: Mapped[SubProgram] = relationship(back_populates="sub_projects")
    phase_assessments: Mapped[list[PhaseAssessment]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    manpower_cells: Mapped[list[ManpowerCell]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    project_risks: Mapped[list[ProjectRisk]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="sub_project", cascade="all, delete-orphan")
    goals: Mapped[list[Goal]] = relationship(
        back_populates="sub_project", cascade="all, delete-orphan"
    )
    team_members: Mapped[list[TeamMember]] = relationship(
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
    on_track: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actual_delivery: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="phase_assessments")


class ManpowerDepartmentGroup(Base):
    """人力表头：一级部门分组（按年）。"""

    __tablename__ = "manpower_department_groups"
    __table_args__ = (UniqueConstraint("year", "name", name="uk_manpower_group_year_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    columns: Mapped[list[ManpowerColumn]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class ManpowerColumn(Base):
    """人力表头：二级列，隶属于一级分组。"""

    __tablename__ = "manpower_columns"
    __table_args__ = (UniqueConstraint("group_id", "name", name="uk_manpower_column_group_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("manpower_department_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    group: Mapped[ManpowerDepartmentGroup] = relationship(back_populates="columns")
    cells: Mapped[list[ManpowerCell]] = relationship(back_populates="column", cascade="all, delete-orphan")


class ManpowerCell(Base):
    """人力单元格：子项目 × 月 × 列 -> 投入值。"""

    __tablename__ = "manpower_cells"
    __table_args__ = (
        UniqueConstraint("sub_project_id", "period", "column_id", name="uk_manpower_cell"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    column_id: Mapped[int] = mapped_column(
        ForeignKey("manpower_columns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allocation: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="manpower_cells")
    column: Mapped[ManpowerColumn] = relationship(back_populates="cells")


class ProjectRisk(Base):
    __tablename__ = "project_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_source: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="中", index=True)
    assignee: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resolution_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Open", index=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="project_risks")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="milestones")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="tasks")


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_column_id: Mapped[int] = mapped_column(
        ForeignKey("manpower_columns.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    participation: Mapped[str] = mapped_column(String(20), nullable=False, default="核心成员")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(back_populates="team_members")
    team_column: Mapped[ManpowerColumn] = relationship()
    allocations: Mapped[list[TeamMemberAllocation]] = relationship(
        back_populates="team_member", cascade="all, delete-orphan"
    )


class TeamMemberAllocation(Base):
    """项目成员在某年月的投入（人月）。"""

    __tablename__ = "team_member_allocations"
    __table_args__ = (UniqueConstraint("team_member_id", "period", name="uk_team_member_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_member_id: Mapped[int] = mapped_column(
        ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    allocation: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    team_member: Mapped[TeamMember] = relationship(back_populates="allocations")


# --- 目标跟踪 ---


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sub_project_id: Mapped[int] = mapped_column(
        ForeignKey("sub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    initial_target: Mapped[str] = mapped_column(String(200), nullable=False)
    mid_term_target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="higher_better")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow, nullable=False)

    sub_project: Mapped[SubProject] = relationship(
        back_populates="goals",
        foreign_keys=[sub_project_id],
    )
    links: Mapped[list[GoalLink]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )


class GoalLink(Base):
    __tablename__ = "goal_links"
    __table_args__ = (
        UniqueConstraint("goal_id", "target_type", "target_id", name="uk_goal_link_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'milestone' | 'task'
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow, nullable=False)

    goal: Mapped[Goal] = relationship(back_populates="links")
