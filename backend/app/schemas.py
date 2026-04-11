from typing import Any

from pydantic import BaseModel, Field


class ManpowerState(BaseModel):
    """与前端 PM-tool-manpower-v1 根对象对齐（savedAt 可由服务端覆盖）。"""

    data: list[Any] = Field(default_factory=list)
    deptGroups: list[Any] = Field(default_factory=list)
    savedAt: str | None = None


class PhaseState(BaseModel):
    """与前端 PM-tool-phase-v1 根对象对齐。"""

    phaseData: list[Any] = Field(default_factory=list)
    savedAt: str | None = None


class RiskState(BaseModel):
    """与前端 PM-tool-risk-v1 根对象对齐。"""

    riskRows: list[Any] = Field(default_factory=list)
    savedAt: str | None = None
