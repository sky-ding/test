import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password

logger = logging.getLogger(__name__)

# 未设置 PM_SKY_INITIAL_PASSWORD 时，默认管理员 Sky 的初始密码（生产请通过环境变量覆盖）
DEFAULT_SKY_INITIAL_PASSWORD = "123123"


def seed_users(db: Session) -> None:
    """若不存在 Sky，则创建默认系统管理员；密码优先取 PM_SKY_INITIAL_PASSWORD，否则为 DEFAULT_SKY_INITIAL_PASSWORD。"""
    existing = db.execute(select(User).where(User.username == "Sky")).scalar_one_or_none()
    if existing:
        return
    raw = (settings.sky_initial_password or "").strip() or DEFAULT_SKY_INITIAL_PASSWORD
    db.add(
        User(
            username="Sky",
            password_hash=hash_password(raw),
            role="admin",
            is_active=True,
            auth_source="local",
        )
    )
    db.commit()
    logger.info("Seeded default admin user Sky")
