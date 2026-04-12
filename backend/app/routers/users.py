from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser
from app.models import User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _count_active_admins(db: Session) -> int:
    n = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.is_active.is_(True))
    )
    return int(n or 0)


def _ensure_not_last_active_admin(db: Session, target: User) -> None:
    if target.role != "admin" or not target.is_active:
        return
    if _count_active_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove or demote the last active admin",
        )


@router.get("", response_model=list[UserOut])
def list_users(_admin: AdminUser, db: Session = Depends(get_db)):
    return list(db.execute(select(User).order_by(User.id)).scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    _admin: AdminUser,
    db: Session = Depends(get_db),    
) -> User:
    exists = (
        db.execute(select(User).where(User.username == body.username))
        .scalar_one_or_none()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    u = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
        auth_source="local",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    _admin: AdminUser,
    db: Session = Depends(get_db),    
) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role == "viewer" and u.role == "admin":
        _ensure_not_last_active_admin(db, u)
    if body.is_active is False and u.role == "admin" and u.is_active:
        _ensure_not_last_active_admin(db, u)

    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password is not None:
        u.password_hash = hash_password(body.password)

    db.commit()
    db.refresh(u)
    return u


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _admin: AdminUser,
    db: Session = Depends(get_db),    
) -> None:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if u.role == "admin" and u.is_active:
        _ensure_not_last_active_admin(db, u)
    db.delete(u)
    db.commit()
