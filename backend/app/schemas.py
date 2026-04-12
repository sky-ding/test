"""
与 frontend/index.html 中 localStorage / 业务对象字段名对齐。

人力：data[].name / projects[].name / manpowerByMonth / manpower（可选，运行时列）
      deptGroups[].name / depts
阶段：phaseData[].name / projects[].name / phaseByMonth[yyyy-MM].{goal,deliver,highlight,weakness,nextNote}
风险：riskRows[].{project,regTime,registrant,desc,assessment,level,status,resolveEta}
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- 人力登记（PM-tool-manpower-v1）---


class DeptGroup(BaseModel):
    """部门分组：与 normalizeDeptGroups / defaultDeptGroups 一致。"""

    model_config = ConfigDict(extra="ignore")

    name: str = "部门分组"
    depts: list[str] = Field(default_factory=list)


class ManpowerProject(BaseModel):
    """项目集下的单行项目：fixManpowerInData 保证 manpowerByMonth 与 manpower。"""

    model_config = ConfigDict(extra="ignore")

    name: str = "新项目"
    manpowerByMonth: dict[str, list[int | float]] = Field(default_factory=dict)
    manpower: list[int | float] | None = None


class ManpowerProjectSet(BaseModel):
    """项目集（data 数组元素）。"""

    model_config = ConfigDict(extra="ignore")

    name: str = "项目集"
    projects: list[ManpowerProject] = Field(default_factory=list)


class ManpowerState(BaseModel):
    """根对象：saveManpowerData 写入 { data, deptGroups, savedAt }。"""

    model_config = ConfigDict(extra="ignore")

    data: list[ManpowerProjectSet] = Field(default_factory=list)
    deptGroups: list[DeptGroup] = Field(default_factory=list)
    savedAt: str | None = None


# --- 项目阶段（PM-tool-phase-v1）---


class PhaseMonthRow(BaseModel):
    """phaseByMonth 中单月一行：PHASE_FIELD_KEYS / newPhaseMonthRow。"""

    model_config = ConfigDict(extra="ignore")

    goal: str = ""
    deliver: str = ""
    highlight: str = ""
    weakness: str = ""
    nextNote: str = ""


class PhaseProject(BaseModel):
    """阶段表中的项目行（仅存 name + phaseByMonth，不含 _phaseSlice）。"""

    model_config = ConfigDict(extra="ignore")

    name: str = "新项目"
    phaseByMonth: dict[str, PhaseMonthRow] = Field(default_factory=dict)


class PhaseProjectSet(BaseModel):
    """阶段项目集。"""

    model_config = ConfigDict(extra="ignore")

    name: str = "项目集"
    projects: list[PhaseProject] = Field(default_factory=list)


class PhaseState(BaseModel):
    """根对象：{ phaseData, savedAt }。"""

    model_config = ConfigDict(extra="ignore")

    phaseData: list[PhaseProjectSet] = Field(default_factory=list)
    savedAt: str | None = None


# --- 项目风险（PM-tool-risk-v1）---


class RiskRow(BaseModel):
    """与 RISK_FIELD_ORDER / mapRiskRowsFromStorage 字段一致。"""

    model_config = ConfigDict(extra="ignore")

    project: str = ""
    regTime: str = ""
    registrant: str = ""
    desc: str = ""
    assessment: str = ""
    level: str = ""
    status: str = ""
    resolveEta: str = ""


class RiskState(BaseModel):
    """根对象：{ riskRows, savedAt }。"""

    model_config = ConfigDict(extra="ignore")

    riskRows: list[RiskRow] = Field(default_factory=list)
    savedAt: str | None = None


# --- 认证与用户管理 ---


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class MeResponse(BaseModel):
    id: int
    username: str
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    auth_source: str


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=256)
    role: Literal["admin", "viewer"] = "viewer"

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("username required")
        return s


class UserUpdate(BaseModel):
    role: Literal["admin", "viewer"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=256)


class LoginOkResponse(BaseModel):
    ok: bool = True
    username: str
    role: str
