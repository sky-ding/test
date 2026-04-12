from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PM_", env_file=".env", extra="ignore")

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

    # 首次创建 Sky 时覆盖默认初始密码（默认见 seed.DEFAULT_SKY_INITIAL_PASSWORD，当前为 123123）
    sky_initial_password: str | None = None

    # local | oa_oauth（预留）
    auth_mode: str = "local"
    # 为 True 时跳过登录与会话校验（仅本地开发，禁止用于生产）
    auth_disabled: bool = False

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
