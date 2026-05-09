from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PM_", env_file=".env", extra="ignore")

    # MySQL：同时设置 host、user、database 时启用；否则回落 SQLite（backend/data/app.db）
    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = ""
    mysql_database: str = ""
    mysql_charset: str = "utf8mb4"

    # 逗号分隔，开发期默认覆盖常见静态服务端口
    cors_origins: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "http://127.0.0.1:5500,http://localhost:5500,"
        "http://127.0.0.1:8080,http://localhost:8080"
    )

    # 会话 Cookie（生产务必设置 PM_SESSION_SECRET）
    session_secret: str = Field(
        default="dev-insecure-change-with-PM_SESSION_SECRET",
        description="Starlette SessionMiddleware 签名密钥",
    )
    session_same_site: str = "lax"
    session_https_only: bool = False

    # 首次创建内置本地账号（含 roster 与兼容用 Sky）时覆盖默认初始密码（默认见 seed.DEFAULT_SKY_INITIAL_PASSWORD）
    sky_initial_password: str | None = None

    # local | oa_oauth（预留）
    auth_mode: str = "local"
    # 为 True 时跳过登录与会话校验（仅本地开发，禁止用于生产）
    auth_disabled: bool = False

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def uses_mysql(self) -> bool:
        h = (self.mysql_host or "").strip()
        u = (self.mysql_user or "").strip()
        d = (self.mysql_database or "").strip()
        return bool(h and u and d)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """运行时数据库 URL：MySQL 或 SQLite。"""
        if self.uses_mysql:
            user = quote_plus((self.mysql_user or "").strip())
            password = quote_plus(self.mysql_password or "")
            host = (self.mysql_host or "").strip()
            db = (self.mysql_database or "").strip()
            port = int(self.mysql_port)
            charset = (self.mysql_charset or "utf8mb4").strip() or "utf8mb4"
            return (
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
                f"?charset={quote_plus(charset)}"
            )
        sqlite_path = (DATA_DIR / "app.db").as_posix()
        return f"sqlite:///{sqlite_path}"


settings = Settings()
