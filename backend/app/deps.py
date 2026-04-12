from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

SESSION_UID_KEY = "uid"


@dataclass
class DevBypassUser:
    """PM_AUTH_DISABLED 时的占位用户（视为管理员）。"""

    id: int = 0
    username: str = "dev"
    role: str = "admin"
    is_active: bool = True


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | DevBypassUser:
    if settings.auth_disabled:
        return DevBypassUser()

    uid = request.session.get(SESSION_UID_KEY)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.get(User, int(uid))
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(
    user: Annotated[User | DevBypassUser, Depends(get_current_user)],
) -> User | DevBypassUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin required",
        )
    return user


CurrentUser = Annotated[User | DevBypassUser, Depends(get_current_user)]
AdminUser = Annotated[User | DevBypassUser, Depends(require_admin)]
