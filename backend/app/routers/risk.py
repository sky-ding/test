from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AdminUser, CurrentUser
from app.registry_store import KEY_RISK, get_json, put_json
from app.schemas import RiskState

router = APIRouter(prefix="/risk", tags=["risk"])

EMPTY = {"riskRows": []}


@router.get("", response_model=RiskState)
def get_risk(
    _user: CurrentUser,
    db: Session = Depends(get_db),
) -> RiskState:
    return RiskState.model_validate(get_json(db, KEY_RISK, EMPTY))


@router.put("", response_model=RiskState)
def put_risk(
    body: RiskState,
    _admin: AdminUser,
    db: Session = Depends(get_db),
) -> RiskState:
    stored = put_json(db, KEY_RISK, body.model_dump(exclude_none=False))
    return RiskState.model_validate(stored)
