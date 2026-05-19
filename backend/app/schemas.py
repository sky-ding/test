"""认证与用户管理 API 的 Pydantic 模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
