"""规范化登记 API 的请求/响应模型（/api/v1/programs、phase-assessments 等）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- 项目树 ---


class SubProjectNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str = "active"
    sort_order: int = 0


class SubProgramNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int = 0
    sub_projects: list[SubProjectNode] = Field(default_factory=list)


class ProgramNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int = 0
    sub_programs: list[SubProgramNode] = Field(default_factory=list)


class ProgramTreeResponse(BaseModel):
    year: int
    programs: list[ProgramNode]


class ProgramListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    name: str
    sort_order: int


class ProgramCreate(BaseModel):
    year: Annotated[int, Field(ge=2000, le=2100)]
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class ProgramPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class SubProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class SubProgramPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class SubProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    status: str = Field(default="active", max_length=20)
    sort_order: int = 0


class SubProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    sort_order: int | None = None


# --- 阶段 ---


class PhaseAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sub_project_id: int
    period: str
    delivery_target: str | None = None
    on_track: str | None = None
    actual_delivery: str | None = None
    execution_analysis: str | None = None
    problem_analysis: str | None = None
    improvement_plan: str | None = None


class PhaseAssessmentUpsert(BaseModel):
    """写入一行；字段名与表一致；亦可从旧 JSON 字段名兼容。"""

    sub_project_id: int
    period: str = Field(min_length=7, max_length=7)
    delivery_target: str | None = None
    on_track: str | None = Field(default=None, max_length=10)
    actual_delivery: str | None = None
    execution_analysis: str | None = None
    problem_analysis: str | None = None
    improvement_plan: str | None = None

    goal: str | None = None
    deliver: str | None = None
    planMatch: str | None = None
    highlight: str | None = None
    weakness: str | None = None
    nextNote: str | None = None

    @model_validator(mode="after")
    def map_legacy_keys(self) -> PhaseAssessmentUpsert:
        if self.delivery_target is None and self.goal is not None:
            object.__setattr__(self, "delivery_target", self.goal)
        if self.actual_delivery is None and self.deliver is not None:
            object.__setattr__(self, "actual_delivery", self.deliver)
        if self.on_track is None and self.planMatch is not None:
            object.__setattr__(self, "on_track", self.planMatch)
        if self.execution_analysis is None and self.highlight is not None:
            object.__setattr__(self, "execution_analysis", self.highlight)
        if self.problem_analysis is None and self.weakness is not None:
            object.__setattr__(self, "problem_analysis", self.weakness)
        if self.improvement_plan is None and self.nextNote is not None:
            object.__setattr__(self, "improvement_plan", self.nextNote)
        return self


# --- 人力矩阵（v1，见 docs/项目管理登记系统数据库设计文档.md §15.2） ---


class ManpowerMatrixColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int = 0


class ManpowerMatrixGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int = 0
    columns: list[ManpowerMatrixColumnOut] = Field(default_factory=list)


class ManpowerMatrixCellOut(BaseModel):
    sub_project_id: int
    period: str
    column_id: int
    allocation: Decimal


class ManpowerMatrixResponse(BaseModel):
    year: int
    period: str
    dept_groups: list[ManpowerMatrixGroupOut]
    cells: list[ManpowerMatrixCellOut]


class ManpowerMatrixCellIn(BaseModel):
    sub_project_id: int = Field(ge=1)
    column_id: int = Field(ge=1)
    allocation: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("9999.99"))

    @field_validator("allocation")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class ManpowerMatrixPutBody(BaseModel):
    cells: list[ManpowerMatrixCellIn]


class ManpowerDepartmentGroupCreate(BaseModel):
    year: Annotated[int, Field(ge=2000, le=2100)]
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    first_column_name: str | None = Field(default=None, min_length=1, max_length=100)


class ManpowerDepartmentGroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


class ManpowerColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class ManpowerColumnPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None


# --- 风险 ---


class ProjectRiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sub_project_id: int
    risk_category: str
    risk_source: str
    description: str
    solution: str | None = None
    level: str
    assignee: str
    resolution_date: date | None = None
    status: str
    closed_at: datetime | None = None


class ProjectRiskCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub_project_id: int
    risk_category: str = Field(max_length=50)
    risk_source: str = Field(max_length=50)
    description: str | None = None
    solution: str | None = None
    level: str = Field(default="中", max_length=10)
    assignee: str | None = Field(default=None, max_length=100)
    resolution_date: date | None = None
    status: str = Field(default="Open", max_length=20)
    issue: str | None = None
    owner: str | None = None
    closeTime: str | None = None

    @model_validator(mode="after")
    def coerce_issue_owner(self) -> ProjectRiskCreate:
        desc = (self.description or "").strip()
        if not desc and self.issue is not None:
            desc = (self.issue or "").strip()
            object.__setattr__(self, "description", desc)
        assignee = (self.assignee or "").strip()
        if not assignee and self.owner is not None:
            assignee = (self.owner or "").strip()
            object.__setattr__(self, "assignee", assignee)
        if self.resolution_date is None and self.closeTime:
            s = (self.closeTime or "").strip()[:10]
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                try:
                    object.__setattr__(
                        self,
                        "resolution_date",
                        date(int(s[:4]), int(s[5:7]), int(s[8:10])),
                    )
                except ValueError:
                    pass
        return self

    @model_validator(mode="after")
    def require_text(self) -> ProjectRiskCreate:
        if not (self.description or "").strip():
            raise ValueError("description or issue is required")
        if not (self.assignee or "").strip():
            raise ValueError("assignee or owner is required")
        return self


class ProjectRiskPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    risk_category: str | None = Field(default=None, max_length=50)
    risk_source: str | None = Field(default=None, max_length=50)
    description: str | None = None
    solution: str | None = None
    level: str | None = Field(default=None, max_length=10)
    assignee: str | None = Field(default=None, max_length=100)
    resolution_date: date | None = None
    status: str | None = Field(default=None, max_length=20)
    issue: str | None = None
    owner: str | None = None
    closeTime: str | None = None

    @model_validator(mode="after")
    def coerce_issue_owner(self) -> ProjectRiskPatch:
        if self.description is None and self.issue is not None:
            object.__setattr__(self, "description", self.issue)
        if self.assignee is None and self.owner is not None:
            object.__setattr__(self, "assignee", self.owner)
        if self.resolution_date is None and self.closeTime is not None:
            s = (self.closeTime or "").strip()[:10]
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                try:
                    object.__setattr__(
                        self,
                        "resolution_date",
                        date(int(s[:4]), int(s[5:7]), int(s[8:10])),
                    )
                except ValueError:
                    pass
        return self
