from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATA_DIR, settings
from app.models import Base
import app.models_relational  # noqa: F401 — register relational tables on Base.metadata

if not settings.uses_mysql:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

if settings.uses_mysql:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
