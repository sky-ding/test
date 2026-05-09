import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password

logger = logging.getLogger(__name__)

# 未设置 PM_SKY_INITIAL_PASSWORD 时，内置账号（含 Sky）的默认初始密码（生产请通过环境变量覆盖）
DEFAULT_SKY_INITIAL_PASSWORD = "123123"

# 启动时若不存在则创建（按用户名小写判重）。初始密码与 Sky 相同：优先 PM_SKY_INITIAL_PASSWORD，否则为上方的默认值。
DEFAULT_ROSTER: list[tuple[str, str]] = [
    ("alfred.wang", "admin"),
    ("fanny.wu", "admin"),
    ("veking.lee", "admin"),
    ("sky.ding", "admin"),
    ("test", "viewer"),
]


def _initial_password() -> str:
    return (settings.sky_initial_password or "").strip() or DEFAULT_SKY_INITIAL_PASSWORD


def _ensure_user(db: Session, username: str, plain_password: str, role: str) -> bool:
    """若不存在同名用户（忽略大小写）则创建。返回是否新建。"""
    uname = username.strip()
    if not uname:
        return False
    existing = db.execute(
        select(User).where(func.lower(User.username) == uname.lower())
    ).scalar_one_or_none()
    if existing:
        return False
    db.add(
        User(
            username=uname,
            password_hash=hash_password(plain_password),
            role=role,
            is_active=True,
            auth_source="local",
        )
    )
    return True


def seed_users(db: Session) -> None:
    """启动时补齐内置账号；并保留兼容历史的默认管理员 Sky。新建用户密码规则均与 Sky 一致。"""
    created: list[str] = []
    raw = _initial_password()

    for username, role in DEFAULT_ROSTER:
        if _ensure_user(db, username, raw, role):
            created.append(username)

    # 兼容：若不存在用户名为 sky（不区分大小写）的账号，则创建默认 Sky
    if _ensure_user(db, "Sky", raw, "admin"):
        created.append("Sky")

    if created:
        db.commit()
        logger.info("Seeded users: %s", ", ".join(created))
