from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, SESSION_UID_KEY
from app.models import User
from app.schemas import LoginOkResponse, LoginRequest, MeResponse
from app.security import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOkResponse)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> LoginOkResponse:
    if settings.auth_disabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is disabled (PM_AUTH_DISABLED)",
        )
    uname_key = body.username.strip().lower()
    user = (
        db.execute(select(User).where(func.lower(User.username) == uname_key))
        .scalar_one_or_none()
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    request.session[SESSION_UID_KEY] = user.id
    return LoginOkResponse(username=user.username, role=user.role)


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return MeResponse(id=user.id, username=user.username, role=user.role)


@router.get("/oa/authorize")
def oa_authorize_placeholder() -> None:
    """预留：对接公司 OA 时改为重定向至 IdP 授权端点。"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OA authorization is not configured",
    )
