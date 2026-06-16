"""规范化登记 API 的请求/响应模型（/api/v1/programs、phase-assessments 等）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self
from typing import Literal


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
    description: str | None = None
    key_goal: str | None = None
    automation_rate_goal: str | None = Field(default=None, max_length=50)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    sort_order: int | None = None


class SubProjectDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sub_program_id: int
    name: str
    status: str = "active"
    sort_order: int = 0
    description: str | None = None
    key_goal: str | None = None
    automation_rate_goal: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None


# --- 阶段 ---


class PhaseMonthlyDataOut(BaseModel):
    """单个子项目的月度自动填充数据。"""
    sub_project_id: int
    auto_goal_text: str = ""           # 自动填充的阶段交付目标文本
    auto_status: str = "not_started"   # 自动计算的目标达成状态
    auto_status_emoji: str = "⏳"      # 状态 emoji


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
    """写入一行；字段名与表一致；亦可从旧 JSON 字段名兼容。

    特殊约定：
    - goal 为 ""（空字符串）时，清空 delivery_target（恢复自动填充）
    - planMatch 为 ""（空字符串）时，清空 on_track（恢复自动计算）
    """

    sub_project_id: int
    period: str = Field(min_length=7, max_length=7)
    delivery_target: str | None = None
    on_track: str | None = Field(default=None, max_length=20)
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
    def map_legacy_keys(self) -> Self:
        updates: dict[str, object] = {}
        # goal 为空字符串时，显式清空 delivery_target（恢复自动填充）
        if self.goal == "":
            updates["delivery_target"] = None
        elif self.delivery_target is None and self.goal is not None:
            updates["delivery_target"] = self.goal
        if self.actual_delivery is None and self.deliver is not None:
            updates["actual_delivery"] = self.deliver
        # planMatch 为空字符串时，显式清空 on_track（恢复自动计算）
        if self.planMatch == "":
            updates["on_track"] = None
        elif self.on_track is None and self.planMatch is not None:
            updates["on_track"] = self.planMatch
        if self.execution_analysis is None and self.highlight is not None:
            updates["execution_analysis"] = self.highlight
        if self.problem_analysis is None and self.weakness is not None:
            updates["problem_analysis"] = self.weakness
        if self.improvement_plan is None and self.nextNote is not None:
            updates["improvement_plan"] = self.nextNote
        if updates:
            return self.model_copy(update=updates)
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


def _parse_risk_close_time(close_time: str | None) -> date | None:
    if not close_time:
        return None
    s = close_time.strip()[:10]
    if len(s) < 10 or s[4] != "-" or s[7] != "-":
        return None
    try:
        return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return None


def _project_risk_alias_updates(
    *,
    description: str | None,
    issue: str | None,
    assignee: str | None,
    owner: str | None,
    resolution_date: date | None,
    close_time: str | None,
    patch: bool,
) -> dict[str, object]:
    updates: dict[str, object] = {}
    if patch:
        if description is None and issue is not None:
            updates["description"] = issue
        if assignee is None and owner is not None:
            updates["assignee"] = owner
    else:
        desc = (description or "").strip()
        if not desc and issue is not None:
            updates["description"] = (issue or "").strip()
        asn = (assignee or "").strip()
        if not asn and owner is not None:
            updates["assignee"] = (owner or "").strip()
    if resolution_date is None and close_time:
        parsed = _parse_risk_close_time(close_time)
        if parsed is not None:
            updates["resolution_date"] = parsed
    return updates


class _ProjectRiskAliasBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    assignee: str | None = Field(default=None, max_length=100)
    resolution_date: date | None = None
    issue: str | None = None
    owner: str | None = None
    closeTime: str | None = None

    @model_validator(mode="after")
    def coerce_issue_owner(self) -> Self:
        updates = _project_risk_alias_updates(
            description=self.description,
            issue=self.issue,
            assignee=self.assignee,
            owner=self.owner,
            resolution_date=self.resolution_date,
            close_time=self.closeTime,
            patch=False,
        )
        if updates:
            return self.model_copy(update=updates)
        return self


class _ProjectRiskPatchAliasBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    assignee: str | None = Field(default=None, max_length=100)
    resolution_date: date | None = None
    issue: str | None = None
    owner: str | None = None
    closeTime: str | None = None

    @model_validator(mode="after")
    def coerce_issue_owner(self) -> Self:
        updates = _project_risk_alias_updates(
            description=self.description,
            issue=self.issue,
            assignee=self.assignee,
            owner=self.owner,
            resolution_date=self.resolution_date,
            close_time=self.closeTime,
            patch=True,
        )
        if updates:
            return self.model_copy(update=updates)
        return self


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
    created_at: datetime


class ProjectRiskCreate(_ProjectRiskAliasBody):
    sub_project_id: int
    risk_category: str = Field(max_length=50)
    risk_source: str = Field(max_length=50)
    solution: str | None = None
    level: str = Field(default="中", max_length=10)
    status: str = Field(default="Open", max_length=20)

    @model_validator(mode="after")
    def require_text(self) -> Self:
        if not (self.description or "").strip():
            raise ValueError("description or issue is required")
        if not (self.assignee or "").strip():
            raise ValueError("assignee or owner is required")
        return self


class ProjectRiskPatch(_ProjectRiskPatchAliasBody):
    sub_project_id: int | None = None
    risk_category: str | None = Field(default=None, max_length=50)
    risk_source: str | None = Field(default=None, max_length=50)
    solution: str | None = None
    level: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=20)


class ProjectRiskDetailOut(ProjectRiskOut):
    created_at: datetime


# --- 项目信息（聚合读写） ---

_PROJECT_STATUSES = frozenset({"active", "archived"})
_MILESTONE_STATUSES = frozenset({"pending", "in-progress", "completed", "overdue"})
_TASK_PHASES = frozenset({"需求与设计", "开发实施", "测试验证", "部署上线"})
_PARTICIPATION = frozenset({"核心成员", "兼职参与", "外部协作"})


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    planned_date: date
    status: str
    description: str | None = None
    sort_order: int = 0
    goal_ids: list[int] = Field(default_factory=list)


class MilestoneIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    planned_date: date
    status: str = Field(max_length=20)
    description: str | None = None
    sort_order: int = Field(ge=0)
    goal_ids: list[int] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        s = v.strip()
        if s not in _MILESTONE_STATUSES:
            raise ValueError("invalid milestone status")
        return s


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phase: str
    assignee: str | None = None
    start_date: date
    end_date: date
    progress: int = 0
    sort_order: int = 0
    goal_ids: list[int] = Field(default_factory=list)


class TaskIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    phase: str = Field(max_length=50)
    assignee: str | None = Field(default=None, max_length=100)
    start_date: date
    end_date: date
    progress: int = Field(default=0, ge=0, le=100)
    sort_order: int = Field(ge=0)
    goal_ids: list[int] = Field(default_factory=list)

    @field_validator("phase")
    @classmethod
    def valid_phase(cls, v: str) -> str:
        s = v.strip()
        if s not in _TASK_PHASES:
            raise ValueError("invalid task phase")
        return s

    @model_validator(mode="after")
    def end_after_start(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TeamMemberOut(BaseModel):
    id: int
    name: str
    team_column_id: int
    team_column_name: str
    role: str
    participation: str
    remark: str | None = None
    sort_order: int = 0
    monthly_allocation: Decimal = Decimal("0.00")
    person_total_allocation: Decimal = Decimal("0.00")
    person_saturation_rate: Decimal = Decimal("0.0000")
    person_saturation_level: str = "low"


class TeamMemberIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    team_column_id: int = Field(ge=1)
    role: str = Field(min_length=1, max_length=50)
    participation: str = Field(max_length=20)
    remark: str | None = None
    sort_order: int = Field(ge=0)
    monthly_allocation: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("1"))

    @field_validator("participation")
    @classmethod
    def valid_participation(cls, v: str) -> str:
        s = v.strip()
        if s not in _PARTICIPATION:
            raise ValueError("invalid participation")
        return s

    @field_validator("monthly_allocation")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class ProjectInfoRiskIn(BaseModel):
    id: int | None = None
    risk_category: str = Field(max_length=50)
    risk_source: str = Field(max_length=50)
    description: str = Field(min_length=1)
    solution: str | None = None
    level: str = Field(max_length=10)
    assignee: str = Field(min_length=1, max_length=100)
    resolution_date: date | None = None
    status: str = Field(max_length=20)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        s = v.strip()
        if s.lower() in ("close", "closed", "关闭"):
            return "Close"
        if s.lower() in ("open", "开放"):
            return "Open"
        if s in ("Open", "Close"):
            return s
        raise ValueError("status must be Open or Close")


class ProjectInfoManpowerCellIn(BaseModel):
    column_id: int = Field(ge=1)
    allocation: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("9999.99"))

    @field_validator("allocation")
    @classmethod
    def two_decimals(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class ProjectInfoManpowerIn(BaseModel):
    period: str = Field(min_length=7, max_length=7)
    cells: list[ProjectInfoManpowerCellIn] = Field(default_factory=list)


class ProjectInfoManpowerOut(BaseModel):
    period: str
    dept_groups: list[ManpowerMatrixGroupOut]
    cells: list[ManpowerMatrixCellOut]


class ProjectInfoBreadcrumb(BaseModel):
    program_id: int
    program_name: str
    sub_program_id: int
    sub_program_name: str
    sub_project_id: int
    sub_project_name: str


class ProjectInfoSubProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    status: str = Field(max_length=20)
    description: str | None = None
    key_goal: str | None = None
    automation_rate_goal: str | None = Field(default=None, max_length=50)
    planned_start_date: date
    planned_end_date: date
    actual_start_date: date | None = None
    actual_end_date: date | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        s = v.strip()
        if s not in _PROJECT_STATUSES:
            raise ValueError("status must be active or archived")
        return s

    @model_validator(mode="after")
    def end_after_start(self) -> Self:
        if self.planned_end_date < self.planned_start_date:
            raise ValueError("planned_end_date must be on or after planned_start_date")
        return self


class ProjectInfoPutBody(BaseModel):
    sub_project: ProjectInfoSubProjectIn
    milestones: list[MilestoneIn] = Field(default_factory=list)
    deleted_milestone_ids: list[int] = Field(default_factory=list)
    tasks: list[TaskIn] = Field(default_factory=list)
    deleted_task_ids: list[int] = Field(default_factory=list)
    team_members: list[TeamMemberIn] = Field(default_factory=list)
    deleted_team_member_ids: list[int] = Field(default_factory=list)
    risks: list[ProjectInfoRiskIn] = Field(default_factory=list)
    deleted_risk_ids: list[int] = Field(default_factory=list)
    manpower: ProjectInfoManpowerIn
    goals: list[GoalIn] = Field(default_factory=list)
    deleted_goal_ids: list[int] = Field(default_factory=list)


class ProjectInfoGetResponse(BaseModel):
    year: int
    period: str
    sub_project: SubProjectDetailOut
    milestones: list[MilestoneOut]
    tasks: list[TaskOut]
    team_members: list[TeamMemberOut]
    risks: list[ProjectRiskDetailOut]
    manpower: ProjectInfoManpowerOut
    breadcrumb: ProjectInfoBreadcrumb
    project_monthly_total: Decimal = Decimal("0.00")
    goals: list[GoalOut] = Field(default_factory=list)


class PersonSummaryProjectOut(BaseModel):
    sub_project_id: int
    sub_project_name: str
    program_name: str
    allocation: Decimal


class PersonSummaryRowOut(BaseModel):
    name: str
    total_allocation: Decimal
    saturation_rate: Decimal
    saturation_level: str
    projects: list[PersonSummaryProjectOut]


class PersonSummaryResponse(BaseModel):
    year: int
    period: str
    capacity_per_person: Decimal
    persons: list[PersonSummaryRowOut]


# --- 目标跟踪 ---


class GoalLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_type: str    # 'milestone' | 'task'
    target_id: int


class GoalLinkIn(BaseModel):
    target_type: Literal["milestone", "task"]
    target_id: int = Field(ge=1)


class GoalDerivedProgress(BaseModel):
    """系统自动推导的季度/月度进展(只读,不存库)。"""
    period: str               # 'YYYY-MM' 或 'YYYY-Q1' 等
    related_items: list[str]  # 关联的里程碑/任务名称列表
    progress_pct: float | None  # 进度百分比(0-100),布尔型目标为 None
    status: str               # 'completed' | 'in_progress' | 'at_risk' | 'not_started' | 'manual'


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    metric_unit: str | None = None
    initial_target: str
    mid_term_target: str | None = None
    current_value: str | None = None
    direction: str
    sort_order: int = 0
    links: list[GoalLinkOut] = Field(default_factory=list)
    derived_progress: list[GoalDerivedProgress] = Field(default_factory=list)
    overall_status: str = "not_started"  # 自动计算的整体状态


class GoalIn(BaseModel):
    id: int | None = None  # None = 新建,有值 = 更新
    name: str = Field(min_length=1, max_length=200)
    metric_unit: str | None = Field(default=None, max_length=50)
    initial_target: str = Field(min_length=1, max_length=200)
    mid_term_target: str | None = Field(default=None, max_length=200)
    current_value: str | None = Field(default=None, max_length=200)
    direction: Literal["higher_better", "lower_better", "boolean"] = "higher_better"
    sort_order: int = 0
    # links 不再由 GoalIn 维护，改由 MilestoneIn.goal_ids / TaskIn.goal_ids 维护


class GoalSummaryOut(BaseModel):
    """项目阶段状态页用的只读摘要。"""
    sub_project_id: int
    sub_project_name: str
    name: str
    metric_unit: str | None = None
    target_value: str           # 取 mid_term_target 或 initial_target
    current_value: str | None   # 自动推导或手动更新的当前值
    status: str                 # 'on_track' | 'at_risk' | 'behind' | 'completed' | 'not_started'
    status_emoji: str           # 🟢 / 🟡 / 🔴 / ✅ / ⏳
