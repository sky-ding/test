from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import RegistryEntry

KEY_MANPOWER = "manpower"
KEY_PHASE = "phase"
KEY_RISK = "risk"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_json(db: Session, key: str, default: dict) -> dict:
    row = db.get(RegistryEntry, key)
    if row is None:
        return {**default}
    return dict(row.payload)


def put_json(db: Session, key: str, payload: dict) -> dict:
    body = dict(payload)
    body["savedAt"] = _now_iso()
    row = db.get(RegistryEntry, key)
    if row is None:
        row = RegistryEntry(key=key, payload=body)
        db.add(row)
    else:
        row.payload = body
        flag_modified(row, "payload")
    db.commit()
    db.refresh(row)
    return dict(row.payload)
