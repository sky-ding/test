from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.registry_store import KEY_MANPOWER, get_json, put_json
from app.schemas import ManpowerState

router = APIRouter(prefix="/manpower", tags=["manpower"])

EMPTY = {"data": [], "deptGroups": []}


@router.get("", response_model=ManpowerState)
def get_manpower(
    _user: CurrentUser,
    db: Session = Depends(get_db),
) -> ManpowerState:
    return ManpowerState.model_validate(get_json(db, KEY_MANPOWER, EMPTY))


@router.put("", response_model=ManpowerState)
def put_manpower(
    body: ManpowerState,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> ManpowerState:
    stored = put_json(db, KEY_MANPOWER, body.model_dump(exclude_none=False))
    return ManpowerState.model_validate(stored)
