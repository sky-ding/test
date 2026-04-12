from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.registry_store import KEY_PHASE, get_json, put_json
from app.schemas import PhaseState

router = APIRouter(prefix="/phase", tags=["phase"])

EMPTY = {"phaseData": []}


@router.get("", response_model=PhaseState)
def get_phase(
    _user: CurrentUser,
    db: Session = Depends(get_db),
) -> PhaseState:
    return PhaseState.model_validate(get_json(db, KEY_PHASE, EMPTY))


@router.put("", response_model=PhaseState)
def put_phase(
    body: PhaseState,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> PhaseState:
    stored = put_json(db, KEY_PHASE, body.model_dump(exclude_none=False))
    return PhaseState.model_validate(stored)
